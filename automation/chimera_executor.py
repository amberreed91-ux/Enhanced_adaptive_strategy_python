from __future__ import annotations

import csv
import fnmatch
import json
import math
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from loguru import logger

from automation.broker_router import BrokerRouter
from bookmap_engine.bridge import bridge_signal_age_seconds, read_bridge_signal
from config import init_config

TRADINGVIEW_PAPER_BROKER = "tradingview_paper"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_utc(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    except ValueError:
        return None


def _age_seconds(raw_ts: str) -> float:
    ts = _parse_iso_utc(raw_ts)
    if ts is None:
        return float("inf")
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _normalize_action(raw: str) -> str:
    action = (raw or "").strip().upper()
    if action in {"BUY", "LONG", "GO_LONG"}:
        return "LONG"
    if action in {"SELL", "SHORT", "GO_SHORT"}:
        return "SHORT"
    if action in {"CLOSE", "FLAT", "EXIT"}:
        return "FLAT"
    return "UNKNOWN"


def _normalize_broker_name(raw: Any, default: str = "") -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return str(default or "").strip().lower()
    normalized = value.replace("-", "_").replace(" ", "_")
    if normalized in {"realninja", "real_ninja"}:
        return "ninjatrader"
    if normalized in {
        "tvpaper",
        "tv_paper",
        "tradingviewpaper",
        "tradingview_paper",
        "papertrading",
        "paper_trading",
    }:
        return TRADINGVIEW_PAPER_BROKER
    return normalized


def _parse_price(payload: Dict[str, Any]) -> float:
    for key in ("price", "close", "entry_price"):
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                pass
    return 0.0


def _parse_qty(payload: Dict[str, Any], default_qty: int = 0) -> int:
    for key in ("qty", "quantity", "contracts", "order_qty"):
        if key in payload:
            try:
                val = int(float(payload[key]))
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass
    return max(0, int(default_qty))


@dataclass
class TradingViewSignal:
    symbol: str
    action: str
    price: float
    qty: int
    timestamp_utc: str
    strategy_profile: str
    broker_hint: str
    instrument_type: str
    contract_multiplier: float
    raw: Dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TradingViewSignal":
        symbol = str(payload.get("symbol", "")).upper().strip()
        action_raw = str(payload.get("action", payload.get("signal", "")))
        action = _normalize_action(action_raw)
        price = _parse_price(payload)
        qty = _parse_qty(payload, default_qty=0)
        ts = str(
            payload.get(
                "timestamp_utc",
                payload.get("feed_timestamp_utc", payload.get("bar_timestamp_utc", utc_now_iso())),
            )
        )
        profile = str(payload.get("strategy_profile", payload.get("profile", "default"))).strip().lower()
        broker_raw = payload.get("broker", payload.get("broker_name", payload.get("account", "")))
        broker_hint = _normalize_broker_name(broker_raw, default="")
        instrument_type = str(payload.get("instrument_type", payload.get("asset_class", payload.get("type", "")))).strip().upper()
        try:
            contract_multiplier = float(payload.get("contract_multiplier", payload.get("multiplier", 0.0)))
        except (TypeError, ValueError):
            contract_multiplier = 0.0
        return cls(
            symbol=symbol,
            action=action,
            price=price,
            qty=qty,
            timestamp_utc=ts,
            strategy_profile=profile or "default",
            broker_hint=broker_hint,
            instrument_type=instrument_type,
            contract_multiplier=contract_multiplier,
            raw=payload,
        )


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    bridge: Optional[Dict[str, Any]]
    bridge_age_seconds: float
    profile: str


class ChimeraGate:
    def __init__(self, cfg: Any):
        self.cfg = cfg

    def _profile_params(self) -> Tuple[bool, float, float, bool]:
        profile = str(self.cfg.get("bookmap_bridge.profile", "balanced")).lower()
        if profile == "strict":
            return False, 8.0, 70.0, True
        if profile == "permissive":
            return True, 30.0, 45.0, False
        if profile == "balanced":
            return True, 20.0, 55.0, False
        fail_open = bool(self.cfg.get("bookmap_bridge.fail_open", True))
        max_age = float(self.cfg.get("bookmap_bridge.max_age_seconds", 20))
        min_conf = float(self.cfg.get("bookmap_bridge.min_confidence", 55))
        require_whale = bool(self.cfg.get("bookmap_bridge.require_whale", False))
        return fail_open, max_age, min_conf, require_whale

    def check(self, signal: TradingViewSignal) -> GateDecision:
        if not self.cfg.get("bookmap_bridge.enabled", False):
            return GateDecision(True, "bridge_disabled", bridge=None, bridge_age_seconds=float("inf"), profile="disabled")

        fail_open, max_age, min_conf, require_whale = self._profile_params()
        bridge_file = self.cfg.get("bookmap_bridge.signal_file", "data/bookmap_signal.json")
        bridge = read_bridge_signal(bridge_file)
        profile = str(
            (bridge or {}).get("profile", signal.strategy_profile or self.cfg.get("bookmap_bridge.profile", "default"))
        ).lower()
        if bridge is None:
            if fail_open:
                return GateDecision(True, "bridge_missing_fail_open", bridge=None, bridge_age_seconds=float("inf"), profile=profile)
            return GateDecision(False, "bridge_missing", bridge=None, bridge_age_seconds=float("inf"), profile=profile)

        age = bridge_signal_age_seconds(bridge)
        if age > max_age:
            if fail_open:
                return GateDecision(True, "bridge_stale_fail_open", bridge=bridge, bridge_age_seconds=age, profile=profile)
            return GateDecision(False, f"bridge_stale:{age:.1f}s", bridge=bridge, bridge_age_seconds=age, profile=profile)

        conf = float(bridge.get("confidence", 0.0))
        if conf < min_conf:
            return GateDecision(False, f"bridge_low_conf:{conf:.1f}", bridge=bridge, bridge_age_seconds=age, profile=profile)

        decision = str(bridge.get("decision", "NO_TRADE")).upper()
        if signal.action == "LONG":
            if decision != "GO_LONG":
                return GateDecision(False, f"bridge_decision:{decision}", bridge=bridge, bridge_age_seconds=age, profile=profile)
            if require_whale and not bool(bridge.get("whale_buy", False)):
                return GateDecision(False, "bridge_no_whale_buy", bridge=bridge, bridge_age_seconds=age, profile=profile)
            return GateDecision(True, "bridge_long_ok", bridge=bridge, bridge_age_seconds=age, profile=profile)
        if signal.action == "SHORT":
            if decision != "GO_SHORT":
                return GateDecision(False, f"bridge_decision:{decision}", bridge=bridge, bridge_age_seconds=age, profile=profile)
            if require_whale and not bool(bridge.get("whale_sell", False)):
                return GateDecision(False, "bridge_no_whale_sell", bridge=bridge, bridge_age_seconds=age, profile=profile)
            return GateDecision(True, "bridge_short_ok", bridge=bridge, bridge_age_seconds=age, profile=profile)
        return GateDecision(True, "bridge_flat_ok", bridge=bridge, bridge_age_seconds=age, profile=profile)


class ExecutionAuditTrail:
    def __init__(self, audit_path: Path):
        self.audit_path = audit_path
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, separators=(",", ":"), default=str)
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class ExecutorTelemetry:
    def __init__(self) -> None:
        self.webhook_latencies_ms: List[float] = []
        self.last_webhook_received_utc: str = ""
        self.last_webhook_rtt_ms: float = 0.0
        self.last_feed_delay_seconds: float = float("inf")
        self.last_bridge_age_seconds: float = float("inf")
        self.last_signal_symbol: str = ""
        self.last_watchdog_alert_utc: str = ""
        self.last_watchdog_reason: str = ""

    def update_signal(self, symbol: str, feed_delay_seconds: float, bridge_age_seconds: float) -> None:
        self.last_signal_symbol = symbol
        self.last_feed_delay_seconds = feed_delay_seconds
        self.last_bridge_age_seconds = bridge_age_seconds

    def record_webhook(self, rtt_ms: float) -> None:
        self.last_webhook_received_utc = utc_now_iso()
        self.last_webhook_rtt_ms = float(rtt_ms)
        self.webhook_latencies_ms.append(float(rtt_ms))
        if len(self.webhook_latencies_ms) > 300:
            self.webhook_latencies_ms = self.webhook_latencies_ms[-300:]

    def status(self) -> Dict[str, Any]:
        lat = list(self.webhook_latencies_ms)
        p50 = median(lat) if lat else 0.0
        p95 = 0.0
        if lat:
            lat_sorted = sorted(lat)
            idx = min(len(lat_sorted) - 1, max(0, int(round(0.95 * (len(lat_sorted) - 1)))))
            p95 = lat_sorted[idx]
        return {
            "last_webhook_received_utc": self.last_webhook_received_utc,
            "last_webhook_rtt_ms": round(self.last_webhook_rtt_ms, 2),
            "webhook_rtt_p50_ms": round(float(p50), 2),
            "webhook_rtt_p95_ms": round(float(p95), 2),
            "last_feed_delay_seconds": None if math.isinf(self.last_feed_delay_seconds) else round(self.last_feed_delay_seconds, 2),
            "last_bridge_age_seconds": None if math.isinf(self.last_bridge_age_seconds) else round(self.last_bridge_age_seconds, 2),
            "last_signal_symbol": self.last_signal_symbol,
            "last_watchdog_alert_utc": self.last_watchdog_alert_utc,
            "last_watchdog_reason": self.last_watchdog_reason,
        }


def _post_json_webhook(url: str, payload: Dict[str, Any], timeout: float = 4.0) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if int(getattr(resp, "status", 200)) >= 400:
            raise urllib.error.HTTPError(url=url, code=resp.status, msg="watchdog_http_error", hdrs=None, fp=None)


class PaperBroker:
    def __init__(self, base_dir: Path, broker_name: str, symbol_specs: Dict[str, Dict[str, float]]):
        self.broker_name = broker_name.lower().strip() or "paper"
        self.symbol_specs = symbol_specs
        broker_dir = base_dir / self.broker_name
        self.state_file = broker_dir / "paper_broker_state.json"
        self.orders_file = broker_dir / "paper_orders.csv"
        self.closed_trades_file = broker_dir / "closed_trades.csv"
        base_dir.mkdir(parents=True, exist_ok=True)
        broker_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        default_state = {
            "positions": {},
            "daily_trade_count": 0,
            "last_day": "",
            "last_trade_epoch": 0.0,
            "daily_realized_pnl_usd": 0.0,
            "daily_closed_trades": 0,
            "consecutive_losses": 0,
            "killed_symbols": [],
            "closed_trades": [],
        }
        if self.state_file.exists():
            try:
                loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    merged = dict(default_state)
                    merged.update(loaded)
                    return merged
            except json.JSONDecodeError:
                return default_state
        return default_state

    def _save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _append_order(self, row: Dict[str, Any]) -> None:
        exists = self.orders_file.exists()
        with self.orders_file.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp_utc",
                    "broker",
                    "profile",
                    "symbol",
                    "order_action",
                    "price",
                    "qty",
                    "realized_pnl_usd",
                    "status",
                    "reason",
                ],
            )
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def _append_closed_trade(self, row: Dict[str, Any]) -> None:
        exists = self.closed_trades_file.exists()
        with self.closed_trades_file.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp_utc",
                    "broker",
                    "symbol",
                    "profile",
                    "direction",
                    "entry_price",
                    "exit_price",
                    "qty",
                    "realized_pnl_usd",
                    "reason",
                ],
            )
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def _roll_day(self) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("last_day") != day:
            self.state["last_day"] = day
            self.state["daily_trade_count"] = 0
            self.state["daily_realized_pnl_usd"] = 0.0
            self.state["daily_closed_trades"] = 0
            self.state["consecutive_losses"] = 0

    @staticmethod
    def _parse_windows(raw_windows: List[str]) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for raw in raw_windows:
            value = str(raw or "").strip()
            if "-" not in value:
                continue
            left, right = value.split("-", 1)
            try:
                s_h, s_m = [int(x) for x in left.split(":")]
                e_h, e_m = [int(x) for x in right.split(":")]
            except ValueError:
                continue
            start = max(0, min(1439, s_h * 60 + s_m))
            end = max(0, min(1439, e_h * 60 + e_m))
            out.append((start, end))
        return out

    @staticmethod
    def _minute_in_window(minute_of_day: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= minute_of_day <= end
        return minute_of_day >= start or minute_of_day <= end

    def _session_allowed(self, cfg: Any) -> bool:
        risk_guard = cfg.get("automation.risk_guard", {}) or {}
        session = risk_guard.get("session_lockout", {}) or {}
        if not bool(session.get("enabled", False)):
            return True
        tz_name = str(session.get("timezone", "America/New_York"))
        try:
            now_local = datetime.now(ZoneInfo(tz_name))
        except Exception:
            now_local = datetime.now(timezone.utc)
        windows_raw = session.get("allowed_windows", ["09:30-16:00"])
        windows = self._parse_windows(list(windows_raw) if isinstance(windows_raw, list) else [])
        if not windows:
            return True
        minute = now_local.hour * 60 + now_local.minute
        return any(self._minute_in_window(minute, start, end) for start, end in windows)

    def _killed_symbols(self, cfg: Any) -> set[str]:
        cfg_list = cfg.get("automation.risk_guard.per_symbol_kill_switch", []) or []
        cfg_symbols = {str(s).upper().strip() for s in cfg_list}
        state_symbols = {str(s).upper().strip() for s in self.state.get("killed_symbols", [])}
        return {s for s in cfg_symbols | state_symbols if s}

    def can_trade(self, cfg: Any, symbol: str) -> Tuple[bool, str]:
        self._roll_day()
        max_daily = int(cfg.get("daily_limits.max_daily_trades", 5))
        if int(self.state.get("daily_trade_count", 0)) >= max_daily:
            return False, "daily_trade_limit"
        cooldown = int(cfg.get("automation.cooldown_seconds", 20))
        last_trade = float(self.state.get("last_trade_epoch", 0.0))
        if last_trade > 0 and (time.time() - last_trade) < cooldown:
            return False, "cooldown_active"

        risk_guard = cfg.get("automation.risk_guard", {}) or {}
        if bool(risk_guard.get("enabled", True)):
            max_daily_loss = float(risk_guard.get("max_daily_loss_usd", 0.0))
            realized = float(self.state.get("daily_realized_pnl_usd", 0.0))
            if max_daily_loss > 0 and realized <= -abs(max_daily_loss):
                return False, "daily_loss_limit"

            killed = self._killed_symbols(cfg)
            if symbol.upper() in killed:
                return False, f"symbol_kill_switch:{symbol.upper()}"

            if not self._session_allowed(cfg):
                return False, "session_lockout"
        return True, "ok"

    def _resolve_symbol_params(self, signal: TradingViewSignal) -> Dict[str, float]:
        spec = self.symbol_specs.get(signal.symbol.upper(), {})
        tick_size = float(spec.get("tick_size", 1.0))
        tick_value = float(spec.get("tick_value", 1.0))
        contract_multiplier = float(spec.get("contract_multiplier", 1.0))
        if signal.contract_multiplier > 0:
            contract_multiplier = float(signal.contract_multiplier)
        if signal.instrument_type == "OPTION" and contract_multiplier <= 1.0:
            # Equity/index options usually represent 100 shares per contract.
            contract_multiplier = 100.0
        if tick_size <= 0:
            tick_size = 1.0
        if tick_value <= 0:
            tick_value = 1.0
        if contract_multiplier <= 0:
            contract_multiplier = 1.0
        return {
            "tick_size": float(tick_size),
            "tick_value": float(tick_value),
            "contract_multiplier": float(contract_multiplier),
        }

    def _realized_pnl(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        qty: int,
        *,
        tick_size: float = 1.0,
        tick_value: float = 1.0,
        contract_multiplier: float = 1.0,
    ) -> float:
        if tick_size <= 0:
            tick_size = 1.0
        ticks = (float(exit_price) - float(entry_price)) / tick_size
        pnl = ticks * tick_value * contract_multiplier * int(qty)
        if direction == "SHORT":
            pnl *= -1.0
        return float(pnl)

    def _record_closed_trade(
        self,
        symbol: str,
        profile: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        qty: int,
        realized_pnl_usd: float,
        reason: str,
    ) -> None:
        row = {
            "timestamp_utc": utc_now_iso(),
            "broker": self.broker_name,
            "symbol": symbol,
            "profile": profile,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": qty,
            "realized_pnl_usd": round(realized_pnl_usd, 4),
            "reason": reason,
        }
        self._append_closed_trade(row)
        closed = list(self.state.get("closed_trades", []))
        closed.append(row)
        self.state["closed_trades"] = closed[-500:]
        self.state["daily_closed_trades"] = int(self.state.get("daily_closed_trades", 0)) + 1
        self.state["daily_realized_pnl_usd"] = float(self.state.get("daily_realized_pnl_usd", 0.0)) + float(realized_pnl_usd)
        if realized_pnl_usd < 0:
            self.state["consecutive_losses"] = int(self.state.get("consecutive_losses", 0)) + 1
        else:
            self.state["consecutive_losses"] = 0

    def set_symbol_kill(self, symbol: str, enabled: bool) -> None:
        current = {str(s).upper().strip() for s in self.state.get("killed_symbols", []) if str(s).strip()}
        target = symbol.upper().strip()
        if not target:
            return
        if enabled:
            current.add(target)
        else:
            current.discard(target)
        self.state["killed_symbols"] = sorted(current)
        self._save_state()

    def profile_metrics(self, rolling_trades: int = 60) -> Dict[str, Dict[str, float]]:
        closed = list(self.state.get("closed_trades", []))
        if rolling_trades > 0:
            closed = closed[-rolling_trades:]
        grouped: Dict[str, List[float]] = defaultdict(list)
        for row in closed:
            profile = str(row.get("profile", "unknown")).lower()
            pnl = float(row.get("realized_pnl_usd", 0.0))
            grouped[profile].append(pnl)
        out: Dict[str, Dict[str, float]] = {}
        for profile, pnls in grouped.items():
            count = len(pnls)
            wins = sum(1 for p in pnls if p > 0)
            net = float(sum(pnls))
            avg = net / count if count else 0.0
            out[profile] = {
                "trades": float(count),
                "win_rate": float((wins / count) * 100.0 if count else 0.0),
                "net_pnl_usd": float(round(net, 4)),
                "avg_pnl_usd": float(round(avg, 4)),
            }
        return out

    def status(self, cfg: Any) -> Dict[str, Any]:
        self._roll_day()
        return {
            "broker": self.broker_name,
            "state_file": str(self.state_file),
            "orders_file": str(self.orders_file),
            "closed_trades_file": str(self.closed_trades_file),
            "daily_trade_count": int(self.state.get("daily_trade_count", 0)),
            "daily_realized_pnl_usd": round(float(self.state.get("daily_realized_pnl_usd", 0.0)), 4),
            "daily_closed_trades": int(self.state.get("daily_closed_trades", 0)),
            "consecutive_losses": int(self.state.get("consecutive_losses", 0)),
            "killed_symbols": sorted(self._killed_symbols(cfg)),
            "open_positions": len(self.state.get("positions", {})),
        }

    def execute(self, signal: TradingViewSignal, qty: int, profile: str) -> Tuple[bool, str, Dict[str, Any]]:
        positions = self.state.setdefault("positions", {})
        sym_pos = positions.get(signal.symbol)
        action = signal.action
        realized_pnl_usd = 0.0

        if action == "FLAT":
            if not sym_pos:
                return False, "no_position_to_close", {"realized_pnl_usd": 0.0}
            realized_pnl_usd = self._realized_pnl(
                symbol=signal.symbol,
                direction=str(sym_pos.get("direction", "LONG")),
                entry_price=float(sym_pos.get("entry_price", signal.price)),
                exit_price=float(signal.price),
                qty=int(sym_pos.get("qty", qty)),
                tick_size=float(sym_pos.get("tick_size", 1.0)),
                tick_value=float(sym_pos.get("tick_value", 1.0)),
                contract_multiplier=float(sym_pos.get("contract_multiplier", 1.0)),
            )
            self._record_closed_trade(
                symbol=signal.symbol,
                profile=str(sym_pos.get("profile", profile)),
                direction=str(sym_pos.get("direction", "LONG")),
                entry_price=float(sym_pos.get("entry_price", signal.price)),
                exit_price=float(signal.price),
                qty=int(sym_pos.get("qty", qty)),
                realized_pnl_usd=realized_pnl_usd,
                reason="flat_signal",
            )
            positions.pop(signal.symbol, None)
            self.state["daily_trade_count"] = int(self.state.get("daily_trade_count", 0)) + 1
            self.state["last_trade_epoch"] = time.time()
            self._save_state()
            self._append_order(
                {
                    "timestamp_utc": utc_now_iso(),
                    "broker": self.broker_name,
                    "profile": str(sym_pos.get("profile", profile)),
                    "symbol": signal.symbol,
                    "order_action": "CLOSE",
                    "price": signal.price,
                    "qty": sym_pos.get("qty", qty),
                    "realized_pnl_usd": round(realized_pnl_usd, 4),
                    "status": "FILLED",
                    "reason": "flat_signal",
                }
            )
            return True, "closed", {"realized_pnl_usd": round(realized_pnl_usd, 4)}

        if action not in {"LONG", "SHORT"}:
            return False, "unknown_action", {"realized_pnl_usd": 0.0}

        if sym_pos and sym_pos.get("direction") == action:
            return False, "already_in_same_direction", {"realized_pnl_usd": 0.0}

        if sym_pos and sym_pos.get("direction") != action:
            realized_pnl_usd = self._realized_pnl(
                symbol=signal.symbol,
                direction=str(sym_pos.get("direction", "LONG")),
                entry_price=float(sym_pos.get("entry_price", signal.price)),
                exit_price=float(signal.price),
                qty=int(sym_pos.get("qty", qty)),
                tick_size=float(sym_pos.get("tick_size", 1.0)),
                tick_value=float(sym_pos.get("tick_value", 1.0)),
                contract_multiplier=float(sym_pos.get("contract_multiplier", 1.0)),
            )
            self._record_closed_trade(
                symbol=signal.symbol,
                profile=str(sym_pos.get("profile", profile)),
                direction=str(sym_pos.get("direction", "LONG")),
                entry_price=float(sym_pos.get("entry_price", signal.price)),
                exit_price=float(signal.price),
                qty=int(sym_pos.get("qty", qty)),
                realized_pnl_usd=realized_pnl_usd,
                reason="reverse_close",
            )
            self._append_order(
                {
                    "timestamp_utc": utc_now_iso(),
                    "broker": self.broker_name,
                    "profile": str(sym_pos.get("profile", profile)),
                    "symbol": signal.symbol,
                    "order_action": "CLOSE",
                    "price": signal.price,
                    "qty": sym_pos.get("qty", qty),
                    "realized_pnl_usd": round(realized_pnl_usd, 4),
                    "status": "FILLED",
                    "reason": "reverse_close",
                }
            )

        symbol_params = self._resolve_symbol_params(signal)
        positions[signal.symbol] = {
            "direction": action,
            "qty": qty,
            "entry_price": signal.price,
            "entry_time_utc": utc_now_iso(),
            "profile": profile,
            "tick_size": float(symbol_params["tick_size"]),
            "tick_value": float(symbol_params["tick_value"]),
            "contract_multiplier": float(symbol_params["contract_multiplier"]),
            "instrument_type": signal.instrument_type,
        }
        self.state["daily_trade_count"] = int(self.state.get("daily_trade_count", 0)) + 1
        self.state["last_trade_epoch"] = time.time()
        self._save_state()
        self._append_order(
            {
                "timestamp_utc": utc_now_iso(),
                "broker": self.broker_name,
                "profile": profile,
                "symbol": signal.symbol,
                "order_action": action,
                "price": signal.price,
                "qty": qty,
                "realized_pnl_usd": 0.0,
                "status": "FILLED",
                "reason": "paper_execution",
            }
        )
        return True, "filled", {"realized_pnl_usd": round(realized_pnl_usd, 4)}


class ChimeraExecutionService:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.cfg = init_config(config_path)
        self.allowed_symbols = {s.upper() for s in self.cfg.get("automation.allowed_symbols", ["MNQ1!", "MGC1!"])}
        self.allowed_symbol_patterns = [str(p).upper() for p in (self.cfg.get("automation.allowed_symbol_patterns", []) or [])]
        self.webhook_secret = str(self.cfg.get("automation.webhook_secret", ""))
        self.default_qty = int(self.cfg.get("automation.default_order_qty", 1))
        self.gate = ChimeraGate(self.cfg)
        self.telemetry = ExecutorTelemetry()
        self.router = BrokerRouter(self.cfg)
        self.state_dir = Path(self.cfg.get("automation.state_dir", "data"))
        self.audit = ExecutionAuditTrail(
            Path(self.cfg.get("automation.audit_log_file", str(self.state_dir / "chimera_execution_audit.jsonl")))
        )

        raw_specs = self.cfg.get("automation.symbol_specs", {}) or {}
        self.symbol_specs: Dict[str, Dict[str, float]] = {}
        if isinstance(raw_specs, dict):
            for symbol, spec in raw_specs.items():
                if not isinstance(spec, dict):
                    continue
                self.symbol_specs[str(symbol).upper()] = {
                    "tick_size": float(spec.get("tick_size", 1.0)),
                    "tick_value": float(spec.get("tick_value", 1.0)),
                    "contract_multiplier": float(spec.get("contract_multiplier", 1.0)),
                }

        broker_names = set()
        broker_names.add(_normalize_broker_name(self.cfg.get("automation.broker", "tradovate"), default="tradovate"))
        broker_names.add(_normalize_broker_name(self.router.default_broker, default="tradovate"))
        for rule in self.router.rules:
            broker_names.add(_normalize_broker_name(rule.get("broker", ""), default=""))
        configured = self.cfg.get("automation.brokers", []) or []
        if isinstance(configured, list):
            for item in configured:
                broker_names.add(_normalize_broker_name(item, default=""))
        broker_names.add(TRADINGVIEW_PAPER_BROKER)
        self.paper_brokers: Dict[str, PaperBroker] = {}
        for broker in sorted({b for b in broker_names if b}):
            self.paper_brokers[broker] = PaperBroker(self.state_dir, broker_name=broker, symbol_specs=self.symbol_specs)

    def _paper(self, broker: str) -> PaperBroker:
        key = _normalize_broker_name(broker, default=self.router.default_broker)
        if key not in self.paper_brokers:
            self.paper_brokers[key] = PaperBroker(self.state_dir, broker_name=key, symbol_specs=self.symbol_specs)
        return self.paper_brokers[key]

    def _watchdog_health(self) -> Dict[str, Any]:
        watchdog = self.cfg.get("automation.watchdog", {}) or {}
        if not bool(watchdog.get("enabled", True)):
            return {"ok": True, "alerts": [], "disabled": True}
        alerts: List[str] = []

        max_feed_delay = float(watchdog.get("max_feed_delay_seconds", 20.0))
        if not math.isinf(self.telemetry.last_feed_delay_seconds) and self.telemetry.last_feed_delay_seconds > max_feed_delay:
            alerts.append(f"feed_delay:{self.telemetry.last_feed_delay_seconds:.1f}s>{max_feed_delay:.1f}s")

        max_bridge_age = float(watchdog.get("max_bridge_age_seconds", 30.0))
        if not math.isinf(self.telemetry.last_bridge_age_seconds) and self.telemetry.last_bridge_age_seconds > max_bridge_age:
            alerts.append(f"bridge_age:{self.telemetry.last_bridge_age_seconds:.1f}s>{max_bridge_age:.1f}s")

        max_idle = float(watchdog.get("max_webhook_idle_seconds", 300.0))
        if self.telemetry.last_webhook_received_utc:
            idle_seconds = _age_seconds(self.telemetry.last_webhook_received_utc)
            if idle_seconds > max_idle:
                alerts.append(f"executor_idle:{idle_seconds:.1f}s>{max_idle:.1f}s")

        return {"ok": len(alerts) == 0, "alerts": alerts, "disabled": False}

    def _maybe_send_watchdog_alert(self) -> None:
        health = self._watchdog_health()
        if health.get("ok", True):
            return
        watchdog = self.cfg.get("automation.watchdog", {}) or {}
        url = str(watchdog.get("phone_alert_webhook_url", "")).strip()
        if not url:
            return
        cooldown = float(watchdog.get("phone_alert_cooldown_seconds", 180.0))
        if self.telemetry.last_watchdog_alert_utc:
            last_alert_age = _age_seconds(self.telemetry.last_watchdog_alert_utc)
            if last_alert_age < cooldown:
                return
        payload = {
            "service": "chimera_executor",
            "timestamp_utc": utc_now_iso(),
            "alerts": list(health.get("alerts", [])),
            "feed_delay_seconds": None if math.isinf(self.telemetry.last_feed_delay_seconds) else self.telemetry.last_feed_delay_seconds,
            "bridge_age_seconds": None if math.isinf(self.telemetry.last_bridge_age_seconds) else self.telemetry.last_bridge_age_seconds,
            "last_webhook_received_utc": self.telemetry.last_webhook_received_utc,
        }
        try:
            _post_json_webhook(url, payload)
            self.telemetry.last_watchdog_alert_utc = utc_now_iso()
            self.telemetry.last_watchdog_reason = ",".join(payload["alerts"])
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning(f"Watchdog alert webhook failed: {exc}")

    def _ab_profile_tracker(self, rolling_trades: int) -> Dict[str, Dict[str, Dict[str, float]]]:
        out: Dict[str, Dict[str, Dict[str, float]]] = {}
        for broker, paper in sorted(self.paper_brokers.items()):
            out[broker] = paper.profile_metrics(rolling_trades=rolling_trades)
        return out

    def _audit_event(
        self,
        *,
        request_id: str,
        signal: TradingViewSignal,
        broker: str,
        route: Dict[str, str],
        gate: Optional[GateDecision],
        risk_reason: str,
        response_code: int,
        response_body: Dict[str, Any],
    ) -> None:
        bridge_snapshot = gate.bridge if gate else None
        event = {
            "request_id": request_id,
            "timestamp_utc": utc_now_iso(),
            "signal": {
                "symbol": signal.symbol,
                "action": signal.action,
                "price": signal.price,
                "qty": signal.qty,
                "timestamp_utc": signal.timestamp_utc,
                "strategy_profile": signal.strategy_profile,
                "broker_hint": signal.broker_hint,
                "instrument_type": signal.instrument_type,
                "contract_multiplier": signal.contract_multiplier,
            },
            "routing": route,
            "broker": broker,
            "risk_reason": risk_reason,
            "gate_reason": gate.reason if gate else "not_checked",
            "bridge_age_seconds": None if not gate or math.isinf(gate.bridge_age_seconds) else round(gate.bridge_age_seconds, 3),
            "bridge_snapshot": bridge_snapshot,
            "webhook_response": {
                "http_code": response_code,
                "body": response_body,
            },
        }
        self.audit.append(event)

    def _status_payload(self) -> Dict[str, Any]:
        health = self._watchdog_health()
        ab_rolling = int(self.cfg.get("automation.ab_profile_tracker.rolling_trades", 60))
        latency = self.telemetry.status()
        return {
            "ok": True,
            "service": "chimera_executor",
            "paper_mode": True,
            "allowed_symbols": sorted(self.allowed_symbols),
            "allowed_symbol_patterns": sorted(self.allowed_symbol_patterns),
            "brokers": {name: broker.status(self.cfg) for name, broker in sorted(self.paper_brokers.items())},
            "telemetry": latency,
            "latency_monitor": latency,
            "watchdog": health,
            "audit_log_file": str(self.audit.audit_path),
            "ab_profile_tracker": {
                "rolling_trades": ab_rolling,
                "profiles": self._ab_profile_tracker(rolling_trades=ab_rolling),
            },
        }

    def set_symbol_kill(self, symbol: str, broker: str, enabled: bool) -> Dict[str, Any]:
        norm_broker = _normalize_broker_name(broker, default=self.router.default_broker)
        paper = self._paper(norm_broker)
        paper.set_symbol_kill(symbol=symbol, enabled=enabled)
        return {
            "ok": True,
            "symbol": symbol.upper().strip(),
            "broker": norm_broker,
            "enabled": bool(enabled),
            "killed_symbols": paper.status(self.cfg).get("killed_symbols", []),
        }

    def _symbol_allowed(self, symbol: str) -> bool:
        sym = str(symbol or "").upper().strip()
        if sym in self.allowed_symbols:
            return True
        for pattern in self.allowed_symbol_patterns:
            if fnmatch.fnmatch(sym, pattern):
                return True
        return False

    def process_payload(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        request_id = str(payload.get("request_id", uuid.uuid4().hex))
        signal = TradingViewSignal.from_payload(payload)
        feed_delay_seconds = _age_seconds(signal.timestamp_utc)

        route = self.router.resolve(signal.symbol)
        target_broker = _normalize_broker_name(signal.broker_hint or route["broker"], default=self.router.default_broker)
        paper = self._paper(target_broker)

        default_profile = route.get("profile", "default")
        profile = signal.strategy_profile if signal.strategy_profile != "default" else default_profile

        if not self._symbol_allowed(signal.symbol):
            body = {
                "ok": False,
                "reason": f"symbol_not_allowed:{signal.symbol}",
                "request_id": request_id,
                "broker": target_broker,
            }
            self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=None,
                risk_reason="not_checked",
                response_code=400,
                response_body=body,
            )
            return 400, body
        if signal.action == "UNKNOWN":
            body = {"ok": False, "reason": "unknown_action", "request_id": request_id, "broker": target_broker}
            self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=None,
                risk_reason="not_checked",
                response_code=400,
                response_body=body,
            )
            return 400, body

        can_trade, risk_reason = paper.can_trade(self.cfg, signal.symbol)
        if not can_trade:
            body = {
                "ok": False,
                "reason": risk_reason,
                "symbol": signal.symbol,
                "action": signal.action,
                "broker": target_broker,
                "profile": profile,
                "request_id": request_id,
            }
            self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=None,
                risk_reason=risk_reason,
                response_code=200,
                response_body=body,
            )
            return 200, body

        gate = self.gate.check(signal)
        if gate.profile and gate.profile != "disabled":
            profile = str(gate.profile).lower()
        else:
            profile = str(profile or "default").lower()
        self.telemetry.update_signal(signal.symbol, feed_delay_seconds, gate.bridge_age_seconds)
        if not gate.allowed:
            body = {
                "ok": False,
                "reason": gate.reason,
                "symbol": signal.symbol,
                "action": signal.action,
                "broker": target_broker,
                "profile": profile,
                "request_id": request_id,
            }
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=gate,
                risk_reason=risk_reason,
                response_code=200,
                response_body=body,
            )
            return 200, body

        exec_qty = signal.qty if signal.qty > 0 else self.default_qty
        filled, exec_reason, exec_info = paper.execute(signal, qty=exec_qty, profile=profile)
        body = {
            "ok": filled,
            "reason": exec_reason,
            "gate": gate.reason,
            "symbol": signal.symbol,
            "action": signal.action,
            "qty": exec_qty,
            "profile": profile,
            "broker": target_broker,
            "routing_pattern": route.get("pattern", "*"),
            "paper_mode": True,
            "realized_pnl_usd": float(exec_info.get("realized_pnl_usd", 0.0)),
            "request_id": request_id,
        }
        self._audit_event(
            request_id=request_id,
            signal=signal,
            broker=target_broker,
            route=route,
            gate=gate,
            risk_reason=risk_reason,
            response_code=200,
            response_body=body,
        )
        return 200, body

    def process_fill_mirror_payload(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        Mirror TradingView broker-side fills directly into Chimera paper journals.
        This bypasses Chimera bridge/risk gating so journaling can stay in sync with
        external broker execution driven by TradingView.
        """
        request_id = str(payload.get("request_id", uuid.uuid4().hex))
        signal = TradingViewSignal.from_payload(payload)
        feed_delay_seconds = _age_seconds(signal.timestamp_utc)
        route = self.router.resolve(signal.symbol)
        target_broker = _normalize_broker_name(signal.broker_hint or route["broker"], default=self.router.default_broker)
        paper = self._paper(target_broker)
        default_profile = route.get("profile", "default")
        profile = signal.strategy_profile if signal.strategy_profile != "default" else default_profile
        exec_qty = signal.qty if signal.qty > 0 else self.default_qty

        if not self._symbol_allowed(signal.symbol):
            body = {
                "ok": False,
                "reason": f"symbol_not_allowed:{signal.symbol}",
                "request_id": request_id,
                "broker": target_broker,
                "mode": "fill_mirror",
            }
            self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=None,
                risk_reason="mirror_not_allowed",
                response_code=400,
                response_body=body,
            )
            return 400, body

        if signal.action == "UNKNOWN":
            body = {
                "ok": False,
                "reason": "unknown_action",
                "request_id": request_id,
                "broker": target_broker,
                "mode": "fill_mirror",
            }
            self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
            self._audit_event(
                request_id=request_id,
                signal=signal,
                broker=target_broker,
                route=route,
                gate=None,
                risk_reason="mirror_unknown_action",
                response_code=400,
                response_body=body,
            )
            return 400, body

        filled, exec_reason, exec_info = paper.execute(signal, qty=exec_qty, profile=profile)
        self.telemetry.update_signal(signal.symbol, feed_delay_seconds, float("inf"))
        body = {
            "ok": filled,
            "reason": exec_reason,
            "symbol": signal.symbol,
            "action": signal.action,
            "qty": exec_qty,
            "profile": profile,
            "broker": target_broker,
            "routing_pattern": route.get("pattern", "*"),
            "paper_mode": True,
            "mode": "fill_mirror",
            "realized_pnl_usd": float(exec_info.get("realized_pnl_usd", 0.0)),
            "request_id": request_id,
        }
        self._audit_event(
            request_id=request_id,
            signal=signal,
            broker=target_broker,
            route=route,
            gate=None,
            risk_reason="mirror_fill",
            response_code=200,
            response_body=body,
        )
        return 200, body


def run_server(config_path: str, host: str, port: int) -> None:
    service = ChimeraExecutionService(config_path=config_path)

    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            if not service.webhook_secret:
                return True
            secret = self.headers.get("X-Chimera-Secret", "")
            return secret == service.webhook_secret

        def _send(self, code: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/status"):
                body = service._status_payload()
                service._maybe_send_watchdog_alert()
                self._send(200, body)
                return
            if self.path.startswith("/risk/status"):
                body = service._status_payload()
                self._send(200, {"ok": True, "risk": body["brokers"], "watchdog": body["watchdog"]})
                return
            self._send(404, {"ok": False, "reason": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.startswith("/risk/kill"):
                if not self._authorized():
                    self._send(401, {"ok": False, "reason": "unauthorized"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("payload_must_be_object")
                except (json.JSONDecodeError, ValueError):
                    self._send(400, {"ok": False, "reason": "invalid_json"})
                    return

                symbol = str(payload.get("symbol", "")).upper().strip()
                broker = _normalize_broker_name(payload.get("broker", service.router.default_broker), default=service.router.default_broker)
                enabled = bool(payload.get("enabled", True))
                if not symbol:
                    self._send(400, {"ok": False, "reason": "missing_symbol"})
                    return
                body = service.set_symbol_kill(symbol=symbol, broker=broker, enabled=enabled)
                self._send(200, body)
                return

            is_tv_paper = self.path.startswith("/webhook/tradingview/paper")
            is_fill_mirror = self.path.startswith("/webhook/tradingview/fill") or is_tv_paper
            if not self.path.startswith("/webhook/tradingview"):
                self._send(404, {"ok": False, "reason": "not_found"})
                return

            if not self._authorized():
                self._send(401, {"ok": False, "reason": "unauthorized"})
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("payload_must_be_object")
            except (json.JSONDecodeError, ValueError):
                self._send(400, {"ok": False, "reason": "invalid_json"})
                return

            if is_tv_paper:
                payload["broker"] = TRADINGVIEW_PAPER_BROKER

            started = time.perf_counter()
            if is_fill_mirror:
                code, body = service.process_fill_mirror_payload(payload)
            else:
                code, body = service.process_payload(payload)
            rtt_ms = (time.perf_counter() - started) * 1000.0
            service.telemetry.record_webhook(rtt_ms)
            service._maybe_send_watchdog_alert()
            body["latency"] = {
                "webhook_rtt_ms": round(rtt_ms, 2),
                "feed_delay_seconds": None
                if math.isinf(service.telemetry.last_feed_delay_seconds)
                else round(service.telemetry.last_feed_delay_seconds, 2),
                "bridge_age_seconds": None
                if math.isinf(service.telemetry.last_bridge_age_seconds)
                else round(service.telemetry.last_bridge_age_seconds, 2),
            }
            self._send(code, body)

    server = ThreadingHTTPServer((host, port), Handler)
    logger.info(f"Chimera executor listening on http://{host}:{port}")
    server.serve_forever()

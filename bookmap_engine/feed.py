from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import requests

from bookmap_engine.core import OrderBookSnapshot


@dataclass
class SyntheticFeedConfig:
    seed: int = 42
    start_price: float = 25000.0
    tick_size: float = 0.25
    levels_per_side: int = 30
    base_depth: float = 40.0
    volatility: float = 2.0


@dataclass
class BinanceFeedConfig:
    symbol: str = "btcusdt"
    depth_limit: int = 100
    timeout_seconds: float = 3.0


@dataclass
class ExternalL2BridgeConfig:
    path: str = "data/live_l2_snapshot.json"
    stale_after_seconds: float = 3.0
    expected_symbol: str = ""


@dataclass
class ReplayFeedConfig:
    path: str = "data/replay_snapshots.jsonl"
    loop: bool = False


class SyntheticOrderBookFeed:
    """Synthetic L2 feed for UI and signal validation without broker connection."""

    def __init__(self, cfg: SyntheticFeedConfig) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.mid = cfg.start_price
        self._last_side = "buy"

    def next_snapshot(self) -> OrderBookSnapshot:
        drift = self.rng.normal(0.0, self.cfg.volatility)
        self.mid = max(self.cfg.tick_size, self.mid + drift)

        bids: Dict[float, float] = {}
        asks: Dict[float, float] = {}
        for i in range(1, self.cfg.levels_per_side + 1):
            bid_px = self.mid - i * self.cfg.tick_size
            ask_px = self.mid + i * self.cfg.tick_size
            decay = np.exp(-i / 10.0)
            bid_sz = max(0.1, self.cfg.base_depth * decay * (1.0 + self.rng.normal(0.0, 0.25)))
            ask_sz = max(0.1, self.cfg.base_depth * decay * (1.0 + self.rng.normal(0.0, 0.25)))
            bids[round(bid_px, 8)] = float(bid_sz)
            asks[round(ask_px, 8)] = float(ask_sz)

        # Controlled event injection keeps chart informative but not chaotic.
        event_roll = self.rng.random()
        if event_roll < 0.05:
            # Spoof-like large resting liquidity one side.
            if self.rng.random() > 0.5:
                px = round(self.mid + 4 * self.cfg.tick_size, 8)
                asks[px] = asks.get(px, 0.0) + self.cfg.base_depth * 3.0
            else:
                px = round(self.mid - 4 * self.cfg.tick_size, 8)
                bids[px] = bids.get(px, 0.0) + self.cfg.base_depth * 3.0

        trade_side = "buy" if self.rng.random() > 0.5 else "sell"
        trade_size = float(max(1.0, abs(self.rng.normal(8.0, 5.0))))
        if self.rng.random() < 0.12:
            trade_size *= 2.5  # occasional aggressive burst
        trade_px = self.mid + (self.cfg.tick_size if trade_side == "buy" else -self.cfg.tick_size)
        self._last_side = trade_side

        return OrderBookSnapshot(
            ts=datetime.now(timezone.utc),
            mid=float(self.mid),
            bids=bids,
            asks=asks,
            last_trade_price=float(round(trade_px, 8)),
            last_trade_size=trade_size,
            last_trade_side=trade_side,
        )


class BinanceRestOrderBookFeed:
    """Public Binance REST feed with region fallback (futures -> spot -> binance.us)."""

    def __init__(self, cfg: BinanceFeedConfig) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        self.endpoints = [
            # Binance Futures (global)
            ("https://fapi.binance.com", "/fapi/v1/depth", "/fapi/v1/trades"),
            # Binance Spot (global)
            ("https://api.binance.com", "/api/v3/depth", "/api/v3/trades"),
            # Binance US Spot
            ("https://api.binance.us", "/api/v3/depth", "/api/v3/trades"),
        ]

    def _fetch_depth(self, base_url: str, depth_path: str) -> dict:
        url = f"{base_url}{depth_path}"
        params = {"symbol": self.cfg.symbol.upper(), "limit": self.cfg.depth_limit}
        resp = self.session.get(url, params=params, timeout=self.cfg.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def _fetch_trade(self, base_url: str, trades_path: str) -> dict:
        url = f"{base_url}{trades_path}"
        params = {"symbol": self.cfg.symbol.upper(), "limit": 1}
        resp = self.session.get(url, params=params, timeout=self.cfg.timeout_seconds)
        resp.raise_for_status()
        trades = resp.json()
        if not trades:
            return {"price": "0", "qty": "0", "isBuyerMaker": False}
        return trades[0]

    def next_snapshot(self) -> OrderBookSnapshot:
        last_error = None
        depth = None
        trade = None

        for base_url, depth_path, trades_path in self.endpoints:
            try:
                depth = self._fetch_depth(base_url, depth_path)
                trade = self._fetch_trade(base_url, trades_path)
                last_error = None
                break
            except requests.RequestException as exc:
                last_error = exc
                continue

        if depth is None or trade is None:
            raise RuntimeError(f"All Binance endpoints failed for {self.cfg.symbol.upper()}: {last_error}")

        bids: Dict[float, float] = {}
        asks: Dict[float, float] = {}

        for px_str, qty_str in depth.get("bids", []):
            bids[float(px_str)] = float(qty_str)
        for px_str, qty_str in depth.get("asks", []):
            asks[float(px_str)] = float(qty_str)

        best_bid = max(bids.keys()) if bids else 0.0
        best_ask = min(asks.keys()) if asks else 0.0
        mid = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else float(trade.get("price", 0.0))

        trade_price = float(trade.get("price", 0.0))
        trade_size = float(trade.get("qty", 0.0))
        trade_side = "sell" if bool(trade.get("isBuyerMaker", False)) else "buy"

        return OrderBookSnapshot(
            ts=datetime.now(timezone.utc),
            mid=mid,
            bids=bids,
            asks=asks,
            last_trade_price=trade_price,
            last_trade_size=trade_size,
            last_trade_side=trade_side,
        )


def snapshot_to_record(snapshot: OrderBookSnapshot) -> Dict[str, Any]:
    return {
        "timestamp_utc": snapshot.ts.astimezone(timezone.utc).isoformat(),
        "mid": float(snapshot.mid),
        "bids": {str(px): float(sz) for px, sz in snapshot.bids.items()},
        "asks": {str(px): float(sz) for px, sz in snapshot.asks.items()},
        "last_trade_price": float(snapshot.last_trade_price),
        "last_trade_size": float(snapshot.last_trade_size),
        "last_trade_side": str(snapshot.last_trade_side),
    }


def _snapshot_from_record(record: Dict[str, Any]) -> OrderBookSnapshot:
    ts_raw = str(record.get("timestamp_utc", ""))
    ts = datetime.now(timezone.utc)
    if ts_raw:
        try:
            parsed = datetime.fromisoformat(ts_raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            ts = parsed.astimezone(timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)
    bids = {float(px): float(sz) for px, sz in dict(record.get("bids", {})).items()}
    asks = {float(px): float(sz) for px, sz in dict(record.get("asks", {})).items()}
    return OrderBookSnapshot(
        ts=ts,
        mid=float(record.get("mid", 0.0)),
        bids=bids,
        asks=asks,
        last_trade_price=float(record.get("last_trade_price", 0.0)),
        last_trade_size=float(record.get("last_trade_size", 0.0)),
        last_trade_side=str(record.get("last_trade_side", "buy")),
    )


class ExternalL2BridgeFeed:
    """
    File bridge adapter for real broker/vendor L2 snapshots.
    Expected JSON schema matches `snapshot_to_record`.
    """

    def __init__(self, cfg: ExternalL2BridgeConfig) -> None:
        self.cfg = cfg
        self.path = Path(cfg.path)

    def next_snapshot(self) -> OrderBookSnapshot:
        if not self.path.exists():
            raise RuntimeError(f"External L2 bridge file missing: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("External L2 bridge payload must be a JSON object")
        expected = str(self.cfg.expected_symbol or "").upper().strip()
        bridge_symbol = str(raw.get("symbol", "")).upper().strip()
        if expected and bridge_symbol and bridge_symbol != expected:
            raise RuntimeError(
                f"External L2 symbol mismatch (bridge={bridge_symbol}, app={expected}). "
                "Switch Source to Binance Futures (REST) for BTC/ETH or choose matching bridge symbol."
            )
        snap = _snapshot_from_record(raw)
        age_seconds = (datetime.now(timezone.utc) - snap.ts.astimezone(timezone.utc)).total_seconds()
        if age_seconds > float(self.cfg.stale_after_seconds):
            raise RuntimeError(f"External L2 bridge snapshot stale ({age_seconds:.1f}s)")
        return snap


class ReplayOrderBookFeed:
    def __init__(self, cfg: ReplayFeedConfig) -> None:
        self.cfg = cfg
        self.path = Path(cfg.path)
        self.records: List[OrderBookSnapshot] = []
        self.index = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            raise RuntimeError(f"Replay file missing: {self.path}")
        snapshots: List[OrderBookSnapshot] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                row = line.strip()
                if not row:
                    continue
                payload = json.loads(row)
                if isinstance(payload, dict):
                    snapshots.append(_snapshot_from_record(payload))
        if not snapshots:
            raise RuntimeError(f"Replay file has no snapshots: {self.path}")
        self.records = snapshots
        self.index = 0

    def next_snapshot(self) -> OrderBookSnapshot:
        if not self.records:
            raise RuntimeError("Replay feed has no records")
        if self.index >= len(self.records):
            if not self.cfg.loop:
                raise RuntimeError("Replay completed")
            self.index = 0
        snap = self.records[self.index]
        self.index += 1
        return snap

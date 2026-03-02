#!/usr/bin/env python3
"""
Write normalized L2 snapshots for Chimera app consumption.

This bridge supports three input providers:
- file-poll: poll a broker/vendor JSON file and normalize it
- binance-rest: public REST depth snapshots (useful for live testing)
- synthetic: deterministic simulated L2 stream

Output schema matches `bookmap_engine.feed.snapshot_to_record` and is written to:
  data/live_l2_snapshot.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from loguru import logger

# Ensure project root is importable when script is run directly.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bookmap_engine.core import OrderBookSnapshot
from bookmap_engine.feed import (
    BinanceFeedConfig,
    BinanceRestOrderBookFeed,
    SyntheticFeedConfig,
    SyntheticOrderBookFeed,
    snapshot_to_record,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pairs_to_book(levels: Iterable[Any], price_key: str, size_key: str) -> Dict[float, float]:
    out: Dict[float, float] = {}
    for row in levels:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            px = _coerce_float(row[0], 0.0)
            sz = _coerce_float(row[1], 0.0)
        elif isinstance(row, dict):
            px = _coerce_float(row.get(price_key), 0.0)
            sz = _coerce_float(row.get(size_key), 0.0)
        else:
            continue
        if px > 0 and sz >= 0:
            out[float(px)] = float(sz)
    return out


def _normalize_external_payload(payload: Dict[str, Any]) -> OrderBookSnapshot:
    ts_raw = str(payload.get("timestamp_utc", payload.get("timestamp", utc_now_iso())))
    try:
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        ts = datetime.now(timezone.utc)

    # Already normalized schema.
    if isinstance(payload.get("bids"), dict) and isinstance(payload.get("asks"), dict):
        bids = {float(k): _coerce_float(v) for k, v in payload["bids"].items()}
        asks = {float(k): _coerce_float(v) for k, v in payload["asks"].items()}
    else:
        # Support list-style levels from common broker/vendor payloads.
        raw_bids = payload.get("bids", payload.get("bid_levels", []))
        raw_asks = payload.get("asks", payload.get("ask_levels", []))
        bids = _pairs_to_book(raw_bids if isinstance(raw_bids, list) else [], "price", "size")
        asks = _pairs_to_book(raw_asks if isinstance(raw_asks, list) else [], "price", "size")
        if not bids and isinstance(raw_bids, list):
            bids = _pairs_to_book(raw_bids, "price", "liquidity")
        if not asks and isinstance(raw_asks, list):
            asks = _pairs_to_book(raw_asks, "price", "liquidity")

    best_bid = max(bids.keys()) if bids else 0.0
    best_ask = min(asks.keys()) if asks else 0.0
    mid = _coerce_float(payload.get("mid"), 0.0)
    if mid <= 0 and best_bid > 0 and best_ask > 0:
        mid = (best_bid + best_ask) / 2.0

    trade_price = _coerce_float(payload.get("last_trade_price"), mid)
    trade_size = _coerce_float(payload.get("last_trade_size"), 0.0)
    trade_side = str(payload.get("last_trade_side", "buy")).lower().strip()
    if trade_side not in {"buy", "sell"}:
        trade_side = "buy"

    return OrderBookSnapshot(
        ts=ts.astimezone(timezone.utc),
        mid=mid,
        bids=bids,
        asks=asks,
        last_trade_price=trade_price,
        last_trade_size=trade_size,
        last_trade_side=trade_side,
    )


@dataclass
class BridgeConfig:
    symbol: str
    broker: str
    provider: str
    input_file: str
    output_file: str
    poll_ms: int
    stale_after_seconds: float
    fallback_provider: str


class FilePollProvider:
    def __init__(self, input_file: str, stale_after_seconds: float):
        self.path = Path(input_file)
        self.stale_after_seconds = float(stale_after_seconds)
        self.last_payload_hash = ""

    def next_snapshot(self) -> OrderBookSnapshot:
        if not self.path.exists():
            raise RuntimeError(f"Input file missing: {self.path}")
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            raise RuntimeError(f"Input file is empty: {self.path}")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("Input file payload must be a JSON object")
        snap = _normalize_external_payload(payload)
        age = (datetime.now(timezone.utc) - snap.ts.astimezone(timezone.utc)).total_seconds()
        if age > self.stale_after_seconds:
            raise RuntimeError(f"Input snapshot stale ({age:.1f}s > {self.stale_after_seconds:.1f}s)")
        return snap


def _synthetic_profile_for_symbol(symbol: str) -> Tuple[float, float, float]:
    s = (symbol or "").upper().strip()
    if s.startswith("MNQ") or s.startswith("NQ"):
        return 25000.0, 0.25, 6.0
    if s.startswith("MGC") or s.startswith("GC"):
        return 5200.0, 0.1, 1.8
    if s.startswith("EUR") or s.startswith("USD"):
        return 1.1000, 0.0001, 0.0008
    return 25000.0, 0.25, 2.0


def _build_provider(cfg: BridgeConfig):
    provider = cfg.provider.lower().strip()
    if provider == "file-poll":
        return FilePollProvider(cfg.input_file, stale_after_seconds=cfg.stale_after_seconds)
    if provider == "binance-rest":
        symbol = cfg.symbol.replace("!", "").replace("_", "").lower()
        return BinanceRestOrderBookFeed(BinanceFeedConfig(symbol=symbol, depth_limit=100, timeout_seconds=4.0))
    start_price, tick_size, vol = _synthetic_profile_for_symbol(cfg.symbol)
    return SyntheticOrderBookFeed(
        SyntheticFeedConfig(
            seed=42,
            start_price=start_price,
            tick_size=tick_size,
            levels_per_side=30,
            volatility=vol,
        )
    )


def _write_snapshot(output_file: str, snapshot: OrderBookSnapshot, broker: str, provider: str, symbol: str) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = snapshot_to_record(snapshot)
    payload["source"] = provider
    payload["broker"] = broker
    payload["symbol"] = symbol
    payload["bridge_write_timestamp_utc"] = utc_now_iso()

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def parse_args() -> BridgeConfig:
    parser = argparse.ArgumentParser(description="Run Chimera L2 bridge writer")
    parser.add_argument("--symbol", default="MGC1!", help="Target symbol (MGC1!, MNQ1!, EUR_USD, ...)")
    parser.add_argument("--broker", default="tradovate", help="Broker label for metadata")
    parser.add_argument(
        "--provider",
        default="file-poll",
        choices=["file-poll", "binance-rest", "synthetic"],
        help="Input provider mode",
    )
    parser.add_argument(
        "--input-file",
        default="data/bridges/tradovate_l2.json",
        help="Broker/vendor input JSON path when provider=file-poll",
    )
    parser.add_argument(
        "--output-file",
        default="data/live_l2_snapshot.json",
        help="Output JSON snapshot consumed by Chimera app",
    )
    parser.add_argument("--poll-ms", type=int, default=300, help="Polling interval in milliseconds")
    parser.add_argument("--stale-after-seconds", type=float, default=3.0, help="Maximum age for input snapshot")
    parser.add_argument(
        "--fallback-provider",
        default="synthetic",
        choices=["synthetic", "binance-rest", "none"],
        help="Fallback mode if primary provider errors",
    )
    args = parser.parse_args()
    return BridgeConfig(
        symbol=args.symbol,
        broker=args.broker,
        provider=args.provider,
        input_file=args.input_file,
        output_file=args.output_file,
        poll_ms=max(50, int(args.poll_ms)),
        stale_after_seconds=max(0.5, float(args.stale_after_seconds)),
        fallback_provider=args.fallback_provider,
    )


def main() -> None:
    cfg = parse_args()
    logger.info(
        "Starting L2 bridge: provider={} symbol={} broker={} output={}",
        cfg.provider,
        cfg.symbol,
        cfg.broker,
        cfg.output_file,
    )
    primary = _build_provider(cfg)

    fallback = None
    if cfg.fallback_provider != "none":
        fallback_cfg = BridgeConfig(
            symbol=cfg.symbol,
            broker=cfg.broker,
            provider=cfg.fallback_provider,
            input_file=cfg.input_file,
            output_file=cfg.output_file,
            poll_ms=cfg.poll_ms,
            stale_after_seconds=cfg.stale_after_seconds,
            fallback_provider="none",
        )
        fallback = _build_provider(fallback_cfg)

    while True:
        started = time.time()
        try:
            snap = primary.next_snapshot()
            _write_snapshot(cfg.output_file, snap, broker=cfg.broker, provider=cfg.provider, symbol=cfg.symbol)
        except Exception as exc:
            if fallback is None:
                logger.warning("Bridge write failed (no fallback): {}", exc)
            else:
                try:
                    snap = fallback.next_snapshot()
                    _write_snapshot(
                        cfg.output_file,
                        snap,
                        broker=cfg.broker,
                        provider=f"{cfg.provider}->fallback:{cfg.fallback_provider}",
                        symbol=cfg.symbol,
                    )
                    logger.warning("Primary provider failed, wrote fallback snapshot: {}", exc)
                except Exception as fallback_exc:
                    logger.error("Primary+fallback failed: primary={} fallback={}", exc, fallback_exc)

        elapsed_ms = (time.time() - started) * 1000.0
        wait_ms = max(0.0, float(cfg.poll_ms) - elapsed_ms)
        time.sleep(wait_ms / 1000.0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Run Chimera L2 bridge writer with sensible defaults.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def _load_bridge_defaults(config_path: str) -> dict:
    try:
        raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            automation = raw.get("automation", {}) if isinstance(raw.get("automation", {}), dict) else {}
            bridge = automation.get("l2_bridge", {}) if isinstance(automation.get("l2_bridge", {}), dict) else {}
            return bridge
    except Exception:
        pass
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Chimera L2 bridge writer")
    parser.add_argument("--config", default="config/config.yaml", help="Config YAML path for bridge defaults")
    parser.add_argument("--symbol", default=None, help="Symbol for bridge metadata")
    parser.add_argument("--broker", default=None, help="Broker label (tradovate, ninjatrader, oanda)")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["file-poll", "binance-rest", "synthetic"],
        help="Primary bridge provider",
    )
    parser.add_argument("--input-file", default=None, help="Input JSON path for file-poll")
    parser.add_argument("--output-file", default=None, help="Output Chimera snapshot path")
    parser.add_argument("--poll-ms", type=int, default=None, help="Polling interval ms")
    parser.add_argument("--stale-after-seconds", type=float, default=None, help="Max input snapshot age")
    parser.add_argument(
        "--fallback-provider",
        default=None,
        choices=["synthetic", "binance-rest", "none"],
        help="Fallback provider if primary fails",
    )
    args = parser.parse_args()
    bridge_defaults = _load_bridge_defaults(args.config)

    symbol = args.symbol or str(bridge_defaults.get("symbol", "MGC1!"))
    broker = args.broker or str(bridge_defaults.get("broker", "tradovate"))
    provider = args.provider or str(bridge_defaults.get("provider", "file-poll"))
    input_file = args.input_file or str(bridge_defaults.get("input_file", "data/bridges/tradovate_l2.json"))
    output_file = args.output_file or str(bridge_defaults.get("output_file", "data/live_l2_snapshot.json"))
    poll_ms = args.poll_ms if args.poll_ms is not None else int(bridge_defaults.get("poll_ms", 300))
    stale_after = (
        args.stale_after_seconds if args.stale_after_seconds is not None else float(bridge_defaults.get("stale_after_seconds", 3.0))
    )
    fallback = args.fallback_provider or str(bridge_defaults.get("fallback_provider", "synthetic"))

    root = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        str(root / "scripts" / "chimera_l2_bridge.py"),
        "--symbol",
        symbol,
        "--broker",
        broker,
        "--provider",
        provider,
        "--input-file",
        input_file,
        "--output-file",
        output_file,
        "--poll-ms",
        str(poll_ms),
        "--stale-after-seconds",
        str(stale_after),
        "--fallback-provider",
        fallback,
    ]
    try:
        subprocess.run(cmd, cwd=str(root), check=True)
    except KeyboardInterrupt:
        print("\nBridge stopped.")


if __name__ == "__main__":
    main()

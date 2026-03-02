#!/usr/bin/env python3
"""
Run Chimera backtests with isolated profile configs and output folders.

This prevents trend-only and range research runs from overwriting each other.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "backtest.py"
PYTHON = ROOT / "venv" / "bin" / "python"

PROFILE_CONFIG = {
    "trend_only": ROOT / "config" / "config_trend_only.yaml",
    "range_preserved": ROOT / "config" / "config_range_preserved.yaml",
    "ict_asian_sweep": ROOT / "config" / "config_ict_asian_sweep.yaml",
    "ict_asian_sweep_inverted": ROOT / "config" / "config_ict_asian_sweep_inverted.yaml",
    "combined_trend_ict_range": ROOT / "config" / "config_combined_trend_ict_range.yaml",
    "combined_tradecount_v2": ROOT / "config" / "config_combined_tradecount_v2.yaml",
}

DATASET_PATH = {
    "mixed_6k": ROOT / "data" / "historical" / "chimera_mixed_6k.csv",
    "mixed_50k": ROOT / "data" / "historical" / "chimera_mixed_50k.csv",
    "ranging_6k": ROOT / "data" / "historical" / "chimera_ranging_6k.csv",
    "ranging_50k": ROOT / "data" / "historical" / "chimera_ranging_50k.csv",
}


def _run_one(
    config_path: Path,
    data_path: Path,
    output_path: Path,
    instrument: str,
) -> int:
    output_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(PYTHON),
        str(BACKTEST),
        "--data",
        str(data_path),
        "--config",
        str(config_path),
        "--output",
        str(output_path),
        "--instrument",
        instrument,
        "--no-train",
        "--enforce-data-quality",
        "--log-level",
        "WARNING",
    ]
    print(" ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated Chimera backtest profiles.")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_CONFIG.keys()),
        required=True,
        help="Which config profile to use.",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASET_PATH.keys()),
        required=True,
        help="Which historical dataset to run.",
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Optional suffix for output folder name.",
    )
    args = parser.parse_args()

    config_path = PROFILE_CONFIG[args.profile]
    data_path = DATASET_PATH[args.dataset]
    if not config_path.exists():
        print(f"Missing config profile: {config_path}", file=sys.stderr)
        return 2
    if not data_path.exists():
        print(f"Missing dataset: {data_path}", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    run_root = ROOT / "results" / "backtests" / args.profile / f"{args.dataset}_{stamp}{tag}"
    run_root.mkdir(parents=True, exist_ok=True)

    # Save a frozen config copy with each run for reproducibility.
    (run_root / "config_used.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    rc_mgc = _run_one(config_path, data_path, run_root / "mgc", "MGC")
    rc_mnq = _run_one(config_path, data_path, run_root / "mnq", "MNQ")

    print(f"\nProfile: {args.profile}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {run_root}")
    print(f"Return codes: MGC={rc_mgc}, MNQ={rc_mnq}")
    return 0 if (rc_mgc == 0 and rc_mnq == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

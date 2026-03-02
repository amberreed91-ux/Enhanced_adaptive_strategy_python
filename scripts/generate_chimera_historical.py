#!/usr/bin/env python3
"""
Generate stable synthetic OHLCV files for Chimera backtest/training.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _build_close_series_mixed(n: int, base_price: float) -> np.ndarray:
    prices = [base_price]
    i = 1
    regime_cycle = ["up", "range", "down", "range"]
    regime_idx = 0

    while i < n:
        block = min(int(np.random.randint(350, 900)), n - i)
        regime = regime_cycle[regime_idx % len(regime_cycle)]
        regime_idx += 1

        for _ in range(block):
            p = float(prices[-1])
            if regime == "up":
                ret = np.random.normal(0.00012, 0.00145)
            elif regime == "down":
                ret = np.random.normal(-0.00010, 0.00155)
            else:
                mean_revert = 0.06 * ((base_price / max(p, 1e-9)) - 1.0)
                ret = mean_revert + np.random.normal(0.0, 0.00115)

            ret = float(np.clip(ret, -0.03, 0.03))
            prices.append(max(50.0, p * (1.0 + ret)))
            i += 1
            if i >= n:
                break
    return np.array(prices[:n], dtype=float)


def _build_close_series_ranging(n: int, base_price: float) -> np.ndarray:
    prices = [base_price]
    for _ in range(1, n):
        p = float(prices[-1])
        mean_revert = 0.10 * (base_price - p)
        noise = np.random.normal(0.0, 10.0)
        prices.append(max(50.0, p + mean_revert + noise))
    return np.array(prices[:n], dtype=float)


def build_ohlcv(
    bars: int,
    mode: str = "mixed",
    base_price: float = 2000.0,
    start: str = "2024-01-01",
) -> pd.DataFrame:
    if mode == "mixed":
        close = _build_close_series_mixed(bars, base_price=base_price)
    elif mode == "ranging":
        close = _build_close_series_ranging(bars, base_price=base_price)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    open_ = np.empty_like(close)
    open_[0] = close[0]
    open_[1:] = close[:-1]

    hi = np.maximum(open_, close)
    lo = np.minimum(open_, close)
    wiggle = np.abs(np.random.normal(0.0, 0.0009, size=bars))
    high = hi * (1.0 + wiggle)
    low = lo * (1.0 - wiggle)

    rets = np.abs((close - open_) / np.maximum(open_, 1e-9))
    volume = (850.0 * (1.0 + rets * 45.0) * np.random.uniform(0.7, 1.35, size=bars)).astype(int)

    timestamps = pd.date_range(start=start, periods=bars, freq="5min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Chimera synthetic historical data")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--bars", type=int, default=6000, help="Number of 5m bars")
    parser.add_argument("--mode", choices=["mixed", "ranging"], default="mixed")
    parser.add_argument("--base-price", type=float, default=2000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", default="2024-01-01", help="Start timestamp (YYYY-MM-DD)")
    args = parser.parse_args()

    np.random.seed(int(args.seed))
    df = build_ohlcv(
        bars=int(args.bars),
        mode=str(args.mode),
        base_price=float(args.base_price),
        start=str(args.start),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    close_ratio = float(df["close"].iloc[-1] / max(df["close"].iloc[0], 1e-9))
    max_abs_bar = float(df["close"].pct_change().abs().max() * 100.0)
    print(f"Wrote {len(df)} rows to {output_path}")
    print(
        "Stats: "
        f"close_ratio={close_ratio:.3f}, return_pct={(close_ratio - 1.0) * 100.0:.2f}%, "
        f"max_abs_bar_return={max_abs_bar:.2f}%"
    )


if __name__ == "__main__":
    main()


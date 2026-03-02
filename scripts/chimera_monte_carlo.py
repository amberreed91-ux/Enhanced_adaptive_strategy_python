#!/usr/bin/env python3
"""
Monte Carlo robustness analysis for Chimera trade results.

Usage:
  python scripts/chimera_monte_carlo.py --trades results/run_fix_mgc/trades.csv --paths 5000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Monte Carlo analysis on trade outcomes")
    p.add_argument("--trades", required=True, help="Path to trades.csv")
    p.add_argument("--paths", type=int, default=5000, help="Number of Monte Carlo paths")
    p.add_argument("--initial-equity", type=float, default=100000.0, help="Initial equity for simulation")
    p.add_argument("--slippage-perturb", type=float, default=0.0, help="Extra random perturbation pct (0.10 = +/-10 pct)")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    p.add_argument("--max-dd-limit", type=float, default=4.0, help="Target max drawdown %% for pass/fail")
    p.add_argument("--pf-limit", type=float, default=1.3, help="Target profit factor for pass/fail")
    p.add_argument("--winrate-limit", type=float, default=45.0, help="Target win rate %% for pass/fail")
    p.add_argument("--avg-trade-limit", type=float, default=25.0, help="Target avg trade $ for pass/fail")
    return p.parse_args()


def detect_pnl_column(df: pd.DataFrame) -> str:
    candidates = ["net_pnl", "realized_pnl", "pnl", "trade_pnl", "profit", "net"]
    lower_map = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in lower_map:
            return lower_map[c]
    # fallback: first numeric column with positive + negative values
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for c in numeric_cols:
        s = df[c].dropna()
        if len(s) > 0 and (s > 0).any() and (s < 0).any():
            return c
    raise ValueError("Could not detect PnL column. Please include a numeric trade PnL column.")


def max_drawdown_pct(equity_curve: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - running_max) / np.maximum(running_max, 1e-9)
    return float(abs(dd.min()) * 100.0)


def longest_losing_streak(returns: np.ndarray) -> int:
    longest = 0
    cur = 0
    for r in returns:
        if r < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return int(longest)


def run_mc(
    trade_pnl: np.ndarray,
    paths: int,
    initial_equity: float,
    perturb: float,
    seed: int,
) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(trade_pnl)
    final_equity = np.zeros(paths)
    max_dd = np.zeros(paths)
    win_rate = np.zeros(paths)
    avg_trade = np.zeros(paths)
    profit_factor = np.zeros(paths)
    lose_streak = np.zeros(paths)

    for i in range(paths):
        sample = rng.permutation(trade_pnl)
        if perturb > 0:
            noise = rng.uniform(-perturb, perturb, size=n)
            sample = sample * (1.0 + noise)

        equity = initial_equity + np.cumsum(sample)
        full_curve = np.concatenate([[initial_equity], equity])
        final_equity[i] = float(full_curve[-1])
        max_dd[i] = max_drawdown_pct(full_curve)
        win_rate[i] = float((sample > 0).mean() * 100.0)
        avg_trade[i] = float(sample.mean())

        gross_profit = float(sample[sample > 0].sum())
        gross_loss = float(abs(sample[sample < 0].sum()))
        profit_factor[i] = gross_profit / gross_loss if gross_loss > 0 else np.inf
        lose_streak[i] = longest_losing_streak(sample)

    return {
        "final_equity": final_equity,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "avg_trade": avg_trade,
        "profit_factor": profit_factor,
        "lose_streak": lose_streak,
    }


def summarize(arr: np.ndarray) -> Dict[str, float]:
    return {
        "p05": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "mean": float(np.mean(arr)),
    }


def main() -> None:
    args = parse_args()
    trades_path = Path(args.trades)
    if not trades_path.exists():
        raise FileNotFoundError(f"Trades file not found: {trades_path}")

    df = pd.read_csv(trades_path)
    if df.empty:
        raise ValueError("Trades file is empty.")

    pnl_col = detect_pnl_column(df)
    trade_pnl = pd.to_numeric(df[pnl_col], errors="coerce").dropna().to_numpy(dtype=float)
    if len(trade_pnl) < 5:
        raise ValueError("Need at least 5 trades for meaningful Monte Carlo.")

    mc = run_mc(
        trade_pnl=trade_pnl,
        paths=args.paths,
        initial_equity=args.initial_equity,
        perturb=args.slippage_perturb,
        seed=args.seed,
    )

    metrics = {
        "final_equity": summarize(mc["final_equity"]),
        "max_dd_pct": summarize(mc["max_dd"]),
        "win_rate_pct": summarize(mc["win_rate"]),
        "avg_trade_usd": summarize(mc["avg_trade"]),
        "profit_factor": summarize(mc["profit_factor"]),
        "losing_streak": summarize(mc["lose_streak"]),
    }

    # pass/fail scorecard (conservative: 25th percentile and median drawdown)
    pass_pf = metrics["profit_factor"]["p25"] >= args.pf_limit
    pass_dd = metrics["max_dd_pct"]["p50"] <= args.max_dd_limit
    pass_wr = metrics["win_rate_pct"]["p25"] >= args.winrate_limit
    pass_avg = metrics["avg_trade_usd"]["p25"] >= args.avg_trade_limit

    scorecard = {
        "pass_profit_factor": pass_pf,
        "pass_max_drawdown": pass_dd,
        "pass_win_rate": pass_wr,
        "pass_avg_trade": pass_avg,
        "overall_pass": bool(pass_pf and pass_dd and pass_wr and pass_avg),
    }

    out_dir = Path("results") / "monte_carlo"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = trades_path.parent.name

    summary_path = out_dir / f"{stem}_mc_summary.json"
    pd.Series(
        {
            "paths": args.paths,
            "initial_equity": args.initial_equity,
            "pnl_column": pnl_col,
            "trade_count": int(len(trade_pnl)),
            "slippage_perturb": args.slippage_perturb,
        }
    ).to_json(out_dir / f"{stem}_mc_meta.json", indent=2)

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "scorecard": scorecard}, f, indent=2)

    rows = []
    for name, stats in metrics.items():
        row = {"metric": name}
        row.update(stats)
        rows.append(row)
    df_out = pd.DataFrame(rows)
    csv_path = out_dir / f"{stem}_mc_summary.csv"
    df_out.to_csv(csv_path, index=False)

    print(f"Trades file: {trades_path}")
    print(f"Detected PnL column: {pnl_col}")
    print(f"Trade count: {len(trade_pnl)} | Paths: {args.paths}")
    print(f"Scorecard: {scorecard}")
    print(f"Summary JSON: {summary_path}")
    print(f"Summary CSV:  {csv_path}")


if __name__ == "__main__":
    main()

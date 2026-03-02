#!/usr/bin/env python3
"""
Trade-count-focused optimizer for Chimera combined trend + ICT range profile.

Workflow:
1) Run a coarse sweep on a smaller dataset.
2) Validate top candidates on the full 50k dataset.
3) Rank by "more trades first" with minimum quality constraints.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "backtest.py"
PYTHON = ROOT / "venv" / "bin" / "python"
DEFAULT_CONFIG = ROOT / "config" / "config_combined_trend_ict_range.yaml"
DEFAULT_DATA_COARSE = ROOT / "data" / "historical" / "chimera_mixed_6k.csv"
DEFAULT_DATA_FULL = ROOT / "data" / "historical" / "chimera_mixed_50k.csv"


@dataclass
class Gates:
    min_trades: float
    min_win_rate: float
    min_pf: float
    min_return_pct: float
    max_drawdown_abs_pct: float


@dataclass
class RunMetrics:
    trades: float
    win_rate: float
    pf: float
    ret_pct: float
    net_pnl: float
    max_drawdown_pct: float
    ranging_trades: float
    trending_trades: float


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config root: {path}")
    return data


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def _set_nested(cfg: Dict[str, Any], key: str, value: Any) -> None:
    cur = cfg
    parts = key.split(".")
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _candidate_grid(max_candidates: int) -> Iterable[Dict[str, Any]]:
    # Kept intentionally small/structured to avoid combinatorial explosion.
    long_mins = [72, 68, 64]
    short_mgc = [68, 64, 60]
    short_mnq = [72, 68, 64]
    bias_mins = [86, 82, 78]
    range_long_mins = [58, 54, 50]
    range_short_mins = [58, 54, 50]
    mtf_align = [3, 2]
    min_rvol = [1.20, 1.10, 1.00]
    min_abs_imb = [0.10, 0.08, 0.06]
    min_dir_imb = [0.06, 0.05, 0.04]
    min_eff = [0.55, 0.50, 0.45]
    min_atr_pct = [0.00045, 0.00035]
    range_max_eff = [0.60, 0.65, 0.70]
    req_kz = [True, False]
    req_disp = [True, False]
    min_disp = [0.10, 0.06, 0.03]
    ict_min_dir = [0.02, 0.015, 0.01]

    seen: set[str] = set()
    count = 0
    for vals in itertools.product(
        long_mins,
        short_mgc,
        short_mnq,
        bias_mins,
        range_long_mins,
        range_short_mins,
        mtf_align,
        min_rvol,
        min_abs_imb,
        min_dir_imb,
        min_eff,
        min_atr_pct,
        range_max_eff,
        req_kz,
        req_disp,
        min_disp,
        ict_min_dir,
    ):
        (
            long_min,
            short_mgc_min,
            short_mnq_min,
            bias_min,
            rlong,
            rshort,
            mtf_th,
            rvol,
            abs_imb,
            dir_imb,
            mineff,
            atrp,
            rmaxeff,
            require_kz,
            require_disp,
            min_disp_atr,
            ict_min_dir_imb,
        ) = vals

        # Keep displacement threshold meaningful only when enabled.
        if not require_disp and min_disp_atr != 0.10:
            continue
        # If kill-zone is disabled, keep stricter directionality to limit noise.
        if (not require_kz) and ict_min_dir_imb < 0.015:
            continue

        params = {
            "regime_split.range_mode": "ICT_ASIAN_SWEEP",
            "thresholds.long_entry_min": long_min,
            "thresholds.short_entry_min_mgc": short_mgc_min,
            "thresholds.short_entry_min_mnq": short_mnq_min,
            "thresholds.bias_only_min": bias_min,
            "thresholds.range_long_entry_min": rlong,
            "thresholds.range_short_entry_min": rshort,
            "mtf.alignment_threshold": mtf_th,
            "entry_quality.min_rvol": rvol,
            "entry_quality.min_abs_imbalance": abs_imb,
            "entry_quality.min_directional_imbalance": dir_imb,
            "general.min_efficiency_ratio": mineff,
            "general.min_atr_pct": atrp,
            "regime_split.range_max_efficiency_ratio": rmaxeff,
            "ict_asian_sweep.require_kill_zone": require_kz,
            "ict_asian_sweep.require_displacement_candle": require_disp,
            "ict_asian_sweep.min_displacement_atr": min_disp_atr,
            "ict_asian_sweep.min_directional_imbalance_mgc": ict_min_dir_imb,
            "ict_asian_sweep.min_directional_imbalance_mnq": ict_min_dir_imb,
        }
        sig = json.dumps(params, sort_keys=True)
        if sig in seen:
            continue
        seen.add(sig)
        yield params
        count += 1
        if count >= max_candidates:
            break


def _run_backtest(cfg_path: Path, data_path: Path, out_dir: Path, instrument: str) -> int:
    cmd = [
        str(PYTHON),
        str(BACKTEST),
        "--data",
        str(data_path),
        "--config",
        str(cfg_path),
        "--output",
        str(out_dir),
        "--instrument",
        instrument,
        "--no-train",
        "--enforce-data-quality",
        "--log-level",
        "WARNING",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    return int(proc.returncode)


def _compute_max_drawdown_pct(equities: List[float]) -> float:
    if not equities:
        return 0.0
    peak = equities[0]
    worst = 0.0
    for e in equities:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak * 100.0
            if dd < worst:
                worst = dd
    return float(worst)


def _metrics(run_dir: Path) -> RunMetrics:
    trades_path = run_dir / "trades.csv"
    equity_path = run_dir / "equity_curve.csv"
    if not trades_path.exists() or not equity_path.exists():
        return RunMetrics(0, 0, 0, 0, 0, 0, 0, 0)

    pnls: List[float] = []
    ranging = 0.0
    trending = 0.0
    with trades_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        pnl_key = "realized_pnl" if "realized_pnl" in (reader.fieldnames or []) else "pnl"
        for row in reader:
            try:
                pnls.append(float(row.get(pnl_key, "0") or 0.0))
            except ValueError:
                pnls.append(0.0)
            regime = str(row.get("entry_regime", "")).upper()
            if regime == "RANGING":
                ranging += 1.0
            elif regime == "TRENDING":
                trending += 1.0

    equities: List[float] = []
    with equity_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                equities.append(float(row.get("equity", "0") or 0.0))
            except ValueError:
                continue

    trades = float(len(pnls))
    wins = sum(1 for p in pnls if p > 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    if not math.isfinite(pf):
        pf = 999.0

    ret_pct = 0.0
    if len(equities) >= 2 and equities[0] != 0:
        ret_pct = ((equities[-1] - equities[0]) / equities[0]) * 100.0
    return RunMetrics(
        trades=trades,
        win_rate=float((wins / trades * 100.0) if trades else 0.0),
        pf=float(pf),
        ret_pct=float(ret_pct),
        net_pnl=float(sum(pnls)),
        max_drawdown_pct=float(_compute_max_drawdown_pct(equities)),
        ranging_trades=ranging,
        trending_trades=trending,
    )


def _passes_pair(mgc: RunMetrics, mnq: RunMetrics, g: Gates) -> bool:
    both = [mgc, mnq]
    return all(
        (
            m.trades >= g.min_trades
            and m.win_rate >= g.min_win_rate
            and m.pf >= g.min_pf
            and m.ret_pct >= g.min_return_pct
            and abs(m.max_drawdown_pct) <= g.max_drawdown_abs_pct
            and m.net_pnl > 0.0
        )
        for m in both
    )


def _score(mgc: RunMetrics, mnq: RunMetrics) -> Tuple[float, float, float, float]:
    min_trades = min(mgc.trades, mnq.trades)
    min_pf = min(mgc.pf, mnq.pf)
    min_wr = min(mgc.win_rate, mnq.win_rate)
    min_ret = min(mgc.ret_pct, mnq.ret_pct)
    return (min_trades, min_pf, min_wr, min_ret)


def main() -> None:
    ap = argparse.ArgumentParser(description="Optimize combined trend+ICT profile for higher trade count.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--coarse-data", default=str(DEFAULT_DATA_COARSE))
    ap.add_argument("--full-data", default=str(DEFAULT_DATA_FULL))
    ap.add_argument("--output-dir", default=str(ROOT / "results" / "optimizer" / "combined_trade_count_latest"))
    ap.add_argument("--max-candidates", type=int, default=24)
    ap.add_argument("--topk-full", type=int, default=5)
    ap.add_argument("--coarse-min-trades", type=float, default=14.0)
    ap.add_argument("--coarse-min-win-rate", type=float, default=45.0)
    ap.add_argument("--coarse-min-pf", type=float, default=1.05)
    ap.add_argument("--coarse-min-return-pct", type=float, default=0.0)
    ap.add_argument("--coarse-max-dd-abs-pct", type=float, default=10.0)
    ap.add_argument("--full-min-trades", type=float, default=90.0)
    ap.add_argument("--full-min-win-rate", type=float, default=50.0)
    ap.add_argument("--full-min-pf", type=float, default=1.35)
    ap.add_argument("--full-min-return-pct", type=float, default=0.0)
    ap.add_argument("--full-max-dd-abs-pct", type=float, default=6.0)
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = _read_yaml(Path(args.config))
    coarse_gates = Gates(
        min_trades=float(args.coarse_min_trades),
        min_win_rate=float(args.coarse_min_win_rate),
        min_pf=float(args.coarse_min_pf),
        min_return_pct=float(args.coarse_min_return_pct),
        max_drawdown_abs_pct=float(args.coarse_max_dd_abs_pct),
    )
    full_gates = Gates(
        min_trades=float(args.full_min_trades),
        min_win_rate=float(args.full_min_win_rate),
        min_pf=float(args.full_min_pf),
        min_return_pct=float(args.full_min_return_pct),
        max_drawdown_abs_pct=float(args.full_max_dd_abs_pct),
    )

    coarse_rows: List[Dict[str, Any]] = []
    for idx, params in enumerate(_candidate_grid(int(args.max_candidates)), start=1):
        cfg = dict(base_cfg)
        for k, v in params.items():
            _set_nested(cfg, k, v)
        with tempfile.TemporaryDirectory(prefix="chimera_combined_opt_") as td:
            td_path = Path(td)
            cfg_path = td_path / "cfg.yaml"
            _write_yaml(cfg_path, cfg)
            out_mgc = td_path / "mgc"
            out_mnq = td_path / "mnq"
            out_mgc.mkdir(parents=True, exist_ok=True)
            out_mnq.mkdir(parents=True, exist_ok=True)
            rc_mgc = _run_backtest(cfg_path, Path(args.coarse_data), out_mgc, "MGC")
            rc_mnq = _run_backtest(cfg_path, Path(args.coarse_data), out_mnq, "MNQ")
            m_mgc = _metrics(out_mgc)
            m_mnq = _metrics(out_mnq)

        pass_pair = rc_mgc == 0 and rc_mnq == 0 and _passes_pair(m_mgc, m_mnq, coarse_gates)
        row = {
            "candidate": idx,
            "stage": "coarse",
            "pass_pair": pass_pair,
            "score": _score(m_mgc, m_mnq),
            "mgc": m_mgc.__dict__,
            "mnq": m_mnq.__dict__,
            "params": params,
            "rc_mgc": rc_mgc,
            "rc_mnq": rc_mnq,
        }
        coarse_rows.append(row)
        print(
            f"[coarse {idx:02d}] pass={pass_pair} "
            f"MGC(tr={m_mgc.trades:.0f},wr={m_mgc.win_rate:.1f},pf={m_mgc.pf:.2f}) "
            f"MNQ(tr={m_mnq.trades:.0f},wr={m_mnq.win_rate:.1f},pf={m_mnq.pf:.2f})"
        )

    coarse_sorted = sorted(coarse_rows, key=lambda r: (r["pass_pair"], r["score"]), reverse=True)
    coarse_selected = [r for r in coarse_sorted if r["pass_pair"]][: int(args.topk_full)]
    if not coarse_selected:
        coarse_selected = coarse_sorted[: int(args.topk_full)]

    full_rows: List[Dict[str, Any]] = []
    for rank, row in enumerate(coarse_selected, start=1):
        params = row["params"]
        cfg = dict(base_cfg)
        for k, v in params.items():
            _set_nested(cfg, k, v)
        run_dir = out_dir / f"full_candidate_{rank:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = run_dir / "config_used.yaml"
        _write_yaml(cfg_path, cfg)

        out_mgc = run_dir / "mgc"
        out_mnq = run_dir / "mnq"
        out_mgc.mkdir(parents=True, exist_ok=True)
        out_mnq.mkdir(parents=True, exist_ok=True)
        rc_mgc = _run_backtest(cfg_path, Path(args.full_data), out_mgc, "MGC")
        rc_mnq = _run_backtest(cfg_path, Path(args.full_data), out_mnq, "MNQ")
        m_mgc = _metrics(out_mgc)
        m_mnq = _metrics(out_mnq)
        pass_pair = rc_mgc == 0 and rc_mnq == 0 and _passes_pair(m_mgc, m_mnq, full_gates)
        full_row = {
            "candidate": row["candidate"],
            "rank": rank,
            "stage": "full",
            "pass_pair": pass_pair,
            "score": _score(m_mgc, m_mnq),
            "mgc": m_mgc.__dict__,
            "mnq": m_mnq.__dict__,
            "params": params,
            "rc_mgc": rc_mgc,
            "rc_mnq": rc_mnq,
            "run_dir": str(run_dir),
        }
        full_rows.append(full_row)
        print(
            f"[full {rank:02d}] pass={pass_pair} "
            f"MGC(tr={m_mgc.trades:.0f},wr={m_mgc.win_rate:.1f},pf={m_mgc.pf:.2f},dd={m_mgc.max_drawdown_pct:.2f}%) "
            f"MNQ(tr={m_mnq.trades:.0f},wr={m_mnq.win_rate:.1f},pf={m_mnq.pf:.2f},dd={m_mnq.max_drawdown_pct:.2f}%)"
        )

    best_full = sorted(full_rows, key=lambda r: (r["pass_pair"], r["score"]), reverse=True)
    summary = {
        "config": str(Path(args.config)),
        "coarse_data": str(Path(args.coarse_data)),
        "full_data": str(Path(args.full_data)),
        "coarse_gates": coarse_gates.__dict__,
        "full_gates": full_gates.__dict__,
        "coarse_candidates": len(coarse_rows),
        "coarse_selected": len(coarse_selected),
        "best_full": best_full[0] if best_full else None,
        "full_results": best_full,
    }

    (out_dir / "coarse_results.json").write_text(json.dumps(coarse_rows, indent=2), encoding="utf-8")
    (out_dir / "full_results.json").write_text(json.dumps(full_rows, indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Target-driven parameter sweep for Chimera strategy.

Goal: find parameter sets that pass win-rate/profit/longevity gates on BOTH MGC and MNQ.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "backtest.py"
CONFIG = ROOT / "config" / "config.yaml"
PYTHON = ROOT / "venv" / "bin" / "python"


@dataclass
class Targets:
    min_win_rate: float
    min_profit_factor: float
    min_return_pct: float
    min_trades: int


def _set_nested(cfg: Dict[str, Any], path: str, value: Any) -> None:
    cur = cfg
    keys = path.split(".")
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid YAML root at {path}")
    return loaded


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def _metrics_from_output(run_dir: Path) -> Dict[str, float]:
    trades_path = run_dir / "trades.csv"
    equity_path = run_dir / "equity_curve.csv"
    if not trades_path.exists() or not equity_path.exists():
        return {
            "trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
        }

    pnls: List[float] = []
    with trades_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        pnl_key = "realized_pnl" if "realized_pnl" in (reader.fieldnames or []) else "pnl"
        for row in reader:
            try:
                pnls.append(float(row.get(pnl_key, "0") or 0.0))
            except ValueError:
                pnls.append(0.0)

    equities: List[float] = []
    with equity_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                equities.append(float(row.get("equity", "0") or 0.0))
            except ValueError:
                continue

    if not equities:
        return {
            "trades": float(len(pnls)),
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_pnl": float(sum(pnls)),
            "return_pct": 0.0,
        }

    wins = sum(1 for p in pnls if p > 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)

    start_eq = equities[0]
    end_eq = equities[-1]
    ret = ((end_eq - start_eq) / start_eq * 100.0) if start_eq != 0 else 0.0
    return {
        "trades": float(len(pnls)),
        "win_rate": float((wins / len(pnls) * 100.0) if pnls else 0.0),
        "profit_factor": float(profit_factor if math.isfinite(profit_factor) else 999.0),
        "net_pnl": float(sum(pnls)),
        "return_pct": float(ret),
    }


def _passes(m: Dict[str, float], t: Targets) -> bool:
    return (
        m["trades"] >= t.min_trades
        and m["win_rate"] >= t.min_win_rate
        and m["profit_factor"] >= t.min_profit_factor
        and m["return_pct"] >= t.min_return_pct
        and m["net_pnl"] > 0.0
    )


def _run_backtest(
    config_path: Path,
    data_path: Path,
    output_dir: Path,
    instrument: str,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(PYTHON),
        str(BACKTEST),
        "--data",
        str(data_path),
        "--config",
        str(config_path),
        "--output",
        str(output_dir),
        "--instrument",
        instrument,
        "--no-train",
        "--enforce-data-quality",
        "--log-level",
        "WARNING",
    ]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)


def _candidate_grid() -> Iterable[Dict[str, Any]]:
    base = {
        "thresholds.long_entry_min": 72,
        "thresholds.short_entry_min_mgc": 68,
        "thresholds.short_entry_min_mnq": 72,
        "thresholds.bias_only_min": 86,
        "thresholds.range_long_entry_min": 64,
        "thresholds.range_short_entry_min": 64,
        "regime_split.range_mode": "MEAN_REVERT",
        "session.trade_sessions": "NY",
        "general.min_efficiency_ratio": 0.48,
        "general.trend_fast_ema": 21,
        "general.trend_slow_ema": 55,
        "general.trend_macro_ema": 200,
        "general.min_atr_pct": 0.00030,
        "entry_quality.min_rvol": 1.05,
        "entry_quality.min_abs_imbalance": 0.06,
        "entry_quality.min_directional_imbalance": 0.03,
        "trend_quality.ema_spread_min_pct": 0.00025,
        "trend_quality.ema_slope_min_pct": 0.00008,
        "trend_quality.structure_persistence_bars": 2,
        "stop_loss.range_mean_revert_mult": 1.0,
        "take_profit.range_mean_revert_t1_mult": 0.7,
        "capital.max_risk_per_trade_usd": 200.0,
        "capital.max_notional_pct": 0.08,
    }

    curated_first = [
        {
            "regime_split.range_mode": "NO_TRADE",
            "session.trade_sessions": "NY",
            "thresholds.long_entry_min": 80,
            "thresholds.short_entry_min_mgc": 76,
            "thresholds.short_entry_min_mnq": 80,
            "thresholds.bias_only_min": 92,
            "entry_quality.min_rvol": 1.35,
            "entry_quality.min_abs_imbalance": 0.14,
            "entry_quality.min_directional_imbalance": 0.10,
            "trend_quality.ema_spread_min_pct": 0.00055,
            "trend_quality.ema_slope_min_pct": 0.00020,
            "trend_quality.structure_persistence_bars": 4,
        },
        {
            "regime_split.range_mode": "NO_TRADE",
            "session.trade_sessions": "NY",
            "thresholds.long_entry_min": 76,
            "thresholds.short_entry_min_mgc": 72,
            "thresholds.short_entry_min_mnq": 76,
            "thresholds.bias_only_min": 90,
            "entry_quality.min_rvol": 1.20,
            "entry_quality.min_abs_imbalance": 0.10,
            "entry_quality.min_directional_imbalance": 0.06,
            "trend_quality.ema_spread_min_pct": 0.00040,
            "trend_quality.ema_slope_min_pct": 0.00014,
            "trend_quality.structure_persistence_bars": 3,
        },
        {
            "regime_split.range_mode": "MEAN_REVERT",
            "session.trade_sessions": "NY",
            "thresholds.range_long_entry_min": 80,
            "thresholds.range_short_entry_min": 80,
            "entry_quality.min_rvol": 1.20,
            "entry_quality.min_abs_imbalance": 0.10,
            "entry_quality.min_directional_imbalance": 0.06,
            "stop_loss.range_mean_revert_mult": 0.8,
            "take_profit.range_mean_revert_t1_mult": 0.9,
        },
        {
            "regime_split.range_mode": "MEAN_REVERT",
            "session.trade_sessions": "Both",
            "thresholds.long_entry_min": 76,
            "thresholds.short_entry_min_mgc": 72,
            "thresholds.short_entry_min_mnq": 76,
            "thresholds.bias_only_min": 90,
            "thresholds.range_long_entry_min": 72,
            "thresholds.range_short_entry_min": 72,
            "entry_quality.min_rvol": 1.20,
            "entry_quality.min_abs_imbalance": 0.10,
            "entry_quality.min_directional_imbalance": 0.06,
            "trend_quality.structure_persistence_bars": 3,
        },
        {
            "regime_split.range_mode": "NO_TRADE",
            "session.trade_sessions": "Both",
            "thresholds.long_entry_min": 72,
            "thresholds.short_entry_min_mgc": 68,
            "thresholds.short_entry_min_mnq": 72,
            "thresholds.bias_only_min": 86,
            "general.min_efficiency_ratio": 0.55,
            "general.min_atr_pct": 0.00045,
            "entry_quality.min_rvol": 1.20,
            "entry_quality.min_abs_imbalance": 0.10,
            "entry_quality.min_directional_imbalance": 0.06,
        },
    ]

    seen: set[str] = set()

    def _emit(overrides: Dict[str, Any]) -> Dict[str, Any] | None:
        candidate = dict(base)
        candidate.update(overrides)
        sig = json.dumps(candidate, sort_keys=True)
        if sig in seen:
            return None
        seen.add(sig)
        return candidate

    for overrides in curated_first:
        candidate = _emit(overrides)
        if candidate is not None:
            yield candidate

    long_min = [72, 76, 80]
    short_mgc = [68, 72, 76]
    short_mnq = [72, 76, 80]
    bias_min = [86, 90, 94]
    range_mode = ["NO_TRADE", "MEAN_REVERT"]
    range_long_min = [64, 72, 80]
    range_short_min = [64, 72, 80]
    trade_sessions = ["NY", "Both"]
    min_eff = [0.48, 0.55, 0.62]
    min_atr_pct = [0.00030, 0.00045, 0.00060]
    min_rvol = [1.05, 1.20, 1.35]
    min_abs_imbalance = [0.06, 0.10, 0.14]
    min_dir_imbalance = [0.03, 0.06, 0.10]
    trend_spread_min_pct = [0.00025, 0.00040, 0.00055]
    trend_slope_min_pct = [0.00008, 0.00014, 0.00020]
    trend_struct_persist = [2, 3, 4]
    range_stop_mult = [0.8, 1.0, 1.2]
    range_tp1_mult = [0.7, 0.9, 1.1]
    max_risk_abs = [200.0, 250.0]
    max_notional = [0.08, 0.10]

    # NOTE: rightmost iterables change fastest in itertools.product.
    # Keep threshold/regime dimensions on the right so low max-combo runs still explore behavior shifts.
    for vals in itertools.product(
        max_risk_abs,
        max_notional,
        min_eff,
        min_atr_pct,
        min_rvol,
        min_abs_imbalance,
        min_dir_imbalance,
        trend_spread_min_pct,
        trend_slope_min_pct,
        trend_struct_persist,
        range_stop_mult,
        range_tp1_mult,
        trade_sessions,
        range_mode,
        range_long_min,
        range_short_min,
        bias_min,
        short_mnq,
        short_mgc,
        long_min,
    ):
        (
            risk_abs,
            max_notional_pct,
            mineff,
            atrp,
            mrvol,
            min_abs_imb,
            min_dir_imb,
            tq_spread,
            tq_slope,
            tq_persist,
            r_stop,
            r_tp1,
            tsession,
            rmode,
            rlong,
            rshort,
            bmin,
            smnq,
            smgc,
            lmin,
        ) = vals
        candidate = _emit(
            {
                "thresholds.long_entry_min": lmin,
                "thresholds.short_entry_min_mgc": smgc,
                "thresholds.short_entry_min_mnq": smnq,
                "thresholds.bias_only_min": bmin,
                "thresholds.range_long_entry_min": rlong,
                "thresholds.range_short_entry_min": rshort,
                "regime_split.range_mode": rmode,
                "session.trade_sessions": tsession,
                "general.min_efficiency_ratio": mineff,
                "general.min_atr_pct": atrp,
                "entry_quality.min_rvol": mrvol,
                "entry_quality.min_abs_imbalance": min_abs_imb,
                "entry_quality.min_directional_imbalance": min_dir_imb,
                "trend_quality.ema_spread_min_pct": tq_spread,
                "trend_quality.ema_slope_min_pct": tq_slope,
                "trend_quality.structure_persistence_bars": tq_persist,
                "stop_loss.range_mean_revert_mult": r_stop,
                "take_profit.range_mean_revert_t1_mult": r_tp1,
                "capital.max_risk_per_trade_usd": risk_abs,
                "capital.max_notional_pct": max_notional_pct,
            }
        )
        if candidate is not None:
            yield candidate


def _pine_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        s = f"{value:.6f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(value)


def _pine_override_snippet(best_params: Dict[str, Any]) -> str:
    mapping = {
        "thresholds.long_entry_min": "long_entry_min_in",
        "thresholds.short_entry_min_mgc": "short_entry_min_mgc_in",
        "thresholds.short_entry_min_mnq": "short_entry_min_mnq_in",
        "thresholds.bias_only_min": "bias_only_min_in",
        "thresholds.range_long_entry_min": "range_long_entry_min_in",
        "thresholds.range_short_entry_min": "range_short_entry_min_in",
        "general.trend_fast_ema": "trend_fast_ema_in",
        "general.trend_slow_ema": "trend_slow_ema_in",
        "general.trend_macro_ema": "trend_macro_ema_in",
        "general.min_efficiency_ratio": "min_efficiency_ratio_in",
        "general.min_atr_pct": "min_atr_pct_in",
        "entry_quality.min_rvol": "min_rvol_in",
        "entry_quality.min_abs_imbalance": "min_abs_imbalance_in",
        "entry_quality.min_directional_imbalance": "min_directional_imbalance_in",
    }
    lines = ["// Pine overrides from Chimera target optimizer:"]
    for cfg_key, pine_key in mapping.items():
        if cfg_key not in best_params:
            continue
        lines.append(f"{pine_key} = input.float({_pine_value(best_params[cfg_key])}, \"{pine_key}\")")
    return "\n".join(lines) + "\n"


def _replace_pine_input_default(text: str, var_name: str, value: Any) -> str:
    pattern = rf"({re.escape(var_name)}\s*=\s*input\.(?:int|float)\()([^,]+)(,)"
    repl = rf"\1{_pine_value(value)}\3"
    return re.sub(pattern, repl, text, count=1)


def _apply_best_to_pine_and_config(
    best_params: Dict[str, Any],
    config_path: Path,
    pine_files: List[Path],
    backup_dir: Path,
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Update config.
    cfg = _read_yaml(config_path)
    for k, v in best_params.items():
        _set_nested(cfg, k, v)
    config_backup = backup_dir / f"{config_path.name}.bak"
    config_backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    _write_yaml(config_path, cfg)

    # Update Pine defaults.
    pine_map = {
        "thresholds.long_entry_min": "long_entry_min_in",
        "thresholds.short_entry_min_mgc": "short_entry_min_mgc_in",
        "thresholds.short_entry_min_mnq": "short_entry_min_mnq_in",
        "thresholds.bias_only_min": "bias_only_min_in",
        "thresholds.range_long_entry_min": "range_long_entry_min_in",
        "thresholds.range_short_entry_min": "range_short_entry_min_in",
        "general.trend_fast_ema": "trend_fast_ema_in",
        "general.trend_slow_ema": "trend_slow_ema_in",
        "general.trend_macro_ema": "trend_macro_ema_in",
        "general.min_efficiency_ratio": "min_efficiency_ratio_in",
        "general.min_atr_pct": "min_atr_pct_in",
        "entry_quality.min_rvol": "min_rvol_in",
        "entry_quality.min_abs_imbalance": "min_abs_imbalance_in",
        "entry_quality.min_directional_imbalance": "min_directional_imbalance_in",
    }

    for pine_path in pine_files:
        original = pine_path.read_text(encoding="utf-8")
        updated = original
        for cfg_key, pine_var in pine_map.items():
            if cfg_key in best_params:
                updated = _replace_pine_input_default(updated, pine_var, best_params[cfg_key])
        backup = backup_dir / f"{pine_path.name}.bak"
        backup.write_text(original, encoding="utf-8")
        pine_path.write_text(updated, encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Chimera target optimizer for MNQ/MGC")
    p.add_argument("--config", default=str(CONFIG))
    p.add_argument("--data-mgc", default=str(ROOT / "data" / "historical" / "chimera_mixed_6k.csv"))
    p.add_argument("--data-mnq", default=str(ROOT / "data" / "historical" / "chimera_mixed_6k.csv"))
    p.add_argument("--output-dir", default=str(ROOT / "results" / "optimizer" / "latest"))
    p.add_argument("--max-combos", type=int, default=12, help="Stop after this many parameter combos")
    p.add_argument("--min-win-rate", type=float, default=62.5)
    p.add_argument("--min-profit-factor", type=float, default=1.2)
    p.add_argument("--min-return-pct", type=float, default=0.0)
    p.add_argument("--min-trades", type=int, default=25)
    p.add_argument(
        "--apply-best-when-pass",
        action="store_true",
        help="If at least one combo passes both symbols, apply best params to config + Pine defaults.",
    )
    args = p.parse_args()

    targets = Targets(
        min_win_rate=float(args.min_win_rate),
        min_profit_factor=float(args.min_profit_factor),
        min_return_pct=float(args.min_return_pct),
        min_trades=int(args.min_trades),
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = _read_yaml(Path(args.config))
    rows: List[Dict[str, Any]] = []
    best_row: Dict[str, Any] | None = None

    for combo_idx, params in enumerate(_candidate_grid(), start=1):
        if combo_idx > int(args.max_combos):
            break

        cfg = dict(base_cfg)
        for k, v in params.items():
            _set_nested(cfg, k, v)

        with tempfile.TemporaryDirectory(prefix="chimera_opt_") as td:
            td_path = Path(td)
            tmp_cfg = td_path / "config.yaml"
            _write_yaml(tmp_cfg, cfg)

            out_mgc = td_path / "run_mgc"
            out_mnq = td_path / "run_mnq"
            out_mgc.mkdir(parents=True, exist_ok=True)
            out_mnq.mkdir(parents=True, exist_ok=True)

            proc_mgc = _run_backtest(tmp_cfg, Path(args.data_mgc), out_mgc, "MGC")
            proc_mnq = _run_backtest(tmp_cfg, Path(args.data_mnq), out_mnq, "MNQ")

            m_mgc = _metrics_from_output(out_mgc)
            m_mnq = _metrics_from_output(out_mnq)

        pass_mgc = _passes(m_mgc, targets)
        pass_mnq = _passes(m_mnq, targets)
        pass_both = pass_mgc and pass_mnq and proc_mgc.returncode == 0 and proc_mnq.returncode == 0

        row = {
            "combo": combo_idx,
            "pass_both": pass_both,
            "pass_mgc": pass_mgc,
            "pass_mnq": pass_mnq,
            "mgc_trades": m_mgc["trades"],
            "mgc_win_rate": m_mgc["win_rate"],
            "mgc_pf": m_mgc["profit_factor"],
            "mgc_return_pct": m_mgc["return_pct"],
            "mnq_trades": m_mnq["trades"],
            "mnq_win_rate": m_mnq["win_rate"],
            "mnq_pf": m_mnq["profit_factor"],
            "mnq_return_pct": m_mnq["return_pct"],
            "score_min_trades": min(m_mgc["trades"], m_mnq["trades"]),
            "score_trade_util": min(m_mgc["trades"], m_mnq["trades"]) / max(1, targets.min_trades),
            "score_min_pf": min(m_mgc["profit_factor"], m_mnq["profit_factor"]),
            "score_min_win_rate": min(m_mgc["win_rate"], m_mnq["win_rate"]),
            "params": params,
            "mgc_rc": proc_mgc.returncode,
            "mnq_rc": proc_mnq.returncode,
        }
        rows.append(row)

        if best_row is None:
            best_row = row
        else:
            cur = (
                row["pass_both"],
                row["score_trade_util"],
                row["score_min_pf"],
                row["score_min_win_rate"],
            )
            best = (
                best_row["pass_both"],
                best_row["score_trade_util"],
                best_row["score_min_pf"],
                best_row["score_min_win_rate"],
            )
            if cur > best:
                best_row = row

        print(
            f"[{combo_idx:02d}] pass_both={pass_both} "
            f"MGC(wr={m_mgc['win_rate']:.1f},pf={m_mgc['profit_factor']:.2f},tr={m_mgc['trades']:.0f}) "
            f"MNQ(wr={m_mnq['win_rate']:.1f},pf={m_mnq['profit_factor']:.2f},tr={m_mnq['trades']:.0f})"
        )

    csv_path = output_dir / "grid_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "combo",
            "pass_both",
            "pass_mgc",
            "pass_mnq",
            "mgc_trades",
            "mgc_win_rate",
            "mgc_pf",
            "mgc_return_pct",
            "mnq_trades",
            "mnq_win_rate",
            "mnq_pf",
            "mnq_return_pct",
            "score_min_trades",
            "score_trade_util",
            "score_min_pf",
            "score_min_win_rate",
            "mgc_rc",
            "mnq_rc",
            "params",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_copy = dict(row)
            row_copy["params"] = json.dumps(row_copy["params"], sort_keys=True)
            writer.writerow(row_copy)

    summary = {
        "targets": vars(targets),
        "combos_ran": len(rows),
        "pass_both_count": sum(1 for r in rows if r["pass_both"]),
        "best": best_row,
    }
    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if best_row and isinstance(best_row.get("params"), dict):
        pine_path = output_dir / "pine_overrides.txt"
        pine_path.write_text(_pine_override_snippet(best_row["params"]), encoding="utf-8")

    print(f"\nSaved optimizer results to: {csv_path}")
    print(f"Saved summary to: {summary_path}")
    if summary["pass_both_count"] > 0:
        print("At least one parameter set met BOTH-symbol targets.")
        if args.apply_best_when_pass and best_row and isinstance(best_row.get("params"), dict):
            backups_dir = output_dir / "applied_backups"
            _apply_best_to_pine_and_config(
                best_params=best_row["params"],
                config_path=Path(args.config),
                pine_files=[
                    ROOT / "universal_adaptive_working.txt",
                    ROOT / "fixed_ultimate_5.2_coding2_working.txt",
                ],
                backup_dir=backups_dir,
            )
            print(f"Applied best params to config + Pine files. Backups saved in: {backups_dir}")
    else:
        print("No parameter set met BOTH-symbol targets in this sweep.")


if __name__ == "__main__":
    main()

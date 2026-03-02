# Backtest Profiles

Use profile-specific configs so trend-only and range runs stay isolated.

## Profiles

- `trend_only` -> `config/config_trend_only.yaml`
- `range_preserved` -> `config/config_range_preserved.yaml`
- `ict_asian_sweep` -> `config/config_ict_asian_sweep.yaml`
- `ict_asian_sweep_inverted` -> `config/config_ict_asian_sweep_inverted.yaml`
- `combined_trend_ict_range` -> `config/config_combined_trend_ict_range.yaml`

## Run Commands

Trend-only on mixed data:

```bash
venv/bin/python scripts/run_backtest_profile.py --profile trend_only --dataset mixed_50k
```

Range-preserved on ranging data:

```bash
venv/bin/python scripts/run_backtest_profile.py --profile range_preserved --dataset ranging_50k
```

ICT Asian sweep on ranging data:

```bash
venv/bin/python scripts/run_backtest_profile.py --profile ict_asian_sweep --dataset ranging_50k
```

ICT Asian sweep inverted on ranging data:

```bash
venv/bin/python scripts/run_backtest_profile.py --profile ict_asian_sweep_inverted --dataset ranging_50k
```

Combined trend + best range layer:

```bash
venv/bin/python scripts/run_backtest_profile.py --profile combined_trend_ict_range --dataset mixed_50k
```

## Output Isolation

Each run writes to its own folder:

`results/backtests/<profile>/<dataset>_<timestamp>/`

Each run also saves `config_used.yaml` in that folder for reproducibility.

# Range Edge Research (ICT Asian Sweep)

Date: 2026-02-27

## Profiles Tested

- `range_preserved` (baseline)
- `ict_asian_sweep` (direct sweep-reclaim)
- `ict_asian_sweep_inverted` (same logic with `ict_asian_sweep.invert_signals=true`)

## Key Results

### Baseline on `ranging_50k`

- MGC: 7 trades, 0.00% win rate, PF 0.00, return -2.34%
- MNQ: 6 trades, 0.00% win rate, PF 0.00, return -0.58%

### ICT sweep (non-inverted) on `ranging_6k`

- MGC: 10 trades, 0.00% win rate, PF 0.00, return -1.78%
- MNQ: 9 trades, 0.00% win rate, PF 0.00, return -0.64%

### ICT sweep inverted on `ranging_6k`

- MGC: 10 trades, 90.00% win rate, PF 8.18, return +1.37%
- MNQ: 9 trades, 100.00% win rate, PF inf, return +0.62%

### ICT sweep inverted on `ranging_50k`

- MGC: 93 trades, 60.22% win rate, PF 1.31, return +2.35%
- MNQ: 90 trades, 62.22% win rate, PF 1.53, return +1.34%

### ICT sweep inverted on `mixed_50k`

- MGC: 106 trades, 54.72% win rate, PF 1.89, return +11.77%
- MNQ: 85 trades, 54.12% win rate, PF 2.07, return +1.46%

## Interpretation

- The original range profile has no viable edge on ranging synthetic data.
- The direct ICT sweep-reclaim variant is directionally wrong for this dataset.
- Inverted ICT sweep materially improves expectancy and trade count on both symbols.
- It is close to, but does not yet fully meet, the strict 62.5% dual-symbol win-rate target:
  - MGC is still below target at 60.22% on `ranging_50k`.

## Next Iteration

1. Add an FVG/CE confirmation sub-filter for ICT entries (fewer but higher-quality entries).
2. Add instrument-specific ICT thresholds (MGC/MNQ) for confluence and sweep buffer.
3. Re-run on `ranging_50k` with target gates:
   - win rate >= 62.5
   - PF >= 1.2
   - positive return
   - minimum trades >= 80

## Follow-up Test (FVG + Per-Instrument Thresholds)

Date: 2026-02-27 (later session)

### Grid on `ranging_50k` (ICT inverted base)

- `base_inv` (no FVG): MGC 60.22% / PF 1.31, MNQ 62.22% / PF 1.53, trades 93/90
- `fvg35`: sharply worse, both symbols negative
- `fvg25`: sharply worse, both symbols negative
- `fvg30_mgc60`: worse, both symbols negative
- `fvg30_mgc62`: worse, both symbols negative
- `fvg30_mgc62_buf07`: worse, both symbols negative

Conclusion: no clear improvement from FVG/CE and per-instrument threshold variants on this dataset.

## Finalized Combined Profile

Per instruction, after no clear follow-up improvement, we finalized the best range result and combined it with the trend profile:

- Config: `config/config_combined_trend_ict_range.yaml`
- Mode: trend engine + ICT range layer (`range_mode=ICT_ASIAN_SWEEP`, inverted signals, FVG disabled)

### Combined profile validation

`mixed_50k`
- MGC: 48 trades, 54.17% win rate, PF 2.40, return +6.59%
- MNQ: 48 trades, 54.17% win rate, PF 2.32, return +0.81%

`ranging_50k`
- MGC: 47 trades, 68.09% win rate, PF 1.95, return +2.72%
- MNQ: 47 trades, 68.09% win rate, PF 1.72, return +0.67%

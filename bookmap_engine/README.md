# Clean Bookmap Engine (v1)

This module provides a clean, low-noise Bookmap-style engine:

- L2 depth heatmap
- Mid-price trace
- DOM ladder
- Microstructure signals (imbalance, sweep, absorption, whale hits)
- Feed switcher: Synthetic or Binance Futures (REST)

## Run

```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python
streamlit run bookmap_engine/app_streamlit.py
```

## Notes

- Current feed is synthetic so you can test visuals and logic safely.
- Binance Futures REST mode is also available for live public data snapshots.
- Engine is separated from your strategy files and does not change trading logic.
- Next step can plug in live L2 adapters (Binance, Alpaca, IB, etc.) using the same snapshot schema.

## Strategy Bridge (enabled now)

The app can write a bridge file for your Python strategy:

- Default path: `data/bookmap_signal.json`
- Fields include: `decision` (`GO_LONG`, `GO_SHORT`, `NO_TRADE`), confidence, imbalance, whale flags.

In your strategy config (`config/config.yaml`):

```yaml
bookmap_bridge:
  enabled: true
  profile: "strict"   # strict | balanced | permissive | custom
  signal_file: "data/bookmap_signal.json"
  # Below values are only used when profile = custom:
  max_age_seconds: 20
  min_confidence: 55
  require_whale: false
  fail_open: true
```

When enabled, `StrategyEngine` only allows long/short entries that match bridge direction.

Profile behavior:

- `strict`: fail_open=false, max_age=8s, min_conf=70, require_whale=true
- `balanced`: fail_open=true, max_age=20s, min_conf=55, require_whale=false
- `permissive`: fail_open=true, max_age=30s, min_conf=45, require_whale=false
- `custom`: uses explicit YAML values

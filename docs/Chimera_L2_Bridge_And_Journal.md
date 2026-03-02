# Chimera L2 Bridge + Journal/Backtest

## 1) Start full stack with bridge

```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python
source venv/bin/activate
python run_chimera_stack.py --config config/config.yaml --with-bridge
```

This starts:
- Streamlit app
- executor
- L2 bridge writer

## 2) Switch broker input file

The bridge reads a source JSON and writes:

`data/live_l2_snapshot.json`

Starter source files:
- `data/bridges/tradovate_l2.json`
- `data/bridges/ninjatrader_l2.json`
- `data/bridges/oanda_l2.json`

Run bridge only:

```bash
python run_chimera_l2_bridge.py --config config/config.yaml --broker tradovate --symbol MGC1! --input-file data/bridges/tradovate_l2.json
```

## 3) App feed mode

In Chimera sidebar:
- `Source` = `Futures L2 Bridge (JSON)`
- `Live L2 JSON Path` = `data/live_l2_snapshot.json`

## 4) Trade Journal

In app:
- open `Journal + Backtest` section
- `Trade Journal` tab shows:
  - closed trades
  - order log
  - execution audit trail

## 5) Backtest Lab

In app:
- `Backtest Lab` tab
- choose data file (e.g. `data/historical/sample_data_50k.csv`)
- set output dir (e.g. `results/ui_backtest_latest`)
- click `Run Backtest Now`

The tab displays:
- backtest summary metrics
- equity curve
- generated trades table
- stdout/stderr console output

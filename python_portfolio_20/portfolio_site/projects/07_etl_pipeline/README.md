# ETL Pipeline Project

## Problem
Raw data feeds often contain invalid rows that break downstream analytics.

## Approach
Implemented extraction + transform pipeline with data quality filtering and schema normalization.

## Tech Stack
Python, csv, io, ETL transformation logic

## Measurable Results
- Average `run_demo()` latency: **0.0067 ms**
- P95 latency: **0.0053 ms**
- Estimated throughput: **149441.3 runs/sec**
- Transforms source data and loads 2 valid rows after quality filtering.

## Production Signals
- Included in full smoke run: `python3 run_all_smoke.py`
- Included in smoke test: `python3 tests/test_portfolio_smoke.py`
- Deployment-ready portfolio site integration (featured + proof metadata)

## Tradeoffs
CSV input is deterministic but real systems also require schema versioning and source-level drift detection.

## Next Steps
Add load stage to database, schema contracts, and scheduled pipeline orchestration.

## Screenshots And Demo
![07_etl_pipeline preview](../../portfolio_site/assets/project_media/07_etl_pipeline/preview.png)

![07_etl_pipeline gif demo](../../portfolio_site/assets/project_media/07_etl_pipeline/demo.gif)

## Run
```bash
python3 /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/projects/07_etl_pipeline/main.py
```

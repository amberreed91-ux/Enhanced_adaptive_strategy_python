# Capstone: End-to-End ML Product

## Problem
Hiring teams want proof you can connect model training to serving predictions.

## Approach
Implemented full fit-to-predict pipeline with deterministic inference behavior.

## Tech Stack
Python, linear modeling, inference pipeline design

## Measurable Results
- Average `run_demo()` latency: **0.0018 ms**
- P95 latency: **0.0019 ms**
- Estimated throughput: **552281.4 runs/sec**
- Fits linear model and returns deterministic prediction 10.0.

## Production Signals
- Included in full smoke run: `python3 run_all_smoke.py`
- Included in smoke test: `python3 tests/test_portfolio_smoke.py`
- Deployment-ready portfolio site integration (featured + proof metadata)

## Tradeoffs
Linear model is intentionally simple; production deployment should include monitoring and retraining triggers.

## Next Steps
Wrap in model API with drift checks and experiment tracking.

## Screenshots And Demo
![20_capstone_end_to_end_ml_product preview](../../portfolio_site/assets/project_media/20_capstone_end_to_end_ml_product/preview.png)

![20_capstone_end_to_end_ml_product gif demo](../../portfolio_site/assets/project_media/20_capstone_end_to_end_ml_product/demo.gif)

## Run
```bash
python3 /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/projects/20_capstone_end_to_end_ml_product/main.py
```

# REST API with FastAPI-style Design

## Problem
Teams need a clean API service pattern that can scale from prototype to production handlers.

## Approach
Built a typed service layer with strict validation and deterministic create/list behavior.

## Tech Stack
Python, dataclasses, service-layer architecture, validation patterns

## Measurable Results
- Average `run_demo()` latency: **0.0009 ms**
- P95 latency: **0.0009 ms**
- Estimated throughput: **1165538.9 runs/sec**
- Creates and lists 2 API-style items in deterministic order.

## Production Signals
- Included in full smoke run: `python3 run_all_smoke.py`
- Included in smoke test: `python3 tests/test_portfolio_smoke.py`
- Deployment-ready portfolio site integration (featured + proof metadata)

## Tradeoffs
In-memory persistence is simple for demonstration but should be replaced by a database adapter in production.

## Next Steps
Add persistence interface + FastAPI routes + auth middleware + integration tests.

## Screenshots And Demo
![04_rest_api_fastapi_style preview](../../portfolio_site/assets/project_media/04_rest_api_fastapi_style/preview.png)

![04_rest_api_fastapi_style gif demo](../../portfolio_site/assets/project_media/04_rest_api_fastapi_style/demo.gif)

## Run
```bash
python3 /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/projects/04_rest_api_fastapi_style/main.py
```

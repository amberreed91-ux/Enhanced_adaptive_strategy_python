# Asynchronous API Aggregator

## Problem
Serial API calls increase latency and make dashboards feel slow.

## Approach
Used asyncio concurrency to collect multiple upstream responses in parallel and aggregate once.

## Tech Stack
Python, asyncio, task orchestration, response aggregation

## Measurable Results
- Average `run_demo()` latency: **22.4078 ms**
- P95 latency: **25.3414 ms**
- Estimated throughput: **44.6 runs/sec**
- Aggregates 3 async sources into total value 140.

## Production Signals
- Included in full smoke run: `python3 run_all_smoke.py`
- Included in smoke test: `python3 tests/test_portfolio_smoke.py`
- Deployment-ready portfolio site integration (featured + proof metadata)

## Tradeoffs
Current source calls are simulated; production version should include retry and timeout strategy per source.

## Next Steps
Integrate real HTTP clients, circuit breakers, and latency/error observability.

## Screenshots And Demo
![11_async_api_aggregator preview](../../portfolio_site/assets/project_media/11_async_api_aggregator/preview.png)

![11_async_api_aggregator gif demo](../../portfolio_site/assets/project_media/11_async_api_aggregator/demo.gif)

## Run
```bash
python3 /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/projects/11_async_api_aggregator/main.py
```

# Recommendation System

## Problem
Applications need transparent ranking logic to personalize user experiences.

## Approach
Implemented cosine-similarity scoring with deterministic ranking output.

## Tech Stack
Python, vector math, ranking algorithms

## Measurable Results
- Average `run_demo()` latency: **0.004 ms**
- P95 latency: **0.0042 ms**
- Estimated throughput: **247504.7 runs/sec**
- Produces ranked recommendations with top item 'item_a'.

## Production Signals
- Included in full smoke run: `python3 run_all_smoke.py`
- Included in smoke test: `python3 tests/test_portfolio_smoke.py`
- Deployment-ready portfolio site integration (featured + proof metadata)

## Tradeoffs
Content vectors are handcrafted; production systems need feature pipelines and feedback loops.

## Next Steps
Add offline evaluation metrics and online click-through telemetry.

## Screenshots And Demo
![13_recommender_system preview](../../portfolio_site/assets/project_media/13_recommender_system/preview.png)

![13_recommender_system gif demo](../../portfolio_site/assets/project_media/13_recommender_system/demo.gif)

## Run
```bash
python3 /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/projects/13_recommender_system/main.py
```

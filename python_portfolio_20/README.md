# Python Portfolio: 20 Projects

This portfolio contains 20 production-style mini projects that demonstrate core Python proficiency across backend engineering, data systems, automation, async, and ML.

## Quick start
```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20
python3 run_all_smoke.py
python3 tests/test_portfolio_smoke.py
python3 portfolio_site/scripts/build_site_data.py
python3 portfolio_site/scripts/validate_portfolio_links.py
python3 -m http.server 8000
```

Then open `http://localhost:8000/portfolio_site/index.html`.

## Website Features
- Search and category filtering across all 20 projects
- Per-project modal with run command and live demo output snapshot
- About section, contact links, and downloadable resume
- Featured-project panel with hiring proof (outcomes, metrics, verification)
- Metadata-driven project credibility fields from `portfolio_site/assets/project_meta.json`
- Featured project demo pages under `portfolio_site/demos/` with screenshot and GIF assets
- One-page resume PDF at `portfolio_site/assets/amber_reed_jr_python_resume.pdf`

## Deployment
- GitHub Pages: workflow at `/Users/amberreed/Enhanced_adaptive_strategy_python/.github/workflows/deploy-portfolio-site.yml`
- Netlify: config at `/Users/amberreed/Enhanced_adaptive_strategy_python/netlify.toml`
- Vercel: config at `/Users/amberreed/Enhanced_adaptive_strategy_python/vercel.json`
- Full guide: [DEPLOYMENT.md](/Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/DEPLOYMENT.md)

## Projects
1. `01_finance_tracker_cli`
2. `02_password_manager_encrypted`
3. `03_web_scraper_data_cleaner`
4. `04_rest_api_fastapi_style`
5. `05_task_manager_webapp`
6. `06_jwt_auth_service`
7. `07_etl_pipeline`
8. `08_data_dashboard`
9. `09_price_alert_bot`
10. `10_log_analyzer_monitor`
11. `11_async_api_aggregator`
12. `12_chat_bot`
13. `13_recommender_system`
14. `14_nlp_text_classifier`
15. `15_time_series_forecaster`
16. `16_computer_vision_mini_app`
17. `17_dockerized_microservice`
18. `18_ci_cd_project_template`
19. `19_distributed_job_queue`
20. `20_capstone_end_to_end_ml_product`

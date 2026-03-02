# Deploying The Portfolio Website

This project includes deployment setup for GitHub Pages, Netlify, and Vercel.

## 1) GitHub Pages (Automatic via GitHub Actions)
Config file:
- `/Users/amberreed/Enhanced_adaptive_strategy_python/.github/workflows/deploy-portfolio-site.yml`

How it works:
1. Push changes to `main` or `master`.
2. The workflow builds `projects.json`.
3. The workflow deploys `python_portfolio_20/portfolio_site` to GitHub Pages.

Repository settings required:
1. Go to **Settings > Pages**.
2. Ensure source is **GitHub Actions**.

## 2) Netlify
Config file:
- `/Users/amberreed/Enhanced_adaptive_strategy_python/netlify.toml`

How it works:
1. Connect this repository in Netlify.
2. Netlify uses the config automatically:
   - Base: `python_portfolio_20`
   - Build command: `python3 portfolio_site/scripts/build_site_data.py`
   - Publish directory: `portfolio_site`

## 3) Vercel
Config file:
- `/Users/amberreed/Enhanced_adaptive_strategy_python/vercel.json`

How it works:
1. Import this repository into Vercel.
2. Vercel runs the configured build command.
3. Output is served from `python_portfolio_20/portfolio_site`.

## Local pre-deploy check
```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20
python3 portfolio_site/scripts/build_site_data.py
python3 tests/test_portfolio_smoke.py
python3 -m http.server 8000
```

Then open `http://localhost:8000/portfolio_site/index.html`.

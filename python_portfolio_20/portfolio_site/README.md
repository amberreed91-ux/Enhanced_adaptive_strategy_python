# Portfolio Website

This website showcases all 20 Python portfolio projects with search, category filters, and per-project demo output.
It also includes About, Contact, and Resume sections.

## Build data
```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20
python3 portfolio_site/scripts/build_site_data.py
python3 portfolio_site/scripts/validate_portfolio_links.py
```

## Serve locally
```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20
python3 -m http.server 8000
```

Open `http://localhost:8000/portfolio_site/index.html`.

## Update workflow
1. Edit any project under `projects/*/main.py` or `projects/*/README.md`.
2. Add hiring-focused proof in `portfolio_site/assets/project_meta.json`:
   - `featured`, `completion`, `impact_metrics`, `outcomes`, `proof_points`
   - `links.live`, `links.repo`, `links.docs`, `links.video`
3. Re-run `python3 portfolio_site/scripts/build_site_data.py`.
4. Refresh the browser.

## Recruiter view checklist
- Mark your best 3-5 projects as `featured: true`
- Add measurable outcomes under `impact_metrics`
- Add public GitHub/live/demo links in `project_meta.json`
- Keep each project README outcome-oriented
- Add screenshot + GIF assets under `portfolio_site/assets/project_media/<slug>/`
- Keep one-page resume PDF updated at `portfolio_site/assets/amber_reed_jr_python_resume.pdf`

## Deploy
- GitHub Pages workflow: `/Users/amberreed/Enhanced_adaptive_strategy_python/.github/workflows/deploy-portfolio-site.yml`
- Netlify config: `/Users/amberreed/Enhanced_adaptive_strategy_python/netlify.toml`
- Vercel config: `/Users/amberreed/Enhanced_adaptive_strategy_python/vercel.json`
- Full deployment guide: [DEPLOYMENT.md](/Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20/DEPLOYMENT.md)

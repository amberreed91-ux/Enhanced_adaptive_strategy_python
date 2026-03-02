from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = ROOT / "projects"
OUTPUT_JSON = ROOT / "portfolio_site" / "assets" / "projects.json"
SITE_PROJECTS_DIR = ROOT / "portfolio_site" / "projects"
META_PATH = ROOT / "portfolio_site" / "assets" / "project_meta.json"

CATEGORY_MAP = {
    "01_finance_tracker_cli": "Core Python",
    "02_password_manager_encrypted": "Core Python",
    "03_web_scraper_data_cleaner": "Data & Analytics",
    "04_rest_api_fastapi_style": "Backend & APIs",
    "05_task_manager_webapp": "Backend & APIs",
    "06_jwt_auth_service": "Backend & APIs",
    "07_etl_pipeline": "Data & Analytics",
    "08_data_dashboard": "Data & Analytics",
    "09_price_alert_bot": "Automation & Bots",
    "10_log_analyzer_monitor": "Automation & Bots",
    "11_async_api_aggregator": "Backend & APIs",
    "12_chat_bot": "Automation & Bots",
    "13_recommender_system": "ML & AI",
    "14_nlp_text_classifier": "ML & AI",
    "15_time_series_forecaster": "ML & AI",
    "16_computer_vision_mini_app": "ML & AI",
    "17_dockerized_microservice": "Systems & DevOps",
    "18_ci_cd_project_template": "Systems & DevOps",
    "19_distributed_job_queue": "Systems & DevOps",
    "20_capstone_end_to_end_ml_product": "Capstone",
}


def parse_readme(readme_path: Path) -> tuple[str, str, list[str]]:
    text = readme_path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else readme_path.parent.name

    summary = ""
    summary_match = re.search(r"##\s+What it shows\n(.+)", text)
    if summary_match:
        summary = summary_match.group(1).strip()

    skills = []
    skills_match = re.search(r"##\s+Skills demonstrated\n(.+)", text)
    if skills_match:
        raw_skills = skills_match.group(1).strip()
        skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

    return title, summary, skills


def load_main(main_path: Path):
    module_name = f"portfolio_site_{main_path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {main_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def package_project_files() -> None:
    if SITE_PROJECTS_DIR.exists():
        shutil.rmtree(SITE_PROJECTS_DIR)
    SITE_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    for source_dir in sorted(PROJECTS_DIR.glob("*")):
        if not source_dir.is_dir():
            continue
        target_dir = SITE_PROJECTS_DIR / source_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / "main.py", target_dir / "main.py")
        shutil.copy2(source_dir / "README.md", target_dir / "README.md")


def load_metadata() -> dict[str, object]:
    if not META_PATH.exists():
        return {"defaults": {}, "projects": {}}
    raw = json.loads(META_PATH.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    projects = raw.get("projects", {})
    if not isinstance(defaults, dict) or not isinstance(projects, dict):
        raise ValueError("project_meta.json must include object keys: defaults and projects")
    return raw


def merge_project_meta(defaults: dict[str, object], override: dict[str, object], slug: str) -> dict[str, object]:
    links_default = defaults.get("links", {}) if isinstance(defaults.get("links", {}), dict) else {}
    links_override = override.get("links", {}) if isinstance(override.get("links", {}), dict) else {}

    links = {
        "live": str(links_override.get("live", links_default.get("live", ""))),
        "repo": str(links_override.get("repo", links_default.get("repo", ""))),
        "docs": str(links_override.get("docs", links_default.get("docs", ""))),
        "video": str(links_override.get("video", links_default.get("video", ""))),
    }

    return {
        "featured": bool(override.get("featured", defaults.get("featured", False))),
        "featured_rank": int(override.get("featured_rank", defaults.get("featured_rank", 999))),
        "completion": str(override.get("completion", defaults.get("completion", "In Progress"))),
        "client_value": str(
            override.get(
                "client_value",
                defaults.get("client_value", "Demonstrates practical engineering and delivery quality."),
            )
        ),
        "impact_metrics": list(override.get("impact_metrics", defaults.get("impact_metrics", []))),
        "outcomes": list(override.get("outcomes", defaults.get("outcomes", []))),
        "proof_points": list(override.get("proof_points", defaults.get("proof_points", []))),
        "links": links,
        "slug": slug,
    }


def build_payload() -> dict[str, object]:
    projects = []
    meta = load_metadata()
    defaults = meta.get("defaults", {})
    per_project = meta.get("projects", {})

    for main_path in sorted(PROJECTS_DIR.glob("*/main.py")):
        slug = main_path.parent.name
        readme_path = main_path.parent / "README.md"
        title, summary, skills = parse_readme(readme_path)

        module = load_main(main_path)
        demo_output = module.run_demo()

        run_command = f"python3 projects/{slug}/main.py"
        merged_meta = merge_project_meta(defaults, per_project.get(slug, {}), slug)

        projects.append(
            {
                "slug": slug,
                "title": title,
                "summary": summary,
                "skills": skills,
                "category": CATEGORY_MAP.get(slug, "General Python"),
                "run_command": run_command,
                "code_path": f"./projects/{slug}/main.py",
                "readme_path": f"./projects/{slug}/README.md",
                "demo_output": demo_output,
                "completion": merged_meta["completion"],
                "client_value": merged_meta["client_value"],
                "impact_metrics": merged_meta["impact_metrics"],
                "outcomes": merged_meta["outcomes"],
                "proof_points": merged_meta["proof_points"],
                "featured": merged_meta["featured"],
                "featured_rank": merged_meta["featured_rank"],
                "links": merged_meta["links"],
            }
        )

    categories = sorted({p["category"] for p in projects})
    all_skills = sorted({skill for p in projects for skill in p["skills"]})
    featured = sorted(
        [p for p in projects if p.get("featured")],
        key=lambda item: (item.get("featured_rank", 999), item["title"]),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(projects),
        "featured_count": len(featured),
        "categories": categories,
        "skills": all_skills,
        "projects": projects,
        "featured_projects": featured,
    }


def main() -> None:
    package_project_files()
    payload = build_payload()
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()

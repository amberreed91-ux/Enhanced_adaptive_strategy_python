from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path('/Users/amberreed/Enhanced_adaptive_strategy_python/python_portfolio_20')
SITE = ROOT / 'portfolio_site'
DATA = SITE / 'assets' / 'projects.json'
REPORT = SITE / 'assets' / 'link_audit.json'


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def check_path(value: str) -> tuple[bool, str]:
    target = (SITE / value.lstrip('./')).resolve()
    ok = target.exists()
    return ok, str(target)


def main() -> None:
    payload = json.loads(DATA.read_text(encoding='utf-8'))
    records: list[dict[str, object]] = []

    for project in payload.get('projects', []):
        slug = project.get('slug', '')
        checks: list[dict[str, object]] = []

        for key in ['code_path', 'readme_path']:
            value = project.get(key, '')
            ok, resolved = check_path(str(value))
            checks.append({'field': key, 'value': value, 'valid': ok, 'resolved': resolved})

        links = project.get('links', {}) or {}
        for key in ['live', 'repo', 'docs', 'video']:
            value = str(links.get(key, '')).strip()
            if not value:
                checks.append({'field': f'links.{key}', 'value': value, 'valid': False, 'reason': 'empty'})
                continue
            if value.startswith('./'):
                ok, resolved = check_path(value)
                checks.append({'field': f'links.{key}', 'value': value, 'valid': ok, 'resolved': resolved})
            else:
                checks.append({'field': f'links.{key}', 'value': value, 'valid': is_http_url(value), 'reason': 'url-format-only'})

        all_valid = all(bool(item['valid']) for item in checks)
        records.append({'slug': slug, 'all_valid': all_valid, 'checks': checks})

    report = {
        'project_count': len(records),
        'valid_projects': sum(1 for item in records if item['all_valid']),
        'records': records,
        'note': 'External URL reachability is not verified in this offline environment. URL format is validated only.',
    }

    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Wrote {REPORT}')


if __name__ == '__main__':
    main()

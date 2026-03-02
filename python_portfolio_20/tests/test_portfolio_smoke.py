from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = sorted((ROOT / 'projects').glob('*/main.py'))


def load_module(path: Path):
    module_name = f"portfolio_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_all_projects_have_run_demo() -> None:
    assert len(PROJECTS) == 20
    for main_py in PROJECTS:
        module = load_module(main_py)
        result = module.run_demo()
        assert isinstance(result, dict)
        assert 'project' in result


if __name__ == '__main__':
    test_all_projects_have_run_demo()
    print('portfolio smoke test passed')

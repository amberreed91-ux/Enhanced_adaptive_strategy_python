from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAINS = sorted((ROOT / 'projects').glob('*/main.py'))


def load(path: Path):
    module_name = f"portfolio_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    for p in MAINS:
        mod = load(p)
        print(f'{p.parent.name}: {mod.run_demo()}')


if __name__ == '__main__':
    main()

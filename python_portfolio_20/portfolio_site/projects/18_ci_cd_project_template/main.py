from __future__ import annotations


def quality_gate(results: dict[str, bool]) -> tuple[bool, list[str]]:
    failed = [name for name, ok in results.items() if not ok]
    return (len(failed) == 0, failed)


def run_demo() -> dict[str, object]:
    passed, failed = quality_gate({'tests': True, 'lint': True, 'types': False})
    return {'project': 'ci_cd_project_template', 'passed': passed, 'failed': failed}


if __name__ == '__main__':
    print(run_demo())

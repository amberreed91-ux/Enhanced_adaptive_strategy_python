from __future__ import annotations

import re

LOG_RE = re.compile(r'\[(?P<level>[A-Z]+)\] (?P<msg>.+)')


def error_rate(lines: list[str]) -> float:
    parsed = [LOG_RE.match(line) for line in lines]
    ok = [m for m in parsed if m]
    if not ok:
        return 0.0
    errors = sum(1 for m in ok if m.group('level') == 'ERROR')
    return errors / len(ok)


def run_demo() -> dict[str, object]:
    lines = ['[INFO] boot', '[ERROR] timeout', '[INFO] retry', '[ERROR] failed']
    rate = error_rate(lines)
    return {'project': 'log_analyzer_monitor', 'error_rate': rate, 'anomaly': rate > 0.3}


if __name__ == '__main__':
    print(run_demo())

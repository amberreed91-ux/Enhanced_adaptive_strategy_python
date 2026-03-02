from __future__ import annotations

from statistics import mean


def build_kpis(values: list[float]) -> dict[str, float]:
    return {
        'count': float(len(values)),
        'avg': mean(values),
        'min': min(values),
        'max': max(values),
    }


def run_demo() -> dict[str, object]:
    kpis = build_kpis([12.0, 14.5, 9.0, 21.5])
    return {'project': 'data_dashboard', 'avg': kpis['avg']}


if __name__ == '__main__':
    print(run_demo())

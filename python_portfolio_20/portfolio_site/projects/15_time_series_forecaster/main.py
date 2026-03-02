from __future__ import annotations


def moving_average_forecast(series: list[float], window: int, horizon: int) -> list[float]:
    seed = series[-window:]
    out: list[float] = []
    for _ in range(horizon):
        nxt = sum(seed) / len(seed)
        out.append(round(nxt, 2))
        seed = seed[1:] + [nxt]
    return out


def mape(actual: list[float], predicted: list[float]) -> float:
    errors = [abs((a - p) / a) for a, p in zip(actual, predicted, strict=False) if a]
    return sum(errors) / len(errors)


def run_demo() -> dict[str, object]:
    forecast = moving_average_forecast([100, 102, 101, 105, 107], window=3, horizon=2)
    return {'project': 'time_series_forecaster', 'forecast': forecast}


if __name__ == '__main__':
    print(run_demo())

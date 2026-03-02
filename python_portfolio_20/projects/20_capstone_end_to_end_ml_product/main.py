from __future__ import annotations


def fit_linear(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = float(len(xs))
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=False))
    den = sum((x - x_mean) ** 2 for x in xs)
    m = num / den if den else 0.0
    b = y_mean - m * x_mean
    return m, b


def predict(model: tuple[float, float], x: float) -> float:
    m, b = model
    return round(m * x + b, 4)


def run_demo() -> dict[str, object]:
    model = fit_linear([1, 2, 3, 4], [2, 4, 6, 8])
    y = predict(model, 5)
    return {'project': 'capstone_end_to_end_ml_product', 'prediction': y}


if __name__ == '__main__':
    print(run_demo())

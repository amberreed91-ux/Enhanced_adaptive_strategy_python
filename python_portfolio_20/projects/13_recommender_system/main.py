from __future__ import annotations

from math import sqrt


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def recommend(user_vec: list[float], catalog: dict[str, list[float]]) -> list[tuple[str, float]]:
    ranked = [(name, cosine(user_vec, vec)) for name, vec in catalog.items()]
    return sorted(ranked, key=lambda pair: pair[1], reverse=True)


def run_demo() -> dict[str, object]:
    ranked = recommend([1, 0, 1], {'item_a': [1, 0, 1], 'item_b': [0, 1, 0], 'item_c': [1, 1, 0]})
    return {'project': 'recommender_system', 'top_item': ranked[0][0]}


if __name__ == '__main__':
    print(run_demo())

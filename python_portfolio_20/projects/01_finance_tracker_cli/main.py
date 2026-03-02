from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections import defaultdict


@dataclass(frozen=True)
class Transaction:
    when: date
    amount: float
    category: str


def monthly_summary(transactions: list[Transaction]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for tx in transactions:
        totals[tx.category] += tx.amount
    return dict(sorted(totals.items()))


def run_demo() -> dict[str, object]:
    txs = [
        Transaction(date(2026, 1, 2), -42.5, 'food'),
        Transaction(date(2026, 1, 5), -12.0, 'transport'),
        Transaction(date(2026, 1, 28), 2600.0, 'income'),
    ]
    return {'project': 'finance_tracker_cli', 'summary': monthly_summary(txs)}


if __name__ == '__main__':
    print(run_demo())

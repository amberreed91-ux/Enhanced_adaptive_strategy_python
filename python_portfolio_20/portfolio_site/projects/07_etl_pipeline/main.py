from __future__ import annotations

import csv
import io


def extract(csv_blob: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_blob)))


def transform(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    out = []
    for row in rows:
        amount = float(row['amount'])
        if amount <= 0:
            continue
        out.append({'name': row['name'].strip().title(), 'amount': round(amount, 2)})
    return out


def run_demo() -> dict[str, object]:
    rows = extract("name,amount\nalpha,10\nbeta,-2\ngamma,5.5\n")
    shaped = transform(rows)
    return {'project': 'etl_pipeline', 'loaded_rows': len(shaped)}


if __name__ == '__main__':
    print(run_demo())

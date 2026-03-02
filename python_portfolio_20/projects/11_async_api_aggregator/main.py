from __future__ import annotations

import asyncio


async def fake_fetch(name: str, delay: float) -> dict[str, object]:
    await asyncio.sleep(delay)
    return {'source': name, 'value': len(name) * 10}


async def aggregate() -> list[dict[str, object]]:
    tasks = [fake_fetch('alpha', 0.01), fake_fetch('beta', 0.02), fake_fetch('gamma', 0.01)]
    return await asyncio.gather(*tasks)


def run_demo() -> dict[str, object]:
    rows = asyncio.run(aggregate())
    total = sum(int(row['value']) for row in rows)
    return {'project': 'async_api_aggregator', 'sources': len(rows), 'total': total}


if __name__ == '__main__':
    print(run_demo())

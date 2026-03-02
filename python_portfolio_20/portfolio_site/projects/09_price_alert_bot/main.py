from __future__ import annotations


def evaluate_alerts(symbol: str, prices: list[float], low: float, high: float) -> list[str]:
    alerts: list[str] = []
    for price in prices:
        if price <= low:
            alerts.append(f'BUY {symbol} @ {price}')
        elif price >= high:
            alerts.append(f'SELL {symbol} @ {price}')
    return alerts


def run_demo() -> dict[str, object]:
    alerts = evaluate_alerts('BTCUSD', [96000, 101500, 108000], low=97000, high=107000)
    return {'project': 'price_alert_bot', 'alerts': alerts}


if __name__ == '__main__':
    print(run_demo())

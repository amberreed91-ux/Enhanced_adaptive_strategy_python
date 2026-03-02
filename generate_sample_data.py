#!/usr/bin/env python3
"""
Generate sample OHLCV data for testing.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_sample_data(
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    interval_minutes: int = 5,
    base_price: float = 2000.0,
    volatility: float = 0.02,
    trend: float = 0.0001
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for backtesting.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval_minutes: Bar interval in minutes
        base_price: Starting price
        volatility: Price volatility (std dev as fraction of price)
        trend: Upward/downward drift per bar

    Returns:
        DataFrame with OHLCV data
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    # Generate timestamps
    timestamps = pd.date_range(start, end, freq=f'{interval_minutes}min')
    n_bars = len(timestamps)

    # Generate price series with trend and noise
    np.random.seed(42)
    returns = np.random.normal(trend, volatility, n_bars)
    prices = base_price * (1 + returns).cumprod()

    # Generate OHLC from close prices
    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        # Add intrabar volatility
        high = close * (1 + abs(np.random.normal(0, volatility/2)))
        low = close * (1 - abs(np.random.normal(0, volatility/2)))

        if i == 0:
            open_price = base_price
        else:
            open_price = data[-1]['close']

        # Ensure OHLC relationships
        high = max(high, open_price, close)
        low = min(low, open_price, close)

        # Generate volume with some correlation to price movement
        price_change = abs((close - open_price) / open_price)
        base_volume = 1000
        volume = int(base_volume * (1 + price_change * 10) * np.random.uniform(0.5, 1.5))

        data.append({
            'timestamp': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    return df


def generate_trending_data(n_bars: int = 1000) -> pd.DataFrame:
    """Generate trending market data."""
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(minutes=5*i) for i in range(n_bars)]

    np.random.seed(42)
    trend = 0.0005  # Strong upward trend
    volatility = 0.01
    base_price = 2000.0

    returns = np.random.normal(trend, volatility, n_bars)
    prices = base_price * (1 + returns).cumprod()

    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        high = close * (1 + abs(np.random.normal(0, 0.005)))
        low = close * (1 - abs(np.random.normal(0, 0.005)))
        open_price = data[-1]['close'] if i > 0 else base_price
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        volume = int(1000 * np.random.uniform(0.8, 1.2))

        data.append({
            'timestamp': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    return pd.DataFrame(data)


def generate_ranging_data(n_bars: int = 1000) -> pd.DataFrame:
    """Generate ranging (mean-reverting) market data."""
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(minutes=5*i) for i in range(n_bars)]

    np.random.seed(42)
    base_price = 2000.0

    # Mean-reverting process
    prices = [base_price]
    for i in range(1, n_bars):
        # Pull back to mean
        mean_reversion = (base_price - prices[-1]) * 0.1
        noise = np.random.normal(0, 10)
        new_price = prices[-1] + mean_reversion + noise
        prices.append(new_price)

    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        high = close * (1 + abs(np.random.normal(0, 0.005)))
        low = close * (1 - abs(np.random.normal(0, 0.005)))
        open_price = data[-1]['close'] if i > 0 else base_price
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        volume = int(1000 * np.random.uniform(0.8, 1.2))

        data.append({
            'timestamp': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    return pd.DataFrame(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate sample OHLCV data')
    parser.add_argument('--output', default='data/historical/sample_data.csv', help='Output CSV file')
    parser.add_argument('--type', choices=['mixed', 'trending', 'ranging'], default='mixed')
    parser.add_argument('--bars', type=int, default=10000, help='Number of bars')

    args = parser.parse_args()

    if args.type == 'trending':
        df = generate_trending_data(args.bars)
    elif args.type == 'ranging':
        df = generate_ranging_data(args.bars)
    else:
        df = generate_sample_data(
            start_date="2023-01-01",
            end_date="2024-12-31",
            interval_minutes=5
        )

    # Ensure directory exists
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    df.to_csv(args.output, index=False)
    print(f"Generated {len(df)} bars")
    print(f"Saved to {args.output}")
    print(f"\nSample data:")
    print(df.head())
    print(f"\nStats:")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    print(f"Avg volume: {df['volume'].mean():.0f}")

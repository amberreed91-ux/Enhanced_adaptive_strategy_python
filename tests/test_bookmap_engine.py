from datetime import datetime, timezone

from bookmap_engine.core import BookmapEngine
from bookmap_engine.core import OrderBookSnapshot
from bookmap_engine.feed import SyntheticFeedConfig, SyntheticOrderBookFeed


def test_bookmap_engine_ingest_and_ladder():
    engine = BookmapEngine(levels=40, history=80)
    feed = SyntheticOrderBookFeed(SyntheticFeedConfig(seed=7, start_price=1000.0, tick_size=0.5, levels_per_side=20))

    for _ in range(25):
        engine.ingest(feed.next_snapshot())

    assert len(engine.snapshots) == 25
    assert engine.heatmap.shape == (80, 40)
    ladder = engine.latest_ladder(depth=8)
    assert len(ladder) > 0


def test_signals_computed_without_errors():
    engine = BookmapEngine(levels=30, history=60)
    feed = SyntheticOrderBookFeed(SyntheticFeedConfig(seed=10, start_price=2000.0, tick_size=0.25, levels_per_side=15))

    for _ in range(40):
        engine.ingest(feed.next_snapshot())

    sig = engine.last_signals
    assert -1.0 <= sig.imbalance <= 1.0


def test_whale_signal_detection():
    engine = BookmapEngine(levels=20, history=40)
    engine.set_signal_config(whale_percentile=95, whale_min_size=15.0, absorption_percentile=80, sweep_percentile=75)

    # Build baseline distribution.
    for i in range(25):
        px = 100.0 + i * 0.25
        snapshot = OrderBookSnapshot(
            ts=datetime.now(timezone.utc),
            mid=px,
            bids={px - 0.25: 10.0, px - 0.5: 8.0},
            asks={px + 0.25: 9.5, px + 0.5: 7.0},
            last_trade_price=px + 0.25,
            last_trade_size=5.0 + (i % 3),
            last_trade_side="buy",
        )
        engine.ingest(snapshot)

    whale = OrderBookSnapshot(
        ts=datetime.now(timezone.utc),
        mid=110.0,
        bids={109.75: 11.0, 109.5: 8.0},
        asks={110.25: 9.0, 110.5: 7.5},
        last_trade_price=110.25,
        last_trade_size=40.0,
        last_trade_side="buy",
    )
    engine.ingest(whale)
    assert engine.last_signals.whale_buy is True

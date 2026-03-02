from datetime import datetime, timezone

from bookmap_engine.app_streamlit import _derive_bridge_decision
from bookmap_engine.core import BookmapEngine, OrderBookSnapshot


def _snapshot(mid: float, size: float = 10.0) -> OrderBookSnapshot:
    bids = {mid - 0.25: size, mid - 0.5: size * 0.8}
    asks = {mid + 0.25: size * 0.9, mid + 0.5: size * 0.7}
    return OrderBookSnapshot(
        ts=datetime.now(timezone.utc),
        mid=mid,
        bids=bids,
        asks=asks,
        last_trade_price=mid + 0.25,
        last_trade_size=size * 0.2,
        last_trade_side="buy",
    )


def test_derive_bridge_decision_adaptive_mode_runs():
    engine = BookmapEngine(levels=80, history=200)
    for i in range(24):
        engine.ingest(_snapshot(20000.0 + (i * 0.25), size=12.0 + i))
    sig = engine.last_signals
    decision, notes = _derive_bridge_decision(
        sig,
        quiet_mode=False,
        engine=engine,
        decision_mode="Adaptive Objective",
        min_score=2.0,
    )
    assert decision in {"GO_LONG", "GO_SHORT", "NO_TRADE"}
    assert isinstance(notes, str)
    assert "mode=adaptive" in notes or "confidence<" in notes


def test_derive_bridge_decision_classic_mode_runs():
    engine = BookmapEngine(levels=60, history=120)
    for i in range(12):
        engine.ingest(_snapshot(1000.0 + (i * 0.1), size=8.0 + i))
    sig = engine.last_signals
    decision, notes = _derive_bridge_decision(
        sig,
        quiet_mode=False,
        engine=engine,
        decision_mode="Classic Votes",
        min_score=2.0,
    )
    assert decision in {"GO_LONG", "GO_SHORT", "NO_TRADE"}
    assert isinstance(notes, str)

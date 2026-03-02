import json
from datetime import datetime, timezone
from pathlib import Path

from bookmap_engine.feed import (
    ExternalL2BridgeConfig,
    ExternalL2BridgeFeed,
    ReplayFeedConfig,
    ReplayOrderBookFeed,
)


def _snapshot_record(price: float) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mid": price,
        "bids": {str(price - 0.25): 12.0, str(price - 0.5): 8.0},
        "asks": {str(price + 0.25): 10.0, str(price + 0.5): 6.0},
        "last_trade_price": price + 0.25,
        "last_trade_size": 5.0,
        "last_trade_side": "buy",
    }


def test_external_l2_bridge_feed_reads_snapshot(tmp_path: Path):
    p = tmp_path / "live_l2_snapshot.json"
    p.write_text(json.dumps(_snapshot_record(25000.0)), encoding="utf-8")
    feed = ExternalL2BridgeFeed(ExternalL2BridgeConfig(path=str(p), stale_after_seconds=30))
    snap = feed.next_snapshot()
    assert snap.mid == 25000.0
    assert len(snap.bids) == 2
    assert len(snap.asks) == 2


def test_replay_feed_iterates_and_loops(tmp_path: Path):
    p = tmp_path / "replay.jsonl"
    rows = [_snapshot_record(100.0), _snapshot_record(101.0)]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    feed = ReplayOrderBookFeed(ReplayFeedConfig(path=str(p), loop=True))
    first = feed.next_snapshot()
    second = feed.next_snapshot()
    third = feed.next_snapshot()
    assert first.mid == 100.0
    assert second.mid == 101.0
    assert third.mid == 100.0

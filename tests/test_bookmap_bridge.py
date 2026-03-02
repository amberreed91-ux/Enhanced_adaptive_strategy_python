from pathlib import Path

from bookmap_engine.bridge import (
    BookmapBridgeSignal,
    bridge_signal_age_seconds,
    read_bridge_signal,
    utc_now_iso,
    write_bridge_signal,
)


def test_bridge_write_and_read(tmp_path: Path):
    p = tmp_path / "bookmap_signal.json"
    payload = BookmapBridgeSignal(
        timestamp_utc=utc_now_iso(),
        source="Synthetic",
        symbol="BTCUSDT",
        profile="balanced",
        decision="GO_LONG",
        confidence=77.0,
        imbalance=0.12,
        whale_buy=True,
        whale_sell=False,
        whale_size=50.0,
        whale_threshold=30.0,
        sweep_up=True,
        sweep_down=False,
        absorption_bid=True,
        absorption_ask=False,
        notes="test",
    )
    write_bridge_signal(p, payload)
    data = read_bridge_signal(p)
    assert data is not None
    assert data["decision"] == "GO_LONG"
    assert data["symbol"] == "BTCUSDT"


def test_bridge_age_is_finite(tmp_path: Path):
    p = tmp_path / "bookmap_signal.json"
    payload = BookmapBridgeSignal(
        timestamp_utc=utc_now_iso(),
        source="Synthetic",
        symbol="BTCUSDT",
        profile="balanced",
        decision="NO_TRADE",
        confidence=10.0,
        imbalance=0.0,
        whale_buy=False,
        whale_sell=False,
        whale_size=1.0,
        whale_threshold=20.0,
        sweep_up=False,
        sweep_down=False,
        absorption_bid=False,
        absorption_ask=False,
    )
    write_bridge_signal(p, payload)
    data = read_bridge_signal(p)
    assert data is not None
    age = bridge_signal_age_seconds(data)
    assert age >= 0.0
    assert age < 10.0

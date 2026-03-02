from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class BookmapBridgeSignal:
    timestamp_utc: str
    source: str
    symbol: str
    profile: str
    decision: str
    confidence: float
    imbalance: float
    whale_buy: bool
    whale_sell: bool
    whale_size: float
    whale_threshold: float
    sweep_up: bool
    sweep_down: bool
    absorption_bid: bool
    absorption_ask: bool
    notes: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_bridge_signal(path: str | Path, payload: BookmapBridgeSignal) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(asdict(payload), f, indent=2)


def read_bridge_signal(path: str | Path) -> Optional[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def bridge_signal_age_seconds(data: Dict[str, Any]) -> float:
    ts_raw = data.get("timestamp_utc")
    if not ts_raw:
        return float("inf")
    try:
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (now - ts.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        return float("inf")

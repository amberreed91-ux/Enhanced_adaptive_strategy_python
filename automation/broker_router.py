from __future__ import annotations

import fnmatch
from typing import Any, Dict, List


def _normalize_broker_name(raw: Any, default: str = "") -> str:
    value = str(raw or "").strip().lower()
    if not value:
        value = str(default or "").strip().lower()
    normalized = value.replace("-", "_").replace(" ", "_")
    if normalized in {"realninja", "real_ninja"}:
        return "ninjatrader"
    return normalized


class BrokerRouter:
    """Routes symbols to brokers using wildcard rules."""

    def __init__(self, cfg: Any):
        self.default_broker = _normalize_broker_name(
            cfg.get("automation.broker_routing.default_broker", "tradovate"),
            default="tradovate",
        )
        self.rules: List[Dict[str, str]] = cfg.get("automation.broker_routing.rules", []) or []

    def resolve(self, symbol: str) -> Dict[str, str]:
        sym = (symbol or "").upper().strip()
        for rule in self.rules:
            pattern = str(rule.get("pattern", "")).upper().strip()
            if pattern and fnmatch.fnmatch(sym, pattern):
                return {
                    "broker": _normalize_broker_name(rule.get("broker", self.default_broker), default=self.default_broker),
                    "profile": str(rule.get("profile", "default")),
                    "pattern": pattern,
                }
        return {"broker": self.default_broker, "profile": "default", "pattern": "*"}

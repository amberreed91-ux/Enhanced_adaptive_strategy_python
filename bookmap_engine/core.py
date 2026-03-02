from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class OrderBookSnapshot:
    ts: datetime
    mid: float
    bids: Dict[float, float]
    asks: Dict[float, float]
    last_trade_price: float
    last_trade_size: float
    last_trade_side: str


@dataclass
class BookmapSignals:
    imbalance: float
    sweep_up: bool
    sweep_down: bool
    absorption_bid: bool
    absorption_ask: bool
    whale_buy: bool
    whale_sell: bool
    whale_size: float
    whale_threshold: float
    confidence: float


class BookmapEngine:
    """Maintains heatmap state and simple microstructure signals."""

    def __init__(self, levels: int = 60, history: int = 180) -> None:
        self.levels = levels
        self.history = history
        self.snapshots: List[OrderBookSnapshot] = []
        self.mid_prices: List[float] = []
        self.trade_prices: List[float] = []
        self.trade_sizes: List[float] = []
        self.trade_sides: List[str] = []
        self.heatmap = np.zeros((history, levels), dtype=np.float32)
        self.price_grid: np.ndarray | None = None
        self.last_signals = BookmapSignals(
            imbalance=0.0,
            sweep_up=False,
            sweep_down=False,
            absorption_bid=False,
            absorption_ask=False,
            whale_buy=False,
            whale_sell=False,
            whale_size=0.0,
            whale_threshold=0.0,
            confidence=0.0,
        )
        self.whale_percentile = 97
        self.whale_min_size = 25.0
        self.absorption_percentile = 80
        self.sweep_percentile = 75

    def set_signal_config(
        self,
        whale_percentile: int,
        whale_min_size: float,
        absorption_percentile: int,
        sweep_percentile: int,
    ) -> None:
        self.whale_percentile = int(np.clip(whale_percentile, 80, 99))
        self.whale_min_size = max(1.0, whale_min_size)
        self.absorption_percentile = int(np.clip(absorption_percentile, 60, 99))
        self.sweep_percentile = int(np.clip(sweep_percentile, 60, 99))

    def ingest(self, snapshot: OrderBookSnapshot) -> None:
        self.snapshots.append(snapshot)
        self.mid_prices.append(snapshot.mid)
        self.trade_prices.append(snapshot.last_trade_price)
        self.trade_sizes.append(snapshot.last_trade_size)
        self.trade_sides.append(snapshot.last_trade_side)
        if len(self.snapshots) > self.history:
            self.snapshots = self.snapshots[-self.history :]
            self.mid_prices = self.mid_prices[-self.history :]
            self.trade_prices = self.trade_prices[-self.history :]
            self.trade_sizes = self.trade_sizes[-self.history :]
            self.trade_sides = self.trade_sides[-self.history :]

        self._update_heatmap(snapshot)
        self.last_signals = self._compute_signals(snapshot)

    def _update_heatmap(self, snapshot: OrderBookSnapshot) -> None:
        price_levels = sorted(set(snapshot.bids.keys()) | set(snapshot.asks.keys()))
        if not price_levels:
            return
        diffs = np.diff(np.array(price_levels, dtype=np.float64))
        diffs = diffs[diffs > 0]
        if diffs.size > 0:
            tick = float(np.median(diffs))
        else:
            tick = max(1e-6, abs(float(snapshot.mid)) * 1e-6)

        # Build a stable, centered price grid for this snapshot.
        # This keeps row indexing coherent across symbols and avoids
        # arbitrary reindexing from sorted level slices.
        center = float(snapshot.mid)
        half = self.levels // 2
        grid = np.array([center + (i - half) * tick for i in range(self.levels)], dtype=np.float64)
        self.price_grid = grid

        row = np.zeros((self.levels,), dtype=np.float32)
        max_sz = 1e-9

        def _accumulate(levels: Dict[float, float]) -> None:
            nonlocal max_sz
            for px, sz in levels.items():
                idx = int(round((float(px) - center) / tick)) + half
                if 0 <= idx < self.levels:
                    row[idx] += float(sz)
                    if row[idx] > max_sz:
                        max_sz = float(row[idx])

        _accumulate(snapshot.bids)
        _accumulate(snapshot.asks)

        # Log transform keeps visuals readable and less noisy than raw size.
        row = np.log1p(row) / np.log1p(max_sz)
        self.heatmap = np.roll(self.heatmap, -1, axis=0)
        self.heatmap[-1, :] = row

    def _compute_signals(self, snapshot: OrderBookSnapshot) -> BookmapSignals:
        bid_total = float(sum(snapshot.bids.values()))
        ask_total = float(sum(snapshot.asks.values()))
        total = bid_total + ask_total
        imbalance = 0.0 if total <= 0 else (bid_total - ask_total) / total

        sweep_up = False
        sweep_down = False
        absorption_bid = False
        absorption_ask = False
        whale_buy = False
        whale_sell = False
        whale_size = float(snapshot.last_trade_size)
        whale_threshold = self.whale_min_size

        if len(self.trade_prices) >= 3:
            t0 = self.trade_prices[-1]
            t2 = self.trade_prices[-3]
            px_move = t0 - t2
            total_recent_size = self.trade_sizes[-1] + self.trade_sizes[-2] + self.trade_sizes[-3]
            sweep_cutoff = np.percentile(self.trade_sizes, self.sweep_percentile)
            sweep_up = px_move > 0 and total_recent_size > sweep_cutoff
            sweep_down = px_move < 0 and total_recent_size > sweep_cutoff

        # Absorption heuristic: large aggressive trade without follow-through price movement.
        if len(self.trade_prices) >= 2 and len(self.trade_sizes) >= 2:
            last_sz = self.trade_sizes[-1]
            prev_sz = self.trade_sizes[-2]
            last_move = self.trade_prices[-1] - self.trade_prices[-2]
            absorb_cutoff = np.percentile(self.trade_sizes, self.absorption_percentile)
            big_hit = last_sz > max(absorb_cutoff, prev_sz)
            absorption_ask = big_hit and self.trade_sides[-1] == "buy" and last_move <= 0
            absorption_bid = big_hit and self.trade_sides[-1] == "sell" and last_move >= 0

        if len(self.trade_sizes) >= 20:
            whale_cutoff = float(np.percentile(self.trade_sizes[-200:], self.whale_percentile))
            whale_threshold = max(self.whale_min_size, whale_cutoff)
        whale_buy = snapshot.last_trade_side == "buy" and snapshot.last_trade_size >= whale_threshold
        whale_sell = snapshot.last_trade_side == "sell" and snapshot.last_trade_size >= whale_threshold

        score = 0.0
        score += min(35.0, abs(imbalance) * 70.0)
        score += 20.0 if sweep_up or sweep_down else 0.0
        score += 18.0 if absorption_bid or absorption_ask else 0.0
        score += 27.0 if whale_buy or whale_sell else 0.0
        confidence = float(min(100.0, score))

        return BookmapSignals(
            imbalance=imbalance,
            sweep_up=sweep_up,
            sweep_down=sweep_down,
            absorption_bid=absorption_bid,
            absorption_ask=absorption_ask,
            whale_buy=whale_buy,
            whale_sell=whale_sell,
            whale_size=whale_size,
            whale_threshold=whale_threshold,
            confidence=confidence,
        )

    def latest_ladder(self, depth: int = 12) -> List[Tuple[str, float, float]]:
        if not self.snapshots:
            return []
        snap = self.snapshots[-1]
        bids = sorted(snap.bids.items(), key=lambda x: x[0], reverse=True)[:depth]
        asks = sorted(snap.asks.items(), key=lambda x: x[0])[:depth]
        ladder: List[Tuple[str, float, float]] = []
        for px, sz in asks:
            ladder.append(("ask", px, sz))
        for px, sz in bids:
            ladder.append(("bid", px, sz))
        return ladder

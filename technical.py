"""
Core technical indicators matching Pine Script implementation.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional
from numba import jit


@jit(nopython=True)
def _calc_atr_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Numba-optimized ATR calculation."""
    n = len(high)
    tr = np.zeros(n)
    atr = np.zeros(n)

    # Calculate True Range
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr[i] = max(hl, hc, lc)

    # Calculate ATR (RMA/SMMA)
    atr[period-1] = np.mean(tr[1:period])
    alpha = 1.0 / period

    for i in range(period, n):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1]

    return atr


class TechnicalIndicators:
    """
    Technical indicators matching Pine Script strategy.
    Optimized with NumPy/Numba for performance.
    """

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Average True Range.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period

        Returns:
            ATR series
        """
        atr_values = _calc_atr_numba(
            high.values, 
            low.values, 
            close.values, 
            period
        )
        return pd.Series(atr_values, index=close.index, name='atr')

    @staticmethod
    def efficiency_ratio(close: pd.Series, period: int = 20) -> pd.Series:
        """
        Kaufman's Efficiency Ratio.

        Args:
            close: Close prices
            period: Lookback period

        Returns:
            Efficiency ratio (0-1)
        """
        change = (close - close.shift(period)).abs()
        volatility = (close - close.shift(1)).abs().rolling(period).sum()
        efficiency = change / volatility
        efficiency = efficiency.fillna(0).clip(0, 1)
        return efficiency.rename('efficiency_ratio')

    @staticmethod
    def premium_discount_zones(
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series,
        lookback: int = 50
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Calculate Premium/Discount zones (DRE concept).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            lookback: Swing lookback period

        Returns:
            Tuple of (pd_high, pd_low, pd_mid, in_premium, in_discount)
        """
        # Calculate swing high/low
        pd_high = high.rolling(lookback, center=False).max()
        pd_low = low.rolling(lookback, center=False).min()
        pd_mid = (pd_high + pd_low) / 2

        # Determine if price is in premium or discount
        in_premium = close > pd_mid
        in_discount = close < pd_mid

        return pd_high, pd_low, pd_mid, in_premium, in_discount

    @staticmethod
    def market_structure(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        lookback: int = 50
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Detect market structure (Break of Structure).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            lookback: Lookback period

        Returns:
            Tuple of (structure_bullish, structure_bearish, last_swing_high, last_swing_low)
        """
        # Simple swing detection
        # Use trailing windows only to avoid lookahead bias during incremental backtests.
        window = max(2, lookback // 2)
        swing_high = high.rolling(window, center=False).max()
        swing_low = low.rolling(window, center=False).min()

        # Detect breaks
        structure_bullish = close > swing_high.shift(1)
        structure_bearish = close < swing_low.shift(1)

        last_swing_high = swing_high.ffill()
        last_swing_low = swing_low.ffill()



        return structure_bullish, structure_bearish, last_swing_high, last_swing_low

    @staticmethod
    def breaker_blocks(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        structure_bullish: pd.Series,
        structure_bearish: pd.Series,
        lookback: int = 10
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Identify breaker blocks (failed order blocks).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            structure_bullish: Bullish structure breaks
            structure_bearish: Bearish structure breaks
            lookback: Lookback for breaker detection

        Returns:
            Tuple of (breaker_bull_active, breaker_bear_active, breaker_bull_level, breaker_bear_level)
        """
        breaker_bull_level = pd.Series(np.nan, index=close.index)
        breaker_bear_level = pd.Series(np.nan, index=close.index)
        breaker_bull_age = pd.Series(0, index=close.index)
        breaker_bear_age = pd.Series(0, index=close.index)

        for i in range(lookback, len(close)):
            # Bullish breaker: bearish candle followed by bullish break
            if structure_bullish.iloc[i]:
                # Find last bearish candle
                for j in range(i-1, max(0, i-lookback), -1):
                    if close.iloc[j] < close.iloc[j-1]:
                        breaker_bull_level.iloc[i] = high.iloc[j]
                        breaker_bull_age.iloc[i] = 0
                        break

            # Bearish breaker: bullish candle followed by bearish break
            if structure_bearish.iloc[i]:
                for j in range(i-1, max(0, i-lookback), -1):
                    if close.iloc[j] > close.iloc[j-1]:
                        breaker_bear_level.iloc[i] = low.iloc[j]
                        breaker_bear_age.iloc[i] = 0
                        break

        # Forward fill and age
        breaker_bull_level = breaker_bull_level.fillna(method='ffill')
        breaker_bear_level = breaker_bear_level.fillna(method='ffill')

        breaker_bull_active = ~breaker_bull_level.isna()
        breaker_bear_active = ~breaker_bear_level.isna()

        return breaker_bull_active, breaker_bear_active, breaker_bull_level, breaker_bear_level

    @staticmethod
    def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Relative volume (current / average).

        Args:
            volume: Volume series
            period: Average period

        Returns:
            Relative volume
        """
        avg_volume = volume.rolling(period).mean()
        rvol = volume / avg_volume
        return rvol.fillna(1.0).rename('rvol')

    @staticmethod
    def volume_profile(
        close: pd.Series,
        volume: pd.Series,
        bins: int = 20
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Simple volume profile (POC and VAL).

        Args:
            close: Close prices
            volume: Volume
            bins: Number of price bins

        Returns:
            Tuple of (poc, val) - Point of Control and Value Area Low
        """
        # This is a simplified version - full implementation would use TPO
        hist, bin_edges = np.histogram(close, bins=bins, weights=volume)
        poc_idx = np.argmax(hist)
        poc = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2

        # Value area (70% of volume)
        total_vol = hist.sum()
        cumsum = np.cumsum(hist)
        val_idx = np.searchsorted(cumsum, total_vol * 0.15)
        val = (bin_edges[val_idx] + bin_edges[val_idx + 1]) / 2

        poc_series = pd.Series(poc, index=close.index, name='poc')
        val_series = pd.Series(val, index=close.index, name='val')

        return poc_series, val_series

    @staticmethod
    def volatility_percentile(atr: pd.Series, period: int = 100) -> pd.Series:
        """
        ATR percentile rank.

        Args:
            atr: ATR series
            period: Lookback period

        Returns:
            Percentile (0-100)
        """
        percentile = atr.rolling(period).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
            raw=False
        )
        return percentile.fillna(50).rename('vol_percentile')

    @staticmethod
    def htf_bias(
        close: pd.Series,
        sma_period: int = 50,
        atr: pd.Series = None,
        deadband_mult: float = 0.2
    ) -> pd.Series:
        """
        Higher timeframe bias (trend direction).

        Args:
            close: Close prices
            sma_period: SMA period
            atr: ATR for deadband (optional)
            deadband_mult: Deadband multiplier

        Returns:
            Bias series (1=bullish, -1=bearish, 0=neutral)
        """
        sma = close.rolling(sma_period).mean()
        diff = close - sma

        if atr is not None:
            threshold = atr * deadband_mult
            bias = pd.Series(0, index=close.index)
            bias[diff > threshold] = 1
            bias[diff < -threshold] = -1
        else:
            bias = pd.Series(0, index=close.index)
            bias[diff > 0] = 1
            bias[diff < 0] = -1

        return bias.rename('htf_bias')

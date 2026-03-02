"""
Main strategy engine coordinating all components.
Replicates Pine Script logic with Python enhancements.
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from loguru import logger

from mytypes import (
    Regime, SignalDirection, MarketState, Signal, Position,
    OrderType, RLState
)
from bookmap_engine.bridge import read_bridge_signal, bridge_signal_age_seconds

from config import get_config
from technical import TechnicalIndicators
from regime_classifier import RegimeClassifier
from rl_optimizer import RLExecutionOptimizer
from manager import PortfolioManager

class StrategyEngine:
    """
    Main adaptive strategy engine.
    Integrates all modules: indicators, ML regime detection, RL execution, portfolio management.
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize strategy engine with configuration."""
        self.config = get_config()

        # Initialize components
        self.regime_classifier = RegimeClassifier(
            confidence_threshold=self.config.get('ml_regime.confidence_threshold', 0.65),
            filter_rapid_switches=self.config.get('ml_regime.filter_rapid_switches', True),
            min_bars_between_switches=self.config.get('ml_regime.min_bars_between_switches', 5)
        )

        self.rl_optimizer = RLExecutionOptimizer(
            algorithm=self.config.get('rl_execution.algorithm', 'PPO'),
            learning_rate=self.config.get('rl_execution.learning_rate', 0.0003),
            gamma=self.config.get('rl_execution.gamma', 0.99),
            reward_function=self.config.get('rl_execution.reward_function', 'sharpe_weighted')
        )

        self.portfolio_manager = PortfolioManager(
            symbols=self.config.get('portfolio.symbols', ['MGC1!']),
            correlation_lookback=self.config.get('portfolio.correlation_lookback', 50),
            max_correlation_threshold=self.config.get('portfolio.max_correlation_threshold', 0.7)
        )

        # State variables (matching Pine Script vars)
        self.current_regime = Regime.RANGING
        self.regime_confidence = 50.0
        self.is_expansion = False
        self.is_compression = False
        self.vol_percentile = 50.0

        # Position tracking
        self.current_position: Optional[Position] = None
        self.daily_trade_count = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.last_trade_day = 0

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.last_entry_imbalance = 0.0
        self.last_entry_rvol = 0.0

        logger.info("StrategyEngine initialized")

    def _bookmap_bridge_allows(self, direction: SignalDirection) -> Tuple[bool, str]:
        """Optional external gate from Bookmap bridge file."""
        if not self.config.get('bookmap_bridge.enabled', False):
            return True, "bridge_disabled"

        signal_path = self.config.get('bookmap_bridge.signal_file', 'data/bookmap_signal.json')
        profile = str(self.config.get('bookmap_bridge.profile', 'balanced')).lower()

        if profile == "strict":
            fail_open = False
            max_age = 8.0
            min_conf = 70.0
            require_whale = True
        elif profile == "permissive":
            fail_open = True
            max_age = 30.0
            min_conf = 45.0
            require_whale = False
        elif profile == "balanced":
            fail_open = True
            max_age = 20.0
            min_conf = 55.0
            require_whale = False
        else:
            # custom: use explicit config values
            fail_open = self.config.get('bookmap_bridge.fail_open', True)
            max_age = float(self.config.get('bookmap_bridge.max_age_seconds', 20))
            min_conf = float(self.config.get('bookmap_bridge.min_confidence', 55))
            require_whale = self.config.get('bookmap_bridge.require_whale', False)

        bridge = read_bridge_signal(signal_path)
        if bridge is None:
            return (True, "bridge_missing_fail_open") if fail_open else (False, "bridge_missing")

        age = bridge_signal_age_seconds(bridge)
        if age > max_age:
            return (True, "bridge_stale_fail_open") if fail_open else (False, f"bridge_stale:{age:.1f}s")

        confidence = float(bridge.get("confidence", 0.0))
        if confidence < min_conf:
            return False, f"bridge_low_conf:{confidence:.1f}"

        decision = str(bridge.get("decision", "NO_TRADE")).upper()
        whale_buy = bool(bridge.get("whale_buy", False))
        whale_sell = bool(bridge.get("whale_sell", False))

        if direction == SignalDirection.LONG:
            if decision != "GO_LONG":
                return False, f"bridge_decision:{decision}"
            if require_whale and not whale_buy:
                return False, "bridge_no_whale_buy"
            return True, "bridge_long_ok"

        if direction == SignalDirection.SHORT:
            if decision != "GO_SHORT":
                return False, f"bridge_decision:{decision}"
            if require_whale and not whale_sell:
                return False, "bridge_no_whale_sell"
            return True, "bridge_short_ok"

        return True, "bridge_flat"

    def train_models(self, historical_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train ML models on historical data.

        Args:
            historical_data: OHLCV dataframe with sufficient history

        Returns:
            Training metrics
        """
        logger.info("Training ML models...")

        metrics = {}

        # Train regime classifier
        if self.config.get('ml_regime.enabled', True):
            regime_metrics = self.regime_classifier.train(historical_data)
            metrics['regime_classifier'] = regime_metrics

        # Train RL optimizer
        if self.config.get('rl_execution.enabled', True):
            # Prepare data with features
            prepared_data = self._prepare_rl_data(historical_data)
            rl_metrics = self.rl_optimizer.train(prepared_data, total_timesteps=50000)
            metrics['rl_optimizer'] = rl_metrics

        logger.info("Model training complete")
        return metrics

    def _prepare_rl_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features needed for RL training."""
        data = df.copy()

        # Add ATR
        data['atr'] = TechnicalIndicators.atr(
            data['high'], data['low'], data['close'], 
            self.config.get('general.atr_lookback', 14)
        )

        # Add order flow imbalance (simplified - would use real order book in live)
        data['order_flow_imbalance'] = (data['close'] - data['open']) / (data['high'] - data['low'] + 1e-10)
        data['order_flow_imbalance'] = data['order_flow_imbalance'].clip(-1, 1)

        # Add spread estimate (simplified)
        data['spread_pct'] = 0.01  # 1 bp default

        # Add regime encoding
        regime_map = {Regime.TRENDING: 0, Regime.RANGING: 1, Regime.VOLATILE: 2}
        if 'regime' in data.columns:
            data['regime_encoded'] = data['regime'].map(regime_map).fillna(1)
        else:
            data['regime_encoded'] = 1

        return data

    def process_bar(self, bar: pd.Series, historical_data: pd.DataFrame) -> Optional[Signal]:
        """
        Process new bar and generate trading signals.

        Args:
            bar: Current OHLCV bar
            historical_data: Recent historical data for indicators

        Returns:
            Signal if conditions met, else None
        """
        # Calculate indicators
        market_state = self._calculate_market_state(bar, historical_data)

        # Update portfolio correlations
        if self.config.get('portfolio.enabled', True):
            self._update_portfolio(bar)

        # Check filters
        if not self._check_filters(bar, market_state):
            return None

        # Calculate confluence score
        confluence_score = self._calculate_confluence(bar, historical_data, market_state)

        # Determine signal direction
        signal_direction = self._determine_signal_direction(bar, market_state, confluence_score, historical_data)

        if signal_direction == SignalDirection.FLAT:
            return None

        bridge_ok, bridge_reason = self._bookmap_bridge_allows(signal_direction)
        if not bridge_ok:
            logger.debug(f"Bookmap bridge blocked signal: {bridge_reason}")
            return None

        # Confluence threshold: require minimum quality before trading
        threshold = self._get_confluence_threshold(market_state.regime)
        if confluence_score < threshold:
            return None


        # Calculate position sizing
        position_size = self._calculate_position_size(market_state, confluence_score)

        # Calculate stop and targets
        stop_loss = self._calculate_stop_loss(bar.close, market_state, signal_direction)
        tp1, tp2, tp3 = self._calculate_take_profits(bar.close, market_state, signal_direction)

        # Create signal
        signal = Signal(
            timestamp=bar.name if isinstance(bar.name, datetime) else datetime.now(),
            symbol=self.config.get('instrument.symbol', 'MGC1!'),
            direction=signal_direction,
            confluence_score=confluence_score,
            regime=market_state.regime,
            entry_price=bar.close,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            position_size=position_size,
            risk_amount=abs(bar.close - stop_loss) * position_size,
            metadata={
                'vol_percentile': market_state.vol_percentile,
                'efficiency': market_state.efficiency_ratio,
                'htf_bias': market_state.htf_bias,
                'bookmap_bridge': bridge_reason,
                'entry_imbalance': self.last_entry_imbalance,
                'entry_rvol': self.last_entry_rvol,
            }
        )

        logger.info(f"Signal generated: {signal_direction.value} at {bar.close:.2f}, "
                   f"confluence={confluence_score}, regime={market_state.regime}")

        return signal

    def _calculate_market_state(self, bar: pd.Series, historical_data: pd.DataFrame) -> MarketState:
        """Calculate current market state."""
        # Calculate ATR
        atr = TechnicalIndicators.atr(
            historical_data['high'], 
            historical_data['low'], 
            historical_data['close'],
            self.config.get('general.atr_lookback', 14)
        ).iloc[-1]

        # Calculate efficiency ratio
        efficiency = TechnicalIndicators.efficiency_ratio(
            historical_data['close'],
            self.config.get('general.efficiency_lookback', 20)
        ).iloc[-1]

        # Detect regime (ML-based if enabled)
        if self.config.get('ml_regime.enabled', True) and self.regime_classifier.is_trained:
            regimes, confidences = self.regime_classifier.predict(historical_data, return_confidence=True)
            regime = regimes.iloc[-1]
            if confidences is not None:
                regime_confidence = confidences['max_confidence'].iloc[-1] * 100
            else:
                regime_confidence = 50.0
        else:
            # Fallback rule-based
            regime, regime_confidence = self._rule_based_regime(efficiency, atr, historical_data)

        # Volatility percentile
        vol_percentile = TechnicalIndicators.volatility_percentile(
            pd.Series([atr] * len(historical_data), index=historical_data.index),
            100
        ).iloc[-1]

        # Expansion/compression
        is_expansion = vol_percentile >= self.config.get('volatility.expansion_threshold', 70)
        is_compression = vol_percentile <= self.config.get('volatility.compression_threshold', 30)

        # HTF bias
        htf_bias = TechnicalIndicators.htf_bias(
            historical_data['close'],
            self.config.get('htf_bias.sma_length', 50)
        ).iloc[-1]

        # DRE concepts
        pd_high, pd_low, pd_mid, in_premium, in_discount = TechnicalIndicators.premium_discount_zones(
            historical_data['high'],
            historical_data['low'],
            historical_data['close'],
            self.config.get('dre.pd_lookback', 50)
        )

        structure_bullish, structure_bearish, _, _ = TechnicalIndicators.market_structure(
            historical_data['high'],
            historical_data['low'],
            historical_data['close'],
            self.config.get('dre.pd_lookback', 50)
        )

        return MarketState(
            timestamp=bar.name if isinstance(bar.name, datetime) else datetime.now(),
            symbol=self.config.get('instrument.symbol', 'MGC1!'),
            close=bar.close,
            atr=atr,
            regime=regime,
            regime_confidence=regime_confidence,
            vol_percentile=vol_percentile,
            is_expansion=is_expansion,
            is_compression=is_compression,
            efficiency_ratio=efficiency,
            htf_bias=int(htf_bias),
            in_premium=in_premium.iloc[-1],
            in_discount=in_discount.iloc[-1],
            structure_bullish=structure_bullish.iloc[-1],
            structure_bearish=structure_bearish.iloc[-1]
        )

    def _rule_based_regime(
        self, 
        efficiency: float, 
        atr: float, 
        historical_data: pd.DataFrame
    ) -> Tuple[Regime, float]:
        """Fallback rule-based regime detection."""
        vol_percentile = TechnicalIndicators.volatility_percentile(
            pd.Series([atr] * len(historical_data), index=historical_data.index),
            100
        ).iloc[-1]

        volatile_threshold = self.config.get('thresholds.volatile', 80)
        trending_threshold = self.config.get('thresholds.trending', 70)

        if vol_percentile >= volatile_threshold:
            return Regime.VOLATILE, 75.0
        elif efficiency * 100 >= trending_threshold:
            return Regime.TRENDING, 80.0
        else:
            return Regime.RANGING, 70.0

    def _check_filters(self, bar: pd.Series, market_state: MarketState) -> bool:
        """Check if filters allow trading."""
        # Session filter
        if self.config.get('session.use_filter', True):
            if not self._is_in_session(bar):
                return False

        # Daily limits
        if self.config.get('daily_limits.enabled', True):
            if self.daily_trade_count >= self.config.get('daily_limits.max_daily_trades', 10):
                return False

            if self.consecutive_losses >= self.config.get('daily_limits.max_consecutive_losses', 3):
                return False

        return True

    def _is_in_session(self, bar: pd.Series) -> bool:
        """Check if current time is within trading session."""
        ts = bar.name if isinstance(bar.name, (pd.Timestamp, datetime)) else datetime.now()
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        tz_name = str(self.config.get('session.timezone', 'America/New_York'))
        if ts.tzinfo is not None:
            try:
                ts_local = ts.astimezone(ZoneInfo(tz_name))
            except Exception:
                ts_local = ts
        else:
            ts_local = ts

        allowed_weekdays = self.config.get('session.allowed_weekdays', [0, 1, 2, 3, 4])
        try:
            weekday_set = {int(x) for x in allowed_weekdays}
        except Exception:
            weekday_set = {0, 1, 2, 3, 4}
        if ts_local.weekday() not in weekday_set:
            return False

        trade_sessions = str(self.config.get('session.trade_sessions', 'Both')).strip().lower()
        windows: List[Tuple[str, str]] = []
        if trade_sessions in ('both', 'london'):
            windows.append((str(self.config.get('session.london_start', '03:00')), str(self.config.get('session.london_end', '11:00'))))
        if trade_sessions in ('both', 'ny', 'newyork', 'new_york'):
            windows.append((str(self.config.get('session.ny_start', '09:30')), str(self.config.get('session.ny_end', '16:00'))))

        custom_windows = self.config.get('session.custom_windows', [])
        if isinstance(custom_windows, list):
            for item in custom_windows:
                if isinstance(item, str) and "-" in item:
                    left, right = item.split("-", 1)
                    windows.append((left.strip(), right.strip()))

        parsed_windows: List[Tuple[time, time]] = []
        for start_s, end_s in windows:
            try:
                parsed_windows.append((self._parse_hhmm(start_s), self._parse_hhmm(end_s)))
            except ValueError:
                continue

        if not parsed_windows:
            return True

        now_t = ts_local.time().replace(second=0, microsecond=0)
        return any(self._time_in_window(now_t, start_t, end_t) for start_t, end_t in parsed_windows)

    @staticmethod
    def _parse_hhmm(value: str) -> time:
        parts = value.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time '{value}'")
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour=hour, minute=minute)

    @staticmethod
    def _time_in_window(now_t: time, start_t: time, end_t: time) -> bool:
        if start_t <= end_t:
            return start_t <= now_t <= end_t
        return now_t >= start_t or now_t <= end_t

    def _to_session_tz(self, ts: Any) -> datetime:
        """Normalize timestamp into configured session timezone."""
        tz_name = str(self.config.get('session.timezone', 'America/New_York'))
        tz = ZoneInfo(tz_name)

        if isinstance(ts, pd.Timestamp):
            dt = ts.to_pydatetime()
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = datetime.now(tz)

        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        try:
            return dt.astimezone(tz)
        except Exception:
            return dt

    def _extract_last_asian_range(
        self,
        historical_data: pd.DataFrame,
        current_ts: Any,
    ) -> Optional[Tuple[float, float]]:
        """Return (asian_high, asian_low) for last completed Asian window."""
        if not isinstance(historical_data.index, pd.DatetimeIndex):
            return None

        session_start = str(self.config.get('ict_asian_sweep.session_start', '19:00'))
        session_end = str(self.config.get('ict_asian_sweep.session_end', '00:00'))
        start_t = self._parse_hhmm(session_start)
        end_t = self._parse_hhmm(session_end)
        cur_local = self._to_session_tz(current_ts)

        if (
            not bool(self.config.get('ict_asian_sweep.allow_during_asian_session', False))
            and self._time_in_window(cur_local.time(), start_t, end_t)
        ):
            return None

        session_end_local = datetime.combine(cur_local.date(), end_t, tzinfo=cur_local.tzinfo)
        if cur_local < session_end_local:
            session_end_local -= timedelta(days=1)

        if start_t <= end_t:
            session_start_local = datetime.combine(session_end_local.date(), start_t, tzinfo=cur_local.tzinfo)
        else:
            session_start_local = datetime.combine(
                session_end_local.date() - timedelta(days=1),
                start_t,
                tzinfo=cur_local.tzinfo,
            )

        idx = historical_data.index
        tz_name = str(self.config.get('session.timezone', 'America/New_York'))
        try:
            idx_local = idx.tz_localize(tz_name) if idx.tz is None else idx.tz_convert(tz_name)
        except Exception:
            return None

        mask = (idx_local >= session_start_local) & (idx_local < session_end_local)
        asian_df = historical_data.loc[mask]
        min_bars = int(self.config.get('ict_asian_sweep.min_asian_bars', 12))
        if len(asian_df) < max(1, min_bars):
            return None

        asian_high = float(asian_df['high'].max())
        asian_low = float(asian_df['low'].min())
        if not np.isfinite(asian_high) or not np.isfinite(asian_low) or asian_high <= asian_low:
            return None
        return asian_high, asian_low

    def _is_in_ict_kill_zone(self, ts: Any) -> bool:
        if not bool(self.config.get('ict_asian_sweep.require_kill_zone', True)):
            return True

        default_windows = ["03:00-06:00", "09:30-11:30"]
        windows = self.config.get('ict_asian_sweep.kill_zones', default_windows)
        if not isinstance(windows, list) or not windows:
            windows = default_windows

        ts_local = self._to_session_tz(ts)
        now_t = ts_local.time().replace(second=0, microsecond=0)
        for item in windows:
            if not isinstance(item, str) or "-" not in item:
                continue
            left, right = item.split("-", 1)
            try:
                if self._time_in_window(now_t, self._parse_hhmm(left.strip()), self._parse_hhmm(right.strip())):
                    return True
            except ValueError:
                continue
        return False

    def _ict_instrument_suffix(self) -> str:
        return "mnq" if bool(self.config.get('instrument.is_mnq', False)) else "mgc"

    def _detect_recent_fvg_ce(self, historical_data: pd.DataFrame, bullish: bool) -> Optional[float]:
        """
        Find the most recent 3-candle FVG and return its Consequent Encroachment (CE).
        Bullish FVG: high[i-2] < low[i]
        Bearish FVG: low[i-2] > high[i]
        """
        lookback = max(3, int(self.config.get('ict_asian_sweep.fvg_lookback_bars', 8)))
        window = historical_data.tail(lookback + 2)
        if len(window) < 3:
            return None

        highs = window['high'].to_list()
        lows = window['low'].to_list()
        n = len(window)
        for i in range(n - 1, 1, -1):
            hi_2 = float(highs[i - 2])
            lo_2 = float(lows[i - 2])
            hi_0 = float(highs[i])
            lo_0 = float(lows[i])
            if bullish and hi_2 < lo_0:
                return (hi_2 + lo_0) * 0.5
            if (not bullish) and lo_2 > hi_0:
                return (lo_2 + hi_0) * 0.5
        return None

    def _ict_asian_sweep_signal(
        self,
        bar: pd.Series,
        historical_data: pd.DataFrame,
        market_state: MarketState,
        confluence: int,
        imbalance: float,
        min_dir_imbalance: float,
        trend_up: bool,
        trend_down: bool,
    ) -> SignalDirection:
        """ICT Asian range sweep + reclaim entry logic for ranging regime."""
        if not bool(self.config.get('ict_asian_sweep.enabled', True)):
            return SignalDirection.FLAT

        if not self._is_in_ict_kill_zone(bar.name):
            return SignalDirection.FLAT

        levels = self._extract_last_asian_range(historical_data, bar.name)
        if levels is None:
            return SignalDirection.FLAT
        asian_high, asian_low = levels

        width = asian_high - asian_low
        if width <= 0:
            return SignalDirection.FLAT

        if market_state.atr > 0:
            width_atr = width / market_state.atr
            min_w = float(self.config.get('ict_asian_sweep.min_range_width_atr', 0.6))
            max_w = float(self.config.get('ict_asian_sweep.max_range_width_atr', 6.0))
            if width_atr < min_w or width_atr > max_w:
                return SignalDirection.FLAT

        lookback_bars = max(1, int(self.config.get('ict_asian_sweep.sweep_lookback_bars', 3)))
        recent = historical_data.tail(lookback_bars)
        if len(recent) == 0:
            return SignalDirection.FLAT

        inst = self._ict_instrument_suffix()
        sweep_buffer_atr = float(
            self.config.get(
                f'ict_asian_sweep.sweep_buffer_atr_{inst}',
                self.config.get('ict_asian_sweep.sweep_buffer_atr', 0.05),
            )
        )
        buffer = max(0.0, market_state.atr * sweep_buffer_atr)
        close = float(bar.close)
        open_ = float(bar.open)

        swept_low = float(recent['low'].min()) <= (asian_low - buffer)
        swept_high = float(recent['high'].max()) >= (asian_high + buffer)
        reclaimed_low = close > asian_low
        reclaimed_high = close < asian_high

        require_displacement = bool(self.config.get('ict_asian_sweep.require_displacement_candle', True))
        disp_atr_mult = float(self.config.get('ict_asian_sweep.min_displacement_atr', 0.10))
        body = abs(close - open_)
        displacement_ok = body >= (market_state.atr * disp_atr_mult)
        if require_displacement and not displacement_ok:
            return SignalDirection.FLAT

        range_long_min = int(
            self.config.get(
                f'ict_asian_sweep.range_long_entry_min_{inst}',
                self.config.get('thresholds.range_long_entry_min', 64),
            )
        )
        range_short_min = int(
            self.config.get(
                f'ict_asian_sweep.range_short_entry_min_{inst}',
                self.config.get('thresholds.range_short_entry_min', 64),
            )
        )
        dir_imbalance_min = float(
            self.config.get(
                f'ict_asian_sweep.min_directional_imbalance_{inst}',
                min_dir_imbalance,
            )
        )

        require_fvg_ce = bool(self.config.get('ict_asian_sweep.require_fvg_ce', False))
        if require_fvg_ce:
            ce_tolerance_atr = float(self.config.get('ict_asian_sweep.ce_tolerance_atr', 0.35))
            tol = max(0.0, market_state.atr * ce_tolerance_atr)
            bull_ce = self._detect_recent_fvg_ce(historical_data, bullish=True)
            bear_ce = self._detect_recent_fvg_ce(historical_data, bullish=False)
            long_fvg_ok = bool(bull_ce is not None and abs(close - float(bull_ce)) <= tol)
            short_fvg_ok = bool(bear_ce is not None and abs(close - float(bear_ce)) <= tol)
        else:
            long_fvg_ok = True
            short_fvg_ok = True

        require_pd = bool(self.config.get('ict_asian_sweep.require_pd_alignment', False))
        long_pd_ok = (not require_pd) or market_state.in_discount
        short_pd_ok = (not require_pd) or market_state.in_premium

        long_ok = (
            swept_low
            and reclaimed_low
            and close > open_
            and confluence >= range_long_min
            and imbalance >= dir_imbalance_min
            and not trend_down
            and long_pd_ok
            and long_fvg_ok
        )
        short_ok = (
            swept_high
            and reclaimed_high
            and close < open_
            and confluence >= range_short_min
            and imbalance <= -dir_imbalance_min
            and not trend_up
            and short_pd_ok
            and short_fvg_ok
        )

        if long_ok and not short_ok:
            direction = SignalDirection.LONG
        elif short_ok and not long_ok:
            direction = SignalDirection.SHORT
        elif long_ok and short_ok:
            direction = SignalDirection.LONG if imbalance >= 0 else SignalDirection.SHORT
        else:
            return SignalDirection.FLAT

        if bool(self.config.get('ict_asian_sweep.invert_signals', False)):
            return SignalDirection.SHORT if direction == SignalDirection.LONG else SignalDirection.LONG
        return direction

    def _estimate_bar_imbalance(self, historical_data: pd.DataFrame) -> float:
        """Estimate directional imbalance from recent candles in [-1, 1]."""
        if len(historical_data) == 0:
            return 0.0

        lookback = int(self.config.get('entry_quality.imbalance_lookback', 3))
        window = historical_data.tail(max(1, lookback))
        denom = (window['high'] - window['low']).replace(0, np.nan).fillna(1e-9)
        imbalance = ((window['close'] - window['open']) / denom).clip(-1.0, 1.0)
        val = float(imbalance.mean()) if len(imbalance) else 0.0
        return max(-1.0, min(1.0, val))

    def _trend_quality_gate(
        self,
        historical_data: pd.DataFrame,
        bar_close: float,
        market_state: MarketState,
        ema_fast_series: pd.Series,
        ema_slow_series: pd.Series,
        trend_up: bool,
        trend_down: bool,
    ) -> Tuple[bool, bool]:
        """Return (long_ok, short_ok) for trend entries based on quality constraints."""
        if not bool(self.config.get('trend_quality.enabled', True)):
            return True, True

        if len(ema_fast_series) < 2 or len(ema_slow_series) < 2:
            return False, False

        ema_fast = float(ema_fast_series.iloc[-1])
        ema_slow = float(ema_slow_series.iloc[-1])
        close_abs = max(abs(bar_close), 1e-9)

        spread_min_pct = float(self.config.get('trend_quality.ema_spread_min_pct', 0.00035))
        spread_pct = abs(ema_fast - ema_slow) / close_abs
        if spread_pct < spread_min_pct:
            return False, False

        slope_lb = int(self.config.get('trend_quality.ema_slope_lookback', 5))
        slope_lb = max(1, min(slope_lb, len(ema_fast_series) - 1))
        ema_prev = float(ema_fast_series.iloc[-1 - slope_lb])
        slope_pct = abs(ema_fast - ema_prev) / close_abs
        slope_min_pct = float(self.config.get('trend_quality.ema_slope_min_pct', 0.00012))
        if slope_pct < slope_min_pct:
            return False, False

        structure_lb = int(self.config.get('dre.pd_lookback', 50))
        struct_bull, struct_bear, _, _ = TechnicalIndicators.market_structure(
            historical_data['high'],
            historical_data['low'],
            historical_data['close'],
            structure_lb,
        )
        persist_n = max(1, int(self.config.get('trend_quality.structure_persistence_bars', 2)))
        tail_n = min(persist_n, len(struct_bull))
        bull_tail = struct_bull.tail(tail_n)
        bear_tail = struct_bear.tail(tail_n)
        long_structure_ok = bool((bull_tail.astype(bool)).all() and not (bear_tail.astype(bool)).any())
        short_structure_ok = bool((bear_tail.astype(bool)).all() and not (bull_tail.astype(bool)).any())

        buffer_atr = float(self.config.get('trend_quality.breakout_buffer_atr', 0.10))
        min_buffer = max(0.0, market_state.atr * buffer_atr)
        long_buffer_ok = (bar_close - ema_fast) >= min_buffer
        short_buffer_ok = (ema_fast - bar_close) >= min_buffer

        long_ok = trend_up and long_structure_ok and long_buffer_ok
        short_ok = trend_down and short_structure_ok and short_buffer_ok
        return long_ok, short_ok

    def _is_range_mean_revert_active(self, market_state: MarketState) -> bool:
        return (
            market_state.regime == Regime.RANGING
            and str(self.config.get('regime_split.range_mode', 'NO_TRADE')).upper() == "MEAN_REVERT"
        )

    def _calculate_confluence(
        self,
        bar: pd.Series,
        historical_data: pd.DataFrame,
        market_state: MarketState
    ) -> int:
        """Calculate confluence score (0-100)."""
        score = 0

        # Base score from regime confidence.
        # 0.7 keeps the score in a tradable range with the configured thresholds.
        score += int(market_state.regime_confidence * 0.7)

        # DRE alignment
        if self.config.get('dre.enabled', True):
            if market_state.structure_bullish and market_state.in_discount:
                score += self.config.get('dre.pd_weight_max', 15)
            elif market_state.structure_bearish and market_state.in_premium:
                score += self.config.get('dre.pd_weight_max', 15)

        # HTF bias alignment
        if market_state.htf_bias != 0:
            score += 10

        # Volume confirmation
        rvol = TechnicalIndicators.relative_volume(historical_data['volume'], 20).iloc[-1]
        if rvol >= self.config.get('volume.rvol_threshold', 1.2):
            score += 10

        # Reward clear structure.
        if market_state.structure_bullish or market_state.structure_bearish:
            score += 5

        return min(score, 100)

    def _get_confluence_threshold(self, regime: Regime) -> int:
        """Get confluence threshold for regime."""
        if regime == Regime.TRENDING:
            return int(self.config.get('thresholds.trending', 50)) + 8
        elif regime == Regime.VOLATILE:
            return int(self.config.get('thresholds.volatile', 60)) + 10
        else:
            return int(self.config.get('thresholds.ranging', 40)) + 8

    def _determine_signal_direction(
        self,
        bar: pd.Series,
        market_state: MarketState,
        confluence: int,
        historical_data: pd.DataFrame,
    ) -> SignalDirection:
        """Determine direction with regime split + strict entry quality filters."""
        min_atr_pct = float(self.config.get('general.min_atr_pct', 0.001))
        atr_pct = market_state.atr / max(abs(float(bar.close)), 1e-9)
        if atr_pct < min_atr_pct:
            return SignalDirection.FLAT

        rvol = float(TechnicalIndicators.relative_volume(historical_data['volume'], 20).iloc[-1])
        imbalance = self._estimate_bar_imbalance(historical_data)
        self.last_entry_rvol = rvol
        self.last_entry_imbalance = imbalance

        if bool(self.config.get('entry_quality.enabled', True)):
            min_rvol = float(self.config.get('entry_quality.min_rvol', 1.10))
            if rvol < min_rvol:
                return SignalDirection.FLAT

            min_abs_imbalance = float(self.config.get('entry_quality.min_abs_imbalance', 0.10))
            if abs(imbalance) < min_abs_imbalance:
                return SignalDirection.FLAT

        min_dir_imbalance = float(self.config.get('entry_quality.min_directional_imbalance', 0.06))

        fast_len = int(self.config.get('general.trend_fast_ema', 21))
        slow_len = int(self.config.get('general.trend_slow_ema', 55))
        macro_len = int(self.config.get('general.trend_macro_ema', 200))
        closes = historical_data['close']
        ema_fast_series = closes.ewm(span=max(2, fast_len), adjust=False).mean()
        ema_slow_series = closes.ewm(span=max(3, slow_len), adjust=False).mean()
        ema_macro_series = closes.ewm(span=max(5, macro_len), adjust=False).mean()
        ema_fast = float(ema_fast_series.iloc[-1])
        ema_slow = float(ema_slow_series.iloc[-1])
        ema_macro = float(ema_macro_series.iloc[-1])
        trend_up = ema_fast > ema_slow and ema_slow > ema_macro and float(bar.close) >= ema_fast
        trend_down = ema_fast < ema_slow and ema_slow < ema_macro and float(bar.close) <= ema_fast
        trend_long_quality_ok, trend_short_quality_ok = self._trend_quality_gate(
            historical_data=historical_data,
            bar_close=float(bar.close),
            market_state=market_state,
            ema_fast_series=ema_fast_series,
            ema_slow_series=ema_slow_series,
            trend_up=trend_up,
            trend_down=trend_down,
        )

        regime_split_enabled = bool(self.config.get('regime_split.enabled', True))
        range_mode = str(self.config.get('regime_split.range_mode', 'NO_TRADE')).upper()
        volatile_mode = str(self.config.get('regime_split.volatile_mode', 'NO_TRADE')).upper()

        if regime_split_enabled and market_state.regime == Regime.RANGING:
            if range_mode == "NO_TRADE":
                return SignalDirection.FLAT
            if range_mode == "ICT_ASIAN_SWEEP":
                return self._ict_asian_sweep_signal(
                    bar=bar,
                    historical_data=historical_data,
                    market_state=market_state,
                    confluence=confluence,
                    imbalance=imbalance,
                    min_dir_imbalance=min_dir_imbalance,
                    trend_up=trend_up,
                    trend_down=trend_down,
                )
            if range_mode == "MEAN_REVERT":
                range_max_eff = float(self.config.get('regime_split.range_max_efficiency_ratio', 0.45))
                if market_state.efficiency_ratio > range_max_eff:
                    return SignalDirection.FLAT
                range_long_min = int(self.config.get('thresholds.range_long_entry_min', 82))
                range_short_min = int(self.config.get('thresholds.range_short_entry_min', 82))
                if (
                    market_state.in_discount
                    and market_state.htf_bias >= 0
                    and confluence >= range_long_min
                    and imbalance >= min_dir_imbalance
                    and not trend_down
                ):
                    return SignalDirection.LONG
                if (
                    market_state.in_premium
                    and market_state.htf_bias <= 0
                    and confluence >= range_short_min
                    and imbalance <= -min_dir_imbalance
                    and not trend_up
                ):
                    return SignalDirection.SHORT
                return SignalDirection.FLAT
            if range_mode != "TREND_ONLY":
                # Any unknown/unsupported range mode defaults to safety.
                return SignalDirection.FLAT

        if regime_split_enabled and market_state.regime == Regime.VOLATILE and volatile_mode == "NO_TRADE":
            return SignalDirection.FLAT

        allow_trend_logic = market_state.regime in (Regime.TRENDING, Regime.VOLATILE) or (
            regime_split_enabled and market_state.regime == Regime.RANGING and range_mode == "TREND_ONLY"
        )
        if not allow_trend_logic:
            return SignalDirection.FLAT

        min_eff = float(self.config.get('general.min_efficiency_ratio', 0.50))
        if market_state.efficiency_ratio < min_eff:
            return SignalDirection.FLAT

        long_threshold = int(self.config.get('thresholds.long_entry_min', 92))
        short_threshold = int(
            self.config.get(
                'thresholds.short_entry_min_mnq' if self.config.get('instrument.is_mnq', False) else 'thresholds.short_entry_min_mgc',
                90,
            )
        )
        if market_state.regime == Regime.VOLATILE:
            long_threshold += 6
            short_threshold += 6

        if (
            market_state.structure_bullish
            and not market_state.structure_bearish
            and market_state.htf_bias > 0
            and confluence >= long_threshold
            and trend_up
            and trend_long_quality_ok
            and imbalance >= min_dir_imbalance
        ):
            return SignalDirection.LONG

        if (
            market_state.structure_bearish
            and not market_state.structure_bullish
            and market_state.htf_bias < 0
            and confluence >= short_threshold
            and trend_down
            and trend_short_quality_ok
            and imbalance <= -min_dir_imbalance
        ):
            return SignalDirection.SHORT

        # Only allow a bias-only entry when confluence is extremely strong.
        bias_only_threshold = int(self.config.get('thresholds.bias_only_min', 97))
        if confluence >= bias_only_threshold:
            if (
                market_state.htf_bias > 0
                and trend_up
                and trend_long_quality_ok
                and imbalance >= min_dir_imbalance
            ):
                return SignalDirection.LONG
            if (
                market_state.htf_bias < 0
                and trend_down
                and trend_short_quality_ok
                and imbalance <= -min_dir_imbalance
            ):
                return SignalDirection.SHORT

        return SignalDirection.FLAT

    def _calculate_position_size(self, market_state: MarketState, confluence: int) -> int:
        """Calculate position size based on regime and risk."""
        min_size = int(self.config.get('capital.min_position_size', 1))
        max_size = int(self.config.get('capital.max_position_size', 50))

        # Regime multiplier.
        if market_state.regime == Regime.TRENDING:
            multiplier = self.config.get('position_sizing.trending_multiplier', 1.0)
        elif market_state.regime == Regime.VOLATILE:
            multiplier = self.config.get('position_sizing.volatile_multiplier', 0.3)
        else:
            multiplier = self.config.get('position_sizing.ranging_multiplier', 0.8)

        # Risk-based base size from stop distance and instrument point value.
        stop_mult = self._get_stop_multiplier(market_state.regime)
        tick_size = float(self.config.get('instrument.tick_size', 0.1))
        min_stop_pct = float(self.config.get('capital.min_stop_distance_pct', 0.001))
        min_stop_abs = max(tick_size * 2.0, float(market_state.close) * min_stop_pct)
        stop_distance = max(market_state.atr * stop_mult, min_stop_abs)
        point_value = self._get_point_value()
        initial_capital = float(self.config.get('capital.initial_capital', 100000))
        risk_budget = initial_capital * (self.config.get('capital.base_risk_percent', 1.0) / 100.0)
        max_risk_abs = float(self.config.get('capital.max_risk_per_trade_usd', risk_budget))
        if max_risk_abs > 0:
            risk_budget = min(risk_budget, max_risk_abs)

        risk_size = int(risk_budget / (stop_distance * point_value)) if stop_distance > 0 else min_size
        quality_scale = min(1.4, max(0.6, confluence / 70.0))
        size = int(risk_size * multiplier * quality_scale)
        size = max(min_size, size)

        # Notional cap protects against oversizing when ATR or price collapses.
        contract_multiplier = float(self.config.get('instrument.contract_multiplier', 1.0))
        max_notional_pct = float(self.config.get('capital.max_notional_pct', 0.10))
        max_notional = initial_capital * max_notional_pct
        notional_per_contract = max(1e-9, float(market_state.close) * contract_multiplier)
        max_notional_size = int(max_notional / notional_per_contract) if max_notional > 0 else max_size
        if max_notional_size > 0:
            size = min(size, max_notional_size)
        size = max(min_size, size)

        # Portfolio adjustment
        if self.config.get('portfolio.enabled', True):
            symbol = self.config.get('instrument.symbol', 'MGC1!')
            size = self.portfolio_manager.get_position_size_adjustment(symbol, size)

        return max(min_size, min(size, max_size))

    def _get_stop_multiplier(self, regime: Regime) -> float:
        """Get stop multiplier for current regime."""
        if regime == Regime.TRENDING:
            return float(self.config.get('stop_loss.trending_mult', 2.0))
        if regime == Regime.VOLATILE:
            return float(self.config.get('stop_loss.volatile_mult', 3.0))
        if regime == Regime.RANGING and str(self.config.get('regime_split.range_mode', 'NO_TRADE')).upper() == "MEAN_REVERT":
            return float(self.config.get('stop_loss.range_mean_revert_mult', 1.0))
        return float(self.config.get('stop_loss.ranging_mult', 1.5))

    def _get_point_value(self) -> float:
        """
        Dollar value per 1.0 point.
        Example: MGC tick 0.1 and tick value 1 => point value 10.
        """
        tick_size = float(self.config.get('instrument.tick_size', 0.1))
        tick_value = float(self.config.get('instrument.tick_value', 1.0))
        if tick_size <= 0:
            return max(tick_value, 1.0)
        return max(tick_value / tick_size, 1.0)

    def _calculate_stop_loss(
        self,
        entry_price: float,
        market_state: MarketState,
        direction: SignalDirection
    ) -> float:
        """Calculate stop loss price."""
        # Get regime-specific multiplier
        if market_state.regime == Regime.TRENDING:
            mult = self.config.get('stop_loss.trending_mult', 2.0)
        elif market_state.regime == Regime.VOLATILE:
            mult = self.config.get('stop_loss.volatile_mult', 3.0)
        elif self._is_range_mean_revert_active(market_state):
            mult = self.config.get('stop_loss.range_mean_revert_mult', 1.0)
        else:
            mult = self.config.get('stop_loss.ranging_mult', 1.5)

        stop_distance = market_state.atr * mult

        if direction == SignalDirection.LONG:
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance

    def _calculate_take_profits(
        self,
        entry_price: float,
        market_state: MarketState,
        direction: SignalDirection
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate take profit levels."""
        if market_state.regime == Regime.TRENDING:
            t1_mult = self.config.get('take_profit.trending_t1_mult', 1.5)
            t2_mult = self.config.get('take_profit.trending_t2_mult', 3.0)
            t3_mult = self.config.get('take_profit.trending_t3_mult', 5.0)
        elif market_state.regime == Regime.VOLATILE:
            t1_mult = self.config.get('take_profit.volatile_t1_mult', 1.0)
            t2_mult = self.config.get('take_profit.volatile_t2_mult', 2.0)
            t3_mult = None
        elif self._is_range_mean_revert_active(market_state):
            t1_mult = self.config.get('take_profit.range_mean_revert_t1_mult', 0.9)
            t2_raw = float(self.config.get('take_profit.range_mean_revert_t2_mult', 1.3))
            t2_mult = t2_raw if t2_raw > 0 else None
            t3_mult = None
        else:
            t1_mult = self.config.get('take_profit.ranging_target_mult', 2.0)
            t2_mult = None
            t3_mult = None

        if direction == SignalDirection.LONG:
            tp1 = entry_price + (market_state.atr * t1_mult)
            tp2 = entry_price + (market_state.atr * t2_mult) if t2_mult else None
            tp3 = entry_price + (market_state.atr * t3_mult) if t3_mult else None
        else:
            tp1 = entry_price - (market_state.atr * t1_mult)
            tp2 = entry_price - (market_state.atr * t2_mult) if t2_mult else None
            tp3 = entry_price - (market_state.atr * t3_mult) if t3_mult else None

        return tp1, tp2, tp3

    def _update_portfolio(self, bar: pd.Series) -> None:
        """Update portfolio correlations and metrics."""
        symbol = self.config.get('instrument.symbol', 'MGC1!')
        # In production, would fetch data for all portfolio symbols
        # For now, just update current symbol
        # self.portfolio_manager.update_returns(symbol, prices)
        pass

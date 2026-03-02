"""
Core type definitions and enums for the trading system.
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import numpy as np


class Regime(str, Enum):
    """Market regime types."""
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"


class OrderFlowBias(str, Enum):
    """Order flow bias types."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    AUTO = "AUTO"


class SignalDirection(str, Enum):
    """Trade signal direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class OrderType(str, Enum):
    """Order types for execution."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    VWAP = "VWAP"
    TWAP = "TWAP"


class ExitReason(str, Enum):
    """Reasons for trade exit."""
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    BREAKEVEN = "BREAKEVEN"
    TIME_EXIT = "TIME_EXIT"
    REGIME_CHANGE = "REGIME_CHANGE"
    RISK_LIMIT = "RISK_LIMIT"
    MANUAL = "MANUAL"


class MAZTier(int, Enum):
    """MAZ quality tiers."""
    TIER_0 = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class OHLCV(BaseModel):
    """Standard OHLCV bar data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    class Config:
        arbitrary_types_allowed = True


class MarketState(BaseModel):
    """Current market state snapshot."""
    timestamp: datetime
    symbol: str
    close: float
    atr: float
    regime: Regime
    regime_confidence: float
    vol_percentile: float
    is_expansion: bool
    is_compression: bool
    efficiency_ratio: float
    htf_bias: int  # 1=bullish, -1=bearish, 0=neutral
    in_premium: bool
    in_discount: bool
    structure_bullish: bool
    structure_bearish: bool

    class Config:
        use_enum_values = True


class Signal(BaseModel):
    """Trading signal."""
    timestamp: datetime
    symbol: str
    direction: SignalDirection
    confluence_score: int
    regime: Regime
    entry_price: float
    stop_loss: float
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    position_size: int
    risk_amount: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


    class Config:
        use_enum_values = True


class Position(BaseModel):
    """Active position tracking."""
    symbol: str
    direction: SignalDirection
    entry_time: datetime
    entry_price: float
    quantity: int
    current_price: float
    unrealized_pnl: float
    stop_loss: float
    take_profit: Optional[float] = None
    entry_confluence: int
    entry_regime: Regime
    bars_in_trade: int
    scaled_out: bool = False
    breakeven_triggered: bool = False
    trailing_triggered: bool = False

    class Config:
        use_enum_values = True


class Trade(BaseModel):
    """Completed trade record."""
    trade_id: int
    symbol: str
    direction: SignalDirection
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    realized_pnl: float
    commission: float
    slippage: float
    exit_reason: ExitReason
    entry_confluence: int
    entry_regime: Regime
    bars_held: int
    mae: float  # Maximum Adverse Excursion
    mfe: float  # Maximum Favorable Excursion
    metadata: Dict[str, Any] = Field(default_factory=dict)


    class Config:
        use_enum_values = True


class PortfolioMetrics(BaseModel):
    """Portfolio-level risk metrics."""
    timestamp: datetime
    total_equity: float
    cash: float
    positions_value: float
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    num_positions: int
    correlation_heat: float
    portfolio_beta: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None


class RLState(BaseModel):
    """Reinforcement Learning state representation."""
    current_pnl: float
    position_duration: int
    market_volatility: float
    order_flow_imbalance: float
    spread: float
    time_of_day: float  # Normalized 0-1
    regime: int  # 0=trending, 1=ranging, 2=volatile

    def to_array(self) -> np.ndarray:
        """Convert to numpy array for RL model."""
        return np.array([
            self.current_pnl,
            self.position_duration,
            self.market_volatility,
            self.order_flow_imbalance,
            self.spread,
            self.time_of_day,
            self.regime
        ], dtype=np.float32)


class RLAction(BaseModel):
    """RL execution action."""
    action_type: OrderType
    action_prob: float
    expected_reward: float

    class Config:
        use_enum_values = True




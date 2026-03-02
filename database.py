"""
Database manager for persistent storage using PostgreSQL/SQLite.
"""
import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from mytypes import Trade, Position, Signal

from config import get_config

Base = declarative_base()


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), index=True)
    direction = Column(String(10))
    entry_time = Column(DateTime, index=True)
    exit_time = Column(DateTime, index=True)
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Integer)
    realized_pnl = Column(Float)
    commission = Column(Float)
    slippage = Column(Float)
    exit_reason = Column(String(50))
    entry_confluence = Column(Integer)
    entry_regime = Column(String(20))
    bars_held = Column(Integer)
    mae = Column(Float)
    mfe = Column(Float)
    extra = Column(JSON)



class SignalRecord(Base):
    """Signal record database model."""
    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    confluence_score = Column(Integer)
    regime = Column(String(20))
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit_1 = Column(Float)
    take_profit_2 = Column(Float)
    take_profit_3 = Column(Float)
    position_size = Column(Integer)
    risk_amount = Column(Float)
    executed = Column(Boolean, default=False)
    extra = Column(JSON)



class PerformanceMetric(Base):
    """Performance metrics database model."""
    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    total_equity = Column(Float)
    daily_pnl = Column(Float)
    unrealized_pnl = Column(Float)
    realized_pnl = Column(Float)
    num_positions = Column(Integer)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    extra = Column(JSON)



class DatabaseManager:
    """
    Database manager for trade history and metrics persistence.
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            connection_string: SQLAlchemy connection string
        """
        config = get_config()

        if connection_string is None:
            db_type = config.get('database.type', 'sqlite')

            if db_type == 'postgresql':
                connection_string = config.get('database.connection_string',
                    f"postgresql://{config.get('database.user')}:{config.get('database.password')}@"
                    f"{config.get('database.host')}:{config.get('database.port')}/"
                    f"{config.get('database.database')}"
                )
            else:
                # SQLite fallback
                connection_string = "sqlite:///data/trading.db"

        self.engine = create_engine(connection_string, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        logger.info(f"DatabaseManager initialized with {connection_string}")

    def save_trade(self, trade: Trade) -> None:
        """Save completed trade to database."""
        session = self.SessionLocal()

        try:
            record = TradeRecord(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                direction=trade.direction.value,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                realized_pnl=trade.realized_pnl,
                commission=trade.commission,
                slippage=trade.slippage,
                exit_reason=trade.exit_reason.value,
                entry_confluence=trade.entry_confluence,
                entry_regime=trade.entry_regime.value,
                bars_held=trade.bars_held,
                mae=trade.mae,
                mfe=trade.mfe,
                    extra = Column(JSON)

            )

            session.add(record)
            session.commit()
            logger.debug(f"Trade saved: {trade.trade_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving trade: {e}")
        finally:
            session.close()

    def save_signal(self, signal: Signal, executed: bool = False) -> None:
        """Save trading signal to database."""
        session = self.SessionLocal()

        try:
            record = SignalRecord(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                direction=signal.direction.value,
                confluence_score=signal.confluence_score,
                regime=signal.regime.value,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
                take_profit_3=signal.take_profit_3,
                position_size=signal.position_size,
                risk_amount=signal.risk_amount,
                executed=executed,
                    extra = Column(JSON)

            )

            session.add(record)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving signal: {e}")
        finally:
            session.close()

    def get_trades(
        self, 
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Retrieve trades from database.

        Args:
            symbol: Filter by symbol
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of trades

        Returns:
            DataFrame of trades
        """
        session = self.SessionLocal()

        try:
            query = session.query(TradeRecord)

            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            if start_date:
                query = query.filter(TradeRecord.entry_time >= start_date)
            if end_date:
                query = query.filter(TradeRecord.exit_time <= end_date)

            query = query.order_by(TradeRecord.entry_time.desc())

            if limit:
                query = query.limit(limit)

            records = query.all()

            # Convert to DataFrame
            data = [{
                'trade_id': r.trade_id,
                'symbol': r.symbol,
                'direction': r.direction,
                'entry_time': r.entry_time,
                'exit_time': r.exit_time,
                'entry_price': r.entry_price,
                'exit_price': r.exit_price,
                'quantity': r.quantity,
                'realized_pnl': r.realized_pnl,
                'commission': r.commission,
                'slippage': r.slippage,
                'exit_reason': r.exit_reason,
                'entry_confluence': r.entry_confluence,
                'entry_regime': r.entry_regime,
                'bars_held': r.bars_held,
                'mae': r.mae,
                'mfe': r.mfe
            } for r in records]

            return pd.DataFrame(data)

        except Exception as e:
            logger.error(f"Error retrieving trades: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def get_performance_summary(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate performance summary statistics.

        Args:
            symbol: Filter by symbol

        Returns:
            Dictionary of performance metrics
        """
        trades_df = self.get_trades(symbol=symbol)

        if trades_df.empty:
            return {}

        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['realized_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['realized_pnl'] < 0])

        total_pnl = trades_df['realized_pnl'].sum()
        avg_win = trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].mean() if losing_trades > 0 else 0

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = abs(trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].sum() / 
                           trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].sum())                        if losing_trades > 0 else float('inf')

        # Sharpe ratio approximation
        returns = trades_df['realized_pnl']
        sharpe = (returns.mean() / returns.std()) if returns.std() > 0 else 0

        # Maximum drawdown
        cumulative_pnl = returns.cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown = drawdown.min()

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'avg_bars_held': trades_df['bars_held'].mean()
        }

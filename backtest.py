
#!/usr/bin/env python3
"""
Backtesting script for the Enhanced Adaptive Strategy.
"""
import sys
import argparse
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger

# --- ensure project root is on sys.path ---
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
# ------------------------------------------

from config import init_config
from strategy_engine import StrategyEngine
from database import DatabaseManager
from mytypes import SignalDirection



def load_historical_data(file_path: str) -> pd.DataFrame:
    """
    Load historical OHLCV data from CSV.

    Expected columns: timestamp, open, high, low, close, volume
    """
    logger.info(f"Loading data from {file_path}")

    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last')
    df = df.set_index('timestamp')

    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df[required_cols].copy()
    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=required_cols)

    if len(df) == 0:
        raise ValueError("No usable OHLCV rows after parsing data")

    logger.info(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")

    return df


def analyze_data_quality(
    df: pd.DataFrame,
    min_close_ratio: float,
    max_close_ratio: float,
    max_abs_bar_return: float,
    min_rows: int,
) -> tuple[list[str], dict[str, Any]]:
    """Run basic quality checks so backtest/training results are interpretable."""
    close = pd.to_numeric(df['close'], errors='coerce')
    open_ = pd.to_numeric(df['open'], errors='coerce')
    high = pd.to_numeric(df['high'], errors='coerce')
    low = pd.to_numeric(df['low'], errors='coerce')
    volume = pd.to_numeric(df['volume'], errors='coerce')

    start_close = float(close.iloc[0])
    end_close = float(close.iloc[-1])
    close_ratio = end_close / start_close if abs(start_close) > 1e-9 else 0.0
    close_return_pct = (close_ratio - 1.0) * 100.0

    bar_returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    max_abs_ret = float(bar_returns.abs().max()) if len(bar_returns) > 0 else 0.0

    invalid_ohlc = int(((high < low) | (open_ > high) | (open_ < low) | (close > high) | (close < low)).sum())
    nonpositive_close = int((close <= 0).sum())
    nonpositive_volume = int((volume <= 0).sum())
    duplicate_index = int(df.index.duplicated(keep=False).sum())

    issues: list[str] = []
    if len(df) < min_rows:
        issues.append(f"insufficient_rows:{len(df)}<{min_rows}")
    if close_ratio < min_close_ratio or close_ratio > max_close_ratio:
        issues.append(
            f"close_ratio_out_of_bounds:{close_ratio:.3f} (allowed {min_close_ratio:.3f}-{max_close_ratio:.3f})"
        )
    if max_abs_ret > max_abs_bar_return:
        issues.append(
            f"bar_return_spike:{max_abs_ret * 100:.2f}% (max {max_abs_bar_return * 100:.2f}%)"
        )
    if invalid_ohlc > 0:
        issues.append(f"invalid_ohlc_rows:{invalid_ohlc}")
    if nonpositive_close > 0:
        issues.append(f"nonpositive_close_rows:{nonpositive_close}")
    if duplicate_index > 0:
        issues.append(f"duplicate_timestamps:{duplicate_index}")

    metrics = {
        "rows": int(len(df)),
        "start_close": start_close,
        "end_close": end_close,
        "close_ratio": close_ratio,
        "close_return_pct": close_return_pct,
        "max_abs_bar_return_pct": max_abs_ret * 100.0,
        "invalid_ohlc_rows": invalid_ohlc,
        "nonpositive_close_rows": nonpositive_close,
        "nonpositive_volume_rows": nonpositive_volume,
        "duplicate_timestamps": duplicate_index,
    }
    return issues, metrics


def run_backtest(
    data_file: str,
    config_file: str = "config/config.yaml",
    output_dir: str = "results",
    train_models: bool = True,
    instrument: str | None = None,
    use_bookmap_bridge: bool = False,
    train_split: float = 0.7,
    oos_only: bool = True,
    enforce_data_quality: bool | None = None,
) -> dict:
    """
    Run backtest on historical data.

    Args:
        data_file: Path to historical OHLCV CSV
        config_file: Path to configuration YAML
        output_dir: Output directory for results
        train_models: Whether to train ML models

    Returns:
        Dictionary of backtest results
    """
    # Initialize configuration
    config = init_config(config_file)
    logger.info("Configuration loaded")

    # Optional instrument profile override for quick MGC/MNQ switching.
    if instrument:
        instrument = instrument.upper()
        if instrument == "MGC":
            config.update('instrument.symbol', 'MGC1!')
            config.update('instrument.exchange', 'COMEX')
            config.update('instrument.tick_size', 0.1)
            config.update('instrument.tick_value', 1.0)
            config.update('instrument.contract_multiplier', 10)
            config.update('instrument.is_mgc', True)
            config.update('instrument.is_mnq', False)
            config.update('instrument.commission_per_contract', 0.50)
            config.update('instrument.slippage_ticks', 1.0)
        elif instrument == "MNQ":
            config.update('instrument.symbol', 'MNQ1!')
            config.update('instrument.exchange', 'CME')
            config.update('instrument.tick_size', 0.25)
            config.update('instrument.tick_value', 0.5)
            config.update('instrument.contract_multiplier', 2)
            config.update('instrument.is_mgc', False)
            config.update('instrument.is_mnq', True)
            config.update('instrument.commission_per_contract', 0.20)
            config.update('instrument.slippage_ticks', 0.25)
        else:
            raise ValueError(f"Unsupported instrument override: {instrument}")

    # Historical backtests should not depend on a live bridge file unless explicitly requested.
    if not use_bookmap_bridge:
        config.update('bookmap_bridge.enabled', False)
        logger.info("Backtest mode: bookmap bridge disabled")

    # Load data
    df = load_historical_data(data_file)
    lookback = int(config.get('general.efficiency_lookback', 20)) + 50  # Need history for indicators

    # Quality checks for more reliable training/backtesting.
    min_close_ratio = float(config.get('backtesting.data_quality.min_close_ratio', 0.50))
    max_close_ratio = float(config.get('backtesting.data_quality.max_close_ratio', 2.50))
    max_abs_bar_return = float(config.get('backtesting.data_quality.max_abs_bar_return', 0.20))
    min_rows = int(config.get('backtesting.data_quality.min_rows', 1000))
    config_enforce_quality = bool(config.get('backtesting.data_quality.enforce', False))
    if enforce_data_quality is None:
        enforce_data_quality = config_enforce_quality

    quality_issues, quality_metrics = analyze_data_quality(
        df,
        min_close_ratio=min_close_ratio,
        max_close_ratio=max_close_ratio,
        max_abs_bar_return=max_abs_bar_return,
        min_rows=min_rows,
    )
    logger.info(
        "Data quality summary: "
        f"rows={quality_metrics['rows']}, close_ratio={quality_metrics['close_ratio']:.3f}, "
        f"max_abs_bar_return={quality_metrics['max_abs_bar_return_pct']:.2f}%"
    )
    if quality_issues:
        for issue in quality_issues:
            logger.warning(f"Data quality issue: {issue}")
        if enforce_data_quality:
            raise ValueError(
                "Data quality gate failed: " + "; ".join(quality_issues)
            )

    # Initialize strategy engine
    engine = StrategyEngine()

    train_split = min(max(float(train_split), 0.50), 0.95)
    train_end_idx = int(len(df) * train_split)
    train_end_idx = min(max(train_end_idx, lookback + 200), len(df) - 200)

    # Train models if requested
    if train_models:
        logger.info("Training ML models...")
        training_data = df.iloc[:train_end_idx]
        training_metrics = engine.train_models(training_data)
        logger.info(f"Training complete: {training_metrics}")
    else:
        training_data = pd.DataFrame()

    # Initialize database
    _ = DatabaseManager()

    # Backtest loop selection.
    if train_models and oos_only:
        backtest_start_idx = max(0, train_end_idx - lookback)
        backtest_df = df.iloc[backtest_start_idx:].copy()
        logger.info(
            "Using out-of-sample window only: "
            f"train_bars={len(training_data)}, backtest_bars={len(backtest_df)}"
        )
    else:
        backtest_df = df
        logger.info(
            "Using full dataset for backtest loop: "
            f"bars={len(backtest_df)} (train_models={train_models}, oos_only={oos_only})"
        )

    signals = []
    trades = []
    equity_curve = [config.get('capital.initial_capital', 100000)]
    current_position = None
    trade_id = 0
    current_day = None

    logger.info("Starting backtest...")

    max_trades_total = int(config.get('backtesting.max_trades', 500))
    tick_size = float(config.get('instrument.tick_size', 0.1))
    tick_value = float(config.get('instrument.tick_value', 1.0))
    point_value = tick_value / tick_size if tick_size > 0 else 1.0
    slippage_ticks = float(
        config.get('instrument.slippage_ticks', config.get('backtesting.slippage_ticks', 0))
    )
    commission_per_contract = float(
        config.get('instrument.commission_per_contract', config.get('backtesting.commission_per_contract', 0.0))
    )

    def apply_adverse_slippage(price: float, direction: SignalDirection, is_entry: bool) -> float:
        """Apply adverse slippage by direction and side of execution."""
        slip = slippage_ticks * tick_size
        if direction == SignalDirection.LONG:
            return price + slip if is_entry else price - slip
        return price - slip if is_entry else price + slip

    def trade_pnl(entry_price: float, exit_price: float, direction: SignalDirection, qty: int) -> float:
        """Compute gross PnL in account currency."""
        if direction == SignalDirection.LONG:
            return (exit_price - entry_price) * point_value * qty
        return (entry_price - exit_price) * point_value * qty

    for i in range(lookback, len(backtest_df)):
        current_bar = backtest_df.iloc[i]
        historical_data = backtest_df.iloc[max(0, i - lookback):i + 1]
        bar_day = current_bar.name.date()

        if current_day != bar_day:
            current_day = bar_day
            engine.daily_trade_count = 0
            engine.daily_pnl = 0.0
            engine.consecutive_losses = 0

        # Process bar
        signal = engine.process_bar(current_bar, historical_data)

        if signal is not None:
            # Hard cap on total trades
            if len(trades) >= max_trades_total:
                continue

            signals.append(signal)

            # Simple execution: enter immediately if no position
            if current_position is None:
                entry_price = apply_adverse_slippage(signal.entry_price, signal.direction, is_entry=True)
                entry_adjustment = entry_price - signal.entry_price
                current_position = {
                    'entry_time': current_bar.name,
                    'entry_price': entry_price,
                    'raw_entry_price': signal.entry_price,
                    'direction': signal.direction,
                    'quantity': signal.position_size,
                    'stop_loss': signal.stop_loss + entry_adjustment,
                    'take_profit': (
                        signal.take_profit_3
                        if signal.take_profit_3 is not None
                        else (signal.take_profit_2 if signal.take_profit_2 is not None else signal.take_profit_1)
                    ) + entry_adjustment if signal.take_profit_1 is not None else None,
                    'entry_confluence': signal.confluence_score,
                    'entry_regime': signal.regime,
                    'bars_held': 0,
                    'peak_pnl': 0.0,
                    'worst_pnl': 0.0
                }
                logger.info(f"[{current_bar.name}] Entered {signal.direction} at {entry_price:.2f}")

        # Manage open position


        if current_position is not None:
            current_position['bars_held'] += 1

            # Calculate current P&L
            if current_position['direction'] == SignalDirection.LONG:
                pnl_per_unit = current_bar.close - current_position['entry_price']
            else:
                pnl_per_unit = current_position['entry_price'] - current_bar.close

            current_pnl = pnl_per_unit * point_value * current_position['quantity']
            current_position['peak_pnl'] = max(current_position['peak_pnl'], current_pnl)
            current_position['worst_pnl'] = min(current_position['worst_pnl'], current_pnl)

                        # Check exit conditions
            exit_triggered = False
            exit_reason = None
            exit_price = current_bar.close

            # Stop loss
            if current_position['direction'] == SignalDirection.LONG:
                if current_bar.low <= current_position['stop_loss']:
                    exit_triggered = True
                    exit_reason = "STOP_LOSS"
                    exit_price = current_position['stop_loss']
                elif current_bar.high >= current_position['take_profit']:
                    exit_triggered = True
                    exit_reason = "TARGET_HIT"
                    exit_price = current_position['take_profit']
            else:
                if current_bar.high >= current_position['stop_loss']:
                    exit_triggered = True
                    exit_reason = "STOP_LOSS"
                    exit_price = current_position['stop_loss']
                elif current_bar.low <= current_position['take_profit']:
                    exit_triggered = True
                    exit_reason = "TARGET_HIT"
                    exit_price = current_position['take_profit']

            # Time exit
            if current_position['entry_regime'] == "TRENDING":
                max_bars = int(config.get('exit_management.trending_max_bars', 100))
            elif current_position['entry_regime'] == "VOLATILE":
                max_bars = int(config.get('exit_management.volatile_max_bars', 30))
            else:
                max_bars = int(config.get('exit_management.ranging_max_bars', 50))

            if current_position['bars_held'] >= max_bars:
                exit_triggered = True
                exit_reason = "TIME_EXIT"

            if exit_triggered:
                exit_fill = apply_adverse_slippage(exit_price, current_position['direction'], is_entry=False)
                gross_pnl = trade_pnl(
                    current_position['entry_price'],
                    exit_fill,
                    current_position['direction'],
                    current_position['quantity']
                )
                no_slip_gross_pnl = trade_pnl(
                    current_position['raw_entry_price'],
                    exit_price,
                    current_position['direction'],
                    current_position['quantity']
                )
                commission_cost = commission_per_contract * current_position['quantity'] * 2.0
                final_pnl = gross_pnl - commission_cost

                # Record trade
                trade = {
                    'trade_id': trade_id,
                    'entry_time': current_position['entry_time'],
                    'exit_time': current_bar.name,
                    'direction': current_position['direction'],
                    'entry_price': current_position['entry_price'],
                    'exit_price': exit_fill,
                    'quantity': current_position['quantity'],
                    'realized_pnl': final_pnl,
                    'gross_pnl': gross_pnl,
                    'commission': commission_cost,
                    'slippage_cost': no_slip_gross_pnl - gross_pnl,
                    'exit_reason': exit_reason,
                    'entry_confluence': current_position['entry_confluence'],
                    'entry_regime': current_position['entry_regime'],
                    'bars_held': current_position['bars_held'],
                    'mae': current_position['worst_pnl'],
                    'mfe': current_position['peak_pnl']
                }

                trades.append(trade)
                trade_id += 1

                # Update equity
                equity_curve.append(equity_curve[-1] + final_pnl)
                engine.daily_trade_count += 1
                engine.daily_pnl += final_pnl
                if final_pnl < 0:
                    engine.consecutive_losses += 1
                else:
                    engine.consecutive_losses = 0

                logger.info(f"[{current_bar.name}] Exited {current_position['direction']} at {exit_fill:.2f}, "
                          f"P&L: {final_pnl:.2f}, Reason: {exit_reason}")

                current_position = None

    # Force close open trade at end of data.
    if current_position is not None:
        last_bar = backtest_df.iloc[-1]
        raw_exit = last_bar.close
        exit_fill = apply_adverse_slippage(raw_exit, current_position['direction'], is_entry=False)
        gross_pnl = trade_pnl(
            current_position['entry_price'],
            exit_fill,
            current_position['direction'],
            current_position['quantity']
        )
        no_slip_gross_pnl = trade_pnl(
            current_position['raw_entry_price'],
            raw_exit,
            current_position['direction'],
            current_position['quantity']
        )
        commission_cost = commission_per_contract * current_position['quantity'] * 2.0
        final_pnl = gross_pnl - commission_cost

        trade = {
            'trade_id': trade_id,
            'entry_time': current_position['entry_time'],
            'exit_time': last_bar.name,
            'direction': current_position['direction'],
            'entry_price': current_position['entry_price'],
            'exit_price': exit_fill,
            'quantity': current_position['quantity'],
            'realized_pnl': final_pnl,
            'gross_pnl': gross_pnl,
            'commission': commission_cost,
            'slippage_cost': no_slip_gross_pnl - gross_pnl,
            'exit_reason': "END_OF_DATA",
            'entry_confluence': current_position['entry_confluence'],
            'entry_regime': current_position['entry_regime'],
            'bars_held': current_position['bars_held'],
            'mae': current_position['worst_pnl'],
            'mfe': current_position['peak_pnl']
        }
        trades.append(trade)
        equity_curve.append(equity_curve[-1] + final_pnl)

    # Calculate metrics
    trades_df = pd.DataFrame(trades)

    if len(trades_df) > 0:
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['realized_pnl'] > 0])
        win_rate = winning_trades / total_trades * 100

        total_pnl = trades_df['realized_pnl'].sum()
        avg_win = trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].mean()
        avg_loss = trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].mean()

        profit_factor = abs(trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].sum() / 
                           trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].sum())                        if len(trades_df[trades_df['realized_pnl'] < 0]) > 0 else float('inf')

        # Sharpe ratio
        returns = trades_df['realized_pnl']
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

        # Max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        results = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'final_equity': equity_curve[-1],
            'return_pct': (equity_curve[-1] - equity_curve[0]) / equity_curve[0] * 100,
        }
    else:
        results = {'error': 'No trades generated'}

    results.update({
        'train_models': bool(train_models),
        'train_split': float(train_split),
        'oos_only': bool(oos_only and train_models),
        'train_bars': int(len(training_data)),
        'backtest_bars': int(len(backtest_df)),
        'data_quality_ok': bool(len(quality_issues) == 0),
        'data_quality_issues': "; ".join(quality_issues) if quality_issues else "",
        'data_close_ratio': float(quality_metrics['close_ratio']),
        'data_max_abs_bar_return_pct': float(quality_metrics['max_abs_bar_return_pct']),
    })

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    if len(trades_df) > 0:
        trades_df.to_csv(output_path / 'trades.csv', index=False)
        pd.DataFrame(equity_curve, columns=['equity']).to_csv(output_path / 'equity_curve.csv', index=False)

    logger.info("Backtest complete")
    logger.info(f"Results: {results}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Run backtest for Enhanced Adaptive Strategy')
    parser.add_argument('--data', required=True, help='Path to historical OHLCV CSV file')
    parser.add_argument('--config', default='config/config.yaml', help='Path to config file')
    parser.add_argument('--output', default='results', help='Output directory')
    parser.add_argument('--instrument', choices=['MGC', 'MNQ'], help='Override instrument profile')
    parser.add_argument('--no-train', action='store_true', help='Skip ML model training')
    parser.add_argument('--use-bridge', action='store_true', help='Use bookmap bridge gate during backtest')
    parser.add_argument('--train-split', type=float, default=0.70, help='Train split when model training is enabled')
    parser.add_argument('--include-train-period', action='store_true', help='Backtest on full data instead of OOS-only window')
    parser.add_argument('--enforce-data-quality', action='store_true', help='Fail run when data quality checks fail')
    parser.add_argument('--allow-poor-data', action='store_true', help='Bypass quality gate even if config enables it')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
    logger.add("logs/backtest_{time}.log", rotation="1 day", retention="30 days", level="DEBUG")

    enforce_quality: bool | None = None
    if args.enforce_data_quality:
        enforce_quality = True
    if args.allow_poor_data:
        enforce_quality = False

    # Run backtest
    results = run_backtest(
        data_file=args.data,
        config_file=args.config,
        output_dir=args.output,
        train_models=not args.no_train,
        instrument=args.instrument,
        use_bookmap_bridge=args.use_bridge,
        train_split=args.train_split,
        oos_only=not args.include_train_period,
        enforce_data_quality=enforce_quality,
    )

    # Print summary
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key:.<40} {value:.2f}")
        else:
            print(f"{key:.<40} {value}")
    print("="*60)


if __name__ == '__main__':
    main()

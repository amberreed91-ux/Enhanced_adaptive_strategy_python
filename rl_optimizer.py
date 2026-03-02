"""
Reinforcement Learning execution optimizer using PPO (Stable-Baselines3).
Optimizes order execution timing and order type selection.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO, SAC, TD3
from stable_baselines3.common.callbacks import BaseCallback
from loguru import logger

from mytypes import OrderType, RLState, RLAction


class TradingExecutionEnv(gym.Env):
    """
    Custom Gymnasium environment for RL execution optimization.

    State: [current_pnl, position_duration, market_volatility, order_flow_imbalance, 
            spread, time_of_day, regime]

    Actions: [MARKET, LIMIT, VWAP, TWAP]

    Reward: Sharpe-weighted PnL considering slippage and market impact
    """

    def __init__(
        self,
        market_data: pd.DataFrame,
        reward_function: str = "sharpe_weighted"
    ):
        """
        Initialize trading environment.

        Args:
            market_data: Historical OHLCV data with additional features
            reward_function: Reward calculation method
        """
        super().__init__()

        self.market_data = market_data.reset_index(drop=True)
        self.reward_function = reward_function
        self.current_step = 0
        self.max_steps = len(market_data) - 1

        # Define action space: 4 order types
        self.action_space = spaces.Discrete(4)
        self.action_map = {
            0: OrderType.MARKET,
            1: OrderType.LIMIT,
            2: OrderType.VWAP,
            3: OrderType.TWAP
        }

        # Define observation space: 7 features
        self.observation_space = spaces.Box(
            low=np.array([-10.0, 0, 0, -1.0, 0, 0, 0], dtype=np.float32),
            high=np.array([10.0, 200, 10.0, 1.0, 1.0, 1.0, 2.0], dtype=np.float32),
            dtype=np.float32
        )

        # Episode tracking
        self.episode_pnl = 0.0
        self.episode_trades = 0
        self.position_entry_price = 0.0
        self.position_duration = 0
        self.slippage_costs = []

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        self.current_step = 0
        self.episode_pnl = 0.0
        self.episode_trades = 0
        self.position_entry_price = 0.0
        self.position_duration = 0
        self.slippage_costs = []

        return self._get_observation(), {}

    def _get_observation(self) -> np.ndarray:
        """Get current state observation."""
        if self.current_step >= len(self.market_data):
            self.current_step = len(self.market_data) - 1

        row = self.market_data.iloc[self.current_step]

        # Calculate state features
        current_pnl = self.episode_pnl / 1000.0  # Normalize
        position_duration = min(self.position_duration, 200)
        market_volatility = row.get('atr', 1.0)
        order_flow_imbalance = row.get('order_flow_imbalance', 0.0)
        spread = row.get('spread_pct', 0.01)

        # Time of day (normalized 0-1)
        if 'timestamp' in row:
            time_of_day = (row['timestamp'].hour * 60 + row['timestamp'].minute) / 1440.0
        else:
            time_of_day = 0.5

        # Regime encoding (0=TRENDING, 1=RANGING, 2=VOLATILE)
        regime = row.get('regime_encoded', 1)

        state = np.array([
            current_pnl,
            position_duration,
            market_volatility,
            order_flow_imbalance,
            spread,
            time_of_day,
            regime
        ], dtype=np.float32)

        return state

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute action and return next state, reward, done, truncated, info.

        Args:
            action: Action index (0-3)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        order_type = self.action_map[action]

        # Simulate trade execution with different order types
        row = self.market_data.iloc[self.current_step]
        entry_price = row['close']

        # Calculate slippage based on order type
        if order_type == OrderType.MARKET:
            slippage_pct = 0.0015  # 15 bps
        elif order_type == OrderType.LIMIT:
            slippage_pct = 0.0005  # 5 bps (better fill but risk of no fill)
        elif order_type == OrderType.VWAP:
            slippage_pct = 0.0008  # 8 bps
        else:  # TWAP
            slippage_pct = 0.0010  # 10 bps

        # Adjust slippage by market conditions
        spread = row.get('spread_pct', 0.01)
        volatility = row.get('atr', 1.0)
        slippage_pct *= (1 + spread + volatility * 0.1)

        # Simulate position P&L
        self.current_step += 1
        if self.current_step >= self.max_steps:
            done = True
            truncated = False
        else:
            done = False
            truncated = False

        if not done:
            next_price = self.market_data.iloc[self.current_step]['close']
            price_change = (next_price - entry_price) / entry_price
            trade_pnl = price_change * 10000  # Notional position
            trade_pnl -= slippage_pct * 10000  # Subtract slippage cost

            self.episode_pnl += trade_pnl
            self.episode_trades += 1
            self.position_duration += 1
            self.slippage_costs.append(slippage_pct * 10000)
        else:
            trade_pnl = 0.0

        # Calculate reward
        reward = self._calculate_reward(trade_pnl, slippage_pct)

        # Get next observation
        observation = self._get_observation()

        info = {
            'episode_pnl': self.episode_pnl,
            'episode_trades': self.episode_trades,
            'order_type': order_type.value,
            'slippage': slippage_pct
        }

        return observation, reward, done, truncated, info

    def _calculate_reward(self, trade_pnl: float, slippage: float) -> float:
        """
        Calculate reward based on selected reward function.

        Args:
            trade_pnl: Trade P&L
            slippage: Slippage cost

        Returns:
            Reward value
        """
        if self.reward_function == "pnl":
            return trade_pnl

        elif self.reward_function == "sharpe_weighted":
            # Reward = PnL - slippage penalty, with volatility adjustment
            if len(self.slippage_costs) > 10:
                volatility = np.std(self.slippage_costs[-10:])
                sharpe_factor = trade_pnl / (volatility + 1e-6)
                return sharpe_factor - slippage * 1000
            else:
                return trade_pnl - slippage * 1000

        elif self.reward_function == "risk_adjusted":
            # Penalize high slippage more heavily
            return trade_pnl - (slippage ** 2) * 10000

        else:
            return trade_pnl


class RLExecutionOptimizer:
    """
    Reinforcement Learning execution optimizer using Stable-Baselines3.
    Learns optimal order type selection based on market conditions.
    """

    def __init__(
        self,
        algorithm: str = "PPO",
        learning_rate: float = 0.0003,
        gamma: float = 0.99,
        clip_epsilon: float = 0.2,
        reward_function: str = "sharpe_weighted"
    ):
        """
        Initialize RL optimizer.

        Args:
            algorithm: RL algorithm (PPO, SAC, TD3)
            learning_rate: Learning rate
            gamma: Discount factor
            clip_epsilon: PPO clipping parameter
            reward_function: Reward calculation method
        """
        self.algorithm = algorithm
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.clip_epsilon = clip_epsilon
        self.reward_function = reward_function

        self.model: Optional[Any] = None
        self.env: Optional[TradingExecutionEnv] = None
        self.is_trained = False

        logger.info(f"RLExecutionOptimizer initialized with {algorithm}")

    def train(
        self,
        market_data: pd.DataFrame,
        total_timesteps: int = 50000,
        verbose: int = 0
    ) -> Dict[str, Any]:
        """
        Train RL model on historical data.

        Args:
            market_data: Historical OHLCV + features
            total_timesteps: Training timesteps
            verbose: Verbosity level

        Returns:
            Training metrics
        """
        logger.info(f"Training RL model with {total_timesteps} timesteps...")

        # Create environment
        self.env = TradingExecutionEnv(market_data, self.reward_function)

        # Initialize model
        if self.algorithm == "PPO":
            self.model = PPO(
                "MlpPolicy",
                self.env,
                learning_rate=self.learning_rate,
                gamma=self.gamma,
                clip_range=self.clip_epsilon,
                verbose=verbose,
                device='cpu'  # Use 'cuda' if GPU available
            )
        elif self.algorithm == "SAC":
            self.model = SAC(
                "MlpPolicy",
                self.env,
                learning_rate=self.learning_rate,
                gamma=self.gamma,
                verbose=verbose,
                device='cpu'
            )
        elif self.algorithm == "TD3":
            self.model = TD3(
                "MlpPolicy",
                self.env,
                learning_rate=self.learning_rate,
                gamma=self.gamma,
                verbose=verbose,
                device='cpu'
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        # Train
        self.model.learn(total_timesteps=total_timesteps)
        self.is_trained = True

        logger.info("RL training complete")

        return {
            'total_timesteps': total_timesteps,
            'algorithm': self.algorithm
        }

    def predict_action(self, state: RLState) -> RLAction:
        """
        Predict best execution action for current state.

        Args:
            state: Current RL state

        Returns:
            RLAction with order type and confidence
        """
        if not self.is_trained:
            logger.warning("Model not trained, returning default MARKET order")
            return RLAction(
                action_type=OrderType.MARKET,
                action_prob=1.0,
                expected_reward=0.0
            )

        # Get observation from state
        obs = state.to_array()

        # Predict action
        action, _states = self.model.predict(obs, deterministic=False)

        # Get action probability (approximate for PPO)
        action_type = self.env.action_map[int(action)]

        return RLAction(
            action_type=action_type,
            action_prob=0.75,  # Approximation - would need policy network access for exact
            expected_reward=0.0
        )

    def save_model(self, path: str) -> None:
        """Save trained model to disk."""
        if self.model is not None:
            self.model.save(path)
            logger.info(f"Model saved to {path}")

    def load_model(self, path: str) -> None:
        """Load trained model from disk."""
        if self.algorithm == "PPO":
            self.model = PPO.load(path)
        elif self.algorithm == "SAC":
            self.model = SAC.load(path)
        elif self.algorithm == "TD3":
            self.model = TD3.load(path)

        self.is_trained = True
        logger.info(f"Model loaded from {path}")

"""
Portfolio correlation matrix and Hierarchical Risk Parity (HRP) implementation.
Uses PyPortfolioOpt for professional portfolio optimization.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform
from pypfopt import risk_models, expected_returns
from pypfopt.hierarchical_portfolio import HRPOpt
from loguru import logger


class PortfolioManager:
    """
    Multi-asset portfolio manager with correlation monitoring and HRP.
    """

    def __init__(
        self,
        symbols: List[str],
        correlation_lookback: int = 50,
        max_correlation_threshold: float = 0.7,
        hrp_cluster_threshold: float = 0.5
    ):
        """
        Initialize portfolio manager.

        Args:
            symbols: List of symbols to track
            correlation_lookback: Rolling correlation window
            max_correlation_threshold: Threshold for high correlation warning
            hrp_cluster_threshold: HRP clustering threshold
        """
        self.symbols = symbols
        self.correlation_lookback = correlation_lookback
        self.max_correlation_threshold = max_correlation_threshold
        self.hrp_cluster_threshold = hrp_cluster_threshold

        self.returns_cache: Dict[str, pd.Series] = {}
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.hrp_weights: Optional[Dict[str, float]] = None
        self.portfolio_heat_score: float = 0.0
        self.risk_adjustment_factor: float = 1.0

        logger.info(f"PortfolioManager initialized with {len(symbols)} symbols")

    def update_returns(self, symbol: str, prices: pd.Series) -> None:
        """
        Update returns cache for a symbol.

        Args:
            symbol: Symbol ticker
            prices: Price series
        """
        returns = prices.pct_change().dropna()
        self.returns_cache[symbol] = returns

    def calculate_correlation_matrix(self) -> pd.DataFrame:
        """
        Calculate rolling correlation matrix across all symbols.

        Returns:
            Correlation matrix
        """
        if not self.returns_cache:
            logger.warning("No returns data available for correlation calculation")
            return pd.DataFrame()

        # Align returns
        returns_df = pd.DataFrame(self.returns_cache)
        returns_df = returns_df.dropna()

        if len(returns_df) < self.correlation_lookback:
            logger.warning(f"Insufficient data for correlation (need {self.correlation_lookback} bars)")
            return pd.DataFrame()

        # Calculate rolling correlation
        recent_returns = returns_df.tail(self.correlation_lookback)
        self.correlation_matrix = recent_returns.corr()

        # Calculate heat score (average absolute correlation)
        mask = np.triu(np.ones_like(self.correlation_matrix, dtype=bool), k=1)
        correlations = self.correlation_matrix.values[mask]
        self.portfolio_heat_score = np.mean(np.abs(correlations)) * 100

        # Calculate risk adjustment factor
        if self.portfolio_heat_score < 40:
            self.risk_adjustment_factor = 1.0
        elif self.portfolio_heat_score < 60:
            self.risk_adjustment_factor = 0.85
        elif self.portfolio_heat_score < 80:
            self.risk_adjustment_factor = 0.7
        else:
            self.risk_adjustment_factor = 0.5

        logger.debug(f"Correlation heat score: {self.portfolio_heat_score:.1f}%, "
                    f"Risk adjustment: {self.risk_adjustment_factor:.2f}")

        return self.correlation_matrix

    def check_diversification(self) -> Tuple[bool, List[Tuple[str, str, float]]]:
        """
        Check if portfolio is adequately diversified.

        Returns:
            Tuple of (is_diversified, list of high correlation pairs)
        """
        if self.correlation_matrix is None:
            return True, []

        high_corr_pairs = []
        n = len(self.correlation_matrix)

        for i in range(n):
            for j in range(i+1, n):
                corr = abs(self.correlation_matrix.iloc[i, j])
                if corr > self.max_correlation_threshold:
                    symbol1 = self.correlation_matrix.index[i]
                    symbol2 = self.correlation_matrix.columns[j]
                    high_corr_pairs.append((symbol1, symbol2, corr))

        is_diversified = len(high_corr_pairs) == 0

        if not is_diversified:
            logger.warning(f"Found {len(high_corr_pairs)} highly correlated pairs")

        return is_diversified, high_corr_pairs

    def optimize_hrp_weights(self) -> Dict[str, float]:
        """
        Calculate Hierarchical Risk Parity portfolio weights.

        Returns:
            Dictionary of symbol -> weight
        """
        if not self.returns_cache:
            logger.warning("No returns data for HRP optimization")
            return {symbol: 1.0/len(self.symbols) for symbol in self.symbols}

        # Prepare returns dataframe
        returns_df = pd.DataFrame(self.returns_cache).dropna()

        if len(returns_df) < self.correlation_lookback:
            logger.warning("Insufficient data for HRP")
            return {symbol: 1.0/len(self.symbols) for symbol in self.symbols}

        recent_returns = returns_df.tail(self.correlation_lookback)

        try:
            # Calculate HRP using PyPortfolioOpt
            hrp = HRPOpt(recent_returns)
            self.hrp_weights = hrp.optimize()

            logger.info(f"HRP weights: {self.hrp_weights}")

            return self.hrp_weights

        except Exception as e:
            logger.error(f"HRP optimization failed: {e}")
            # Fallback: inverse volatility weighting
            return self._inverse_volatility_weights(recent_returns)

    def _inverse_volatility_weights(self, returns: pd.DataFrame) -> Dict[str, float]:
        """
        Fallback: Calculate inverse volatility weights.

        Args:
            returns: Returns dataframe

        Returns:
            Dictionary of weights
        """
        volatilities = returns.std()
        inv_vol = 1.0 / volatilities
        weights = inv_vol / inv_vol.sum()
        return weights.to_dict()

    def calculate_portfolio_metrics(self) -> Dict[str, float]:
        """
        Calculate comprehensive portfolio risk metrics.

        Returns:
            Dictionary of metrics
        """
        if not self.returns_cache or self.correlation_matrix is None:
            return {}

        returns_df = pd.DataFrame(self.returns_cache).dropna()

        # Portfolio returns (equal weighted for now)
        portfolio_returns = returns_df.mean(axis=1)

        # Calculate metrics
        sharpe_ratio = (portfolio_returns.mean() / portfolio_returns.std()) * np.sqrt(252)                        if portfolio_returns.std() > 0 else 0.0

        # Maximum drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # CVaR (Conditional Value at Risk) - 95% confidence
        var_95 = portfolio_returns.quantile(0.05)
        cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()

        metrics = {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'volatility': portfolio_returns.std() * np.sqrt(252),
            'var_95': var_95,
            'cvar_95': cvar_95,
            'correlation_heat': self.portfolio_heat_score,
            'risk_adjustment_factor': self.risk_adjustment_factor
        }

        return metrics

    def get_position_size_adjustment(self, symbol: str, base_size: int) -> int:
        """
        Adjust position size based on HRP weights and correlation risk.

        Args:
            symbol: Trading symbol
            base_size: Base position size

        Returns:
            Adjusted position size
        """
        # Apply correlation risk adjustment
        adjusted_size = int(base_size * self.risk_adjustment_factor)

        # Further adjust by HRP weights if available
        if self.hrp_weights and symbol in self.hrp_weights:
            weight = self.hrp_weights[symbol]
            adjusted_size = int(adjusted_size * weight * len(self.symbols))

        return max(1, adjusted_size)

    def get_risk_status(self) -> str:
        """
        Get portfolio risk status color.

        Returns:
            Risk status: GREEN, YELLOW, or RED
        """
        if self.portfolio_heat_score < 40:
            return "GREEN"
        elif self.portfolio_heat_score < 60:
            return "YELLOW"
        else:
            return "RED"

"""
Advanced regime detection using machine learning (XGBoost).
Replaces Pine Script's simplified ensemble voting.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, Any
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from loguru import logger

from mytypes import Regime
from technical import TechnicalIndicators



class RegimeClassifier:
    """
    ML-based regime classifier using XGBoost.
    Classifies market into TRENDING, RANGING, or VOLATILE regimes.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.65,
        filter_rapid_switches: bool = True,
        min_bars_between_switches: int = 5
    ):
        """
        Initialize regime classifier.

        Args:
            confidence_threshold: Minimum confidence for classification
            filter_rapid_switches: Prevent rapid regime changes
            min_bars_between_switches: Minimum bars between regime changes
        """
        self.confidence_threshold = confidence_threshold
        self.filter_rapid_switches = filter_rapid_switches
        self.min_bars_between_switches = min_bars_between_switches

        self.model: Optional[xgb.XGBClassifier] = None
        self.scaler = StandardScaler()
        self.is_trained = False

        # Regime mapping
        self.regime_map = {
            0: Regime.TRENDING,
            1: Regime.RANGING,
            2: Regime.VOLATILE
        }
        self.reverse_map = {v: k for k, v in self.regime_map.items()}

        # State for filtering
        self.last_regime = Regime.RANGING
        self.bars_since_switch = 100

        logger.info("RegimeClassifier initialized")

    def _extract_features(
        self,
        df: pd.DataFrame,
        atr_lookback: int = 14,
        efficiency_lookback: int = 20
    ) -> pd.DataFrame:
        """
        Extract features for regime classification.

        Args:
            df: OHLCV dataframe
            atr_lookback: ATR period
            efficiency_lookback: Efficiency ratio period

        Returns:
            Feature dataframe
        """
        features = pd.DataFrame(index=df.index)

        # Calculate base indicators
        atr = TechnicalIndicators.atr(df['high'], df['low'], df['close'], atr_lookback)
        efficiency = TechnicalIndicators.efficiency_ratio(df['close'], efficiency_lookback)
        vol_percentile = TechnicalIndicators.volatility_percentile(atr, 100)

        # Feature 1: ATR Percentile (volatility level)
        features['atr_percentile'] = vol_percentile

        # Feature 2: Efficiency Ratio (trend strength)
        features['efficiency_ratio'] = efficiency

        # Feature 3: Price Momentum
        features['momentum_5'] = df['close'].pct_change(5)
        features['momentum_20'] = df['close'].pct_change(20)

        # Feature 4: Volatility Clustering (GARCH-like)
        returns = df['close'].pct_change()
        features['volatility_clustering'] = returns.rolling(20).std()

        # Feature 5: Autocorrelation (mean reversion indicator)
        features['autocorr_5'] = returns.rolling(20).apply(
            lambda x: x.autocorr(5) if len(x) >= 5 else 0
        )

        # Feature 6: Volume Profile
        rvol = TechnicalIndicators.relative_volume(df['volume'], 20)
        features['relative_volume'] = rvol

        # Feature 7: Bollinger Band Width (volatility)
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        bb_width = (std * 2) / sma * 100
        features['bb_width_pct'] = bb_width

        # Feature 8: Directional Movement
        plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
        minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)
        features['directional_movement'] = (plus_dm - minus_dm).rolling(14).mean()

        # Feature 9: Close position in range
        features['close_position'] = (df['close'] - df['low'].rolling(20).min()) / \
                                     (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 1e-10)

        # Feature 10: Range expansion/compression
        current_range = df['high'] - df['low']
        avg_range = current_range.rolling(20).mean()
        features['range_ratio'] = current_range / (avg_range + 1e-10)

        return features.fillna(method='bfill').fillna(0)

    def _create_labels(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
        trending_threshold: int = 70,
        ranging_threshold: int = 60,
        volatile_threshold: int = 80
    ) -> pd.Series:
        """
        Create training labels using rule-based logic (mimics Pine Script).

        Args:
            df: OHLCV dataframe
            features: Feature dataframe
            trending_threshold: Efficiency threshold for trending
            ranging_threshold: Lower bound for ranging
            volatile_threshold: Vol percentile for volatile

        Returns:
            Label series (0=TRENDING, 1=RANGING, 2=VOLATILE)
        """
        labels = pd.Series(1, index=df.index)  # Default: RANGING

        efficiency = features['efficiency_ratio'] * 100
        vol_percentile = features['atr_percentile']

        # Volatile: high volatility percentile
        volatile_mask = vol_percentile >= volatile_threshold
        labels[volatile_mask] = 2

        # Trending: high efficiency and not volatile
        trending_mask = (efficiency >= trending_threshold) & (~volatile_mask)
        labels[trending_mask] = 0

        # Ranging: everything else (already set as default)

        return labels

    def train(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1
    ) -> Dict[str, float]:
        """
        Train XGBoost classifier on historical data.

        Args:
            df: OHLCV dataframe with sufficient history
            test_size: Proportion for test set
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Learning rate

        Returns:
            Training metrics dict
        """
        logger.info("Training regime classifier...")

        # Extract features and labels
        features = self._extract_features(df)
        labels = self._create_labels(df, features)

        # Remove NaN rows
        valid_mask = ~(features.isna().any(axis=1) | labels.isna())
        X = features[valid_mask]
        y = labels[valid_mask]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=False
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train XGBoost
        self.model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective='multi:softprob',
            eval_metric='mlogloss',
            random_state=42
        )

        self.model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_test_scaled, y_test)],
            verbose=False
        )

        self.is_trained = True

        # Calculate metrics
        train_acc = self.model.score(X_train_scaled, y_train)
        test_acc = self.model.score(X_test_scaled, y_test)

        # Feature importance
        feature_importance = dict(zip(
            features.columns,
            self.model.feature_importances_
        ))

        metrics = {
            'train_accuracy': train_acc,
            'test_accuracy': test_acc,
            'n_samples': len(X),
            'feature_importance': feature_importance
        }

        logger.info(f"Training complete - Train Acc: {train_acc:.3f}, Test Acc: {test_acc:.3f}")

        return metrics

    def predict(
        self,
        df: pd.DataFrame,
        return_confidence: bool = True
    ) -> Tuple[pd.Series, Optional[pd.DataFrame]]:
        """
        Predict regime for new data.

        Args:
            df: OHLCV dataframe
            return_confidence: Whether to return confidence scores

        Returns:
            Tuple of (regime_series, confidence_df)
        """
        if not self.is_trained:
            logger.warning("Model not trained, using rule-based fallback")
            return self._rule_based_predict(df), None

        # Extract features
        features = self._extract_features(df)
        X = features.fillna(method='bfill').fillna(0)
        X_scaled = self.scaler.transform(X)

        # Predict probabilities
        probas = self.model.predict_proba(X_scaled)

        # Get predictions
        predicted_classes = np.argmax(probas, axis=1)
        max_probas = np.max(probas, axis=1)

        # Apply confidence threshold
        confident_mask = max_probas >= self.confidence_threshold
        regimes = pd.Series([self.regime_map[c] for c in predicted_classes], index=df.index)

        # Low confidence: use previous regime or RANGING
        regimes[~confident_mask] = Regime.RANGING

        # Filter rapid switches
        if self.filter_rapid_switches:
            regimes = self._filter_switches(regimes)

        if return_confidence:
            confidence_df = pd.DataFrame(
                probas,
                columns=[self.regime_map[i].value for i in range(3)],
                index=df.index
            )
            confidence_df['max_confidence'] = max_probas
            return regimes, confidence_df

        return regimes, None

    def _rule_based_predict(self, df: pd.DataFrame) -> pd.Series:
        """Fallback rule-based prediction (mimics Pine Script)."""
        features = self._extract_features(df)
        labels = self._create_labels(df, features)
        return pd.Series([self.regime_map[l] for l in labels], index=df.index)

    def _filter_switches(self, regimes: pd.Series) -> pd.Series:
        """
        Filter rapid regime switches.

        Args:
            regimes: Raw regime predictions

        Returns:
            Filtered regime series
        """
        filtered = regimes.copy()

        for i in range(len(regimes)):
            if i == 0:
                self.last_regime = regimes.iloc[i]
                self.bars_since_switch = 0
                continue

            current_regime = regimes.iloc[i]

            if current_regime != self.last_regime:
                self.bars_since_switch += 1

                # Block switch if too soon
                if self.bars_since_switch < self.min_bars_between_switches:
                    filtered.iloc[i] = self.last_regime
                else:
                    self.last_regime = current_regime
                    self.bars_since_switch = 0
            else:
                self.bars_since_switch += 1

        return filtered

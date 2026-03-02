"""
Configuration management with validation and environment variable support.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field, validator
from string import Template


class Config(BaseModel):
    """Main configuration model with validation."""
    instrument: Dict[str, Any]
    capital: Dict[str, Any]
    general: Dict[str, Any]
    dre: Dict[str, Any]
    volatility: Dict[str, Any]
    slippage: Dict[str, Any]
    monte_carlo: Dict[str, Any]
    wfo: Dict[str, Any]
    maz: Dict[str, Any]
    htf_bias: Dict[str, Any]
    rejection_blocks: Dict[str, Any]
    volume: Dict[str, Any]
    thresholds: Dict[str, Any]
    mtf: Dict[str, Any]
    filters: Dict[str, Any]
    position_sizing: Dict[str, Any]
    stop_loss: Dict[str, Any]
    take_profit: Dict[str, Any]
    exit_management: Dict[str, Any]
    session: Dict[str, Any]
    daily_limits: Dict[str, Any]
    anti_repainting: Dict[str, Any]
    portfolio: Dict[str, Any]
    ml_regime: Dict[str, Any]
    online_learning: Dict[str, Any]
    rl_execution: Dict[str, Any]
    market_impact: Dict[str, Any]
    database: Dict[str, Any]
    live_trading: Dict[str, Any]
    logging: Dict[str, Any]
    monitoring: Dict[str, Any]
    backtesting: Dict[str, Any]

    class Config:
        extra = "allow"


class ConfigManager:
    """
    Manages configuration loading, validation, and environment variable substitution.
    """

    def __init__(self, config_path: Optional[str] = None, env_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to config.yaml (default: config/config.yaml)
            env_path: Path to .env file (default: .env)
        """
        self.config_path = config_path or "config/config.yaml"
        self.env_path = env_path or ".env"

        # Load environment variables
        if os.path.exists(self.env_path):
            load_dotenv(self.env_path)
            logger.info(f"Loaded environment variables from {self.env_path}")
        else:
            logger.warning(f"No .env file found at {self.env_path}")

        # Load and validate configuration
        self.config = self._load_config()
        logger.info(f"Configuration loaded from {self.config_path}")

    def _load_config(self) -> Config:
        """Load and parse YAML configuration with environment variable substitution."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config_str = f.read()

        # Substitute environment variables (${VAR_NAME})
        config_str = self._substitute_env_vars(config_str)

        # Parse YAML
        config_dict = yaml.safe_load(config_str)

        # Validate with Pydantic
        return Config(**config_dict)

    def _substitute_env_vars(self, config_str: str) -> str:
        """
        Replace ${VAR_NAME} with environment variable values.

        Args:
            config_str: Configuration string with placeholders

        Returns:
            Configuration string with substituted values
        """
        template = Template(config_str)
        env_dict = os.environ.copy()

        # Provide defaults for missing variables
        defaults = {
            'DB_PASSWORD': 'password',
            'BROKER_API_KEY': '',
            'BROKER_API_SECRET': '',
            'BROKER_ACCOUNT_ID': ''
        }

        for key, default in defaults.items():
            if key not in env_dict:
                env_dict[key] = default

        return template.safe_substitute(env_dict)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., 'instrument.symbol')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key_path.split('.')
        value = self.config.dict()

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key_path: str, value: Any) -> None:
        """
        Update configuration value (runtime only, not persisted).

        Args:
            key_path: Dot-separated path
            value: New value
        """
        keys = key_path.split('.')
        config_dict = self.config.dict()

        # Navigate to parent
        current = config_dict
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Update value
        current[keys[-1]] = value

        # Re-validate
        self.config = Config(**config_dict)
        logger.debug(f"Updated config: {key_path} = {value}")

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Save current configuration to YAML file.

        Args:
            output_path: Output path (default: overwrite current config)
        """
        output_path = output_path or self.config_path

        with open(output_path, 'w') as f:
            yaml.dump(self.config.dict(), f, default_flow_style=False, sort_keys=False)

        logger.info(f"Configuration saved to {output_path}")

    def __repr__(self) -> str:
        return f"ConfigManager(config_path={self.config_path})"


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> ConfigManager:
    """
    Initialize global configuration manager.

    Args:
        config_path: Path to config.yaml
        env_path: Path to .env file

    Returns:
        ConfigManager instance
    """
    global _config_manager
    _config_manager = ConfigManager(config_path, env_path)
    return _config_manager

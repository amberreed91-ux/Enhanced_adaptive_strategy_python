# Enhanced Adaptive Trading Strategy - Python Implementation

**Production-ready algorithmic trading system with machine learning, reinforcement learning, and portfolio optimization.**

---

## 🚀 Overview

This is a complete Python translation and enhancement of the Pine Script "Enhanced Adaptive Strategy v5.1". It unlocks capabilities impossible in TradingView:

### Key Enhancements Over Pine Script

✅ **Real-time live trading** with broker APIs (Tradovate, Alpaca, Interactive Brokers)  
✅ **Professional ML regime classification** (XGBoost/LightGBM with cross-validation)  
✅ **Reinforcement learning execution** (Stable-Baselines3 PPO/SAC for order optimization)  
✅ **Full Hierarchical Risk Parity** (PyPortfolioOpt with dendrograms)  
✅ **PostgreSQL/Redis persistence** for state and trade history  
✅ **Level 2 order book analysis** (when using supported brokers)  
✅ **Parallel processing** for Monte Carlo and walk-forward optimization  
✅ **Real market impact tracking** with Kyle's Lambda  
✅ **Production monitoring** with Dash/Streamlit dashboards  

---

## 📁 Project Structure

```
enhanced_adaptive_strategy_python/
├── config/
│   └── config.yaml              # Main configuration file
├── src/
│   ├── core/
│   │   ├── types.py            # Type definitions and data models
│   │   ├── config.py           # Configuration manager
│   │   └── strategy_engine.py  # Main strategy orchestration
│   ├── indicators/
│   │   └── technical.py        # Technical indicators (DRE, volatility, efficiency)
│   ├── ml/
│   │   ├── regime_classifier.py # XGBoost regime detection
│   │   └── rl_optimizer.py      # RL execution optimizer (PPO/SAC)
│   ├── portfolio/
│   │   └── manager.py           # Portfolio correlation + HRP
│   ├── execution/
│   │   └── broker_api.py        # Live broker integrations
│   ├── data/
│   │   └── database.py          # PostgreSQL/SQLite persistence
│   ├── risk/
│   │   └── manager.py           # Risk management logic
│   └── utils/
│       └── helpers.py           # Utility functions
├── tests/                       # Unit tests
├── logs/                        # Log files
├── data/                        # Historical and live data
├── models/                      # Trained ML model checkpoints
├── notebooks/                   # Jupyter notebooks for analysis
├── backtest.py                  # Backtesting script
├── live_trade.py                # Live trading script
├── train_models.py              # Model training script
├── requirements.txt             # Python dependencies
├── .env.template                # Environment variables template
└── README.md                    # This file
```

---

## 🛠️ Installation

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd enhanced_adaptive_strategy_python
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

```bash
cp .env.template .env
# Edit .env with your API keys and database credentials
```

### 5. Initialize Database (Optional - PostgreSQL)

```bash
# If using PostgreSQL
createdb trading_db

# Or use SQLite (default - no setup needed)
```

---

## 🎯 Quick Start

### Backtesting

```bash
# Run backtest with sample data
python backtest.py --data data/historical/MGC_5m.csv --config config/config.yaml

# Output will be in results/ directory:
# - trades.csv
# - equity_curve.csv
# - performance_metrics.json
```

### Train ML Models

```bash
# Train regime classifier and RL optimizer
python train_models.py --data data/historical/MGC_5m.csv --output models/
```

### Live Trading (Paper)

```bash
# Start live trading in paper mode
python live_trade.py --config config/config.yaml --paper
```

---

## 📊 Configuration

All strategy parameters are in `config/config.yaml`. Key sections:

### Instrument Settings
```yaml
instrument:
  symbol: "MGC1!"
  exchange: "COMEX"
  tick_size: 0.1
  is_mgc: true
```

### DRE Concepts (Smart Money)
```yaml
dre:
  enabled: true
  pd_lookback: 50
  require_pd_alignment: true
  breaker_block_lookback: 10
```

### Machine Learning
```yaml
ml_regime:
  enabled: true
  model_type: "xgboost"
  confidence_threshold: 0.65
  retrain_frequency: 100
```

### Reinforcement Learning
```yaml
rl_execution:
  enabled: true
  algorithm: "PPO"
  learning_rate: 0.0003
  actions: ["MARKET", "LIMIT", "VWAP", "TWAP"]
```

### Portfolio Optimization
```yaml
portfolio:
  enabled: true
  symbols: ["MNQ1!", "MGC1!", "ES1!"]
  use_hierarchical_risk_parity: true
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test file
pytest tests/test_indicators.py -v
```

---

## 📈 Features Mapping: Pine Script → Python

| Feature | Pine Script | Python Enhancement |
|---------|-------------|-------------------|
| **Regime Detection** | Rule-based scoring | XGBoost classifier with confidence |
| **Execution** | Market orders only | RL-optimized (MARKET/LIMIT/VWAP/TWAP) |
| **Portfolio Risk** | Basic correlation check | Full HRP with dendrograms |
| **State Management** | `var` (session only) | PostgreSQL + Redis (persistent) |
| **Order Flow** | Volume-based proxy | Real L2 order book (with broker) |
| **Monte Carlo** | Static perturbation | Copula-based correlation simulation |
| **Walk-Forward** | Anchored in-sample | Parallel grid search optimization |
| **Market Impact** | Approximate slippage | Kyle's Lambda from tick data |
| **Monitoring** | TradingView charts | Real-time Dash/Streamlit dashboard |

---

## 🔧 Advanced Usage

### Custom Indicator Development

```python
from src.indicators.technical import TechnicalIndicators

# Add your custom indicator
class CustomIndicators(TechnicalIndicators):
    @staticmethod
    def my_indicator(close: pd.Series, period: int) -> pd.Series:
        # Your logic here
        return result
```

### Live Data Streaming

```python
from src.execution.broker_api import TradovateAPI

api = TradovateAPI(api_key="...", api_secret="...")
api.subscribe_market_data("MGC1!", callback=strategy_engine.process_bar)
```

### Custom RL Reward Function

Edit `src/ml/rl_optimizer.py`:

```python
def _calculate_reward(self, trade_pnl: float, slippage: float) -> float:
    # Implement your custom reward logic
    return custom_reward
```

---

## 📊 Performance Monitoring

### Real-Time Dashboard

```bash
python dashboard.py --port 8050
# Navigate to http://localhost:8050
```

Displays:
- Live P&L chart
- Regime detection visualization
- Correlation heatmap
- Trade execution quality
- RL action probabilities

---

## 🔐 Security Best Practices

1. **Never commit `.env` file** - Contains API keys
2. **Use paper trading first** - Test with virtual money
3. **Enable 2FA** on broker accounts
4. **Monitor API rate limits** - Avoid account restrictions
5. **Set daily loss limits** - Protect capital
6. **Use IP whitelisting** - Restrict API access

---

## 🐛 Troubleshooting

### Issue: "Model not trained" warning
**Solution:** Run `python train_models.py` before backtesting

### Issue: Database connection error
**Solution:** Check `.env` database credentials or use SQLite default

### Issue: RL training very slow
**Solution:** Install PyTorch with GPU support or reduce `total_timesteps`

### Issue: Correlation matrix empty
**Solution:** Ensure sufficient history (50+ bars) for all portfolio symbols

---

## 📚 Documentation

- **API Reference**: See `docs/api_reference.md`
- **Strategy Logic**: See `docs/strategy_guide.md`
- **Broker Integration**: See `docs/broker_setup.md`
- **ML Model Details**: See `docs/ml_models.md`

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

MIT License - See LICENSE file

---

## ⚠️ Disclaimer

**This software is for educational purposes only. Trading involves substantial risk of loss. Past performance does not guarantee future results. Always test strategies thoroughly before risking real capital.**

---

## 📞 Support

- GitHub Issues: Report bugs and request features
- Email: your.email@example.com
- Discord: [Your Discord Server]

---

## 🙏 Acknowledgments

- Original Pine Script strategy design
- Stable-Baselines3 for RL framework
- PyPortfolioOpt for HRP implementation
- XGBoost team for gradient boosting library

---

**Built with ❤️ for algorithmic traders**

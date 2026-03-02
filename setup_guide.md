# Setup Guide - Enhanced Adaptive Strategy

## Complete Installation & Configuration Guide

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Broker Integration](#broker-integration)
6. [Running Your First Backtest](#running-your-first-backtest)
7. [Training ML Models](#training-ml-models)
8. [Going Live](#going-live)
9. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, or Windows 10+
- **Python**: 3.10 or higher
- **RAM**: 8GB
- **Storage**: 10GB free space
- **CPU**: 4 cores (8+ recommended for ML training)

### Recommended for Production
- **OS**: Ubuntu 22.04 LTS or macOS
- **Python**: 3.11
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **CPU**: 8+ cores
- **GPU**: NVIDIA GPU with CUDA support (optional, for faster RL training)

---

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/enhanced-adaptive-strategy.git
cd enhanced-adaptive-strategy-python
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# If using GPU for RL training (optional)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4. Verify Installation

```bash
python -c "import xgboost, stable_baselines3, pypfopt; print('All key packages installed successfully')"
```

---

## Configuration

### 1. Copy Environment Template

```bash
cp .env.template .env
```

### 2. Edit `.env` File

Open `.env` in your text editor and configure:

```bash
# Database (use SQLite for quick start)
DB_PASSWORD=your_secure_password

# For PostgreSQL (production)
DB_CONNECTION_STRING=postgresql://trader:password@localhost:5432/trading_db

# Broker API (get from your broker)
BROKER_API_KEY=your_api_key_here
BROKER_API_SECRET=your_api_secret_here
BROKER_ACCOUNT_ID=your_account_id

# Environment
ENVIRONMENT=development  # or production
LOG_LEVEL=INFO
```

### 3. Edit Configuration File

Open `config/config.yaml` and customize:

```yaml
# Key settings to review:
instrument:
  symbol: "MGC1!"  # Change to your trading symbol
  is_mgc: true

capital:
  initial_capital: 100000  # Adjust to your capital

daily_limits:
  max_daily_loss_percent: 3.0  # Risk management
  max_daily_trades: 10

# Enable/disable modules
ml_regime:
  enabled: true

rl_execution:
  enabled: true

portfolio:
  enabled: true
  symbols: ["MNQ1!", "MGC1!", "ES1!"]  # Your portfolio
```

---

## Database Setup

### Option 1: SQLite (Quick Start - Default)

**No setup needed!** The system will create `data/trading.db` automatically.

### Option 2: PostgreSQL (Production)

**Install PostgreSQL:**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Create Database:**

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE trading_db;
CREATE USER trader WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading_db TO trader;
\q
```

**Update `.env`:**
```bash
DB_CONNECTION_STRING=postgresql://trader:your_password@localhost:5432/trading_db
```

**Verify Connection:**
```bash
python -c "from src.data.database import DatabaseManager; db = DatabaseManager(); print('Database connected!')"
```

---

## Broker Integration

### Tradovate Setup

1. **Get API Credentials:**
   - Log into Tradovate
   - Navigate to Account → API Keys
   - Generate new API credentials

2. **Configure `.env`:**
```bash
TRADOVATE_USERNAME=your_username
TRADOVATE_PASSWORD=your_password
TRADOVATE_CID=your_cid
TRADOVATE_SECRET=your_secret
```

3. **Test Connection:**
```bash
python scripts/test_broker_connection.py --broker tradovate
```

### Alpaca Setup (for equities)

1. **Create Account:** https://alpaca.markets/

2. **Get API Keys:** Dashboard → API Keys

3. **Configure `.env`:**
```bash
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
```

---

## Running Your First Backtest

### 1. Generate Sample Data

```bash
python generate_sample_data.py --output data/historical/MGC_5m.csv --bars 10000
```

### 2. Run Backtest

```bash
python backtest.py \
    --data data/historical/MGC_5m.csv \
    --config config/config.yaml \
    --output results/backtest_001
```

### 3. View Results

```bash
# Check equity curve
cat results/backtest_001/equity_curve.csv

# View trades
cat results/backtest_001/trades.csv

# Performance summary (printed in terminal)
```

**Expected Output:**
```
============================================================
BACKTEST RESULTS
============================================================
total_trades........................................ 150
winning_trades...................................... 82
losing_trades....................................... 68
win_rate............................................ 54.67
total_pnl........................................... 15234.56
sharpe_ratio........................................ 1.85
max_drawdown........................................ -5.2
============================================================
```

---

## Training ML Models

### 1. Prepare Training Data

Ensure you have sufficient historical data (1000+ bars recommended):

```bash
# Check data
python -c "import pandas as pd; df = pd.read_csv('data/historical/MGC_5m.csv'); print(f'Bars: {len(df)}')"
```

### 2. Train Models

```bash
python train_models.py \
    --data data/historical/MGC_5m.csv \
    --output models/ \
    --regime-model xgboost \
    --rl-algorithm PPO \
    --rl-timesteps 50000
```

**Training Time:**
- Regime Classifier: ~1-2 minutes
- RL Optimizer: ~10-30 minutes (CPU), ~2-5 minutes (GPU)

### 3. Verify Trained Models

```bash
ls -lh models/
# Should see:
# regime_classifier.pkl
# rl_optimizer.zip
```

### 4. Run Backtest with Trained Models

```bash
python backtest.py \
    --data data/historical/MGC_5m.csv \
    --no-train  # Use pre-trained models
```

---

## Going Live

### ⚠️ Important: Start with Paper Trading

**Never go live with real money until:**
- ✅ Backtests show consistent profitability
- ✅ Paper trading runs successfully for 1+ month
- ✅ You understand all risk parameters
- ✅ You have tested emergency stop procedures

### 1. Paper Trading Setup

```bash
# Edit config/config.yaml
live_trading:
  enabled: true
  paper_trading: true  # CRITICAL: Keep true for testing
  broker: "tradovate"
```

### 2. Start Paper Trading

```bash
python live_trade.py --config config/config.yaml --paper
```

Monitor logs:
```bash
tail -f logs/live_trading_*.log
```

### 3. Run for 1+ Month

- Monitor daily P&L
- Check execution quality
- Verify risk limits work
- Test emergency stop

### 4. Go Live (After Successful Paper Trading)

**Edit `config/config.yaml`:**
```yaml
live_trading:
  paper_trading: false  # ONLY after thorough testing
```

**Start with minimum position sizes:**
```yaml
capital:
  min_position_size: 1
  max_position_size: 1  # Start with 1 contract
```

**Launch:**
```bash
python live_trade.py --config config/config.yaml
```

---

## Troubleshooting

### Issue: Import Errors

**Error:** `ModuleNotFoundError: No module named 'xgboost'`

**Solution:**
```bash
pip install -r requirements.txt --force-reinstall
```

### Issue: Database Connection Failed

**Error:** `sqlalchemy.exc.OperationalError`

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Or use SQLite (edit config/config.yaml)
database:
  type: "sqlite"
```

### Issue: Model Training Very Slow

**Solution:**
```bash
# Reduce training timesteps
python train_models.py --rl-timesteps 10000

# Or install PyTorch with GPU support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Issue: Backtest No Signals

**Possible Causes:**
1. Confluence threshold too high
2. Insufficient data for indicators
3. Session filter blocking trades

**Solution:**
```yaml
# Lower thresholds temporarily for testing
thresholds:
  trending: 50
  ranging: 40
  volatile: 60
```

### Issue: Live Trading Not Executing

**Check:**
```bash
# Verify broker connection
python scripts/test_broker_connection.py

# Check API rate limits (in logs)
grep "rate limit" logs/live_trading_*.log

# Verify capital/risk limits not exceeded
grep "daily limit" logs/live_trading_*.log
```

---

## Next Steps

1. **Read Strategy Guide:** `docs/strategy_guide.md`
2. **Understand ML Models:** `docs/ml_models.md`
3. **Monitor Performance:** `python dashboard.py`
4. **Join Community:** [Discord link]

---

## Support

- **GitHub Issues:** https://github.com/yourusername/repo/issues
- **Email:** support@example.com
- **Documentation:** https://docs.example.com

**Remember:** Never risk more than you can afford to lose. Test thoroughly before going live.

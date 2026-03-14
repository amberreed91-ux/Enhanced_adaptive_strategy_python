from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import numpy as np
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'default-secret')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))

security = HTTPBearer()

# Create the main app
app = FastAPI(title="Quantitative Research Laboratory API")

# Create routers
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
market_router = APIRouter(prefix="/market-data", tags=["Market Data"])
features_router = APIRouter(prefix="/features", tags=["Features"])
signals_router = APIRouter(prefix="/signals", tags=["Alpha Signals"])
strategies_router = APIRouter(prefix="/strategies", tags=["Strategies"])
backtests_router = APIRouter(prefix="/backtests", tags=["Backtests"])
chat_router = APIRouter(prefix="/chat", tags=["AI Assistant"])

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================= MODELS =======================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class MarketDataConfig(BaseModel):
    asset: str
    exchange: str
    timeframe: str
    data_type: str

class MarketDataResponse(BaseModel):
    id: str
    asset: str
    exchange: str
    timeframe: str
    data_type: str
    record_count: int
    last_updated: str
    status: str

class FeatureConfig(BaseModel):
    name: str
    category: str
    definition: Dict[str, Any]
    lookback_periods: Optional[List[int]] = None

class FeatureResponse(BaseModel):
    id: str
    name: str
    category: str
    definition: Dict[str, Any]
    correlation_to_returns: Optional[float] = None
    information_coefficient: Optional[float] = None
    significance_score: Optional[float] = None
    created_at: str

class SignalCreate(BaseModel):
    name: str
    feature_id: str
    threshold_values: Dict[str, Any]
    market: str

class SignalResponse(BaseModel):
    id: str
    name: str
    feature_id: str
    threshold_values: Dict[str, Any]
    expected_return_distribution: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    market: str
    status: str
    created_at: str

class StrategyCreate(BaseModel):
    name: str
    signal_ids: List[str]
    entry_rules: Dict[str, Any]
    exit_rules: Dict[str, Any]
    position_sizing: str
    risk_params: Dict[str, Any]

class StrategyResponse(BaseModel):
    id: str
    name: str
    signal_ids: List[str]
    entry_rules: Dict[str, Any]
    exit_rules: Dict[str, Any]
    position_sizing: str
    risk_params: Dict[str, Any]
    regime_tags: Optional[List[str]] = []
    status: str
    created_at: str

class BacktestConfig(BaseModel):
    strategy_id: str
    asset: str
    exchange: str
    start_date: str
    end_date: str
    timeframe: str
    slippage: float = 0.001
    commission: float = 0.001

class BacktestResponse(BaseModel):
    id: str
    strategy_id: str
    asset: str
    exchange: str
    date_range: Dict[str, str]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trade_count: int
    equity_curve: List[Dict[str, Any]]
    trade_log: List[Dict[str, Any]]
    created_at: str

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

# ======================= AUTH HELPERS =======================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ======================= AUTH ROUTES =======================

@auth_router.post("/register", response_model=TokenResponse)
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    user_doc = {
        "id": user_id,
        "email": user.email,
        "name": user.name,
        "password_hash": hash_password(user.password),
        "created_at": now
    }
    await db.users.insert_one(user_doc)
    
    token = create_token(user_id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user_id, email=user.email, name=user.name, created_at=now)
    )

@auth_router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])
    )

@auth_router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])

# ======================= MOCK EXCHANGE DATA =======================

MOCK_ASSETS = {
    "futures": ["ES", "NQ", "CL", "GC"],
    "crypto": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT"]
}

MOCK_EXCHANGES = ["CME Group", "Binance", "Coinbase", "Kraken"]

def generate_mock_ohlcv(length: int = 500) -> List[Dict]:
    """Generate realistic mock OHLCV data"""
    data = []
    price = 100.0
    base_time = datetime.now(timezone.utc) - timedelta(days=length)
    
    for i in range(length):
        volatility = random.uniform(0.01, 0.03)
        change = random.gauss(0, volatility)
        price *= (1 + change)
        
        high = price * (1 + random.uniform(0, 0.02))
        low = price * (1 - random.uniform(0, 0.02))
        open_price = price * (1 + random.uniform(-0.01, 0.01))
        volume = random.randint(10000, 100000)
        
        data.append({
            "timestamp": (base_time + timedelta(days=i)).isoformat(),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2),
            "volume": volume
        })
    return data

def generate_mock_orderbook() -> Dict:
    """Generate mock order book data"""
    mid_price = random.uniform(90, 110)
    bids = []
    asks = []
    
    for i in range(10):
        bid_price = mid_price * (1 - 0.001 * (i + 1))
        ask_price = mid_price * (1 + 0.001 * (i + 1))
        bids.append({"price": round(bid_price, 2), "size": random.randint(100, 1000)})
        asks.append({"price": round(ask_price, 2), "size": random.randint(100, 1000)})
    
    return {
        "bids": bids,
        "asks": asks,
        "mid_price": round(mid_price, 2),
        "spread": round(asks[0]["price"] - bids[0]["price"], 4),
        "imbalance": round(random.uniform(-1, 1), 3)
    }

# ======================= MARKET DATA ROUTES =======================

@market_router.get("/assets")
async def get_assets():
    return MOCK_ASSETS

@market_router.get("/exchanges")
async def get_exchanges():
    return MOCK_EXCHANGES

@market_router.post("/ingest", response_model=MarketDataResponse)
async def ingest_market_data(config: MarketDataConfig, user: dict = Depends(get_current_user)):
    data_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate mock data
    ohlcv_data = generate_mock_ohlcv(500)
    
    doc = {
        "id": data_id,
        "user_id": user["id"],
        "asset": config.asset,
        "exchange": config.exchange,
        "timeframe": config.timeframe,
        "data_type": config.data_type,
        "data": ohlcv_data,
        "record_count": len(ohlcv_data),
        "last_updated": now,
        "status": "active"
    }
    await db.market_data.insert_one(doc)
    
    return MarketDataResponse(
        id=data_id, asset=config.asset, exchange=config.exchange,
        timeframe=config.timeframe, data_type=config.data_type,
        record_count=len(ohlcv_data), last_updated=now, status="active"
    )

@market_router.get("/feeds", response_model=List[MarketDataResponse])
async def get_market_feeds(user: dict = Depends(get_current_user)):
    feeds = await db.market_data.find({"user_id": user["id"]}, {"_id": 0, "data": 0}).to_list(100)
    return [MarketDataResponse(**f) for f in feeds]

@market_router.get("/orderbook/{asset}")
async def get_orderbook(asset: str):
    return generate_mock_orderbook()

@market_router.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: str, user: dict = Depends(get_current_user)):
    result = await db.market_data.delete_one({"id": feed_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"status": "deleted"}

# ======================= FEATURE ROUTES =======================

@features_router.post("/generate", response_model=List[FeatureResponse])
async def generate_features(configs: List[FeatureConfig], user: dict = Depends(get_current_user)):
    features = []
    now = datetime.now(timezone.utc).isoformat()
    
    for config in configs:
        feature_id = str(uuid.uuid4())
        
        # Generate mock statistical metrics
        correlation = round(random.uniform(-0.5, 0.5), 4)
        ic = round(random.uniform(0, 0.15), 4)
        significance = round(random.uniform(0, 1), 4)
        
        doc = {
            "id": feature_id,
            "user_id": user["id"],
            "name": config.name,
            "category": config.category,
            "definition": config.definition,
            "correlation_to_returns": correlation,
            "information_coefficient": ic,
            "significance_score": significance,
            "created_at": now
        }
        await db.features.insert_one(doc)
        features.append(FeatureResponse(**{k: v for k, v in doc.items() if k != "user_id"}))
    
    return features

@features_router.get("/", response_model=List[FeatureResponse])
async def get_features(user: dict = Depends(get_current_user)):
    features = await db.features.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(500)
    return [FeatureResponse(**f) for f in features]

@features_router.delete("/{feature_id}")
async def delete_feature(feature_id: str, user: dict = Depends(get_current_user)):
    result = await db.features.delete_one({"id": feature_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feature not found")
    return {"status": "deleted"}

# ======================= SIGNALS ROUTES =======================

@signals_router.post("/", response_model=SignalResponse)
async def create_signal(signal: SignalCreate, user: dict = Depends(get_current_user)):
    signal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate mock distribution
    distribution = {
        "mean": round(random.uniform(-0.02, 0.05), 4),
        "std": round(random.uniform(0.01, 0.05), 4),
        "skew": round(random.uniform(-1, 1), 4),
        "kurtosis": round(random.uniform(2, 5), 4)
    }
    
    doc = {
        "id": signal_id,
        "user_id": user["id"],
        "name": signal.name,
        "feature_id": signal.feature_id,
        "threshold_values": signal.threshold_values,
        "expected_return_distribution": distribution,
        "confidence_score": round(random.uniform(0.5, 0.95), 3),
        "market": signal.market,
        "status": "active",
        "created_at": now
    }
    await db.signals.insert_one(doc)
    
    return SignalResponse(**{k: v for k, v in doc.items() if k != "user_id"})

@signals_router.get("/", response_model=List[SignalResponse])
async def get_signals(user: dict = Depends(get_current_user)):
    signals = await db.signals.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(500)
    return [SignalResponse(**s) for s in signals]

@signals_router.patch("/{signal_id}/status")
async def update_signal_status(signal_id: str, status: str, user: dict = Depends(get_current_user)):
    result = await db.signals.update_one(
        {"id": signal_id, "user_id": user["id"]},
        {"$set": {"status": status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"status": "updated"}

# ======================= STRATEGIES ROUTES =======================

@strategies_router.post("/", response_model=StrategyResponse)
async def create_strategy(strategy: StrategyCreate, user: dict = Depends(get_current_user)):
    strategy_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    doc = {
        "id": strategy_id,
        "user_id": user["id"],
        "name": strategy.name,
        "signal_ids": strategy.signal_ids,
        "entry_rules": strategy.entry_rules,
        "exit_rules": strategy.exit_rules,
        "position_sizing": strategy.position_sizing,
        "risk_params": strategy.risk_params,
        "regime_tags": [],
        "status": "draft",
        "created_at": now
    }
    await db.strategies.insert_one(doc)
    
    return StrategyResponse(**{k: v for k, v in doc.items() if k != "user_id"})

@strategies_router.get("/", response_model=List[StrategyResponse])
async def get_strategies(user: dict = Depends(get_current_user)):
    strategies = await db.strategies.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(100)
    return [StrategyResponse(**s) for s in strategies]

@strategies_router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, user: dict = Depends(get_current_user)):
    strategy = await db.strategies.find_one({"id": strategy_id, "user_id": user["id"]}, {"_id": 0, "user_id": 0})
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyResponse(**strategy)

@strategies_router.patch("/{strategy_id}/status")
async def update_strategy_status(strategy_id: str, status: str, user: dict = Depends(get_current_user)):
    result = await db.strategies.update_one(
        {"id": strategy_id, "user_id": user["id"]},
        {"$set": {"status": status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "updated"}

@strategies_router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, user: dict = Depends(get_current_user)):
    result = await db.strategies.delete_one({"id": strategy_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "deleted"}

# ======================= BACKTEST ROUTES =======================

def run_mock_backtest(config: BacktestConfig) -> Dict:
    """Run a mock backtest simulation"""
    # Generate synthetic equity curve
    equity = [10000.0]
    trades = []
    
    num_trades = random.randint(50, 200)
    base_time = datetime.fromisoformat(config.start_date.replace('Z', '+00:00'))
    
    for i in range(num_trades):
        pnl = random.gauss(0.002, 0.01) * equity[-1]
        equity.append(equity[-1] + pnl)
        
        trade_time = base_time + timedelta(days=i)
        trades.append({
            "id": str(uuid.uuid4())[:8],
            "timestamp": trade_time.isoformat(),
            "side": "long" if random.random() > 0.5 else "short",
            "entry_price": round(random.uniform(90, 110), 2),
            "exit_price": round(random.uniform(90, 110), 2),
            "pnl": round(pnl, 2),
            "duration_hours": random.randint(1, 48)
        })
    
    # Calculate metrics
    returns = [(equity[i] - equity[i-1]) / equity[i-1] for i in range(1, len(equity))]
    
    max_dd = 0
    peak = equity[0]
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > max_dd:
            max_dd = dd
    
    winning_trades = len([t for t in trades if t["pnl"] > 0])
    gross_profit = sum([t["pnl"] for t in trades if t["pnl"] > 0])
    gross_loss = abs(sum([t["pnl"] for t in trades if t["pnl"] < 0]))
    
    equity_curve = [
        {"timestamp": (base_time + timedelta(days=i)).isoformat(), "equity": round(e, 2)}
        for i, e in enumerate(equity)
    ]
    
    return {
        "total_return": round((equity[-1] - equity[0]) / equity[0] * 100, 2),
        "sharpe_ratio": round(np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": round(winning_trades / len(trades) * 100, 2),
        "profit_factor": round(gross_profit / gross_loss if gross_loss > 0 else 0, 2),
        "trade_count": len(trades),
        "equity_curve": equity_curve,
        "trade_log": trades
    }

@backtests_router.post("/run", response_model=BacktestResponse)
async def run_backtest(config: BacktestConfig, user: dict = Depends(get_current_user)):
    # Verify strategy exists
    strategy = await db.strategies.find_one({"id": config.strategy_id, "user_id": user["id"]})
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    backtest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Run mock backtest
    results = run_mock_backtest(config)
    
    doc = {
        "id": backtest_id,
        "user_id": user["id"],
        "strategy_id": config.strategy_id,
        "asset": config.asset,
        "exchange": config.exchange,
        "date_range": {"start": config.start_date, "end": config.end_date},
        "timeframe": config.timeframe,
        "total_return": results["total_return"],
        "sharpe_ratio": results["sharpe_ratio"],
        "max_drawdown": results["max_drawdown"],
        "win_rate": results["win_rate"],
        "profit_factor": results["profit_factor"],
        "trade_count": results["trade_count"],
        "equity_curve": results["equity_curve"],
        "trade_log": results["trade_log"],
        "created_at": now
    }
    await db.backtests.insert_one(doc)
    
    return BacktestResponse(**{k: v for k, v in doc.items() if k not in ["user_id", "timeframe"]})

@backtests_router.get("/", response_model=List[BacktestResponse])
async def get_backtests(user: dict = Depends(get_current_user)):
    backtests = await db.backtests.find(
        {"user_id": user["id"]}, 
        {"_id": 0, "user_id": 0, "timeframe": 0}
    ).to_list(100)
    return [BacktestResponse(**b) for b in backtests]

@backtests_router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(backtest_id: str, user: dict = Depends(get_current_user)):
    backtest = await db.backtests.find_one(
        {"id": backtest_id, "user_id": user["id"]}, 
        {"_id": 0, "user_id": 0, "timeframe": 0}
    )
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return BacktestResponse(**backtest)

# ======================= AI CHAT ROUTES =======================

@chat_router.post("/message", response_model=ChatResponse)
async def chat_message(message: ChatMessage, user: dict = Depends(get_current_user)):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    session_id = message.session_id or str(uuid.uuid4())
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key not configured")
    
    # Get user's data context
    strategies_count = await db.strategies.count_documents({"user_id": user["id"]})
    signals_count = await db.signals.count_documents({"user_id": user["id"]})
    backtests_count = await db.backtests.count_documents({"user_id": user["id"]})
    
    system_message = f"""You are an AI research assistant for a Quantitative Research Laboratory. 
You help traders and researchers with algorithmic trading questions.

Current user context:
- Active strategies: {strategies_count}
- Alpha signals: {signals_count}
- Completed backtests: {backtests_count}

You can answer questions about:
- Trading strategies and alpha generation
- Market regimes and conditions
- Backtesting results and performance metrics
- Risk management and portfolio allocation
- Feature generation and signal discovery

Be concise, technical, and data-driven in your responses."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        user_msg = UserMessage(text=message.message)
        response = await chat.send_message(user_msg)
        
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")

# ======================= DASHBOARD ROUTES =======================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    strategies = await db.strategies.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    backtests = await db.backtests.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    signals = await db.signals.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    
    active_strategies = len([s for s in strategies if s.get("status") == "live"])
    
    # Get top signals by IC
    top_signals = sorted(
        [{"name": s["name"], "ic": s.get("confidence_score", 0)} for s in signals],
        key=lambda x: x["ic"],
        reverse=True
    )[:5]
    
    # Mock regime detection
    regimes = ["Trend", "Range", "Volatility Expansion", "Mean Reversion"]
    current_regime = random.choice(regimes)
    
    # Generate portfolio equity curve (mock aggregation)
    equity_curve = []
    base = 100000
    for i in range(30):
        base *= (1 + random.gauss(0.001, 0.01))
        equity_curve.append({
            "date": (datetime.now(timezone.utc) - timedelta(days=30-i)).strftime("%Y-%m-%d"),
            "equity": round(base, 2)
        })
    
    # Capital allocation mock
    allocation = []
    if strategies:
        for s in strategies[:5]:
            allocation.append({
                "name": s["name"],
                "allocation": round(random.uniform(10, 30), 1)
            })
    
    return {
        "active_strategies": active_strategies,
        "total_strategies": len(strategies),
        "total_signals": len(signals),
        "total_backtests": len(backtests),
        "current_regime": current_regime,
        "top_signals": top_signals,
        "equity_curve": equity_curve,
        "capital_allocation": allocation,
        "research_cycle_progress": random.randint(20, 80),
        "current_drawdown": round(random.uniform(0, 15), 2),
        "drawdown_threshold": 20,
        "system_health": {
            "market_data": "healthy",
            "feature_engine": "healthy",
            "backtest_engine": "healthy",
            "execution_engine": "idle",
            "risk_monitor": "healthy"
        }
    }

# ======================= ROOT ROUTE =======================

@api_router.get("/")
async def root():
    return {"message": "Quantitative Research Laboratory API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(market_router)
api_router.include_router(features_router)
api_router.include_router(signals_router)
api_router.include_router(strategies_router)
api_router.include_router(backtests_router)
api_router.include_router(chat_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

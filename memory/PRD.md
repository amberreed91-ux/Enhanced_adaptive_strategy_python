# Quantitative Research Laboratory - PRD

## Original Problem Statement
Build a full-stack web application called Quantitative Research Laboratory - a professional-grade algorithmic trading research platform that autonomously discovers, validates, stress tests, evolves, and deploys trading strategies across futures and cryptocurrency markets.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Recharts + Shadcn/UI components
- **Backend**: FastAPI (Python) with async MongoDB (Motor)
- **Database**: MongoDB
- **Authentication**: JWT-based email/password auth
- **AI Integration**: GPT-5.2 via Emergent LLM key
- **Exchange APIs**: Mocked (Binance, Coinbase, Kraken, CME Group)

## User Personas
1. **Quantitative Researcher** - Discovers alpha signals, generates features
2. **Algorithm Trader** - Builds and backtests strategies
3. **Portfolio Manager** - Monitors performance and risk

## Core Requirements
- Multi-page dashboard with collapsible sidebar navigation
- Dark trading terminal aesthetic with electric blue/green accents
- Real-time charts and data visualization
- Strategy lifecycle management (draft → testing → live → retired)
- AI research assistant chat widget

## What's Been Implemented (March 2026)

### MVP Phase 1 - Complete
1. **Authentication System** - JWT login/register with protected routes
2. **Dashboard** - Portfolio equity curve, market regime detection, system health
3. **Market Data Manager** - Asset/exchange selection, data feed ingestion, order book viewer
4. **Feature Generation Engine** - Configurable features (price, volume, cross-timeframe, microstructure)
5. **Backtesting Engine** - Strategy testing with equity curves, trade logs, performance metrics
6. **Strategy Builder** - Strategy creation with entry/exit rules, position sizing, risk parameters
7. **Settings Page** - Exchange connection status, user preferences
8. **AI Research Assistant** - GPT-5.2 powered chat widget

### Technical Implementation
- Custom CSS variables for trading terminal aesthetic
- Responsive sidebar with collapsible navigation groups
- Recharts for financial data visualization
- MongoDB with proper ObjectId handling
- sonner for toast notifications

## Prioritized Backlog

### P0 - Critical (Next)
- [ ] Alpha Signal Library page
- [ ] Monte Carlo Simulator page
- [ ] Robustness Validator page

### P1 - High Priority
- [ ] Simulation Market Lab (synthetic market stress testing)
- [ ] Strategy Evolution Engine (genetic algorithm)
- [ ] Market Regime Detector (ML-based classification)

### P2 - Medium Priority
- [ ] Portfolio Allocation Engine
- [ ] Execution Engine with real exchange integration
- [ ] Risk Management Console enhancements

### P3 - Low Priority
- [ ] Research Experiment Tracker
- [ ] Meta Optimization Engine
- [ ] Adaptive Research Scheduler
- [ ] Live Performance Monitor enhancements

## Next Action Items
1. Implement Alpha Signal Library for storing discovered signals
2. Add Monte Carlo simulation for strategy validation
3. Create Robustness Validator with walk-forward testing
4. Build Simulation Market Lab for synthetic stress testing
5. Connect real exchange APIs when user provides API keys

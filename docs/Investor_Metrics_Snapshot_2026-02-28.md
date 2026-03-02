# Investor Metrics Snapshot (Chimera)
Date: February 28, 2026

## Executive Read
This snapshot summarizes what can be verified directly from the current Chimera workspace. It separates validated technical evidence from missing business metrics.

## Business KPIs (Currently Missing in Repo)
- Monthly revenue (MRR): Not found
- Active users: Not found
- Paid conversion rate: Not found
- Monthly churn: Not found
- 3-month growth: Not found

Implication: valuation discussion is currently driven by technical proof, not commercial traction.

## Technical Track Record (Verified)
### Logged run-history span
- First backtest log: `logs/backtest_2026-02-22_12-59-19_172227.log`
- Latest backtest log: `logs/backtest_2026-02-28_04-03-18_551603.log`
- Span: ~6 days (~0.2 months)

### Best-Case Performance View (High headline, lower sample)
Source: `results/optimizer/robust_v6_mixed_50k_c12_t40/summary.json`
- MGC trades: 26
- MGC win rate: 69.23%
- MGC profit factor: 4.248
- MNQ trades: 26
- MNQ win rate: 69.23%
- MNQ profit factor: 4.104

Interpretation:
- Strong headline quality, but low trade count for investor-grade confidence.

### Conservative Performance View (Larger sample)
Source: `results/optimizer/goal_625/summary.json`
- MGC trades: 264
- MGC win rate: 54.17%
- MGC profit factor: 1.997
- MNQ trades: 163
- MNQ win rate: 58.90%
- MNQ profit factor: 3.465

Interpretation:
- Better sample depth and still strong PF, but win-rate below the 62.5% stretch target.

## Current Risk/Governance Evidence (Product Strength)
Verified in code/config:
- Webhook executor with routing + profile control
- Hard risk guard controls (daily loss, cooldown, symbol kill switch)
- Audit trail logging of decisions and responses
- Watchdog telemetry and health tracking

Primary references:
- `automation/chimera_executor.py`
- `config/config.yaml`
- `data/chimera_execution_audit.jsonl`

## Investor Narrative (Current Stage)
- Position today: technically credible early-stage system with visible risk controls and promising but still maturing performance evidence.
- Main gap before stronger investability: commercial proof (users/revenue/retention) and longer forward track record.

## 30-60 Day Data Plan to Improve Investability
1. Build a weekly KPI export with stable definitions:
   - Net PnL, PF, win rate, max drawdown, trade count, skipped-trade count.
2. Add paper/live-forward monthly cohorts by symbol/profile.
3. Create a lightweight business metrics table:
   - trials, activated users, paid users, churn, MRR.
4. Freeze one baseline profile and run it unchanged for a fixed evaluation window.

## Confidence Labels
- Business metrics confidence: Low (not present in repo)
- Technical metric confidence: Medium-High (file-verified)
- Forward predictive confidence: Medium-Low (short historical window in current workspace)

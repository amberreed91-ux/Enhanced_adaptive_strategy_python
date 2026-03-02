# Chimera Automation (Tradovate Paper) - MNQ1!/MGC1!

This service receives TradingView webhooks and executes paper orders after Chimera gating.

## 1) Start executor

```bash
cd /Users/amberreed/Enhanced_adaptive_strategy_python
source venv/bin/activate
python run_chimera_executor.py --config config/config.yaml --host 127.0.0.1 --port 8787
```

Status check:

```bash
curl http://127.0.0.1:8787/status
```

## 2) Keep Chimera app running

Chimera bridge file must stay fresh:

```bash
streamlit run bookmap_engine/app_streamlit.py
```

Keep:
- `Write Strategy Bridge File` = ON
- Bridge path = `data/bookmap_signal.json`

## 3) TradingView webhook setup

Create alert webhook URL:

```text
http://127.0.0.1:8787/webhook/tradingview
```

For broker-side fill mirroring (journal sync from TradingView-connected broker), use:

```text
http://127.0.0.1:8787/webhook/tradingview/fill
```

For TradingView Paper Trading specifically, use:

```text
http://127.0.0.1:8787/webhook/tradingview/paper
```

If calling from outside your machine, expose securely (Cloudflare Tunnel/ngrok) and use HTTPS.

## 4) TradingView alert JSON payload

Use a webhook message like:

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": "{{close}}",
  "timestamp_utc": "{{timenow}}"
}
```

For fill mirroring with explicit sizing/broker:

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": "{{close}}",
  "qty": "{{strategy.order.contracts}}",
  "timestamp_utc": "{{timenow}}",
  "strategy_profile": "balanced",
  "broker": "tradovate"
}
```

For TradingView Paper Trading endpoint (`/webhook/tradingview/paper`), broker is auto-set:

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": "{{close}}",
  "qty": "{{strategy.order.contracts}}",
  "timestamp_utc": "{{timenow}}",
  "strategy_profile": "balanced"
}
```

Broker aliases accepted:
- `papertrading`
- `tradingview_paper`
- `tradingview-paper`
- `tv_paper`

Supported actions:
- buy/long/go_long -> LONG
- sell/short/go_short -> SHORT
- close/flat/exit -> FLAT

Allowed symbols are locked to:
- `MNQ1!`
- `MGC1!`

## 5) What gets enforced before paper fill

1. Symbol allow-list
2. Daily trade limit + cooldown
3. Chimera bridge gate (`bookmap_bridge.profile` rules)
4. Paper execution + state/log write

### Fill mirror mode (`/webhook/tradingview/fill`)

- Purpose: keep Chimera journal in sync with TradingView-connected broker fills.
- Bypasses Chimera bridge/risk gate checks (journaling mirror only).
- Still enforces symbol allow-list.
- Writes to the same broker journal files as paper execution.

### TradingView Paper mode (`/webhook/tradingview/paper`)

- Same behavior as fill mirror mode.
- Always routes to broker journal: `data/tradingview_paper/`.

Files written:
- `data/<broker>/paper_broker_state.json`
- `data/<broker>/paper_orders.csv`
- `data/<broker>/closed_trades.csv`

## 6) Security

Optional shared secret:
- set `automation.webhook_secret` in config
- send header `X-Chimera-Secret: <secret>` from your webhook relay

## 7) Current scope

This is Tradovate-aligned paper automation (safe mode).  
No live broker order submission is enabled yet.

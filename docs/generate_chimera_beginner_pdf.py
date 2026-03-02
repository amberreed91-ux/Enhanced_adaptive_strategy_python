from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent
OUT_PDF = ROOT / "Chimera_Beginner_Walkthrough.pdf"
OUT_TXT = ROOT / "Chimera_Beginner_Walkthrough.txt"


def add_title(ax, title: str, subtitle: str = "") -> None:
    ax.axis("off")
    ax.text(0.03, 0.95, title, fontsize=24, fontweight="bold", va="top")
    if subtitle:
        ax.text(0.03, 0.90, subtitle, fontsize=12, color="#333", va="top")


def add_wrapped(ax, x: float, y: float, text: str, width: int = 100, size: int = 11, line_gap: float = 0.035) -> float:
    wrapped = textwrap.fill(text, width=width)
    ax.text(x, y, wrapped, fontsize=size, va="top")
    lines = wrapped.count("\n") + 1
    return y - lines * line_gap


def box(ax, x, y, w, h, label, fc="#eef4ff", ec="#2c5aa0"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02", fc=fc, ec=ec, lw=1.6)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=10, fontweight="bold")


def arrow(ax, x1, y1, x2, y2):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=15, lw=1.5, color="#333")
    ax.add_patch(a)


playbook_text = """CHIMERA BEGINNER WALKTHROUGH + PLAYBOOK
Date: February 28, 2026

WHO THIS IS FOR
You are new to Chimera, TradingView, and strategy automation.
This guide explains what to click, what each signal means, and how to run safe paper testing first.

IMPORTANT
This is educational and process guidance, not financial advice.
No strategy guarantees profit. Use strict risk limits.

=================================================================
1) BIG PICTURE: CHIMERA VS ICC VS PURE ICC
=================================================================

Simple definitions:
- ICC approach: usually structure + liquidity + timing concepts.
- Pure ICC ideology: discretionary, trader interprets everything manually.
- Chimera: ICC-style logic + objective filters + bridge gate + execution auditing.

Why Chimera is usually better for beginners:
1. Fewer impulse trades: bridge can block weak entries.
2. Better consistency: rules are codified instead of memory-only.
3. Better review loop: every webhook/signal is logged.
4. Better safety: paper mode, kill-switches, profile gates.

Tradeoff:
- Pure discretionary trading can be flexible, but consistency is harder.
- Chimera is more structured and therefore easier to audit and improve.

=================================================================
2) CHIMERA SIGNAL FLOW (END-TO-END)
=================================================================

Step A: TradingView strategy finds a setup (LONG/SHORT/FLAT intent).
Step B: Chimera bridge checks microstructure and profile rules.
Step C: Executor decides pass/block and logs reason.
Step D: Paper journal updates (orders, state, closed trades).

Golden rule:
If TradingView and Chimera do not agree -> NO TRADE.

=================================================================
3) HOW TO USE TRADINGVIEW WITH CHIMERA
=================================================================

A) Sign in to TradingView
1. Open your browser and sign in at tradingview.com.
2. Open the chart for the same symbol you use in Chimera (example: MNQ1! or MGC1!).
3. Set your timeframe (example: 5m) and keep it consistent.

B) Load your Pine strategy
1. Open Pine Editor.
2. Paste/load your Chimera-aligned Pine strategy.
3. Click Add to chart and verify strategy orders appear.

C) Create webhook alert
1. Click Alert.
2. Condition: your strategy order event.
3. Webhook URL (local): http://127.0.0.1:8787/webhook/tradingview
4. Message JSON example:
   {
     "symbol":"{{ticker}}",
     "action":"{{strategy.order.action}}",
     "price":"{{close}}",
     "timestamp_utc":"{{timenow}}"
   }

D) If using TradingView Paper mode mirroring
- Use endpoint: /webhook/tradingview/paper
- Chimera stores mirrored journal in data/tradingview_paper/

Note about "sign in to TradingView on Chimera":
Chimera does not replace TradingView login itself. You sign in on TradingView,
then connect to Chimera by webhook endpoint.

=================================================================
4) CHIMERA APP SIGNALS VS TRADINGVIEW SIGNALS
=================================================================

TradingView signal = setup intent from your Pine strategy.
Chimera signal state = execution-quality decision from bridge + guardrails.

Think of it like this:
- TradingView asks: "Do I see a setup?"
- Chimera asks: "Is this setup good enough to execute now?"

When they differ:
- TV LONG + Chimera NO_TRADE -> skip.
- TV SHORT + Chimera GO_LONG -> skip.
- Alignment required for discipline.

=================================================================
5) BEGINNER EXPLANATION OF THE PINE STRATEGY
=================================================================

Most Chimera-aligned Pine scripts do five jobs:
1. Context: trend/range regime detection.
2. Trigger: entry condition (break/sweep/reclaim/etc.).
3. Risk: stop loss + take profit levels.
4. Sizing: fixed or rule-based quantity.
5. Output: sends order actions used by alerts/webhooks.

Keep beginner defaults simple:
- One symbol
- One timeframe
- One risk profile (strict or balanced)
- Fixed size in paper mode

Only optimize one variable at a time.

=================================================================
6) BACKTEST LAB (BEGINNER WORKFLOW)
=================================================================

Goal: validate behavior before live risk.

Quick run example (from this repo):
venv/bin/python scripts/run_backtest_profile.py --profile combined_trend_ict_range --dataset mixed_50k

Useful profiles:
- trend_only
- range_preserved
- ict_asian_sweep
- ict_asian_sweep_inverted
- combined_trend_ict_range

Where results go:
results/backtests/<profile>/<dataset>_<timestamp>/

What to review first:
1. total trades
2. win rate
3. profit factor
4. max drawdown
5. average trade quality

Beginner promotion rule (paper -> more size):
- 60+ trades
- Profit factor >= 1.30
- Max drawdown <= 4%
- Stable behavior across multiple recent runs

=================================================================
7) DAILY CHECKLIST (BEGINNER SOP)
=================================================================

Before session:
- Start Chimera app (bridge writing ON)
- Start executor server
- Confirm /status is healthy
- Confirm TradingView alert is active and pointing to correct webhook

During session:
- Take only aligned signals
- Respect daily loss/trade limits
- Do not switch profiles mid-emotion

After session:
- Review blocked vs executed signals
- Read journal files
- Mark rule violations
- Decide one improvement for next day

=================================================================
8) TROUBLESHOOTING QUICK FIXES
=================================================================

Problem: No fills recorded
- Check executor running on 127.0.0.1:8787
- Check alert webhook URL and JSON fields

Problem: Too many blocked trades
- You may be on strict profile with low-confidence market
- Collect sample before loosening filters

Problem: TV chart and Chimera feel out of sync
- Check symbol/timeframe match
- Check action mapping (LONG/SHORT/FLAT)
- Check clock/timezone consistency

=================================================================
9) FINAL PLAYBOOK SUMMARY
=================================================================

Use this order every day:
1. Prepare system
2. Validate signal alignment
3. Execute only when both engines agree
4. Respect risk limits
5. Review logs and improve process

Chimera wins for beginners when you treat it as a rules engine,
not a prediction machine.
"""

OUT_TXT.write_text(playbook_text)

with PdfPages(OUT_PDF) as pdf:
    # Page 1
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Chimera Beginner Walkthrough", "Playbook: Chimera vs ICC / TradingView / Backtest Lab")
    y = 0.84
    y = add_wrapped(ax, 0.03, y, "This guide is designed for beginners. It gives you a full, step-by-step workflow from setup to review, with visual maps and checklists.", 95, 12)
    y -= 0.02
    y = add_wrapped(ax, 0.03, y, "Core idea: TradingView finds setups. Chimera decides execution quality. You only trade when both agree.", 95, 12)
    y -= 0.03
    ax.text(0.03, y, "What this PDF covers", fontsize=13, fontweight="bold", va="top")
    y -= 0.04
    bullets = [
        "Chimera vs ICC vs pure ICC ideology (plain English)",
        "How Pine strategy logic works for a beginner",
        "How to sign in and connect TradingView to Chimera",
        "Chimera app signals vs TradingView signals",
        "Backtest Lab workflow and promotion gates",
        "Daily checklist and troubleshooting",
    ]
    for b in bullets:
        ax.text(0.05, y, f"- {b}", fontsize=11, va="top")
        y -= 0.04
    ax.text(0.03, 0.08, "Date: February 28, 2026", fontsize=10, color="#555")
    pdf.savefig(fig)
    plt.close(fig)

    # Page 2 comparison visual
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Chimera vs ICC Comparison", "Why Chimera is usually easier for beginners")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    box(ax, 0.05, 0.72, 0.25, 0.14, "Pure ICC\n(Discretionary)", fc="#fef5e7", ec="#b9770e")
    box(ax, 0.37, 0.72, 0.25, 0.14, "ICC-style Rules\n(Structured)", fc="#eaf2f8", ec="#1f618d")
    box(ax, 0.69, 0.72, 0.25, 0.14, "Chimera\n(Rules + Gate + Logs)", fc="#e8f8f5", ec="#117864")

    ax.text(0.05, 0.60, "Flexibility", fontsize=11, fontweight="bold")
    ax.text(0.37, 0.60, "Consistency", fontsize=11, fontweight="bold")
    ax.text(0.69, 0.60, "Auditability", fontsize=11, fontweight="bold")

    ax.text(0.05, 0.54, "High", fontsize=11)
    ax.text(0.37, 0.54, "Medium", fontsize=11)
    ax.text(0.69, 0.54, "High", fontsize=11)

    ax.text(0.05, 0.46, "Main risk", fontsize=11, fontweight="bold")
    ax.text(0.05, 0.42, "Impulse decisions", fontsize=10)
    ax.text(0.37, 0.42, "Rule drift", fontsize=10)
    ax.text(0.69, 0.42, "Over-filtering if too strict", fontsize=10)

    ax.text(0.03, 0.30, "Beginner takeaway", fontsize=13, fontweight="bold")
    ax.text(0.03, 0.25, "Chimera is better when your goal is repeatable process, not discretionary hero trades.", fontsize=11)
    ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)

    # Page 3 system flow
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "System Flow Visual", "From TradingView signal to Chimera journal")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    box(ax, 0.12, 0.78, 0.30, 0.10, "TradingView + Pine\nDetects LONG/SHORT/FLAT", fc="#eaf2ff")
    box(ax, 0.58, 0.78, 0.30, 0.10, "Webhook Alert\nJSON Payload", fc="#f5eef8", ec="#7d3c98")
    box(ax, 0.12, 0.56, 0.30, 0.10, "Chimera Executor\nRisk + Symbol Checks", fc="#fdebd0", ec="#af601a")
    box(ax, 0.58, 0.56, 0.30, 0.10, "Bridge Gate\nGO_LONG/GO_SHORT/NO_TRADE", fc="#e8f8f5", ec="#117864")
    box(ax, 0.35, 0.34, 0.30, 0.10, "Paper Journal\norders/state/closed trades", fc="#ebf5fb", ec="#21618c")

    arrow(ax, 0.42, 0.83, 0.58, 0.83)
    arrow(ax, 0.73, 0.78, 0.73, 0.66)
    arrow(ax, 0.58, 0.61, 0.42, 0.61)
    arrow(ax, 0.27, 0.56, 0.27, 0.44)
    arrow(ax, 0.73, 0.56, 0.50, 0.44)

    ax.text(0.03, 0.22, "Rule: execute only when strategy direction and bridge decision align.", fontsize=11)
    ax.text(0.03, 0.17, "If not aligned, Chimera should block or skip.", fontsize=11)
    ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)

    # Page 4 setup steps
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "TradingView + Chimera Setup", "Exact beginner steps")
    y = 0.86
    steps = [
        "1) Sign in to TradingView in your browser (tradingview.com).",
        "2) Open chart: MNQ1! or MGC1! (same symbol/timeframe as Chimera).",
        "3) Load Pine strategy and verify strategy orders plot on chart.",
        "4) Start executor: python run_chimera_executor.py --config config/config.yaml --host 127.0.0.1 --port 8787",
        "5) In TradingView alert: webhook URL = http://127.0.0.1:8787/webhook/tradingview",
        "6) Use JSON fields: symbol/action/price/timestamp_utc.",
        "7) For TV paper mirror use: /webhook/tradingview/paper",
        "8) Confirm health: curl http://127.0.0.1:8787/status",
    ]
    for s in steps:
        y = add_wrapped(ax, 0.04, y, s, 95, 11)
        y -= 0.012

    ax.text(0.04, y - 0.01, "Important: Chimera does not host TradingView login. You log in on TradingView, then connect via webhook.", fontsize=10, color="#7b241c")
    ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)

    # Page 5 signals comparison
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Signals: TradingView vs Chimera", "How to interpret conflicts")
    ax.axis("off")
    y = 0.86
    lines = [
        "TradingView signal: setup intent from Pine logic.",
        "Chimera signal/gate: execution-quality decision based on bridge profile and guardrails.",
        "",
        "Decision matrix:",
        "- TV LONG + Chimera GO_LONG = eligible",
        "- TV SHORT + Chimera GO_SHORT = eligible",
        "- TV LONG + Chimera GO_SHORT = block",
        "- TV SHORT + Chimera GO_LONG = block",
        "- Any + NO_TRADE = block",
        "",
        "Beginner rule: if in doubt, skip. Missing a trade is cheaper than forcing a bad one.",
    ]
    for ln in lines:
        ax.text(0.04, y, ln, fontsize=11, va="top")
        y -= 0.05
    pdf.savefig(fig)
    plt.close(fig)

    # Page 6 pine explanation
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Pine Strategy Explained", "5 building blocks")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    blocks = [
        (0.08, 0.78, "1) Context\nTrend/Range"),
        (0.55, 0.78, "2) Trigger\nEntry condition"),
        (0.08, 0.58, "3) Risk\nStop + Targets"),
        (0.55, 0.58, "4) Sizing\nQty rules"),
        (0.31, 0.38, "5) Output\nAlerts/Webhook"),
    ]
    for x, y, label in blocks:
        box(ax, x, y, 0.34, 0.12, label, fc="#f8f9f9", ec="#34495e")
    arrow(ax, 0.42, 0.84, 0.55, 0.84)
    arrow(ax, 0.25, 0.78, 0.25, 0.70)
    arrow(ax, 0.72, 0.78, 0.72, 0.70)
    arrow(ax, 0.25, 0.58, 0.48, 0.50)
    arrow(ax, 0.72, 0.58, 0.54, 0.50)

    ax.text(0.05, 0.24, "Beginner default: one symbol, one timeframe, fixed size, strict process.", fontsize=11)
    ax.text(0.05, 0.19, "Optimize one variable at a time.", fontsize=11)
    ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)

    # Page 7 backtest lab
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Backtest Lab Workflow", "From run to promotion decision")
    ax.axis("off")
    y = 0.86
    items = [
        "Run profile:",
        "venv/bin/python scripts/run_backtest_profile.py --profile combined_trend_ict_range --dataset mixed_50k",
        "",
        "Review outputs under: results/backtests/<profile>/<dataset>_<timestamp>/",
        "",
        "Check these metrics first:",
        "1. Total trades",
        "2. Win rate",
        "3. Profit factor",
        "4. Max drawdown",
        "5. Avg trade",
        "",
        "Promotion gate (paper to bigger size):",
        "- 60+ trades",
        "- PF >= 1.30",
        "- Max DD <= 4%",
        "- Stable across multiple windows",
    ]
    for it in items:
        ax.text(0.04, y, it, fontsize=11, va="top")
        y -= 0.045
    pdf.savefig(fig)
    plt.close(fig)

    # Page 8 checklist + troubleshooting
    fig, ax = plt.subplots(figsize=(8.5, 11))
    add_title(ax, "Daily SOP + Troubleshooting", "Beginner-safe operations")
    ax.axis("off")
    y = 0.86
    content = [
        "Before session:",
        "- Chimera app running (bridge writes on)",
        "- Executor healthy at /status",
        "- TradingView alert active with correct webhook",
        "",
        "During session:",
        "- Take aligned signals only",
        "- Respect max daily loss and trade caps",
        "- No revenge sizing",
        "",
        "After session:",
        "- Review blocked vs filled signals",
        "- Read data/<broker>/closed_trades.csv",
        "- Log one process improvement",
        "",
        "Quick fixes:",
        "- No fills: check webhook URL, executor port, JSON keys",
        "- Too many blocks: strict profile may be too selective for current tape",
        "- Sync issues: verify symbol/timeframe/action mapping",
    ]
    for c in content:
        ax.text(0.04, y, c, fontsize=11, va="top")
        y -= 0.04
    ax.text(0.04, 0.07, "Final principle: Chimera is a discipline framework. Let it reduce bad decisions.", fontsize=11, fontweight="bold")
    pdf.savefig(fig)
    plt.close(fig)

print(f"Wrote {OUT_TXT}")
print(f"Wrote {OUT_PDF}")

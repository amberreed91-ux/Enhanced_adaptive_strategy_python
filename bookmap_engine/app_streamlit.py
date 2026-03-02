from __future__ import annotations

import os
import sys
import time
import math
import csv
import html
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yaml

# Ensure project root is importable when Streamlit runs this file directly.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bookmap_engine.core import BookmapEngine
from bookmap_engine.bridge import BookmapBridgeSignal, write_bridge_signal, utc_now_iso
from bookmap_engine.bridge import bridge_signal_age_seconds, read_bridge_signal
from bookmap_engine.feed import (
    BinanceFeedConfig,
    BinanceRestOrderBookFeed,
    ExternalL2BridgeConfig,
    ExternalL2BridgeFeed,
    ReplayFeedConfig,
    ReplayOrderBookFeed,
    SyntheticFeedConfig,
    SyntheticOrderBookFeed,
    snapshot_to_record,
)


def _synthetic_profile_for_symbol(symbol: str) -> tuple[float, float, float]:
    s = (symbol or "").upper().strip()
    if s.startswith("MNQ") or s.startswith("NQ"):
        return 25000.0, 0.25, 6.0
    if s.startswith("MGC") or s.startswith("GC"):
        return 5200.0, 0.1, 1.8
    if s.startswith("ES"):
        return 6100.0, 0.25, 2.2
    if s.startswith("CL"):
        return 70.0, 0.01, 0.35
    if s.startswith("YM"):
        return 44000.0, 1.0, 10.0
    if s.startswith("RTY"):
        return 2300.0, 0.1, 1.2
    if s.startswith("ETH"):
        return 1900.0, 0.1, 4.0
    if s.startswith("BTC"):
        return 65000.0, 1.0, 35.0
    return 25000.0, 0.25, 2.0


def _inject_app_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

        :root {
          --chimera-bg0: #0a1017;
          --chimera-bg1: #101a24;
          --chimera-card: rgba(16, 24, 34, 0.85);
          --chimera-card-soft: rgba(14, 22, 31, 0.62);
          --chimera-border: rgba(245, 176, 0, 0.23);
          --chimera-accent: #f5b000;
          --chimera-accent-soft: #ffd166;
          --chimera-text: #e8eff7;
          --chimera-muted: #9fb2c7;
          --chimera-success: #2ecf9f;
          --chimera-danger: #ff6b6b;
        }

        html, body, [data-testid="stAppViewContainer"] {
          font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
          color: var(--chimera-text);
        }

        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(1200px 560px at 10% -10%, rgba(245,176,0,0.14), transparent 45%),
            radial-gradient(900px 480px at 95% 0%, rgba(46,207,159,0.09), transparent 45%),
            linear-gradient(170deg, var(--chimera-bg0), var(--chimera-bg1));
        }

        [data-testid="stHeader"] {
          background: transparent;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #0d1621 0%, #0a121a 100%);
          border-right: 1px solid rgba(255,255,255,0.07);
        }

        [data-testid="stSidebar"] * {
          font-family: "Space Grotesk", "Avenir Next", sans-serif;
        }

        .stTextInput input, .stNumberInput input, .stTextArea textarea {
          border-radius: 10px !important;
          border: 1px solid rgba(255,255,255,0.14) !important;
          background: rgba(10,16,24,0.72) !important;
        }

        .stSelectbox > div > div, .stMultiSelect > div > div {
          border-radius: 10px !important;
          background: rgba(10,16,24,0.72) !important;
        }

        .stButton > button {
          border-radius: 10px !important;
          border: 1px solid rgba(245,176,0,0.30) !important;
          background: linear-gradient(180deg, rgba(245,176,0,0.20), rgba(245,176,0,0.10)) !important;
          color: var(--chimera-text) !important;
          font-weight: 600 !important;
          min-height: 42px !important;
          letter-spacing: 0.015em;
          transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
        }

        .stButton > button:hover {
          transform: translateY(-1px);
          border-color: rgba(245,176,0,0.72) !important;
          box-shadow: 0 6px 18px rgba(0,0,0,0.28);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
          letter-spacing: 0.04em;
          text-transform: uppercase;
          font-size: 0.92rem !important;
          margin-top: 0.9rem;
          margin-bottom: 0.45rem;
          color: #d9e4f0;
        }

        div[data-testid="metric-container"] {
          background: linear-gradient(180deg, var(--chimera-card), var(--chimera-card-soft));
          border: 1px solid rgba(255,255,255,0.08);
          border-left: 2px solid var(--chimera-border);
          border-radius: 14px;
          padding: 10px 12px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 12px 22px rgba(0,0,0,0.22);
          animation: chimera-rise 280ms ease-out;
        }

        div[data-testid="metric-container"] [data-testid="stMetricValue"],
        div[data-testid="metric-container"] [data-testid="stMetricDelta"],
        .ops-value,
        .signal-number {
          font-variant-numeric: tabular-nums;
          font-feature-settings: "tnum" 1;
        }

        [data-testid="stDataFrame"] {
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 14px;
          overflow: hidden;
        }

        [data-testid="stPlotlyChart"] {
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 14px;
          background: linear-gradient(180deg, rgba(14,21,31,0.70), rgba(8,14,22,0.62));
          padding: 6px;
          box-shadow: 0 14px 24px rgba(0,0,0,0.25);
        }

        .chimera-hero {
          position: relative;
          overflow: hidden;
          border-radius: 18px;
          border: 1px solid rgba(255,255,255,0.10);
          background:
            radial-gradient(600px 240px at -10% 0%, rgba(245,176,0,0.17), transparent 60%),
            linear-gradient(140deg, rgba(16,24,35,0.9), rgba(11,17,25,0.88));
          padding: 20px 22px 16px;
          margin-bottom: 10px;
          box-shadow: 0 14px 34px rgba(0,0,0,0.28);
        }

        .chimera-kicker {
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--chimera-accent-soft);
          font-size: 0.77rem;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .chimera-title {
          margin: 0;
          font-size: clamp(1.45rem, 2.6vw, 2.25rem);
          line-height: 1.05;
          color: var(--chimera-text);
        }

        .chimera-sub {
          margin-top: 6px;
          color: var(--chimera-muted);
          font-size: 0.96rem;
        }

        .chimera-pills {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 12px;
        }

        .chimera-pill {
          font-family: "IBM Plex Mono", monospace;
          font-size: 0.78rem;
          padding: 4px 10px;
          border-radius: 999px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.12);
          color: #d7e3ef;
        }

        .chimera-pill-strong {
          border-color: rgba(245,176,0,0.55);
          color: var(--chimera-accent-soft);
          background: rgba(245,176,0,0.10);
        }

        .signal-card {
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,0.10);
          background: linear-gradient(180deg, rgba(18,28,40,0.88), rgba(10,18,28,0.84));
          padding: 12px 12px 10px;
          margin-bottom: 10px;
        }

        .signal-state {
          display: inline-block;
          font-family: "IBM Plex Mono", monospace;
          letter-spacing: 0.06em;
          font-weight: 700;
          font-size: 1rem;
          border-radius: 999px;
          padding: 5px 12px;
          margin-bottom: 8px;
          border: 1px solid transparent;
        }

        .signal-state-long {
          color: #7ef0c3;
          background: rgba(46, 207, 159, 0.16);
          border-color: rgba(46, 207, 159, 0.45);
        }

        .signal-state-short {
          color: #ff9b9b;
          background: rgba(255, 107, 107, 0.14);
          border-color: rgba(255, 107, 107, 0.42);
        }

        .signal-state-flat {
          color: #ffd166;
          background: rgba(245, 176, 0, 0.12);
          border-color: rgba(245, 176, 0, 0.40);
        }

        .signal-row {
          display: grid;
          grid-template-columns: 1fr auto;
          align-items: center;
          column-gap: 8px;
          font-size: 0.84rem;
          color: #bed0e3;
          margin-top: 8px;
          margin-bottom: 4px;
        }

        .signal-number {
          letter-spacing: 0.02em;
          color: #e7f0f9;
        }

        .signal-bar {
          width: 100%;
          height: 9px;
          border-radius: 999px;
          background: rgba(255,255,255,0.08);
          overflow: hidden;
          border: 1px solid rgba(255,255,255,0.09);
        }

        .signal-bar-fill {
          height: 100%;
          border-radius: 999px;
          transition: width 160ms ease;
        }

        .signal-bar-fill-conf {
          background: linear-gradient(90deg, #ffd166, #f5b000);
        }

        .signal-bar-fill-imb-buy {
          background: linear-gradient(90deg, #41d39f, #2ecf9f);
        }

        .signal-bar-fill-imb-sell {
          background: linear-gradient(90deg, #ff8a8a, #ff6b6b);
        }

        .signal-notes {
          margin-top: 10px;
          color: #9fb2c7;
          font-size: 0.80rem;
          line-height: 1.25;
        }

        .ops-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          margin: 8px 0 12px;
        }

        .ops-card {
          border: 1px solid rgba(255,255,255,0.09);
          border-radius: 12px;
          background: linear-gradient(180deg, rgba(16,25,36,0.86), rgba(11,19,29,0.78));
          padding: 10px 11px;
          min-height: 76px;
        }

        .ops-label {
          color: #9db0c3;
          font-size: 0.76rem;
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }

        .ops-value {
          color: #e8eff7;
          font-size: 1.65rem;
          font-weight: 700;
          line-height: 1.12;
          margin-top: 4px;
        }

        .ops-sub {
          margin-top: 2px;
          color: #89a1b6;
          font-size: 0.79rem;
        }

        .ops-pill {
          display: inline-block;
          margin-top: 6px;
          padding: 3px 9px;
          border-radius: 999px;
          font-size: 0.72rem;
          font-family: "IBM Plex Mono", monospace;
          border: 1px solid transparent;
        }

        .ops-pill-ok {
          color: #7ef0c3;
          background: rgba(46, 207, 159, 0.14);
          border-color: rgba(46, 207, 159, 0.38);
        }

        .ops-pill-warn {
          color: #ffd78a;
          background: rgba(245, 176, 0, 0.13);
          border-color: rgba(245, 176, 0, 0.38);
        }

        .ops-pill-bad {
          color: #ffadad;
          background: rgba(255, 107, 107, 0.14);
          border-color: rgba(255, 107, 107, 0.40);
        }

        .exec-strip {
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.10);
          background: linear-gradient(180deg, rgba(16,25,36,0.82), rgba(10,18,28,0.76));
          padding: 10px 10px 2px;
          margin-bottom: 8px;
        }

        .exec-strip-title {
          color: #9db0c3;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          font-size: 0.75rem;
          margin-bottom: 8px;
        }

        .section-head {
          position: relative;
          margin: 2px 0 8px;
          padding: 8px 10px 8px 12px;
          border-radius: 11px;
          border: 1px solid rgba(255,255,255,0.10);
          background: linear-gradient(90deg, rgba(245,176,0,0.12), rgba(255,255,255,0.03));
        }

        .section-head::before {
          content: "";
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 3px;
          border-radius: 11px 0 0 11px;
          background: linear-gradient(180deg, #ffd166, #2ecf9f);
        }

        .section-head-title {
          letter-spacing: 0.04em;
          text-transform: uppercase;
          font-size: 0.76rem;
          font-weight: 700;
          color: #dce8f4;
          margin: 0;
        }

        .section-head-sub {
          margin: 2px 0 0;
          font-size: 0.75rem;
          color: #9ab1c6;
        }

        .status-marquee {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin: 8px 0 10px;
        }

        .status-chip {
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.12);
          padding: 4px 10px;
          font-family: "IBM Plex Mono", monospace;
          font-size: 0.72rem;
          color: #d7e4f0;
          background: rgba(255,255,255,0.04);
        }

        .status-chip-ok {
          border-color: rgba(46, 207, 159, 0.35);
          background: rgba(46, 207, 159, 0.12);
          color: #9cf1d1;
        }

        .status-chip-warn {
          border-color: rgba(245, 176, 0, 0.40);
          background: rgba(245, 176, 0, 0.13);
          color: #ffdca0;
        }

        .status-chip-bad {
          border-color: rgba(255, 107, 107, 0.42);
          background: rgba(255, 107, 107, 0.14);
          color: #ffb9b9;
        }

        .path-chip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 8px;
          margin: -2px 0 6px;
          padding: 5px 8px;
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.08);
          background: rgba(255,255,255,0.03);
          color: #9fb2c7;
          font-family: "IBM Plex Mono", monospace;
          font-size: 0.67rem;
        }

        .path-chip .path-chip-main {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 210px;
        }

        .path-chip .path-chip-state {
          flex-shrink: 0;
          border-radius: 999px;
          padding: 1px 7px;
          border: 1px solid rgba(255,255,255,0.14);
        }

        .path-chip-ok {
          border-color: rgba(46, 207, 159, 0.30);
          background: rgba(46, 207, 159, 0.08);
        }

        .path-chip-missing {
          border-color: rgba(255, 107, 107, 0.33);
          background: rgba(255, 107, 107, 0.08);
        }

        .chimera-alert {
          border-radius: 12px;
          border: 1px solid transparent;
          margin: 0 0 10px;
          padding: 10px 12px;
          font-weight: 600;
        }

        .chimera-alert-error {
          background: linear-gradient(180deg, rgba(255, 107, 107, 0.19), rgba(112, 34, 34, 0.25));
          border-color: rgba(255, 107, 107, 0.45);
          color: #ffb8b8;
        }

        .chimera-alert-warn {
          background: linear-gradient(180deg, rgba(245, 176, 0, 0.16), rgba(99, 66, 11, 0.24));
          border-color: rgba(245, 176, 0, 0.42);
          color: #ffdfa0;
        }

        .chimera-alert-success {
          background: linear-gradient(180deg, rgba(46, 207, 159, 0.19), rgba(20, 89, 69, 0.24));
          border-color: rgba(46, 207, 159, 0.45);
          color: #a5f3d3;
        }

        .empty-state {
          border-radius: 12px;
          border: 1px dashed rgba(255,255,255,0.18);
          background: linear-gradient(180deg, rgba(16,24,36,0.55), rgba(10,17,26,0.45));
          padding: 14px 14px 12px;
          margin: 6px 0;
        }

        .empty-title {
          margin: 0;
          color: #d5e3f1;
          font-size: 0.94rem;
          font-weight: 600;
        }

        .empty-copy {
          margin: 4px 0 0;
          color: #9eb4c8;
          font-size: 0.82rem;
        }

        .gate-table {
          width: 100%;
          border-collapse: collapse;
          border: 1px solid rgba(255,255,255,0.09);
          border-radius: 12px;
          overflow: hidden;
          margin-top: 8px;
        }

        .gate-table th, .gate-table td {
          text-align: left;
          padding: 9px 10px;
          border-bottom: 1px solid rgba(255,255,255,0.07);
          font-size: 0.84rem;
        }

        .gate-table th {
          color: #b8cade;
          background: rgba(255,255,255,0.03);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          font-size: 0.73rem;
        }

        .gate-status {
          display: inline-block;
          padding: 2px 9px;
          border-radius: 999px;
          font-family: "IBM Plex Mono", monospace;
          font-size: 0.72rem;
          border: 1px solid transparent;
        }

        .gate-status-pass {
          border-color: rgba(46, 207, 159, 0.42);
          background: rgba(46, 207, 159, 0.14);
          color: #a0f0cf;
        }

        .gate-status-fail {
          border-color: rgba(255, 107, 107, 0.42);
          background: rgba(255, 107, 107, 0.14);
          color: #ffb9b9;
        }

        div[data-baseweb="tab-list"] {
          gap: 6px;
          margin: 2px 0 10px;
          padding: 4px;
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.09);
          background: linear-gradient(180deg, rgba(15,23,34,0.88), rgba(9,15,24,0.80));
        }

        button[data-baseweb="tab"] {
          border-radius: 9px !important;
          border: 1px solid transparent !important;
          background: rgba(255,255,255,0.02) !important;
          color: #aac0d6 !important;
          padding-top: 6px !important;
          padding-bottom: 6px !important;
          letter-spacing: 0.02em;
          font-size: 0.85rem !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
          border-color: rgba(245,176,0,0.42) !important;
          background: linear-gradient(180deg, rgba(245,176,0,0.22), rgba(245,176,0,0.12)) !important;
          color: #ffe5b0 !important;
          box-shadow: 0 8px 16px rgba(0,0,0,0.24);
        }

        .stSlider [data-baseweb="slider"] [role="slider"] {
          border: 2px solid rgba(245,176,0,0.72) !important;
          box-shadow: 0 0 0 4px rgba(245,176,0,0.16);
        }

        .stSlider [data-testid="stTickBar"] > div {
          background: linear-gradient(90deg, rgba(245,176,0,0.82), rgba(46,207,159,0.74)) !important;
        }

        /* Hide Streamlit header controls for a cleaner trading-console feel. */
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        #MainMenu,
        header [data-testid="stHeaderActionElements"] {
          display: none !important;
        }

        [data-testid="stAlert"] {
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.10);
        }

        @media (max-width: 1180px) {
          .ops-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @keyframes chimera-rise {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 880px) {
          .chimera-hero {
            padding: 14px 14px 12px;
            border-radius: 14px;
          }
          .chimera-sub {
            font-size: 0.9rem;
          }
          .ops-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .ops-value {
            font-size: 1.40rem;
          }
          .section-head-sub {
            font-size: 0.72rem;
          }
        }

        @media (max-width: 640px) {
          .ops-grid {
            grid-template-columns: 1fr;
          }
          .signal-row {
            font-size: 0.8rem;
          }
          .path-chip .path-chip-main {
            max-width: 160px;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _short_path(path_value: str, max_len: int = 56) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    expanded = os.path.abspath(os.path.expanduser(raw))
    if len(expanded) <= max_len:
        return expanded
    parts = Path(expanded).parts
    if len(parts) >= 3:
        compact = os.path.join("...", *parts[-2:])
        if len(compact) <= max_len:
            return compact
    return "..." + expanded[-(max_len - 3):]


def _render_path_chip(label: str, path_value: str) -> None:
    raw = str(path_value or "").strip()
    if not raw:
        return
    path_obj = Path(os.path.expanduser(raw))
    exists = path_obj.exists()
    state_text = "exists" if exists else "missing"
    chip_state_class = "path-chip-ok" if exists else "path-chip-missing"
    short = _short_path(raw)
    st.markdown(
        (
            f'<div class="path-chip {chip_state_class}" title="{html.escape(str(path_obj))}">'
            f'<span class="path-chip-main">{html.escape(label)}: {html.escape(short)}</span>'
            f'<span class="path-chip-state">{state_text}</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_inline_alert(message: str, level: str = "warn") -> None:
    if level == "success":
        css = "chimera-alert-success"
    elif level == "error":
        css = "chimera-alert-error"
    else:
        css = "chimera-alert-warn"
    st.markdown(
        f'<div class="chimera-alert {css}">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _render_section_head(title: str, subtitle: str = "") -> None:
    safe_title = html.escape(title)
    safe_sub = html.escape(subtitle)
    sub_html = f'<div class="section-head-sub">{safe_sub}</div>' if safe_sub else ""
    st.markdown(
        f"""
        <div class="section-head">
          <div class="section-head-title">{safe_title}</div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_status_marquee(
    session_label: str,
    strategy_profile: str,
    feed_ok: bool,
    bridge_ok: bool,
    exec_ok: bool,
) -> None:
    feed_class = "status-chip-ok" if feed_ok else "status-chip-warn"
    bridge_class = "status-chip-ok" if bridge_ok else "status-chip-warn"
    exec_class = "status-chip-ok" if exec_ok else "status-chip-bad"
    st.markdown(
        f"""
        <div class="status-marquee">
          <span class="status-chip">SESSION: {html.escape(session_label.upper())}</span>
          <span class="status-chip">PROFILE: {html.escape(strategy_profile.upper())}</span>
          <span class="status-chip {feed_class}">FEED: {'OK' if feed_ok else 'WARN'}</span>
          <span class="status-chip {bridge_class}">BRIDGE: {'OK' if bridge_ok else 'WARN'}</span>
          <span class="status-chip {exec_class}">EXECUTOR: {'UP' if exec_ok else 'DOWN'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state(title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
          <p class="empty-title">{html.escape(title)}</p>
          <p class="empty-copy">{html.escape(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_gate_table(gate_rows: List[Dict[str, str]]) -> None:
    body_rows: List[str] = []
    for row in gate_rows:
        status = str(row.get("Status", "FAIL")).upper()
        status_css = "gate-status-pass" if status == "PASS" else "gate-status-fail"
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('Gate', '')))}</td>"
            f"<td><span class='gate-status {status_css}'>{html.escape(status)}</span></td>"
            f"<td>{html.escape(str(row.get('Detail', '')))}</td>"
            "</tr>"
        )
    st.markdown(
        (
            "<table class='gate-table'>"
            "<thead><tr><th>Gate</th><th>Status</th><th>Detail</th></tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table>"
        ),
        unsafe_allow_html=True,
    )


def _render_hero(symbol: str, feed_mode: str, strategy_profile: str) -> None:
    safe_symbol = html.escape(symbol)
    safe_feed_mode = html.escape(feed_mode)
    safe_profile = html.escape(strategy_profile.upper())
    st.markdown(
        f"""
        <section class="chimera-hero">
          <div class="chimera-kicker">CHIMERA EXECUTION CONSOLE</div>
          <h1 class="chimera-title">Bookmap + Automation Control Room</h1>
          <div class="chimera-sub">Production-focused signal panel with replay, watchdog, and broker-aware routing.</div>
          <div class="chimera-pills">
            <span class="chimera-pill chimera-pill-strong">Symbol: {safe_symbol}</span>
            <span class="chimera-pill">Feed: {safe_feed_mode}</span>
            <span class="chimera-pill">Profile: {safe_profile}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_system_overview(
    feed_ok: bool,
    bridge_ok: bool,
    exec_ok: bool,
    session_label: str,
    feed_mode: str,
    bridge_text: str,
    exec_text: str,
    feed_delay_seconds: float,
    bridge_age_seconds: float,
    webhook_rtt_p95_ms: float,
    idle_age_seconds: float,
) -> None:
    feed_delay_text = "NA" if math.isinf(feed_delay_seconds) else f"{feed_delay_seconds:.1f}s"
    bridge_age_text = "NA" if math.isinf(bridge_age_seconds) else f"{bridge_age_seconds:.1f}s"
    idle_text = "NA" if math.isinf(idle_age_seconds) else f"{idle_age_seconds:.0f}s"

    feed_pill = "ops-pill-ok" if feed_ok else "ops-pill-warn"
    bridge_pill = "ops-pill-ok" if bridge_ok else "ops-pill-warn"
    exec_pill = "ops-pill-ok" if exec_ok else "ops-pill-bad"

    st.markdown(
        f"""
        <section class="ops-grid">
          <article class="ops-card">
            <div class="ops-label">Feed Delay</div>
            <div class="ops-value">{feed_delay_text}</div>
            <div class="ops-sub">{feed_mode}</div>
            <span class="ops-pill {feed_pill}">{'FEED OK' if feed_ok else 'FEED WARN'}</span>
          </article>
          <article class="ops-card">
            <div class="ops-label">Bridge Age</div>
            <div class="ops-value">{bridge_age_text}</div>
            <div class="ops-sub">{bridge_text}</div>
            <span class="ops-pill {bridge_pill}">{'BRIDGE OK' if bridge_ok else 'BRIDGE WARN'}</span>
          </article>
          <article class="ops-card">
            <div class="ops-label">Webhook RTT p95</div>
            <div class="ops-value">{float(webhook_rtt_p95_ms):.1f}ms</div>
            <div class="ops-sub">Executor idle: {idle_text}</div>
            <span class="ops-pill {exec_pill}">{'EXEC UP' if exec_ok else 'EXEC DOWN'}</span>
          </article>
          <article class="ops-card">
            <div class="ops-label">Session</div>
            <div class="ops-value">{session_label}</div>
            <div class="ops-sub">Executor: {exec_text}</div>
            <span class="ops-pill ops-pill-ok">LIVE MONITOR</span>
          </article>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _ensure_state() -> None:
    if "engine" not in st.session_state:
        st.session_state.engine = BookmapEngine(
            levels=int(st.session_state.get("heatmap_levels", 60)),
            history=int(st.session_state.get("heatmap_history", 180)),
        )
    if "feed" not in st.session_state:
        cfg = SyntheticFeedConfig(
            seed=42,
            start_price=25000.0,
            tick_size=0.25,
            levels_per_side=max(30, int(st.session_state.get("heatmap_levels", 120) // 2)),
        )
        st.session_state.feed = SyntheticOrderBookFeed(cfg)
    if "seeded" not in st.session_state:
        st.session_state.seeded = False
    if "feed_mode" not in st.session_state:
        st.session_state.feed_mode = "Futures L2 Bridge (JSON)"
    if "feed_symbol" not in st.session_state:
        st.session_state.feed_symbol = "MGC1!"
    if "active_feed_mode" not in st.session_state:
        st.session_state.active_feed_mode = "Futures L2 Bridge (JSON)"
    if "active_feed_symbol" not in st.session_state:
        st.session_state.active_feed_symbol = "MGC1!"
    if "active_heatmap_levels" not in st.session_state:
        st.session_state.active_heatmap_levels = int(getattr(st.session_state.engine, "levels", 60))
    if "active_heatmap_history" not in st.session_state:
        st.session_state.active_heatmap_history = int(getattr(st.session_state.engine, "history", 180))
    if "external_l2_path" not in st.session_state:
        st.session_state.external_l2_path = os.path.join(ROOT, "data", "live_l2_snapshot.json")
    if "replay_file_path" not in st.session_state:
        st.session_state.replay_file_path = os.path.join(ROOT, "data", "replay_snapshots.jsonl")
    if "bridge_path" not in st.session_state:
        st.session_state.bridge_path = os.path.join(ROOT, "data", "bookmap_signal.json")
    if "last_alert_decision" not in st.session_state:
        st.session_state.last_alert_decision = "NO_TRADE"
    if "last_alert_epoch" not in st.session_state:
        st.session_state.last_alert_epoch = 0.0
    if "frozen_y_range" not in st.session_state:
        st.session_state.frozen_y_range = None
    if "decision_history" not in st.session_state:
        st.session_state.decision_history = []
    if "recent_alerts" not in st.session_state:
        st.session_state.recent_alerts = []
    if "last_feed_error" not in st.session_state:
        st.session_state.last_feed_error = ""
    if "last_loaded_ui_symbol" not in st.session_state:
        st.session_state.last_loaded_ui_symbol = ""
    if "ui_settings_path" not in st.session_state:
        st.session_state.ui_settings_path = os.path.join(ROOT, "data", "chimera_ui_settings.json")
    if "strategy_profile" not in st.session_state:
        st.session_state.strategy_profile = "balanced"
    if "last_snapshot_timestamp_utc" not in st.session_state:
        st.session_state.last_snapshot_timestamp_utc = ""
    if "watchdog_last_alert_epoch" not in st.session_state:
        st.session_state.watchdog_last_alert_epoch = 0.0

    # Default UI controls (key-based for persistence/presets).
    tradecount_bt_cfg = os.path.join(ROOT, "config", "config_combined_tradecount_v2.yaml")
    combined_bt_cfg = os.path.join(ROOT, "config", "config_combined_trend_ict_range.yaml")
    if os.path.exists(tradecount_bt_cfg):
        default_bt_cfg = tradecount_bt_cfg
    elif os.path.exists(combined_bt_cfg):
        default_bt_cfg = combined_bt_cfg
    else:
        default_bt_cfg = os.path.join(ROOT, "config", "config.yaml")
    defaults: Dict[str, Any] = {
        "ui_mode": "Pro",
        "whale_pct": 97,
        "whale_min": 25.0,
        "absorb_pct": 80,
        "sweep_pct": 75,
        "quiet_mode": False,
        "zoom_view": True,
        "auto_follow_mid": False,
        "show_trade_bubbles": True,
        "bubble_scale": 1.8,
        "heatmap_levels": 120,
        "heatmap_history": 240,
        "decision_mode": "Adaptive Objective",
        "decision_min_score": 2.0,
        "four_hour_bias_enabled": True,
        "four_hour_bias_min_body_ratio": 0.18,
        "live_loop_enabled": False,
        "live_loop_interval": 5,
        "live_loop_ticks": 6,
        "bridge_enabled": True,
        "alerts_enabled": True,
        "alert_min_conf": 60,
        "alert_cooldown_sec": 15,
        "alert_change_only": True,
        "alert_log_enabled": True,
        "alert_webhook_enabled": False,
        "alert_webhook_url": "",
        "risk_stop_ticks": 20,
        "risk_qty": 1,
        "risk_tick_value": 1.0,
        "dom_depth": 12,
        "dom_compact": False,
        "dom_show_depth_chart": True,
        "footprint_mode": "Lite",
        "footprint_lookback": 30,
        "replay_record_enabled": True,
        "replay_auto_step": 1,
        "replay_loop": False,
        "watchdog_enabled": True,
        "watchdog_feed_stale_seconds": 20,
        "watchdog_bridge_stale_seconds": 25,
        "watchdog_executor_idle_seconds": 180,
        "watchdog_alert_webhook_enabled": False,
        "watchdog_alert_webhook_url": "",
        "watchdog_alert_cooldown_sec": 120,
        "ab_rolling_trades": 60,
        "show_advanced_controls": False,
        "backtest_config_file": default_bt_cfg,
        "backtest_data_file": os.path.join(ROOT, "data", "historical", "chimera_mixed_50k.csv"),
        "backtest_output_dir": os.path.join(ROOT, "results", "ui_backtest_latest"),
        "backtest_instrument": "MGC",
        "backtest_train_models": False,
        "backtest_train_split": 0.70,
        "backtest_oos_only": True,
        "backtest_enforce_quality": True,
        "backtest_use_bridge": False,
        "backtest_last_stdout": "",
        "backtest_last_stderr": "",
        "backtest_last_rc": 0,
        "backtest_hide_stale_results": False,
        "backtest_last_status_msg": "",
        "mc_paths": 2000,
        "mc_slippage_perturb": 0.05,
        "mc_last_stdout": "",
        "mc_last_stderr": "",
        "mc_last_rc": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _load_ui_settings(symbol: str) -> None:
    path = st.session_state.ui_settings_path
    if not os.path.exists(path):
        st.session_state.last_loaded_ui_symbol = symbol
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        payload = data.get(symbol.upper(), {})
        if not isinstance(payload, dict):
            return
        for k, v in payload.items():
            st.session_state[k] = v
        st.session_state.last_loaded_ui_symbol = symbol
    except (OSError, json.JSONDecodeError):
        pass


def _save_ui_settings(symbol: str, keys: List[str]) -> None:
    path = st.session_state.ui_settings_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    data[symbol.upper()] = {k: st.session_state.get(k) for k in keys}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _executor_status_payload() -> Dict[str, Any]:
    url = "http://127.0.0.1:8787/status"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as resp:
            if int(resp.status) != 200:
                return {"ok": False, "state": "DOWN"}
            payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return {"ok": False, "state": "DOWN"}
            payload["state"] = "UP"
            payload["ok"] = bool(payload.get("ok", True))
            return payload
    except Exception:
        return {"ok": False, "state": "DOWN"}


def _executor_status() -> tuple[bool, str]:
    payload = _executor_status_payload()
    ok = bool(payload.get("state") == "UP")
    return ok, "UP" if ok else "DOWN"


def _bridge_status(bridge_path: str) -> tuple[bool, str]:
    payload = read_bridge_signal(bridge_path)
    if payload is None:
        return False, "MISSING"
    age = bridge_signal_age_seconds(payload)
    if age > 20:
        return False, f"STALE {age:.0f}s"
    return True, f"FRESH {age:.0f}s"


def _timestamp_age_seconds(ts_raw: str) -> float:
    if not ts_raw:
        return float("inf")
    try:
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZoneInfo("UTC"))
        now = datetime.now(ZoneInfo("UTC"))
        return max(0.0, (now - ts.astimezone(ZoneInfo("UTC"))).total_seconds())
    except ValueError:
        return float("inf")


def _append_replay_snapshot(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _ingest_feed_ticks(engine: BookmapEngine, feed: Any, count: int, replay_record_enabled: bool, replay_file_path: str) -> None:
    for _ in range(int(count)):
        snap = feed.next_snapshot()
        engine.ingest(snap)
        st.session_state.last_snapshot_timestamp_utc = snap.ts.astimezone(ZoneInfo("UTC")).isoformat()
        if replay_record_enabled:
            try:
                _append_replay_snapshot(replay_file_path, snapshot_to_record(snap))
            except OSError:
                pass


def _current_session_label() -> str:
    ny = datetime.now(ZoneInfo("America/New_York"))
    hhmm = ny.hour * 60 + ny.minute
    london = 3 * 60 <= hhmm <= 11 * 60 + 30
    newyork = 9 * 60 + 30 <= hhmm <= 16 * 60
    if london and newyork:
        return "Overlap"
    if newyork:
        return "NY"
    if london:
        return "London"
    return "Off-Hours"


def _apply_preset(name: str) -> None:
    if name == "Scalp":
        st.session_state.strategy_profile = "scalp"
        st.session_state.alert_min_conf = 50
        st.session_state.quiet_mode = False
        st.session_state.live_loop_interval = 2
        st.session_state.live_loop_ticks = 8
        st.session_state.auto_follow_mid = True
    elif name == "Balanced":
        st.session_state.strategy_profile = "balanced"
        st.session_state.alert_min_conf = 60
        st.session_state.quiet_mode = True
        st.session_state.live_loop_interval = 4
        st.session_state.live_loop_ticks = 6
        st.session_state.auto_follow_mid = False
    elif name == "Strict Prop":
        st.session_state.strategy_profile = "strict"
        st.session_state.alert_min_conf = 75
        st.session_state.quiet_mode = True
        st.session_state.whale_pct = 98
        st.session_state.live_loop_interval = 5
        st.session_state.live_loop_ticks = 5
        st.session_state.auto_follow_mid = False


def _rebuild_feed(
    feed_mode: str,
    symbol: str,
    external_l2_path: str,
    replay_file_path: str,
    replay_loop: bool,
) -> None:
    levels = int(np.clip(int(st.session_state.get("heatmap_levels", 120)), 40, 240))
    history = int(np.clip(int(st.session_state.get("heatmap_history", 240)), 120, 600))
    st.session_state.engine = BookmapEngine(levels=levels, history=history)
    if feed_mode == "Binance Futures (REST)":
        cfg = BinanceFeedConfig(symbol=symbol.lower(), depth_limit=100, timeout_seconds=4.0)
        st.session_state.feed = BinanceRestOrderBookFeed(cfg)
        st.session_state.seeded = False
    elif feed_mode == "Futures L2 Bridge (JSON)":
        bridge_path = _resolve_external_l2_path(symbol, external_l2_path)
        stale_after_seconds = 5.0
        bridges_root = os.path.abspath(os.path.join(ROOT, "data", "bridges"))
        bridge_abs = os.path.abspath(os.path.expanduser(str(bridge_path)))
        if bridge_abs.startswith(bridges_root + os.sep):
            # Bridge fixture files under data/bridges can be intentionally static.
            stale_after_seconds = 86400.0 * 30.0
        cfg = ExternalL2BridgeConfig(
            path=bridge_path,
            stale_after_seconds=stale_after_seconds,
            expected_symbol=symbol.upper(),
        )
        st.session_state.feed = ExternalL2BridgeFeed(cfg)
        st.session_state.seeded = False
    elif feed_mode == "Replay (JSONL)":
        cfg = ReplayFeedConfig(path=replay_file_path, loop=bool(replay_loop))
        st.session_state.feed = ReplayOrderBookFeed(cfg)
        st.session_state.seeded = True
    else:
        start_price, tick_size, vol = _synthetic_profile_for_symbol(symbol)
        levels_per_side = max(30, int(levels // 2))
        cfg = SyntheticFeedConfig(
            seed=42,
            start_price=start_price,
            tick_size=tick_size,
            levels_per_side=levels_per_side,
            volatility=vol,
        )
        st.session_state.feed = SyntheticOrderBookFeed(cfg)
        st.session_state.seeded = False
    st.session_state.active_feed_mode = feed_mode
    st.session_state.active_feed_symbol = symbol.upper()
    st.session_state.active_heatmap_levels = levels
    st.session_state.active_heatmap_history = history
    st.session_state.frozen_y_range = None
    st.session_state.last_feed_error = ""


def _render_heatmap(
    zoom_view: bool,
    show_trade_bubbles: bool,
    bubble_scale: float,
    auto_follow_mid: bool,
) -> go.Figure:
    engine: BookmapEngine = st.session_state.engine
    symbol = str(st.session_state.get("feed_symbol", ""))
    raw_decimals = _raw_price_decimals_for_symbol(symbol)
    z = engine.heatmap.copy()
    y_axis = list(range(z.shape[1]))
    x_axis = list(range(z.shape[0]))
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=z.T,
            x=x_axis,
            y=y_axis,
            colorscale=[
                [0.0, "#0f172a"],
                [0.35, "#1e3a8a"],
                [0.7, "#0ea5a4"],
                [1.0, "#f59e0b"],
            ],
            zmin=0,
            zmax=1,
            colorbar=dict(title="Depth"),
            showscale=True,
            hovertemplate="t=%{x}, lvl=%{y}, depth=%{z:.2f}<extra></extra>",
        )
    )

    min_mid = None
    max_mid = None
    price_grid = engine.price_grid if isinstance(engine.price_grid, np.ndarray) and engine.price_grid.size == engine.levels else None
    if engine.mid_prices:
        mid_series = np.array(engine.mid_prices[-engine.history :], dtype=float)
        min_mid = float(np.min(mid_series))
        max_mid = float(np.max(mid_series))
        if price_grid is not None and len(price_grid) >= 2:
            tick = float(price_grid[1] - price_grid[0])
            if abs(tick) < 1e-12:
                tick = 1e-9
            base = float(price_grid[0])
            mid_norm = (mid_series - base) / tick
        else:
            span = max(max_mid - min_mid, 1e-9)
            mid_norm = (mid_series - min_mid) / span * (engine.levels - 1)
        mid_norm = np.clip(mid_norm, 0, engine.levels - 1)
        mid_start = max(0, z.shape[0] - len(mid_norm))
        mid_x = list(range(mid_start, mid_start + len(mid_norm)))
        fig.add_trace(
            go.Scatter(
                x=mid_x,
                y=mid_norm,
                mode="lines",
                line=dict(color="#f8fafc", width=2),
                name="Mid",
                customdata=mid_series,
                hovertemplate=f"t=%{{x}}<br>mid=%{{customdata:,.{raw_decimals}f}}<extra></extra>",
            )
        )

    # Optional 3D-style trade bubbles: shadow + core markers sized by trade size.
    if show_trade_bubbles and engine.trade_prices and min_mid is not None and max_mid is not None:
        trade_px = np.array(engine.trade_prices[-engine.history :], dtype=float)
        trade_sz = np.array(engine.trade_sizes[-engine.history :], dtype=float)
        trade_side = engine.trade_sides[-engine.history :]
        if price_grid is not None and len(price_grid) >= 2:
            tick = float(price_grid[1] - price_grid[0])
            if abs(tick) < 1e-12:
                tick = 1e-9
            base = float(price_grid[0])
            y_norm = (trade_px - base) / tick
        else:
            span = max(max_mid - min_mid, 1e-9)
            y_norm = (trade_px - min_mid) / span * (engine.levels - 1)
        y_norm = np.clip(y_norm, 0, engine.levels - 1)
        trade_start = max(0, z.shape[0] - len(y_norm))
        x_vals = list(range(trade_start, trade_start + len(y_norm)))

        sizes = np.clip(np.sqrt(np.maximum(trade_sz, 0.01)) * bubble_scale, 4, 42)
        colors = ["#34d399" if s == "buy" else "#fb7185" for s in trade_side]

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_norm,
                mode="markers",
                marker=dict(size=sizes * 1.3, color="rgba(15,23,42,0.35)", line=dict(width=0)),
                name="Trade Bubble Shadow",
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_norm,
                mode="markers",
                marker=dict(
                    size=sizes,
                    color=colors,
                    line=dict(width=1, color="rgba(248,250,252,0.65)"),
                    opacity=0.85,
                ),
                name="Trade Bubbles",
                customdata=trade_px,
                hovertemplate=f"t=%{{x}}<br>trade=%{{customdata:,.{raw_decimals}f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Order-Flow Heatmap",
        margin=dict(l=12, r=12, t=42, b=12),
        height=520,
        xaxis_title="Time",
        yaxis_title="Price",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,17,25,0.72)",
        font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        title_font=dict(size=20),
        legend=dict(orientation="h", yanchor="top", y=1.02, xanchor="left", x=0),
        uirevision="chimera_view_lock",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    if price_grid is not None and len(price_grid) == engine.levels:
        tick_vals = np.linspace(0, engine.levels - 1, 6)
        tick_prices = np.interp(tick_vals, np.arange(engine.levels), price_grid)
        fig.update_yaxes(
            tickmode="array",
            tickvals=[float(v) for v in tick_vals],
            ticktext=[_fmt_price(st.session_state.feed_symbol, float(p)) for p in tick_prices],
            title_text="Price (raw)",
        )
    if zoom_view and engine.mid_prices:
        mid_series = np.array(engine.mid_prices[-engine.history :], dtype=float)
        if price_grid is not None and len(price_grid) >= 2:
            tick = float(price_grid[1] - price_grid[0])
            if abs(tick) < 1e-12:
                tick = 1e-9
            base = float(price_grid[0])
            last_mid_norm = (mid_series[-1] - base) / tick
        else:
            min_mid = float(np.min(mid_series))
            max_mid = float(np.max(mid_series))
            span = max(max_mid - min_mid, 1e-9)
            last_mid_norm = ((mid_series[-1] - min_mid) / span) * (engine.levels - 1)
        zoom_half = max(8, int(engine.levels * 0.18))
        y0 = max(0, int(last_mid_norm - zoom_half))
        y1 = min(engine.levels - 1, int(last_mid_norm + zoom_half))
        if auto_follow_mid:
            st.session_state.frozen_y_range = [y0, y1]
            fig.update_yaxes(range=[y0, y1])
        else:
            if st.session_state.frozen_y_range is None:
                st.session_state.frozen_y_range = [y0, y1]
            fig.update_yaxes(range=st.session_state.frozen_y_range)
    return fig


def _ladder_df(rows: List[tuple[str, float, float]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["side", "price", "size"])
    df = pd.DataFrame(rows, columns=["side", "price", "size"])
    return df.sort_values(["side", "price"], ascending=[True, False])


def _dom_table_df(rows: List[tuple[str, float, float]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["side", "price", "size", "cum_size", "dist_mid"])
    df = pd.DataFrame(rows, columns=["side", "price", "size"])
    asks = df[df["side"] == "ask"].sort_values("price", ascending=True).copy()
    bids = df[df["side"] == "bid"].sort_values("price", ascending=False).copy()
    best_ask = float(asks["price"].iloc[0]) if not asks.empty else np.nan
    best_bid = float(bids["price"].iloc[0]) if not bids.empty else np.nan
    mid = float((best_ask + best_bid) / 2.0) if np.isfinite(best_ask) and np.isfinite(best_bid) else np.nan

    asks["cum_size"] = asks["size"].cumsum()
    bids["cum_size"] = bids["size"].cumsum()
    if np.isfinite(mid):
        asks["dist_mid"] = asks["price"] - mid
        bids["dist_mid"] = bids["price"] - mid
    else:
        asks["dist_mid"] = np.nan
        bids["dist_mid"] = np.nan

    out = pd.concat([asks, bids], ignore_index=True)
    out["side"] = out["side"].map({"ask": "ASK", "bid": "BID"})
    return out[["side", "price", "size", "cum_size", "dist_mid"]]


def _render_dom_depth_chart(rows: List[tuple[str, float, float]]) -> go.Figure:
    fig = go.Figure()
    if not rows:
        fig.update_layout(
            height=280,
            title="Depth Map",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,17,25,0.72)",
            font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        )
        return fig
    df = pd.DataFrame(rows, columns=["side", "price", "size"])
    asks = df[df["side"] == "ask"].sort_values("price", ascending=False)
    bids = df[df["side"] == "bid"].sort_values("price", ascending=False)

    fig.add_trace(
        go.Bar(
            x=-bids["size"],
            y=bids["price"].astype(str),
            orientation="h",
            name="Bids",
            marker_color="rgba(52,211,153,0.75)",
            hovertemplate="BID %{y}<br>size=%{x:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=asks["size"],
            y=asks["price"].astype(str),
            orientation="h",
            name="Asks",
            marker_color="rgba(251,113,133,0.75)",
            hovertemplate="ASK %{y}<br>size=%{x:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=300,
        barmode="overlay",
        title="DOM Depth Map",
        xaxis_title="Bid <- size -> Ask",
        yaxis_title="Price",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,17,25,0.72)",
        font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        margin=dict(l=8, r=8, t=36, b=8),
        legend=dict(orientation="h"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def _footprint_frame(engine: BookmapEngine, lookback: int) -> pd.DataFrame:
    n = min(lookback, len(engine.trade_prices), len(engine.trade_sizes), len(engine.trade_sides))
    if n <= 0:
        return pd.DataFrame(columns=["idx", "buy_vol", "sell_vol", "delta", "imbalance", "control"])

    prices = np.array(engine.trade_prices[-n:], dtype=float)
    sizes = np.array(engine.trade_sizes[-n:], dtype=float)
    sides = engine.trade_sides[-n:]
    bins = np.array([int(i // 3) for i in range(n)])  # group into small bar buckets
    max_bin = int(bins.max()) if len(bins) else -1

    rows = []
    for b in range(max_bin + 1):
        mask = bins == b
        if not np.any(mask):
            continue
        s = sizes[mask]
        sd = [sides[i] for i, m in enumerate(mask) if m]
        buy_vol = float(sum(v for v, side in zip(s, sd) if side == "buy"))
        sell_vol = float(sum(v for v, side in zip(s, sd) if side == "sell"))
        delta = buy_vol - sell_vol
        total = buy_vol + sell_vol
        imbalance = 0.0 if total <= 0 else delta / total
        if imbalance > 0.2:
            control = "Buyer Control"
        elif imbalance < -0.2:
            control = "Seller Control"
        else:
            control = "Balanced"
        rows.append(
            {
                "idx": b,
                "buy_vol": buy_vol,
                "sell_vol": sell_vol,
                "delta": delta,
                "imbalance": imbalance,
                "control": control,
            }
        )
    return pd.DataFrame(rows)


def _ts_from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)


def _fetch_latest_closed_4h_candle(symbol: str) -> Dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return {}
    endpoints = [
        ("https://fapi.binance.com", "/fapi/v1/klines"),
        ("https://api.binance.com", "/api/v3/klines"),
        ("https://api.binance.us", "/api/v3/klines"),
    ]
    now_ms = int(time.time() * 1000.0)
    for base_url, path in endpoints:
        try:
            resp = requests.get(
                f"{base_url}{path}",
                params={"symbol": sym, "interval": "4h", "limit": 5},
                timeout=4.0,
            )
            resp.raise_for_status()
            rows = resp.json()
            if not isinstance(rows, list) or not rows:
                continue

            closed_rows = [
                row
                for row in rows
                if isinstance(row, list) and len(row) >= 7 and int(row[6]) <= now_ms
            ]
            if not closed_rows:
                continue
            row = closed_rows[-1]
            open_ts = int(row[0])
            close_ts = int(row[6])
            return {
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "start_utc": _ts_from_ms(open_ts).isoformat(),
                "end_utc": _ts_from_ms(close_ts).isoformat(),
                "source": "binance_4h_closed",
            }
        except (requests.RequestException, ValueError, TypeError, IndexError):
            continue
    return {}


def _local_current_4h_candle(engine: BookmapEngine) -> Dict[str, Any]:
    if not engine.snapshots:
        return {}
    last_ts = engine.snapshots[-1].ts.astimezone(timezone.utc)
    bucket_hour = (last_ts.hour // 4) * 4
    bucket_start = last_ts.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
    bucket_end = bucket_start.timestamp() + 4.0 * 3600.0

    points: List[tuple[datetime, float]] = []
    for snap in engine.snapshots:
        ts = snap.ts.astimezone(timezone.utc)
        ts_epoch = ts.timestamp()
        if bucket_start.timestamp() <= ts_epoch < bucket_end:
            px = float(snap.last_trade_price) if float(snap.last_trade_price) > 0 else float(snap.mid)
            points.append((ts, px))
    if len(points) < 4:
        return {}
    prices = [p[1] for p in points]
    return {
        "open": float(prices[0]),
        "high": float(max(prices)),
        "low": float(min(prices)),
        "close": float(prices[-1]),
        "start_utc": bucket_start.isoformat(),
        "end_utc": _ts_from_ms(int(bucket_end * 1000.0)).isoformat(),
        "source": "local_4h_partial",
    }


def _resolve_4h_candle(feed_mode: str, symbol: str, engine: BookmapEngine) -> Dict[str, Any]:
    if str(feed_mode) == "Binance Futures (REST)":
        live = _fetch_latest_closed_4h_candle(symbol)
        if live:
            return live
    return _local_current_4h_candle(engine)


def _four_hour_bias(candle: Dict[str, Any], min_body_ratio: float) -> str:
    if not candle:
        return "unknown"
    high = float(candle.get("high", 0.0))
    low = float(candle.get("low", 0.0))
    opn = float(candle.get("open", 0.0))
    close = float(candle.get("close", 0.0))
    candle_range = max(1e-9, high - low)
    body = close - opn
    if abs(body) / candle_range < float(min_body_ratio):
        return "neutral"
    if body > 0:
        return "bullish"
    if body < 0:
        return "bearish"
    return "neutral"


def _render_footprint_lite(df_fp: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df_fp.empty:
        fig.update_layout(
            height=260,
            title="Footprint Lite",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,17,25,0.72)",
            font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        )
        return fig
    fig.add_trace(
        go.Bar(
            x=df_fp["idx"],
            y=df_fp["buy_vol"],
            name="Buy Vol",
            marker_color="rgba(52,211,153,0.75)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df_fp["idx"],
            y=-df_fp["sell_vol"],
            name="Sell Vol",
            marker_color="rgba(251,113,133,0.75)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_fp["idx"],
            y=df_fp["delta"],
            mode="lines+markers",
            name="Delta",
            line=dict(color="#f8fafc", width=2),
            marker=dict(size=5),
        )
    )
    fig.update_layout(
        height=300,
        title="Footprint Lite (Buy/Sell + Delta)",
        barmode="relative",
        xaxis_title="Bar Bucket",
        yaxis_title="Volume / Delta",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,17,25,0.72)",
        font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        margin=dict(l=8, r=8, t=36, b=8),
        legend=dict(orientation="h"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def _adaptive_imbalance_threshold(engine: BookmapEngine, lookback: int = 140) -> float:
    if not engine.snapshots:
        return 0.05
    values: List[float] = []
    for snap in engine.snapshots[-lookback:]:
        bid_total = float(sum(snap.bids.values()))
        ask_total = float(sum(snap.asks.values()))
        total = bid_total + ask_total
        if total <= 0:
            continue
        values.append(abs((bid_total - ask_total) / total))
    if len(values) < 12:
        return 0.05
    threshold = float(np.percentile(np.array(values, dtype=np.float64), 70))
    return float(np.clip(threshold, 0.03, 0.25))


def _derive_bridge_decision_classic(sig, quiet_mode: bool) -> tuple[str, str]:
    long_votes = 0
    short_votes = 0

    if sig.imbalance >= 0.05:
        long_votes += 1
    if sig.imbalance <= -0.05:
        short_votes += 1
    if sig.sweep_up:
        long_votes += 1
    if sig.sweep_down:
        short_votes += 1
    if sig.absorption_bid:
        long_votes += 1
    if sig.absorption_ask:
        short_votes += 1
    if sig.whale_buy:
        long_votes += 2
    if sig.whale_sell:
        short_votes += 2

    min_conf = 50 if quiet_mode else 40
    if sig.confidence < min_conf:
        return "NO_TRADE", f"confidence<{min_conf}"

    if long_votes >= short_votes + 1 and long_votes >= 2:
        return "GO_LONG", f"long_votes={long_votes},short_votes={short_votes}"
    if short_votes >= long_votes + 1 and short_votes >= 2:
        return "GO_SHORT", f"long_votes={long_votes},short_votes={short_votes}"
    return "NO_TRADE", f"long_votes={long_votes},short_votes={short_votes}"


def _derive_bridge_decision_adaptive(sig, quiet_mode: bool, engine: BookmapEngine, min_score: float) -> tuple[str, str]:
    min_conf = 50 if quiet_mode else 40
    if sig.confidence < min_conf:
        return "NO_TRADE", f"confidence<{min_conf}"

    imbalance_threshold = _adaptive_imbalance_threshold(engine)
    long_score = 0.0
    short_score = 0.0

    if sig.imbalance >= imbalance_threshold:
        long_score += 1.0
    if sig.imbalance <= -imbalance_threshold:
        short_score += 1.0
    if sig.sweep_up:
        long_score += 1.0
    if sig.sweep_down:
        short_score += 1.0
    if sig.absorption_bid:
        long_score += 1.0
    if sig.absorption_ask:
        short_score += 1.0
    if sig.whale_buy:
        long_score += 1.0
    if sig.whale_sell:
        short_score += 1.0

    edge = long_score - short_score
    if long_score >= float(min_score) and edge >= 1.0:
        return "GO_LONG", (
            f"mode=adaptive,long={long_score:.1f},short={short_score:.1f},"
            f"imb_thr={imbalance_threshold:.3f}"
        )
    if short_score >= float(min_score) and edge <= -1.0:
        return "GO_SHORT", (
            f"mode=adaptive,long={long_score:.1f},short={short_score:.1f},"
            f"imb_thr={imbalance_threshold:.3f}"
        )
    return "NO_TRADE", (
        f"mode=adaptive,long={long_score:.1f},short={short_score:.1f},"
        f"imb_thr={imbalance_threshold:.3f}"
    )


def _derive_bridge_decision(
    sig,
    quiet_mode: bool,
    engine: BookmapEngine,
    decision_mode: str,
    min_score: float,
) -> tuple[str, str]:
    if str(decision_mode).lower().startswith("classic"):
        return _derive_bridge_decision_classic(sig, quiet_mode=quiet_mode)
    return _derive_bridge_decision_adaptive(sig, quiet_mode=quiet_mode, engine=engine, min_score=min_score)


def _append_alert_log(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp_utc", "symbol", "decision", "confidence", "imbalance", "whale_buy", "whale_sell", "notes"],
            extrasaction="ignore",
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _send_webhook(url: str, payload: dict) -> None:
    resp = requests.post(url, json=payload, timeout=4)
    resp.raise_for_status()


def _looks_like_tv_futures_symbol(symbol: str) -> bool:
    s = (symbol or "").upper().strip()
    if "!" in s:
        return True
    roots = ("MNQ", "MGC", "NQ", "ES", "GC", "CL", "YM", "RTY")
    return any(s.startswith(r) for r in roots)


def _recommended_live_feed_mode(symbol: str) -> str:
    return "Futures L2 Bridge (JSON)" if _looks_like_tv_futures_symbol(symbol) else "Binance Futures (REST)"


def _price_decimals_for_symbol(symbol: str) -> int:
    s = (symbol or "").upper().strip()
    if s.startswith("MNQ") or s.startswith("NQ") or s.startswith("ES"):
        return 2
    if s.startswith("MGC") or s.startswith("GC") or s.startswith("CL"):
        return 4
    if s.startswith("ETH"):
        return 4
    if s.startswith("BTC"):
        return 3
    if s.startswith("EUR") or s.startswith("USD") or s.startswith("XAU"):
        return 5
    return 4


def _raw_price_decimals_for_symbol(symbol: str) -> int:
    base = _price_decimals_for_symbol(symbol)
    return min(8, max(base + 2, 4))


def _fmt_price(symbol: str, value: float) -> str:
    d = _raw_price_decimals_for_symbol(symbol)
    return f"{float(value):,.{d}f}"


def _load_live_snapshot_meta(path: str) -> Dict[str, Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
    except Exception:
        return {}
    return {}


def _futures_bridge_path_for_symbol(symbol: str) -> str:
    root = _symbol_root(symbol)
    if not root:
        return ""
    indexed = _bridge_symbol_index().get(root, "")
    if indexed and os.path.exists(indexed):
        return indexed

    fallback_files = {
        "MNQ": "ninjatrader_l2.json",
        "NQ": "ninjatrader_l2.json",
        "ES": "ninjatrader_l2.json",
        "MES": "ninjatrader_l2.json",
        "YM": "ninjatrader_l2.json",
        "MYM": "ninjatrader_l2.json",
        "RTY": "ninjatrader_l2.json",
        "M2K": "ninjatrader_l2.json",
        "MGC": "tradovate_l2.json",
        "GC": "tradovate_l2.json",
        "CL": "tradovate_l2.json",
    }
    filename = fallback_files.get(root, "")
    if not filename:
        return ""
    fallback = os.path.join(ROOT, "data", "bridges", filename)
    return fallback if os.path.exists(fallback) else ""


def _symbol_root(symbol: str) -> str:
    s = (symbol or "").upper().strip().replace("!", "")
    match = re.match(r"^[A-Z]+", s)
    return match.group(0) if match else ""


@lru_cache(maxsize=1)
def _bridge_symbol_index() -> Dict[str, str]:
    out: Dict[str, str] = {}
    bridges_dir = Path(ROOT) / "data" / "bridges"
    if not bridges_dir.exists():
        return out
    for path in sorted(bridges_dir.glob("*.json")):
        payload = _load_live_snapshot_meta(str(path))
        raw_symbol = str(payload.get("symbol", "")).strip()
        root = _symbol_root(raw_symbol)
        if root and root not in out:
            out[root] = str(path)
    return out


def _resolve_external_l2_path(symbol: str, external_l2_path: str) -> str:
    raw_path = str(external_l2_path or "").strip()
    if not _looks_like_tv_futures_symbol(symbol):
        return raw_path
    mapped = _futures_bridge_path_for_symbol(symbol)
    if not mapped:
        return raw_path
    if not raw_path:
        return mapped

    raw_abs = os.path.abspath(os.path.expanduser(raw_path))
    mapped_abs = os.path.abspath(os.path.expanduser(mapped))
    if raw_abs == mapped_abs:
        return mapped

    raw_basename = os.path.basename(raw_abs).lower()
    bridges_root = os.path.abspath(os.path.join(ROOT, "data", "bridges"))
    if raw_basename == "live_l2_snapshot.json":
        return mapped
    if raw_abs.startswith(bridges_root + os.sep):
        return mapped
    if not os.path.exists(raw_abs):
        return mapped
    return raw_path


def _safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _load_trade_journal_frames(root_dir: str = ROOT) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_dir = Path(root_dir) / "data"
    orders_frames: List[pd.DataFrame] = []
    closed_frames: List[pd.DataFrame] = []

    # Per-broker files: data/<broker>/*
    for broker_dir in data_dir.glob("*"):
        if not broker_dir.is_dir():
            continue
        broker = broker_dir.name
        orders_path = broker_dir / "paper_orders.csv"
        closed_path = broker_dir / "closed_trades.csv"
        if orders_path.exists():
            df = _safe_read_csv(str(orders_path))
            if not df.empty:
                df["broker"] = df.get("broker", broker)
                orders_frames.append(df)
        if closed_path.exists():
            df = _safe_read_csv(str(closed_path))
            if not df.empty:
                df["broker"] = df.get("broker", broker)
                closed_frames.append(df)

    # Backward-compatible legacy files.
    legacy_orders = data_dir / "paper_orders.csv"
    if legacy_orders.exists():
        df = _safe_read_csv(str(legacy_orders))
        if not df.empty:
            if "broker" not in df.columns:
                df["broker"] = "legacy"
            orders_frames.append(df)

    orders_df = pd.concat(orders_frames, ignore_index=True) if orders_frames else pd.DataFrame()
    closed_df = pd.concat(closed_frames, ignore_index=True) if closed_frames else pd.DataFrame()

    audit_path = data_dir / "chimera_execution_audit.jsonl"
    audit_rows: List[Dict[str, Any]] = []
    if audit_path.exists():
        try:
            with audit_path.open("r", encoding="utf-8") as f:
                for line in f:
                    row = line.strip()
                    if not row:
                        continue
                    payload = json.loads(row)
                    if not isinstance(payload, dict):
                        continue
                    sig = payload.get("signal", {}) if isinstance(payload.get("signal", {}), dict) else {}
                    resp = payload.get("webhook_response", {}) if isinstance(payload.get("webhook_response", {}), dict) else {}
                    body = resp.get("body", {}) if isinstance(resp.get("body", {}), dict) else {}
                    audit_rows.append(
                        {
                            "timestamp_utc": payload.get("timestamp_utc"),
                            "request_id": payload.get("request_id"),
                            "broker": payload.get("broker"),
                            "symbol": sig.get("symbol"),
                            "action": sig.get("action"),
                            "risk_reason": payload.get("risk_reason"),
                            "gate_reason": payload.get("gate_reason"),
                            "result_ok": body.get("ok"),
                            "result_reason": body.get("reason"),
                        }
                    )
        except Exception:
            audit_rows = []
    audit_df = pd.DataFrame(audit_rows)

    return orders_df, closed_df, audit_df


def _summarize_closed_trades(closed_df: pd.DataFrame) -> Dict[str, float]:
    if closed_df.empty:
        return {
            "trades": 0.0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_pnl": 0.0,
        }
    pnl = pd.to_numeric(closed_df.get("realized_pnl_usd"), errors="coerce").fillna(0.0)
    trades = float(len(pnl))
    wins = float((pnl > 0).sum())
    return {
        "trades": trades,
        "win_rate": float((wins / trades) * 100.0 if trades > 0 else 0.0),
        "net_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean() if trades > 0 else 0.0),
    }


def _cfg_get(cfg: Dict[str, Any], path: str, default: Any) -> Any:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _load_yaml_cfg(path: str) -> Dict[str, Any]:
    p = str(path or "").strip()
    if not p or not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _prop_readiness_snapshot(
    *,
    closed_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    executor_payload: Dict[str, Any],
    watchdog_alerts: List[str],
    config_path: str,
    strategy_profile: str,
) -> Dict[str, Any]:
    cfg = _load_yaml_cfg(config_path)
    initial_capital = float(_cfg_get(cfg, "capital.initial_capital", 100000.0))
    max_daily_trades = int(_cfg_get(cfg, "daily_limits.max_daily_trades", 5))
    max_consec_losses = int(_cfg_get(cfg, "daily_limits.max_consecutive_losses", 3))
    max_daily_loss_usd = float(_cfg_get(cfg, "automation.risk_guard.max_daily_loss_usd", 0.0))

    # Promotion gates: defaults can be overridden by config.paper_readiness.* if added later.
    min_trades = int(_cfg_get(cfg, "paper_readiness.min_trades", 100))
    min_active_days = int(_cfg_get(cfg, "paper_readiness.min_active_days", 20))
    min_win_rate = float(_cfg_get(cfg, "paper_readiness.min_win_rate", 55.0))
    min_pf = float(_cfg_get(cfg, "paper_readiness.min_profit_factor", 1.5))
    max_dd_abs_pct = float(_cfg_get(cfg, "paper_readiness.max_drawdown_abs_pct", 3.0))

    df = closed_df.copy()
    if not df.empty:
        if "symbol" in df.columns:
            symbols = df["symbol"].astype(str).str.upper()
            mask_symbols = symbols.str.startswith("MNQ") | symbols.str.startswith("MGC")
            if bool(mask_symbols.any()):
                df = df[mask_symbols]
        if "profile" in df.columns:
            p = str(strategy_profile or "").strip().lower()
            if p:
                mask_profile = df["profile"].astype(str).str.lower() == p
                if bool(mask_profile.any()):
                    df = df[mask_profile]

    pnl = pd.to_numeric(df.get("realized_pnl_usd"), errors="coerce").fillna(0.0) if not df.empty else pd.Series(dtype=float)
    trades = int(len(pnl))
    wins = int((pnl > 0).sum()) if trades > 0 else 0
    win_rate = float((wins / trades) * 100.0) if trades > 0 else 0.0
    gross_profit = float(pnl[pnl > 0].sum()) if trades > 0 else 0.0
    gross_loss = float(-pnl[pnl < 0].sum()) if trades > 0 else 0.0
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    net_pnl = float(pnl.sum()) if trades > 0 else 0.0

    active_days = 0
    max_dd_pct = 0.0
    if trades > 0 and "timestamp_utc" in df.columns:
        ts = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
        active_days = int(ts.dropna().dt.date.nunique())
    if trades > 0:
        equity = initial_capital + pnl.cumsum()
        peak = equity.cummax()
        dd = ((equity - peak) / peak.replace(0, np.nan)) * 100.0
        max_dd_pct = float(dd.min()) if not dd.empty else 0.0

    # Recent risk blocks from executor audit (last 7 days).
    recent_risk_blocks = 0
    if not audit_df.empty and "timestamp_utc" in audit_df.columns:
        ts = pd.to_datetime(audit_df["timestamp_utc"], errors="coerce", utc=True)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
        recent = audit_df.loc[ts >= cutoff].copy()
        if not recent.empty:
            risk_reason = recent.get("risk_reason", pd.Series(index=recent.index, dtype=object)).astype(str).str.lower()
            gate_reason = recent.get("gate_reason", pd.Series(index=recent.index, dtype=object)).astype(str).str.lower()
            result_ok = recent.get("result_ok", pd.Series(index=recent.index, dtype=object))
            risk_block = ~risk_reason.isin(["ok", "not_checked", "", "nan", "none"])
            gate_block = gate_reason.isin(["bridge_stale", "stale_bridge", "signal_blocked", "not_allowed"])
            result_block = result_ok.astype(str).str.lower().isin(["false", "0"])
            recent_risk_blocks = int((risk_block | gate_block | result_block).sum())

    brokers = executor_payload.get("brokers", {}) if isinstance(executor_payload, dict) else {}
    active_locks = 0
    if isinstance(brokers, dict):
        for _, b in brokers.items():
            if not isinstance(b, dict):
                continue
            daily_count = int(float(b.get("daily_trade_count", 0) or 0))
            consec_losses = int(float(b.get("consecutive_losses", 0) or 0))
            daily_pnl = float(b.get("daily_realized_pnl_usd", 0.0) or 0.0)
            lock = daily_count >= max_daily_trades or consec_losses >= max_consec_losses
            if max_daily_loss_usd > 0:
                lock = lock or (daily_pnl <= -abs(max_daily_loss_usd))
            active_locks += int(lock)

    exec_up = bool(executor_payload.get("state") == "UP") if isinstance(executor_payload, dict) else False
    infra_ok = exec_up and len(watchdog_alerts) == 0

    gates = [
        {"name": "Sample Size", "ok": trades >= min_trades, "detail": f"{trades}/{min_trades} trades"},
        {"name": "Active Days", "ok": active_days >= min_active_days, "detail": f"{active_days}/{min_active_days} days"},
        {"name": "Win Rate", "ok": win_rate >= min_win_rate, "detail": f"{win_rate:.1f}% / {min_win_rate:.1f}%"},
        {"name": "Profit Factor", "ok": profit_factor >= min_pf, "detail": f"{profit_factor:.2f} / {min_pf:.2f}"},
        {"name": "Max Drawdown", "ok": abs(max_dd_pct) <= max_dd_abs_pct, "detail": f"{max_dd_pct:.2f}% / -{max_dd_abs_pct:.2f}% limit"},
        {"name": "Infra Health", "ok": infra_ok, "detail": "Executor UP + Watchdog clear"},
        {"name": "Hard-Lock Clear", "ok": active_locks == 0, "detail": f"{active_locks} active broker lock(s)"},
        {"name": "Recent Risk Blocks", "ok": recent_risk_blocks == 0, "detail": f"{recent_risk_blocks} in last 7d"},
    ]
    ready = all(bool(g["ok"]) for g in gates)
    return {
        "ready": ready,
        "summary": {
            "trades": trades,
            "active_days": active_days,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "net_pnl": net_pnl,
            "max_dd_pct": max_dd_pct,
            "recent_risk_blocks": recent_risk_blocks,
            "active_locks": active_locks,
        },
        "limits": {
            "max_daily_trades": max_daily_trades,
            "max_consecutive_losses": max_consec_losses,
            "max_daily_loss_usd": max_daily_loss_usd,
        },
        "gates": gates,
        "config_path": config_path,
    }


def _run_backtest_process(
    data_file: str,
    config_file: str,
    output_dir: str,
    instrument: str,
    train_models: bool,
    use_bridge: bool,
    train_split: float,
    oos_only: bool,
    enforce_quality: bool,
) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        str(Path(ROOT) / "backtest.py"),
        "--data",
        data_file,
        "--config",
        config_file,
        "--output",
        output_dir,
        "--instrument",
        instrument,
        "--train-split",
        str(float(train_split)),
    ]
    if not train_models:
        cmd.append("--no-train")
    if use_bridge:
        cmd.append("--use-bridge")
    if not oos_only:
        cmd.append("--include-train-period")
    if enforce_quality:
        cmd.append("--enforce-data-quality")
    else:
        cmd.append("--allow-poor-data")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return int(proc.returncode), proc.stdout, proc.stderr


def _analyze_backtest_data_file(path: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": False,
        "rows": 0,
        "start_ts": "",
        "end_ts": "",
        "close_ratio": 0.0,
        "close_return_pct": 0.0,
        "max_abs_bar_return_pct": 0.0,
        "issues": [],
    }
    if not os.path.exists(path):
        return result
    try:
        df = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            result["issues"] = ["missing_required_columns"]
            result["exists"] = True
            return result
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        if df.empty:
            result["issues"] = ["empty_after_parse"]
            result["exists"] = True
            return result
        close = pd.to_numeric(df["close"], errors="coerce")
        open_ = pd.to_numeric(df["open"], errors="coerce")
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        valid = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}).dropna()
        if valid.empty:
            result["issues"] = ["ohlc_numeric_parse_failed"]
            result["exists"] = True
            return result
        start_close = float(valid["close"].iloc[0])
        end_close = float(valid["close"].iloc[-1])
        ratio = end_close / start_close if abs(start_close) > 1e-9 else 0.0
        bar_rets = valid["close"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        max_abs_ret = float(bar_rets.abs().max()) if len(bar_rets) > 0 else 0.0
        invalid_ohlc = int(
            ((valid["high"] < valid["low"]) | (valid["open"] > valid["high"]) | (valid["open"] < valid["low"]) | (valid["close"] > valid["high"]) | (valid["close"] < valid["low"])).sum()
        )
        issues: List[str] = []
        if len(valid) < 1000:
            issues.append(f"low_rows:{len(valid)}")
        if ratio < 0.50 or ratio > 2.50:
            issues.append(f"close_ratio:{ratio:.3f}")
        if max_abs_ret > 0.20:
            issues.append(f"bar_spike:{max_abs_ret*100:.2f}%")
        if invalid_ohlc > 0:
            issues.append(f"invalid_ohlc:{invalid_ohlc}")
        result.update(
            {
                "exists": True,
                "rows": int(len(valid)),
                "start_ts": str(df["timestamp"].iloc[0]),
                "end_ts": str(df["timestamp"].iloc[-1]),
                "close_ratio": float(ratio),
                "close_return_pct": float((ratio - 1.0) * 100.0),
                "max_abs_bar_return_pct": float(max_abs_ret * 100.0),
                "issues": issues,
            }
        )
        return result
    except Exception as exc:
        result["exists"] = True
        result["issues"] = [f"parse_error:{exc}"]
        return result


def _backtest_summary(output_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    trades_path = Path(output_dir) / "trades.csv"
    equity_path = Path(output_dir) / "equity_curve.csv"
    trades_df = _safe_read_csv(str(trades_path)) if trades_path.exists() else pd.DataFrame()
    equity_df = _safe_read_csv(str(equity_path)) if equity_path.exists() else pd.DataFrame()

    if trades_df.empty:
        return trades_df, equity_df, {"total_trades": 0.0, "win_rate": 0.0, "net_pnl": 0.0}

    pnl_col = "realized_pnl"
    if pnl_col not in trades_df.columns:
        for alt in ("net_pnl", "pnl", "profit"):
            if alt in trades_df.columns:
                pnl_col = alt
                break
    pnl = pd.to_numeric(trades_df[pnl_col], errors="coerce").fillna(0.0)
    total = float(len(pnl))
    wins = float((pnl > 0).sum())
    return trades_df, equity_df, {
        "total_trades": total,
        "win_rate": float((wins / total) * 100.0 if total > 0 else 0.0),
        "net_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean() if total > 0 else 0.0),
    }


def _run_monte_carlo_process(
    trades_file: str,
    paths: int,
    slippage_perturb: float,
) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        str(Path(ROOT) / "scripts" / "chimera_monte_carlo.py"),
        "--trades",
        trades_file,
        "--paths",
        str(int(paths)),
        "--slippage-perturb",
        str(float(slippage_perturb)),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout, proc.stderr


def _load_monte_carlo_summary(trades_file: str) -> Dict[str, Any]:
    trades_path = Path(trades_file)
    stem = trades_path.parent.name
    summary_path = Path(ROOT) / "results" / "monte_carlo" / f"{stem}_mc_summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _render_equity_chart(equity_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if equity_df.empty or "equity" not in equity_df.columns:
        fig.update_layout(
            title="Equity Curve",
            height=280,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,17,25,0.72)",
            font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        )
        return fig
    fig.add_trace(
        go.Scatter(
            x=list(range(len(equity_df))),
            y=pd.to_numeric(equity_df["equity"], errors="coerce"),
            mode="lines",
            line=dict(color="#f5b000", width=2),
            name="Equity",
        )
    )
    fig.update_layout(
        title="Equity Curve",
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,17,25,0.72)",
        font=dict(family="Space Grotesk, sans-serif", color="#e8eff7"),
        margin=dict(l=8, r=8, t=36, b=8),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False)
    return fig


def main() -> None:
    st.set_page_config(page_title="Chimera Control Room", layout="wide", initial_sidebar_state="expanded")
    _inject_app_style()
    _ensure_state()
    engine: BookmapEngine = st.session_state.engine
    feed = st.session_state.feed
    symbol_now = st.session_state.feed_symbol.upper()
    if st.session_state.last_loaded_ui_symbol != symbol_now:
        _load_ui_settings(symbol_now)
    tradecount_cfg = os.path.join(ROOT, "config", "config_combined_tradecount_v2.yaml")
    if os.path.exists(tradecount_cfg):
        current_bt_cfg = str(st.session_state.get("backtest_config_file", "") or "").strip()
        current_bt_cfg_abs = os.path.abspath(os.path.expanduser(current_bt_cfg)) if current_bt_cfg else ""
        legacy_bt_cfgs = {
            "",
            "config/config.yaml",
            "config/config_combined_trend_ict_range.yaml",
            os.path.join(ROOT, "config", "config.yaml"),
            os.path.join(ROOT, "config", "config_combined_trend_ict_range.yaml"),
        }
        legacy_bt_cfgs_abs = {os.path.abspath(os.path.expanduser(x)) for x in legacy_bt_cfgs if x}
        if (
            current_bt_cfg in legacy_bt_cfgs
            or current_bt_cfg_abs in legacy_bt_cfgs_abs
            or (current_bt_cfg and not os.path.exists(current_bt_cfg_abs))
        ):
            st.session_state.backtest_config_file = tradecount_cfg

    with st.sidebar:
        st.header("Mode")
        ui_mode = st.selectbox("Interface", ["Beginner", "Pro"], key="ui_mode")

        st.header("Feed")
        feed_mode = st.selectbox(
            "Source",
            ["Synthetic", "Binance Futures (REST)", "Futures L2 Bridge (JSON)", "Replay (JSONL)"],
            key="feed_mode",
        )
        symbol = st.text_input("Symbol", value=st.session_state.feed_symbol, help="Example: BTCUSDT, ETHUSDT").upper().strip()
        st.session_state.feed_symbol = symbol or "BTCUSDT"
        if str(feed_mode) in {"Binance Futures (REST)", "Futures L2 Bridge (JSON)"}:
            auto_path = _resolve_external_l2_path(st.session_state.feed_symbol, str(st.session_state.external_l2_path))
            if auto_path and auto_path != str(st.session_state.external_l2_path):
                st.session_state.external_l2_path = auto_path
        external_l2_path = st.text_input(
            "Live L2 JSON Path",
            value=str(st.session_state.external_l2_path),
            help="Path written by your broker/data vendor bridge for real MNQ/MGC depth+tape",
            key="external_l2_path",
        )
        replay_file_path = st.text_input(
            "Replay JSONL Path",
            value=str(st.session_state.replay_file_path),
            key="replay_file_path",
        )
        _render_path_chip("Live L2", external_l2_path)
        _render_path_chip("Replay", replay_file_path)
        replay_loop = st.toggle("Replay Loop", value=bool(st.session_state.replay_loop), key="replay_loop")
        replay_record_enabled = st.toggle(
            "Record Live Feed To Replay",
            value=bool(st.session_state.replay_record_enabled),
            key="replay_record_enabled",
        )
        replay_auto_step = st.slider("Replay Step Size", 1, 20, int(st.session_state.replay_auto_step), key="replay_auto_step")
        st.caption("Quick Symbols")
        q1, q2 = st.columns(2)
        if q1.button("MGC1!", use_container_width=True):
            st.session_state.feed_symbol = "MGC1!"
            _rebuild_feed(
                "Futures L2 Bridge (JSON)",
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()
        if q2.button("MNQ1!", use_container_width=True):
            st.session_state.feed_symbol = "MNQ1!"
            _rebuild_feed(
                "Futures L2 Bridge (JSON)",
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()
        q3, q4 = st.columns(2)
        if q3.button("BTC", use_container_width=True):
            st.session_state.feed_symbol = "BTCUSDT"
            _rebuild_feed(
                "Binance Futures (REST)",
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()
        if q4.button("ETH", use_container_width=True):
            st.session_state.feed_symbol = "ETHUSDT"
            _rebuild_feed(
                "Binance Futures (REST)",
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()
        if st.button("Apply Feed", use_container_width=True):
            selected_mode = str(feed_mode)
            if selected_mode in {"Binance Futures (REST)", "Futures L2 Bridge (JSON)"}:
                selected_mode = _recommended_live_feed_mode(st.session_state.feed_symbol)
            _rebuild_feed(
                selected_mode,
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()

        # Keep backend feed in sync with what UI shows.
        effective_feed_mode = str(feed_mode)
        if effective_feed_mode in {"Binance Futures (REST)", "Futures L2 Bridge (JSON)"}:
            recommended = _recommended_live_feed_mode(st.session_state.feed_symbol)
            if effective_feed_mode != recommended:
                effective_feed_mode = recommended
        if (
            st.session_state.active_feed_mode != effective_feed_mode
            or st.session_state.active_feed_symbol != st.session_state.feed_symbol.upper()
            or int(st.session_state.active_heatmap_levels) != int(st.session_state.heatmap_levels)
            or int(st.session_state.active_heatmap_history) != int(st.session_state.heatmap_history)
        ):
            _rebuild_feed(
                effective_feed_mode,
                st.session_state.feed_symbol,
                st.session_state.external_l2_path,
                st.session_state.replay_file_path,
                bool(st.session_state.replay_loop),
            )
            st.rerun()

        st.header("Presets")
        p1, p2, p3 = st.columns(3)
        if p1.button("Scalp", use_container_width=True):
            _apply_preset("Scalp")
            st.rerun()
        if p2.button("Balanced", use_container_width=True):
            _apply_preset("Balanced")
            st.rerun()
        if p3.button("Strict Prop", use_container_width=True):
            _apply_preset("Strict Prop")
            st.rerun()
        strategy_profile = st.selectbox(
            "Strategy Profile",
            ["strict", "balanced", "scalp", "custom"],
            index=["strict", "balanced", "scalp", "custom"].index(
                st.session_state.strategy_profile
                if st.session_state.strategy_profile in ["strict", "balanced", "scalp", "custom"]
                else "balanced"
            ),
            key="strategy_profile",
        )

        advanced_controls = st.toggle(
            "Show Advanced Controls",
            value=bool(st.session_state.show_advanced_controls),
            key="show_advanced_controls",
        )
        if advanced_controls:
            st.header("Signal Tuning")
            whale_pct = st.slider("Whale Percentile", 90, 99, int(st.session_state.whale_pct), key="whale_pct")
            whale_min = st.number_input("Whale Min Size", min_value=1.0, max_value=10000.0, value=float(st.session_state.whale_min), step=1.0, key="whale_min")
            absorb_pct = st.slider("Absorption Percentile", 70, 99, int(st.session_state.absorb_pct), key="absorb_pct")
            sweep_pct = st.slider("Sweep Percentile", 70, 99, int(st.session_state.sweep_pct), key="sweep_pct")
            quiet_mode = st.toggle("Quiet Mode (hide weak events)", value=bool(st.session_state.quiet_mode), key="quiet_mode")
            zoom_view = st.toggle("Zoom Around Mid", value=bool(st.session_state.zoom_view), key="zoom_view")
            auto_follow_mid = st.toggle("Auto Follow Mid (Autoscale)", value=bool(st.session_state.auto_follow_mid), key="auto_follow_mid")
            if st.button("Reset View", use_container_width=True):
                st.session_state.frozen_y_range = None
                st.rerun()
            show_trade_bubbles = st.toggle("3D Trade Bubbles", value=bool(st.session_state.show_trade_bubbles), key="show_trade_bubbles")
            bubble_scale = st.slider("Bubble Scale", 0.5, 4.0, float(st.session_state.bubble_scale), 0.1, key="bubble_scale")
            heatmap_levels = st.slider("Heatmap Price Levels", 40, 240, int(st.session_state.heatmap_levels), 20, key="heatmap_levels")
            heatmap_history = st.slider("Heatmap Time Bars", 120, 600, int(st.session_state.heatmap_history), 20, key="heatmap_history")
            decision_mode = st.selectbox(
                "Decision Mode",
                ["Adaptive Objective", "Classic Votes"],
                index=["Adaptive Objective", "Classic Votes"].index(
                    st.session_state.decision_mode if st.session_state.decision_mode in {"Adaptive Objective", "Classic Votes"} else "Adaptive Objective"
                ),
                key="decision_mode",
            )
            decision_min_score = st.slider(
                "Objective Min Score",
                1.0,
                4.0,
                float(st.session_state.decision_min_score),
                0.25,
                key="decision_min_score",
            )
            four_hour_bias_enabled = st.toggle(
                "Use 4H Candle Bias Gate",
                value=bool(st.session_state.four_hour_bias_enabled),
                key="four_hour_bias_enabled",
            )
            four_hour_bias_min_body_ratio = st.slider(
                "4H Min Body/Range Ratio",
                0.05,
                0.50,
                float(st.session_state.four_hour_bias_min_body_ratio),
                0.01,
                key="four_hour_bias_min_body_ratio",
            )

            st.header("Automation")
            live_loop_enabled = st.toggle("Enable Continuous Auto Loop", value=bool(st.session_state.live_loop_enabled), key="live_loop_enabled")
            live_loop_interval = st.slider("Loop Interval (sec)", 1, 30, int(st.session_state.live_loop_interval), key="live_loop_interval")
            live_loop_ticks = st.slider("Ticks Per Loop", 1, 50, int(st.session_state.live_loop_ticks), key="live_loop_ticks")
            bridge_enabled = st.toggle("Write Strategy Bridge File", value=bool(st.session_state.bridge_enabled), key="bridge_enabled")
            bridge_path = st.text_input("Bridge File Path", value=st.session_state.bridge_path)
            _render_path_chip("Bridge", bridge_path)
            st.session_state.bridge_path = bridge_path

            st.header("Alerts + Watchdog")
            alerts_enabled = st.toggle("Enable Buy/Sell Alerts", value=bool(st.session_state.alerts_enabled), key="alerts_enabled")
            alert_min_conf = st.slider("Alert Min Confidence", 0, 100, int(st.session_state.alert_min_conf), key="alert_min_conf")
            alert_cooldown_sec = st.slider("Alert Cooldown (sec)", 1, 300, int(st.session_state.alert_cooldown_sec), key="alert_cooldown_sec")
            alert_change_only = st.toggle("Alert Only On Decision Change", value=bool(st.session_state.alert_change_only), key="alert_change_only")
            alert_log_enabled = st.toggle("Write Alert Log CSV", value=bool(st.session_state.alert_log_enabled), key="alert_log_enabled")
            alert_webhook_enabled = st.toggle("Webhook Alerts", value=bool(st.session_state.alert_webhook_enabled), key="alert_webhook_enabled")
            alert_webhook_url = st.text_input("Webhook URL", value=str(st.session_state.alert_webhook_url), placeholder="https://...", key="alert_webhook_url")
            watchdog_enabled = st.toggle("Watchdog Enabled", value=bool(st.session_state.watchdog_enabled), key="watchdog_enabled")
            watchdog_feed_stale_seconds = st.slider(
                "Feed Stale (s)",
                5,
                120,
                int(st.session_state.watchdog_feed_stale_seconds),
                key="watchdog_feed_stale_seconds",
            )
            watchdog_bridge_stale_seconds = st.slider(
                "Bridge Stale (s)",
                5,
                120,
                int(st.session_state.watchdog_bridge_stale_seconds),
                key="watchdog_bridge_stale_seconds",
            )
            watchdog_executor_idle_seconds = st.slider(
                "Executor Idle (s)",
                30,
                600,
                int(st.session_state.watchdog_executor_idle_seconds),
                key="watchdog_executor_idle_seconds",
            )
            watchdog_alert_webhook_enabled = st.toggle(
                "Watchdog Phone/Webhook Alert",
                value=bool(st.session_state.watchdog_alert_webhook_enabled),
                key="watchdog_alert_webhook_enabled",
            )
            watchdog_alert_webhook_url = st.text_input(
                "Watchdog Alert URL",
                value=str(st.session_state.watchdog_alert_webhook_url),
                placeholder="https://...",
                key="watchdog_alert_webhook_url",
            )
            watchdog_alert_cooldown_sec = st.slider(
                "Watchdog Cooldown (s)",
                30,
                900,
                int(st.session_state.watchdog_alert_cooldown_sec),
                key="watchdog_alert_cooldown_sec",
            )

            st.header("Desk View")
            ab_rolling_trades = st.slider(
                "Rolling Trades",
                10,
                200,
                int(st.session_state.ab_rolling_trades),
                key="ab_rolling_trades",
            )
            dom_depth = st.slider("Ladder Depth", 6, 30, int(st.session_state.dom_depth), key="dom_depth")
            dom_compact = st.toggle("Compact DOM", value=bool(st.session_state.dom_compact), key="dom_compact")
            dom_show_depth_chart = st.toggle("Show Depth Map", value=bool(st.session_state.dom_show_depth_chart), key="dom_show_depth_chart")
            footprint_mode = st.selectbox("Footprint Mode", ["Off", "Lite", "Pro"], index=["Off", "Lite", "Pro"].index(st.session_state.footprint_mode if st.session_state.footprint_mode in ["Off", "Lite", "Pro"] else "Lite"), key="footprint_mode")
            footprint_lookback = st.slider("Footprint Lookback", 12, 120, int(st.session_state.footprint_lookback), key="footprint_lookback")
        else:
            st.caption("Advanced controls hidden. Toggle on when you need tuning or automation changes.")
            whale_pct = int(st.session_state.whale_pct)
            whale_min = float(st.session_state.whale_min)
            absorb_pct = int(st.session_state.absorb_pct)
            sweep_pct = int(st.session_state.sweep_pct)
            quiet_mode = bool(st.session_state.quiet_mode)
            zoom_view = bool(st.session_state.zoom_view)
            auto_follow_mid = bool(st.session_state.auto_follow_mid)
            show_trade_bubbles = bool(st.session_state.show_trade_bubbles)
            bubble_scale = float(st.session_state.bubble_scale)
            heatmap_levels = int(st.session_state.heatmap_levels)
            heatmap_history = int(st.session_state.heatmap_history)
            decision_mode = str(st.session_state.decision_mode)
            decision_min_score = float(st.session_state.decision_min_score)
            four_hour_bias_enabled = bool(st.session_state.four_hour_bias_enabled)
            four_hour_bias_min_body_ratio = float(st.session_state.four_hour_bias_min_body_ratio)
            live_loop_enabled = bool(st.session_state.live_loop_enabled)
            live_loop_interval = int(st.session_state.live_loop_interval)
            live_loop_ticks = int(st.session_state.live_loop_ticks)
            bridge_enabled = bool(st.session_state.bridge_enabled)
            bridge_path = str(st.session_state.bridge_path)
            alerts_enabled = bool(st.session_state.alerts_enabled)
            alert_min_conf = int(st.session_state.alert_min_conf)
            alert_cooldown_sec = int(st.session_state.alert_cooldown_sec)
            alert_change_only = bool(st.session_state.alert_change_only)
            alert_log_enabled = bool(st.session_state.alert_log_enabled)
            alert_webhook_enabled = bool(st.session_state.alert_webhook_enabled)
            alert_webhook_url = str(st.session_state.alert_webhook_url)
            watchdog_enabled = bool(st.session_state.watchdog_enabled)
            watchdog_feed_stale_seconds = int(st.session_state.watchdog_feed_stale_seconds)
            watchdog_bridge_stale_seconds = int(st.session_state.watchdog_bridge_stale_seconds)
            watchdog_executor_idle_seconds = int(st.session_state.watchdog_executor_idle_seconds)
            watchdog_alert_webhook_enabled = bool(st.session_state.watchdog_alert_webhook_enabled)
            watchdog_alert_webhook_url = str(st.session_state.watchdog_alert_webhook_url)
            watchdog_alert_cooldown_sec = int(st.session_state.watchdog_alert_cooldown_sec)
            ab_rolling_trades = int(st.session_state.ab_rolling_trades)
            dom_depth = int(st.session_state.dom_depth)
            dom_compact = bool(st.session_state.dom_compact)
            dom_show_depth_chart = bool(st.session_state.dom_show_depth_chart)
            footprint_mode = str(st.session_state.footprint_mode)
            footprint_lookback = int(st.session_state.footprint_lookback)
        if st.button("Save Layout", use_container_width=True):
            keys_to_save = [
                "ui_mode", "whale_pct", "whale_min", "absorb_pct", "sweep_pct", "quiet_mode",
                "zoom_view", "auto_follow_mid", "show_trade_bubbles", "bubble_scale",
                "heatmap_levels", "heatmap_history", "decision_mode", "decision_min_score",
                "four_hour_bias_enabled", "four_hour_bias_min_body_ratio",
                "live_loop_enabled",
                "live_loop_interval", "live_loop_ticks", "bridge_enabled", "alerts_enabled",
                "alert_min_conf", "alert_cooldown_sec", "alert_change_only", "alert_log_enabled",
                "alert_webhook_enabled", "alert_webhook_url", "risk_stop_ticks", "risk_qty", "risk_tick_value",
                "dom_depth", "dom_compact", "dom_show_depth_chart", "footprint_mode", "footprint_lookback",
                "external_l2_path", "replay_file_path", "replay_loop", "replay_record_enabled", "replay_auto_step",
                "strategy_profile", "watchdog_enabled", "watchdog_feed_stale_seconds",
                "watchdog_bridge_stale_seconds", "watchdog_executor_idle_seconds",
                "watchdog_alert_webhook_enabled", "watchdog_alert_webhook_url", "watchdog_alert_cooldown_sec",
                "ab_rolling_trades", "show_advanced_controls",
                "backtest_config_file", "backtest_data_file", "backtest_output_dir", "backtest_instrument", "backtest_train_models",
                "backtest_train_split", "backtest_oos_only", "backtest_enforce_quality",
                "backtest_use_bridge", "mc_paths", "mc_slippage_perturb",
            ]
            _save_ui_settings(st.session_state.feed_symbol.upper(), keys_to_save)
            st.success("Layout saved for symbol")

    engine.set_signal_config(
        whale_percentile=whale_pct,
        whale_min_size=whale_min,
        absorption_percentile=absorb_pct,
        sweep_percentile=sweep_pct,
    )

    is_futures_symbol = _looks_like_tv_futures_symbol(st.session_state.feed_symbol)
    binance_symbol_invalid = feed_mode == "Binance Futures (REST)" and is_futures_symbol
    bridge_symbol_invalid = feed_mode == "Futures L2 Bridge (JSON)" and not is_futures_symbol
    feed_symbol_invalid = binance_symbol_invalid or bridge_symbol_invalid

    if binance_symbol_invalid:
        st.warning(
            "Binance mode does not support TradingView CME symbols like MGC1/MNQ1. "
            "Use a Binance symbol (e.g., BTCUSDT) or switch Source to Synthetic."
        )
    if bridge_symbol_invalid:
        st.warning(
            "Futures L2 Bridge mode is for bridge-fed futures symbols (e.g., MGC1!, MNQ1!). "
            "For BTC/ETH, switch Source to Binance Futures (REST)."
        )

    if not st.session_state.seeded:
        warmup = 40 if feed_mode == "Synthetic" else 10
        try:
            if not feed_symbol_invalid and feed_mode != "Replay (JSONL)":
                _ingest_feed_ticks(engine, feed, warmup, replay_record_enabled=False, replay_file_path=replay_file_path)
                st.session_state.last_feed_error = ""
        except Exception as exc:
            st.session_state.last_feed_error = str(exc)
            st.error(f"Feed warmup error: {exc}")
        st.session_state.seeded = True

    _render_hero(
        symbol=st.session_state.feed_symbol.upper(),
        feed_mode=feed_mode,
        strategy_profile=strategy_profile,
    )

    executor_payload = _executor_status_payload()
    exec_ok = bool(executor_payload.get("state") == "UP")
    exec_text = "UP" if exec_ok else "DOWN"
    latency_monitor = executor_payload.get("latency_monitor", {}) if isinstance(executor_payload, dict) else {}
    bridge_payload = read_bridge_signal(bridge_path)
    bridge_age_seconds = bridge_signal_age_seconds(bridge_payload) if isinstance(bridge_payload, dict) else float("inf")
    feed_delay_seconds = _timestamp_age_seconds(st.session_state.last_snapshot_timestamp_utc)

    feed_ok = not feed_symbol_invalid and st.session_state.last_feed_error == ""
    if watchdog_enabled and not math.isinf(feed_delay_seconds):
        feed_ok = feed_ok and feed_delay_seconds <= float(watchdog_feed_stale_seconds)
    bridge_ok, bridge_text = _bridge_status(bridge_path)
    session_label = _current_session_label()
    idle_age = _timestamp_age_seconds(str(latency_monitor.get("last_webhook_received_utc", "")))
    _render_system_overview(
        feed_ok=feed_ok,
        bridge_ok=bridge_ok,
        exec_ok=exec_ok,
        session_label=session_label,
        feed_mode=st.session_state.feed_mode,
        bridge_text=bridge_text,
        exec_text=exec_text,
        feed_delay_seconds=float(feed_delay_seconds),
        bridge_age_seconds=float(bridge_age_seconds),
        webhook_rtt_p95_ms=float(latency_monitor.get("webhook_rtt_p95_ms", 0.0)),
        idle_age_seconds=float(idle_age),
    )
    _render_status_marquee(
        session_label=session_label,
        strategy_profile=strategy_profile,
        feed_ok=feed_ok,
        bridge_ok=bridge_ok,
        exec_ok=exec_ok,
    )

    watchdog_alerts: List[str] = []
    if watchdog_enabled:
        if math.isinf(feed_delay_seconds) or feed_delay_seconds > float(watchdog_feed_stale_seconds):
            watchdog_alerts.append("feed_stale")
        if not bridge_ok or bridge_age_seconds > float(watchdog_bridge_stale_seconds):
            watchdog_alerts.append("bridge_stale")
        if math.isinf(idle_age) or idle_age > float(watchdog_executor_idle_seconds):
            watchdog_alerts.append("executor_idle")
        remote_watchdog = executor_payload.get("watchdog", {}) if isinstance(executor_payload, dict) else {}
        if isinstance(remote_watchdog, dict) and not bool(remote_watchdog.get("ok", True)):
            watchdog_alerts.extend([f"executor:{a}" for a in remote_watchdog.get("alerts", []) if isinstance(a, str)])

    if watchdog_alerts:
        _render_inline_alert(f"Watchdog Alert: {', '.join(watchdog_alerts)}", level="error")
        now_epoch = time.time()
        if (
            watchdog_alert_webhook_enabled
            and str(watchdog_alert_webhook_url).strip()
            and (now_epoch - float(st.session_state.watchdog_last_alert_epoch)) >= float(watchdog_alert_cooldown_sec)
        ):
            try:
                _send_webhook(
                    str(watchdog_alert_webhook_url).strip(),
                    {
                        "timestamp_utc": utc_now_iso(),
                        "alerts": watchdog_alerts,
                        "symbol": st.session_state.feed_symbol.upper(),
                        "feed_mode": feed_mode,
                    },
                )
                st.session_state.watchdog_last_alert_epoch = now_epoch
            except requests.RequestException as exc:
                st.warning(f"Watchdog webhook failed: {exc}")

    if str(st.session_state.last_feed_error).strip():
        _render_inline_alert(f"Feed Error: {st.session_state.last_feed_error}", level="warn")

    _render_section_head("Execution Controls", "Run batch, step one tick, or pulse auto every 5 seconds")
    c1, c2, c3, c4 = st.columns([1.05, 1, 1, 1.1])
    with c1:
        st.caption("Ticks Per Run")
        ticks = st.number_input(
            "Ticks per run",
            min_value=1,
            max_value=500,
            value=30,
            step=1,
            label_visibility="collapsed",
        )
    with c2:
        run_now = st.button("Run Batch", use_container_width=True)
    with c3:
        step_once = st.button("Step 1 Tick", use_container_width=True)
    with c4:
        auto = st.button("Auto 5s", use_container_width=True)

    if step_once:
        try:
            if not feed_symbol_invalid:
                _ingest_feed_ticks(engine, feed, replay_auto_step if feed_mode == "Replay (JSONL)" else 1, replay_record_enabled, replay_file_path)
                st.session_state.last_feed_error = ""
        except Exception as exc:
            st.session_state.last_feed_error = str(exc)
            st.error(f"Feed error: {exc}")
    if run_now:
        try:
            if not feed_symbol_invalid:
                _ingest_feed_ticks(engine, feed, int(ticks), replay_record_enabled, replay_file_path)
                st.session_state.last_feed_error = ""
        except Exception as exc:
            st.session_state.last_feed_error = str(exc)
            st.error(f"Feed error: {exc}. If Binance futures is blocked in your region, try Synthetic.")
    if auto:
        try:
            if not feed_symbol_invalid:
                _ingest_feed_ticks(engine, feed, 5, replay_record_enabled, replay_file_path)
                st.session_state.last_feed_error = ""
        except Exception as exc:
            st.session_state.last_feed_error = str(exc)
            st.error(f"Feed error: {exc}")
        time.sleep(0.15)

    # Continuous loop mode: ingest on every rerun, then self-rerun after interval.
    if live_loop_enabled:
        try:
            if not feed_symbol_invalid:
                _ingest_feed_ticks(engine, feed, int(live_loop_ticks), replay_record_enabled, replay_file_path)
                st.session_state.last_feed_error = ""
        except Exception as exc:
            st.session_state.last_feed_error = str(exc)
            st.error(f"Feed error in live loop: {exc}")

    left, right = st.columns([2.25, 1.0])
    with left:
        _render_section_head("Bookmap Engine", "Heatmap and live tape context")
        if engine.snapshots:
            last_snap = engine.snapshots[-1]
            symbol_now = st.session_state.feed_symbol.upper()
            snap_source = str(st.session_state.feed_mode)
            if str(st.session_state.feed_mode) == "Futures L2 Bridge (JSON)":
                bridge_path = _resolve_external_l2_path(symbol_now, str(st.session_state.external_l2_path))
                snap_meta = _load_live_snapshot_meta(bridge_path)
                snap_source = str(snap_meta.get("source", f"file:{os.path.basename(bridge_path)}")).strip()
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Symbol", symbol_now)
            p2.metric("Last Trade (Raw)", _fmt_price(symbol_now, float(last_snap.last_trade_price)))
            p3.metric("Mid (Raw)", _fmt_price(symbol_now, float(last_snap.mid)))
            p4.metric("Source", snap_source or "unknown")
            st.caption(
                f"Exact last={float(last_snap.last_trade_price):,.8f} | exact mid={float(last_snap.mid):,.8f}"
            )
            if "fallback:synthetic" in snap_source:
                _render_inline_alert(
                    "Bridge source is fallback synthetic. Futures prices may be inaccurate until primary file-poll feed is fresh.",
                    level="warn",
                )
        st.plotly_chart(
            _render_heatmap(
                zoom_view=zoom_view,
                show_trade_bubbles=show_trade_bubbles,
                bubble_scale=bubble_scale,
                auto_follow_mid=auto_follow_mid,
            ),
            width="stretch",
        )

    with right:
        _render_section_head("Signal Command", "Decision, confidence, and imbalance")
        sig = engine.last_signals
        candle_4h = _resolve_4h_candle(
            str(st.session_state.active_feed_mode),
            st.session_state.feed_symbol.upper(),
            engine,
        )
        bias_4h = _four_hour_bias(candle_4h, float(four_hour_bias_min_body_ratio))
        decision, notes = _derive_bridge_decision(
            sig,
            quiet_mode=quiet_mode,
            engine=engine,
            decision_mode=decision_mode,
            min_score=decision_min_score,
        )
        if four_hour_bias_enabled and decision == "GO_LONG" and bias_4h not in {"bullish", "unknown"}:
            decision = "NO_TRADE"
            notes = f"{notes} | 4h_bias={bias_4h} blocks long"
        if four_hour_bias_enabled and decision == "GO_SHORT" and bias_4h not in {"bearish", "unknown"}:
            decision = "NO_TRADE"
            notes = f"{notes} | 4h_bias={bias_4h} blocks short"
        prev = st.session_state.decision_history[-1]["decision"] if st.session_state.decision_history else None
        if decision != prev:
            st.session_state.decision_history.append(
                {"ts": datetime.now().strftime("%H:%M:%S"), "decision": decision, "conf": float(sig.confidence)}
            )
            st.session_state.decision_history = st.session_state.decision_history[-50:]
        decision_label = "LONG" if decision == "GO_LONG" else ("SHORT" if decision == "GO_SHORT" else "NO TRADE")
        decision_class = "signal-state-long" if decision == "GO_LONG" else ("signal-state-short" if decision == "GO_SHORT" else "signal-state-flat")
        conf_value = max(0.0, min(100.0, float(sig.confidence)))
        imb_value = max(-1.0, min(1.0, float(sig.imbalance)))
        imb_bar_width = min(100.0, abs(imb_value) * 100.0)
        imb_side = "BUY" if imb_value > 0.02 else ("SELL" if imb_value < -0.02 else "NEUTRAL")
        imb_fill_class = "signal-bar-fill-imb-buy" if imb_value >= 0 else "signal-bar-fill-imb-sell"
        safe_notes = html.escape(str(notes))

        st.markdown(
            f"""
            <section class="signal-card">
              <div class="signal-state {decision_class}">{decision_label}</div>
              <div class="signal-row"><span>Confidence</span><strong class="signal-number">{conf_value:.0f}/100</strong></div>
              <div class="signal-bar"><div class="signal-bar-fill signal-bar-fill-conf" style="width:{conf_value:.1f}%"></div></div>
              <div class="signal-row"><span>Imbalance ({imb_side})</span><strong class="signal-number">{imb_value:+.2f}</strong></div>
              <div class="signal-bar"><div class="signal-bar-fill {imb_fill_class}" style="width:{imb_bar_width:.1f}%"></div></div>
              <div class="signal-notes">{safe_notes}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        if candle_4h:
            candle_src = str(candle_4h.get("source", "unknown"))
            c_open = _fmt_price(st.session_state.feed_symbol.upper(), float(candle_4h.get("open", 0.0)))
            c_high = _fmt_price(st.session_state.feed_symbol.upper(), float(candle_4h.get("high", 0.0)))
            c_low = _fmt_price(st.session_state.feed_symbol.upper(), float(candle_4h.get("low", 0.0)))
            c_close = _fmt_price(st.session_state.feed_symbol.upper(), float(candle_4h.get("close", 0.0)))
            st.caption(
                f"4H bias={bias_4h.upper()} | O:{c_open} H:{c_high} L:{c_low} C:{c_close} | {candle_src}"
            )
        else:
            st.caption("4H bias=UNKNOWN | waiting for enough bars")

        desk_tabs = st.tabs(["Signal Deck", "DOM Desk", "Risk", "Footprint"])

        with desk_tabs[0]:
            if decision == "NO_TRADE":
                _render_inline_alert(f"Block Reason: {notes}", level="warn")

            show_sweep_up = sig.sweep_up and (not quiet_mode or sig.confidence >= 40)
            show_sweep_down = sig.sweep_down and (not quiet_mode or sig.confidence >= 40)
            show_absorb_bid = sig.absorption_bid and (not quiet_mode or sig.confidence >= 45)
            show_absorb_ask = sig.absorption_ask and (not quiet_mode or sig.confidence >= 45)

            if ui_mode == "Pro":
                st.write(f"Sweep Up: {'Yes' if show_sweep_up else 'No'}")
                st.write(f"Sweep Down: {'Yes' if show_sweep_down else 'No'}")
                st.write(f"Bid Absorption: {'Yes' if show_absorb_bid else 'No'}")
                st.write(f"Ask Absorption: {'Yes' if show_absorb_ask else 'No'}")

            whale_alert = sig.whale_buy or sig.whale_sell
            whale_side = "BUY" if sig.whale_buy else "SELL" if sig.whale_sell else "NONE"
            whale_msg = f"{whale_side} | size={sig.whale_size:.2f} | thr={sig.whale_threshold:.2f}"
            if whale_alert:
                st.success(f"Whale Hit: {whale_msg}")
            elif not quiet_mode:
                st.info(f"Whale Monitor: {whale_msg}")

        with desk_tabs[1]:
            if ui_mode == "Pro":
                ladder_rows = engine.latest_ladder(depth=int(dom_depth))
                dom_tab1, dom_tab2 = st.tabs(["Ladder", "Depth Map"])
                with dom_tab1:
                    dom_df = _dom_table_df(ladder_rows)
                    if not dom_df.empty and dom_compact:
                        dom_df = dom_df[["side", "price", "size"]]
                    st.dataframe(dom_df, width="stretch", hide_index=True)
                with dom_tab2:
                    if dom_show_depth_chart:
                        st.plotly_chart(_render_dom_depth_chart(ladder_rows), width="stretch")
                    else:
                        st.caption("Depth map hidden by toggle.")
            else:
                st.caption("Switch interface to Pro for full DOM view.")

        with desk_tabs[2]:
            risk_stop_ticks = st.number_input("Stop (ticks)", min_value=1, max_value=500, value=int(st.session_state.risk_stop_ticks), key="risk_stop_ticks")
            risk_qty = st.number_input("Qty", min_value=1, max_value=100, value=int(st.session_state.risk_qty), key="risk_qty")
            risk_tick_value = st.number_input("Tick Value ($)", min_value=0.01, max_value=1000.0, value=float(st.session_state.risk_tick_value), step=0.01, key="risk_tick_value")
            est_risk = float(risk_stop_ticks) * float(risk_qty) * float(risk_tick_value)
            st.metric("Est Risk/Trade", f"${est_risk:,.2f}")
            spread_ticks = 0.0
            top_rows = engine.latest_ladder(depth=1)
            if top_rows:
                asks = [r for r in top_rows if r[0] == "ask"]
                bids = [r for r in top_rows if r[0] == "bid"]
                if asks and bids:
                    spread_ticks = max(0.0, float(asks[0][1]) - float(bids[0][1]))
            st.metric("Spread (raw)", f"{spread_ticks:.4f}")

        with desk_tabs[3]:
            if footprint_mode != "Off":
                fp = _footprint_frame(engine, int(footprint_lookback))
                st.plotly_chart(_render_footprint_lite(fp), width="stretch")
                if not fp.empty:
                    last = fp.iloc[-1]
                    st.caption(
                        f"Last Bucket: {last['control']} | "
                        f"Delta {last['delta']:.2f} | "
                        f"Imbalance {last['imbalance']:.2f}"
                    )
                    if footprint_mode == "Pro":
                        st.dataframe(
                            fp[["idx", "buy_vol", "sell_vol", "delta", "imbalance", "control"]].tail(12),
                            width="stretch",
                            hide_index=True,
                        )
            else:
                st.caption("Footprint is disabled in sidebar settings.")

    # Buy/Sell alerts for GO_LONG and GO_SHORT decisions.
    if alerts_enabled and decision in ("GO_LONG", "GO_SHORT") and sig.confidence >= alert_min_conf:
        now_epoch = time.time()
        changed = decision != st.session_state.last_alert_decision
        cooldown_ok = (now_epoch - float(st.session_state.last_alert_epoch)) >= float(alert_cooldown_sec)
        should_alert = cooldown_ok and (changed or not alert_change_only)
        if should_alert:
            emoji = "🟢" if decision == "GO_LONG" else "🔴"
            msg = f"{emoji} {decision} | {st.session_state.feed_symbol.upper()} | conf={sig.confidence:.0f}"
            st.toast(msg)
            st.info(f"Alert sent: {msg}")

            row = {
                "timestamp_utc": utc_now_iso(),
                "symbol": st.session_state.feed_symbol.upper(),
                "decision": decision,
                "confidence": f"{sig.confidence:.2f}",
                "imbalance": f"{sig.imbalance:.4f}",
                "whale_buy": bool(sig.whale_buy),
                "whale_sell": bool(sig.whale_sell),
                "notes": notes,
                # IFTTT-compatible fields
                "value1": decision,
                "value2": st.session_state.feed_symbol.upper(),
                "value3": f"{sig.confidence:.0f}",
            }

            if alert_log_enabled:
                try:
                    _append_alert_log(os.path.join(ROOT, "data", "bookmap_alerts.csv"), row)
                except OSError as exc:
                    st.error(f"Alert log write failed: {exc}")

            if alert_webhook_enabled and alert_webhook_url.strip():
                try:
                    _send_webhook(alert_webhook_url.strip(), row)
                except requests.RequestException as exc:
                    st.error(f"Webhook alert failed: {exc}")

            st.session_state.last_alert_decision = decision
            st.session_state.last_alert_epoch = now_epoch
            st.session_state.recent_alerts.append(
                {
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "symbol": st.session_state.feed_symbol.upper(),
                    "decision": decision,
                    "confidence": f"{sig.confidence:.0f}",
                }
            )
            st.session_state.recent_alerts = st.session_state.recent_alerts[-20:]
    elif decision == "NO_TRADE":
        st.session_state.last_alert_decision = "NO_TRADE"

    if bridge_enabled:
        payload = BookmapBridgeSignal(
            timestamp_utc=utc_now_iso(),
            source=feed_mode,
            symbol=st.session_state.feed_symbol.upper(),
            profile=str(strategy_profile).lower(),
            decision=decision,
            confidence=float(sig.confidence),
            imbalance=float(sig.imbalance),
            whale_buy=bool(sig.whale_buy),
            whale_sell=bool(sig.whale_sell),
            whale_size=float(sig.whale_size),
            whale_threshold=float(sig.whale_threshold),
            sweep_up=bool(sig.sweep_up),
            sweep_down=bool(sig.sweep_down),
            absorption_bid=bool(sig.absorption_bid),
            absorption_ask=bool(sig.absorption_ask),
            notes=notes,
        )
        try:
            write_bridge_signal(bridge_path, payload)
        except OSError as exc:
            st.error(f"Bridge write failed: {exc}")

    # Auto-persist key UI preferences per symbol.
    auto_keys = [
        "ui_mode", "whale_pct", "whale_min", "absorb_pct", "sweep_pct", "quiet_mode",
        "zoom_view", "auto_follow_mid", "show_trade_bubbles", "bubble_scale",
        "heatmap_levels", "heatmap_history", "decision_mode", "decision_min_score",
        "four_hour_bias_enabled", "four_hour_bias_min_body_ratio",
        "live_loop_enabled", "live_loop_interval", "live_loop_ticks", "bridge_enabled",
        "alerts_enabled", "alert_min_conf", "alert_cooldown_sec", "alert_change_only",
        "alert_log_enabled", "alert_webhook_enabled", "alert_webhook_url",
        "risk_stop_ticks", "risk_qty", "risk_tick_value", "dom_depth", "dom_compact", "dom_show_depth_chart",
        "footprint_mode", "footprint_lookback",
        "external_l2_path", "replay_file_path", "replay_loop", "replay_record_enabled", "replay_auto_step",
        "strategy_profile", "watchdog_enabled", "watchdog_feed_stale_seconds",
        "watchdog_bridge_stale_seconds", "watchdog_executor_idle_seconds",
        "watchdog_alert_webhook_enabled", "watchdog_alert_webhook_url", "watchdog_alert_cooldown_sec",
        "ab_rolling_trades", "show_advanced_controls",
        "backtest_config_file", "backtest_data_file", "backtest_output_dir", "backtest_instrument", "backtest_train_models",
        "backtest_train_split", "backtest_oos_only", "backtest_enforce_quality",
        "backtest_use_bridge", "mc_paths", "mc_slippage_perturb",
    ]
    try:
        _save_ui_settings(st.session_state.feed_symbol.upper(), auto_keys)
    except OSError:
        pass

    # Keep app advancing without button clicks while live loop is enabled.
    if live_loop_enabled:
        st.caption(f"Live loop active: {live_loop_ticks} ticks every {live_loop_interval}s")
        time.sleep(float(live_loop_interval))
        st.rerun()

    st.divider()
    _render_section_head("A/B Profile Tracker", "Rolling profile outcomes across brokers")
    ab_payload = executor_payload.get("ab_profile_tracker", {}) if isinstance(executor_payload, dict) else {}
    ab_profiles = ab_payload.get("profiles", {}) if isinstance(ab_payload, dict) else {}
    rows: List[Dict[str, Any]] = []
    if isinstance(ab_profiles, dict):
        for broker_name, by_profile in ab_profiles.items():
            if not isinstance(by_profile, dict):
                continue
            for profile_name, stats in by_profile.items():
                if not isinstance(stats, dict):
                    continue
                rows.append(
                    {
                        "broker": broker_name,
                        "profile": profile_name,
                        "trades": int(float(stats.get("trades", 0))),
                        "win_rate_%": round(float(stats.get("win_rate", 0.0)), 1),
                        "net_pnl_usd": round(float(stats.get("net_pnl_usd", 0.0)), 2),
                        "avg_pnl_usd": round(float(stats.get("avg_pnl_usd", 0.0)), 2),
                    }
                )
    if rows:
        st.dataframe(
            pd.DataFrame(rows).sort_values(["net_pnl_usd", "win_rate_%"], ascending=[False, False]),
            width="stretch",
            hide_index=True,
        )
    else:
        _render_empty_state("No profile stats yet", "Closed trades will populate Strict/Balanced/Scalp comparison.")

    orders_df, closed_df, audit_df = _load_trade_journal_frames(ROOT)
    readiness = _prop_readiness_snapshot(
        closed_df=closed_df,
        audit_df=audit_df,
        executor_payload=executor_payload,
        watchdog_alerts=watchdog_alerts,
        config_path=str(st.session_state.backtest_config_file),
        strategy_profile=str(strategy_profile),
    )

    st.divider()
    _render_section_head("Prop Readiness", "Promotion gates and current readiness snapshot")
    rr = readiness.get("summary", {})
    r1, r2, r3, r4, r5, r6 = st.columns(6)
    r1.metric("Trades", f"{int(rr.get('trades', 0))}")
    r2.metric("Active Days", f"{int(rr.get('active_days', 0))}")
    r3.metric("Win Rate", f"{float(rr.get('win_rate', 0.0)):.1f}%")
    r4.metric("Profit Factor", f"{float(rr.get('profit_factor', 0.0)):.2f}")
    r5.metric("Max DD", f"{float(rr.get('max_dd_pct', 0.0)):.2f}%")
    r6.metric("Risk Blocks (7d)", f"{int(rr.get('recent_risk_blocks', 0))}")
    if bool(readiness.get("ready", False)):
        _render_inline_alert("Promotion gate passed: strategy is ready for prop-phase progression.", level="success")
    else:
        _render_inline_alert("Promotion gate not passed yet: continue paper phase until all checks are green.", level="warn")
    gates = readiness.get("gates", [])
    if isinstance(gates, list) and gates:
        gate_rows: List[Dict[str, Any]] = []
        for g in gates:
            if not isinstance(g, dict):
                continue
            gate_rows.append(
                {
                    "Gate": str(g.get("name", "")),
                    "Status": "PASS" if bool(g.get("ok", False)) else "FAIL",
                    "Detail": str(g.get("detail", "")),
                }
            )
        if gate_rows:
            _render_gate_table(gate_rows)
    limits = readiness.get("limits", {})
    st.caption(
        "Using config "
        f"`{readiness.get('config_path', '')}` | "
        f"daily_trades<={int(float(limits.get('max_daily_trades', 0) or 0))}, "
        f"consecutive_losses<={int(float(limits.get('max_consecutive_losses', 0) or 0))}, "
        f"max_daily_loss_usd={float(limits.get('max_daily_loss_usd', 0.0) or 0.0):.2f}"
    )

    st.divider()
    _render_section_head("Journal + Backtest", "Trade records, diagnostics, and historical lab")
    journal_tab, backtest_tab = st.tabs(["Trade Journal", "Backtest Lab"])

    with journal_tab:
        summary = _summarize_closed_trades(closed_df)
        j1, j2, j3, j4 = st.columns(4)
        j1.metric("Closed Trades", f"{int(summary['trades'])}")
        j2.metric("Win Rate", f"{summary['win_rate']:.1f}%")
        j3.metric("Net PnL", f"${summary['net_pnl']:.2f}")
        j4.metric("Avg/Trade", f"${summary['avg_pnl']:.2f}")

        jt1, jt2, jt3 = st.tabs(["Closed Trades", "Orders", "Audit Trail"])
        with jt1:
            if closed_df.empty:
                _render_empty_state("No closed trades yet", "Run or replay the strategy to start filling your trade journal.")
            else:
                st.dataframe(closed_df.tail(300).iloc[::-1], width="stretch", hide_index=True)
        with jt2:
            if orders_df.empty:
                _render_empty_state("No orders logged yet", "Orders will appear here once alerts/execution events are generated.")
            else:
                st.dataframe(orders_df.tail(300).iloc[::-1], width="stretch", hide_index=True)
        with jt3:
            if audit_df.empty:
                _render_empty_state("No audit records yet", "Decision snapshots and webhook outcomes will be shown in this panel.")
            else:
                st.dataframe(audit_df.tail(400).iloc[::-1], width="stretch", hide_index=True)

    with backtest_tab:
        st.caption("Run historical strategy tests from inside Chimera and inspect output immediately.")
        col_a, col_b = st.columns([2.2, 1.2])
        with col_a:
            bt_config_file = st.text_input(
                "Config YAML",
                value=str(st.session_state.backtest_config_file),
                key="backtest_config_file",
            )
            bt_data_file = st.text_input(
                "Data CSV",
                value=str(st.session_state.backtest_data_file),
                key="backtest_data_file",
            )
            bt_output_dir = st.text_input(
                "Output Directory",
                value=str(st.session_state.backtest_output_dir),
                key="backtest_output_dir",
            )
        with col_b:
            bt_instrument = st.selectbox(
                "Instrument",
                ["MGC", "MNQ"],
                index=["MGC", "MNQ"].index(st.session_state.backtest_instrument if st.session_state.backtest_instrument in ["MGC", "MNQ"] else "MGC"),
                key="backtest_instrument",
            )
            bt_train_models = st.toggle(
                "Train Models",
                value=bool(st.session_state.backtest_train_models),
                key="backtest_train_models",
            )
            bt_train_split = st.slider(
                "Train Split",
                min_value=0.50,
                max_value=0.90,
                value=float(st.session_state.backtest_train_split),
                step=0.05,
                key="backtest_train_split",
                help="Used only when Train Models is ON.",
            )
            bt_oos_only = st.toggle(
                "Out-of-Sample Only",
                value=bool(st.session_state.backtest_oos_only),
                key="backtest_oos_only",
                help="When ON, evaluate only on the holdout period after training.",
            )
            bt_enforce_quality = st.toggle(
                "Enforce Data Quality Gate",
                value=bool(st.session_state.backtest_enforce_quality),
                key="backtest_enforce_quality",
                help="Block backtests on unstable or malformed datasets.",
            )
            bt_use_bridge = st.toggle(
                "Use Live Bridge Gate",
                value=bool(st.session_state.backtest_use_bridge),
                key="backtest_use_bridge",
                help="Keep OFF for clean historical validation unless intentionally testing bridge-gated behavior.",
            )

        bt_health = _analyze_backtest_data_file(bt_data_file)
        if not bt_health.get("exists", False):
            st.warning("Backtest data file not found. Set a valid CSV path to continue.")
        else:
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Data Rows", f"{int(bt_health.get('rows', 0)):,}")
            h2.metric("Close Return", f"{float(bt_health.get('close_return_pct', 0.0)):.2f}%")
            h3.metric("Close Ratio", f"{float(bt_health.get('close_ratio', 0.0)):.3f}")
            h4.metric("Max Bar Move", f"{float(bt_health.get('max_abs_bar_return_pct', 0.0)):.2f}%")
            st.caption(f"Data range: {bt_health.get('start_ts', 'NA')} -> {bt_health.get('end_ts', 'NA')}")
            issues = bt_health.get("issues", [])
            if issues:
                st.error("Data quality issues: " + ", ".join(str(x) for x in issues))
            else:
                st.success("Data quality checks passed.")

        run_blocked = False
        run_error = False
        if st.button("Run Backtest Now", use_container_width=True):
            if not os.path.exists(bt_config_file):
                st.error(f"Config file not found: {bt_config_file}")
                run_blocked = True
                st.session_state.backtest_last_status_msg = "blocked: config file not found"
            elif not os.path.exists(bt_data_file):
                st.error(f"Data file not found: {bt_data_file}")
                run_blocked = True
                st.session_state.backtest_last_status_msg = "blocked: data file not found"
            elif bool(bt_enforce_quality) and bool(bt_health.get("issues")):
                st.error("Blocked by data quality gate. Fix data or disable the gate for this run.")
                run_blocked = True
                st.session_state.backtest_last_status_msg = "blocked: data quality gate"
            else:
                with st.spinner("Running backtest..."):
                    rc, stdout, stderr = _run_backtest_process(
                        data_file=bt_data_file,
                        config_file=bt_config_file,
                        output_dir=bt_output_dir,
                        instrument=bt_instrument,
                        train_models=bool(bt_train_models),
                        train_split=float(bt_train_split),
                        oos_only=bool(bt_oos_only),
                        enforce_quality=bool(bt_enforce_quality),
                        use_bridge=bool(bt_use_bridge),
                    )
                st.session_state.backtest_last_rc = rc
                st.session_state.backtest_last_stdout = stdout[-8000:]
                st.session_state.backtest_last_stderr = stderr[-4000:]
                if rc == 0:
                    st.success("Backtest complete.")
                    st.session_state.backtest_last_status_msg = "ok"
                else:
                    st.error(f"Backtest failed (code {rc}). Check logs below.")
                    run_error = True
                    st.session_state.backtest_last_status_msg = f"error: rc={rc}"

        if run_blocked or run_error:
            st.session_state.backtest_hide_stale_results = True
        elif st.session_state.backtest_last_rc == 0 and st.session_state.backtest_last_status_msg == "ok":
            st.session_state.backtest_hide_stale_results = False

        trades_df_bt, equity_df_bt, bt_summary = _backtest_summary(str(st.session_state.backtest_output_dir))
        if bool(st.session_state.backtest_hide_stale_results):
            trades_df_bt = pd.DataFrame()
            equity_df_bt = pd.DataFrame()
            bt_summary = {"total_trades": 0.0, "win_rate": 0.0, "net_pnl": 0.0, "avg_pnl": 0.0}
            st.info("Previous backtest results hidden until a successful run completes.")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Trades", f"{int(bt_summary.get('total_trades', 0))}")
        b2.metric("Win Rate", f"{float(bt_summary.get('win_rate', 0.0)):.1f}%")
        b3.metric("Net PnL", f"${float(bt_summary.get('net_pnl', 0.0)):.2f}")
        b4.metric("Avg/Trade", f"${float(bt_summary.get('avg_pnl', 0.0)):.2f}")

        st.plotly_chart(_render_equity_chart(equity_df_bt), width="stretch")
        if not trades_df_bt.empty:
            st.dataframe(trades_df_bt.tail(250).iloc[::-1], width="stretch", hide_index=True)
        else:
            st.caption("No trades.csv found in the selected output directory yet.")

        if st.session_state.backtest_last_stdout:
            with st.expander("Backtest Console Output", expanded=False):
                st.code(st.session_state.backtest_last_stdout, language="text")
        if st.session_state.backtest_last_stderr:
            with st.expander("Backtest STDERR", expanded=False):
                st.code(st.session_state.backtest_last_stderr, language="text")

        st.divider()
        st.subheader("Monte Carlo")
        mc_col1, mc_col2, mc_col3 = st.columns([1.2, 1.2, 1.6])
        with mc_col1:
            mc_paths = st.number_input("MC Paths", min_value=200, max_value=20000, value=int(st.session_state.mc_paths), step=200, key="mc_paths")
        with mc_col2:
            mc_perturb = st.slider("Slippage Perturb", 0.0, 0.5, float(st.session_state.mc_slippage_perturb), 0.01, key="mc_slippage_perturb")
        with mc_col3:
            run_mc = st.button("Run Monte Carlo", use_container_width=True)

        trades_file_for_mc = os.path.join(str(st.session_state.backtest_output_dir), "trades.csv")
        if run_mc:
            if not os.path.exists(trades_file_for_mc):
                st.error(f"No trades file found for Monte Carlo: {trades_file_for_mc}")
            else:
                with st.spinner("Running Monte Carlo..."):
                    mc_rc, mc_stdout, mc_stderr = _run_monte_carlo_process(
                        trades_file=trades_file_for_mc,
                        paths=int(mc_paths),
                        slippage_perturb=float(mc_perturb),
                    )
                st.session_state.mc_last_rc = mc_rc
                st.session_state.mc_last_stdout = mc_stdout[-8000:]
                st.session_state.mc_last_stderr = mc_stderr[-4000:]
                if mc_rc == 0:
                    st.success("Monte Carlo complete.")
                else:
                    st.error(f"Monte Carlo failed (code {mc_rc}).")

        mc_summary = _load_monte_carlo_summary(trades_file_for_mc)
        if mc_summary:
            scorecard = mc_summary.get("scorecard", {}) if isinstance(mc_summary.get("scorecard", {}), dict) else {}
            metrics = mc_summary.get("metrics", {}) if isinstance(mc_summary.get("metrics", {}), dict) else {}
            s1, s2, s3 = st.columns(3)
            s1.metric("Overall Pass", "YES" if bool(scorecard.get("overall_pass", False)) else "NO")
            s2.metric("PF Check", "PASS" if bool(scorecard.get("pass_profit_factor", False)) else "FAIL")
            s3.metric("DD Check", "PASS" if bool(scorecard.get("pass_max_drawdown", False)) else "FAIL")

            metric_rows: List[Dict[str, Any]] = []
            for metric_name, vals in metrics.items():
                if not isinstance(vals, dict):
                    continue
                metric_rows.append(
                    {
                        "metric": metric_name,
                        "p25": vals.get("p25"),
                        "p50": vals.get("p50"),
                        "p75": vals.get("p75"),
                        "mean": vals.get("mean"),
                    }
                )
            if metric_rows:
                st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)

        if st.session_state.mc_last_stdout:
            with st.expander("Monte Carlo Console Output", expanded=False):
                st.code(st.session_state.mc_last_stdout, language="text")
        if st.session_state.mc_last_stderr:
            with st.expander("Monte Carlo STDERR", expanded=False):
                st.code(st.session_state.mc_last_stderr, language="text")

    # Decision timeline + alert center strip.
    st.divider()
    st.subheader("Decision Timeline")
    if st.session_state.decision_history:
        icons = {"GO_LONG": "🟢", "GO_SHORT": "🔴", "NO_TRADE": "⚪"}
        timeline = "  ".join(
            f"{icons.get(i['decision'],'⚪')} {i['ts']}" for i in st.session_state.decision_history[-20:]
        )
        st.markdown(timeline)
    else:
        st.caption("No decisions yet.")

    st.subheader("Alert Center")
    if st.session_state.recent_alerts:
        st.dataframe(pd.DataFrame(st.session_state.recent_alerts[::-1]), width="stretch", hide_index=True)
    else:
        st.caption("No alerts yet.")


if __name__ == "__main__":
    main()

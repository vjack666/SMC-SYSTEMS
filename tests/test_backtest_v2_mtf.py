"""MTF top-down gates + nearest TP (no full market download)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ict_backtest.v2.context_mtf import (
    build_context_stack,
    dealing_range_pd,
    top_down_allows_trade,
)
from ict_backtest.v2.coverage import build_coverage_report
from ict_backtest.v2.nearest_tp import nearest_swing_tp


def _ohlc(n=100, start=1.0, step=0.001):
    rows = []
    px = start
    for i in range(n):
        o, c = px, px + step
        rows.append(
            {
                "time": pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=i),
                "open": o,
                "high": max(o, c) + 0.0005,
                "low": min(o, c) - 0.0005,
                "close": c,
                "trend": "BULLISH" if step > 0 else "BEARISH",
            }
        )
        px = c
    return pd.DataFrame(rows)


def test_top_down_rejects_long_in_premium():
    stack = {
        "D1": {"available": True, "trend": "BULLISH"},
        "H4": {"available": True, "trend": "BULLISH"},
        "H1": {"available": True, "trend": "BULLISH"},
        "dealing": {"pd_side": "PREMIUM"},
    }
    ok, reason = top_down_allows_trade(stack, 1, require_pd=True)
    assert ok is False
    assert reason == "long_in_premium"


def test_top_down_allows_long_in_discount():
    stack = {
        "D1": {"available": True, "trend": "BULLISH"},
        "H4": {"available": True, "trend": "BULLISH"},
        "H1": {"available": True, "trend": "RANGING"},
        "dealing": {"pd_side": "DISCOUNT"},
    }
    ok, reason = top_down_allows_trade(stack, 1)
    assert ok is True
    assert reason == "ok"


def test_top_down_d1_against():
    stack = {
        "D1": {"available": True, "trend": "BEARISH"},
        "H4": {"available": True, "trend": "BULLISH"},
        "H1": {"available": True, "trend": "BULLISH"},
        "dealing": {"pd_side": "DISCOUNT"},
    }
    ok, reason = top_down_allows_trade(stack, 1)
    assert ok is False
    assert "d1" in reason


def test_nearest_swing_tp_long():
    # Flat market then a clear isolated swing high at i=20
    n = 50
    df = pd.DataFrame(
        {
            "time": [pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=i) for i in range(n)],
            "open": [1.0] * n,
            "high": [1.001] * n,
            "low": [0.999] * n,
            "close": [1.0] * n,
        }
    )
    df.loc[20, "high"] = 1.05
    # neighbors lower so i=20 is a 3-bar pivot high
    for j in (17, 18, 19, 21, 22, 23):
        df.loc[j, "high"] = 1.001
    tp = nearest_swing_tp(df, entry_at=30, direction=1, entry=1.0, lookback=40)
    assert tp is not None
    assert abs(tp - 1.05) < 1e-9


def test_coverage_mtf_higher_than_legacy():
    leg = build_coverage_report("x", "legacy_subset")
    mtf = build_coverage_report("mtf_intraday", "v2_partial")
    assert mtf.coverage_pct > leg.coverage_pct
    assert mtf.per_capability["C02"] == "implemented"
    assert mtf.per_capability["C10"] == "implemented"


def test_dealing_range_pd_runs():
    d1 = _ohlc(30, start=1.0, step=0.01)
    # rename times to daily-ish
    d1["time"] = [pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=i) for i in range(30)]
    d1["trend"] = "BULLISH"
    t = d1.iloc[-1]["time"]
    out = dealing_range_pd(d1, t, lookback=10)
    assert out["pd_side"] in ("DISCOUNT", "PREMIUM", "EQ", "UNKNOWN")

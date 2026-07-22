"""TDD para ict_backtest/setups/smart_money.py — Smart Money Techniques/Concepts.

Objetivo: probar `is_smart_money(df, context) -> dict` con datos sintéticos
puramente OHLC, SIN ATR ni indicadores, SIN tocar canonical.py/engine.py.
Mínimo 8 tests unitarios + 1 call-site real sobre ICTSignal.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.setups.smart_money import is_smart_money, _avg_range


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(n=120, base="2026-01-04 09:00", freq="15min", tz="UTC"):
    start = pd.Timestamp(base, tz=tz)
    return pd.date_range(start, periods=n, freq=freq, tz=tz)


def _flat(n=120, price=1.1000):
    t = _ts(n)
    return pd.DataFrame({
        "time": t,
        "open": np.full(n, price),
        "high": np.full(n, price + 0.0002),
        "low": np.full(n, price - 0.0002),
        "close": np.full(n, price),
    })


def _ramp(n=100, start=1.1000, end=1.1050):
    t = _ts(n)
    p = np.linspace(start, end, n)
    return pd.DataFrame({
        "time": t,
        "open": p - 0.0001,
        "high": p + 0.0002,
        "low": p - 0.0003,
        "close": p + 0.0001,
    })


def _sweep_down_data(n=120, base_price=1.1000):
    t = _ts(n)
    p = np.linspace(base_price - 0.0010, base_price + 0.0020, n)
    df = pd.DataFrame({
        "time": t,
        "open": p,
        "high": p + 0.0003,
        "low": p - 0.0003,
        "close": p + 0.0001,
    })
    df.loc[df.index[-8:], "low"] -= 0.0010
    df.loc[df.index[-8:], "high"] = df.loc[df.index[-8:], "low"] + 0.0004
    df.loc[df.index[-8:], "open"] = df.loc[df.index[-8:], "low"] + 0.0006
    df.loc[df.index[-8:], "close"] = df.loc[df.index[-8:], "open"] + 0.0012
    return df


def _sweep_up_data(n=120, base_price=1.1000):
    t = _ts(n)
    p = np.linspace(base_price + 0.0010, base_price - 0.0020, n)
    df = pd.DataFrame({
        "time": t,
        "open": p,
        "high": p + 0.0003,
        "low": p - 0.0003,
        "close": p - 0.0001,
    })
    df.loc[df.index[-8:], "high"] += 0.0010
    df.loc[df.index[-8:], "low"] = df.loc[df.index[-8:], "high"] - 0.0004
    df.loc[df.index[-8:], "open"] = df.loc[df.index[-8:], "high"] - 0.0006
    df.loc[df.index[-8:], "close"] = df.loc[df.index[-8:], "open"] - 0.0012
    return df


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_returns_dict_shape():
    res = is_smart_money(_flat())
    assert isinstance(res, dict)
    assert {"smart_money_active", "evidence", "zones"}.issubset(res)
    assert isinstance(res["zones"], list)
    assert isinstance(res["evidence"], dict)


def test_missing_columns_returns_error():
    df = _flat().drop(columns=["close"])
    res = is_smart_money(df)
    assert res["smart_money_active"] is False
    assert "error" in res["evidence"]
    assert res["evidence"]["num_zones"] == 0


def test_insufficient_bars_returns_inactive():
    df = _flat(n=6)
    res = is_smart_money(df)
    assert res["smart_money_active"] is False
    assert res["evidence"].get("error") == "insufficient bars"


def test_no_zones_on_trending_data():
    df = _ramp(n=100, start=1.1000, end=1.1050)
    res = is_smart_money(df, context={"zone_lookback": 20, "tol_ratio": 0.02, "sweep_lookback": 20})
    assert res["evidence"]["num_zones"] == 0
    assert res["evidence"]["eqh_detected"] is False
    assert res["evidence"]["eql_detected"] is False


def test_eqh_zones_detected():
    df = _flat(n=120)
    df.loc[10:12, "high"] = 1.1050
    df.loc[60:62, "high"] = 1.1050
    res = is_smart_money(df, context={"zone_lookback": 120, "tol_ratio": 0.04,
                                      "sweep_lookback": 20, "min_touches": 2})
    eqh = [z for z in res["zones"] if z["type"] == "EQH"]
    assert res["evidence"]["eqh_detected"] is True
    assert len(eqh) >= 1
    assert any(z["touch_count"] >= 2 for z in eqh)


def test_eql_zones_detected():
    df = _flat(n=120)
    df.loc[10:12, "low"] = 1.0950
    df.loc[60:62, "low"] = 1.0950
    res = is_smart_money(df, context={"zone_lookback": 120, "tol_ratio": 0.04,
                                      "sweep_lookback": 20, "min_touches": 2})
    eql = [z for z in res["zones"] if z["type"] == "EQL"]
    assert res["evidence"]["eql_detected"] is True
    assert len(eql) >= 1


def test_sweep_down_then_bullish_rebound_detected():
    df = _sweep_down_data()
    res = is_smart_money(df, context={"sweep_lookback": 35, "zone_lookback": 60})
    assert res["evidence"]["sweep_down"] is True
    assert res["evidence"]["displacement_direction"] == 1


def test_sweep_up_then_bearish_rebound_detected():
    df = _sweep_up_data()
    res = is_smart_money(df, context={"sweep_lookback": 35, "zone_lookback": 60})
    assert res["evidence"]["sweep_up"] is True
    assert res["evidence"]["displacement_direction"] == -1


def test_smart_money_active_state_is_bool():
    df = _sweep_down_data()
    res = is_smart_money(df, context={"sweep_lookback": 35, "zone_lookback": 60})
    e = res["evidence"]
    assert isinstance(res["smart_money_active"], bool)
    assert e["displacement_direction"] in (1, -1, 0)
    assert isinstance(e["zone_anchored"], (bool, type(None)))
    assert isinstance(e["num_zones"], int)
    assert e["num_zones"] >= 0


def test_zone_fields_and_dedup():
    df = _flat(n=120)
    df.loc[10:12, "high"] = 1.1050
    df.loc[60:62, "high"] = 1.1050
    res = is_smart_money(df, context={"zone_lookback": 120, "tol_ratio": 0.04,
                                      "sweep_lookback": 20, "min_touches": 2})
    eqh = next((z for z in res["zones"] if z["type"] == "EQH"), None)
    assert eqh is not None
    assert eqh["touch_count"] >= 2
    assert len(eqh["band"]) == 2
    assert eqh["band"][0] <= eqh["level"] <= eqh["band"][1]
    assert eqh["start"] < eqh["end"]
    # two non-overlapping EQH at 0..9 and 10..12 -> 2 zones if no other zone; otherwise max 2 EQH
    assert sum(1 for z in res["zones"] if z["type"] == "EQH") <= 2


# ---------------------------------------------------------------------------
# Call-site real: ICTSignal real del motor + anotación dinámica (sin engine.py)
# ---------------------------------------------------------------------------

def test_call_site_real_signal_with_smt(monkeypatch):
    """Call-site real: is_smart_money sobre DataFrame con market_structure
    aplicada, luego anotación sobre ICTSignal EXACTO de engine.py sin tocar
    engine.py (principio Brecha D / dataclass dynamic attributes)."""
    from ict_backtest.engine import ICTSignal
    from ict_backtest.market_structure import detect_market_structure
    from ict_backtest.setups import smart_money

    base = pd.Timestamp("2026-01-05 09:00", tz="UTC")
    t = pd.date_range(base, periods=80, freq="15min", tz="UTC")
    price = float(1.1000)
    m15 = pd.DataFrame({
        "time": t,
        "open": np.full(80, price),
        "high": np.full(80, price + 0.0003),
        "low": np.full(80, price - 0.0003),
        "close": np.full(80, price + 0.0001),
    })
    m15.loc[10:12, "high"] = 1.1005  # EQH cluster 1
    m15.loc[50:52, "high"] = 1.1005  # EQH cluster 2 (de-dup luego decide)
    m15.loc[60:70, "low"] -= 0.0010  # sweep down + displacement
    m15.loc[60:70, "high"] = m15.loc[60:70, "low"] + 0.0004
    m15.loc[60:70, "open"] = m15.loc[60:70, "low"] + 0.0006
    m15.loc[60:70, "close"] = m15.loc[60:70, "open"] + 0.0012
    m15 = detect_market_structure(m15)

    smt = smart_money.is_smart_money(
        m15,
        context={"ltf": "M15", "sweep_lookback": 40, "zone_lookback": 80,
                 "min_touches": 2, "tol_ratio": 0.04},
    )
    assert isinstance(smt, dict)
    assert "smart_money_active" in smt
    assert "zones" in smt

    sig = ICTSignal(
        symbol="SYN",
        time=str(t[3]),
        direction=1,
        entry=float(m15.iloc[3]["close"]),
        stop_loss=float(m15.iloc[3]["close"] - 0.001),
        take_profit=float(m15.iloc[3]["close"] + 0.003),
    )
    setattr(sig, "smt_confirmed", bool(smt["smart_money_active"]))
    setattr(sig, "smt_sweep_up", smt["evidence"]["sweep_up"])
    setattr(sig, "smt_sweep_down", smt["evidence"]["sweep_down"])
    setattr(sig, "smt_zones", smt["zones"])
    assert hasattr(sig, "smt_confirmed")
    assert hasattr(sig, "smt_zones")
    assert isinstance(sig.smt_zones, list)

"""Tests §5A del SDD — trigger_engine con máquina de estados + gate de sesión.

TDD: dicts sintéticos, sin I/O. Reloj inyectado (now_utc). Cero MT5.
"""
from datetime import datetime, timezone

import pytest

from app_observador.core.pipeline import trigger_engine, run_pipeline
from app_observador.core.timezone import killzone_en


def _dt(h, m=0):
    return datetime(2026, 7, 23, h, m, tzinfo=timezone.utc)


def _m5_long(close=1.1005):
    """M5 LONG completo: sweep_up, BOS activo alcista, FVG, OB bullish."""
    return {
        "sweep_up": True, "sweep_down": False,
        "bos_dir": 1, "bos_status": "active",
        "fvg_state": "bullish",
        "close": close, "atr": 0.0010,
        "ob_dir": "bullish", "ob_top": 1.1010, "ob_bottom": 1.1000,
        "ote_long": 1.1002, "ote_short": 0.0,
    }


def _m5_short(close=1.0995):
    return {
        "sweep_up": False, "sweep_down": True,
        "bos_dir": -1, "bos_status": "active",
        "fvg_state": "bearish",
        "close": close, "atr": 0.0010,
        "ob_dir": "bearish", "ob_top": 1.1000, "ob_bottom": 1.0990,
        "ote_long": 0.0, "ote_short": 1.0998,
    }


# 1
def test_trigger_ready_long():
    out = trigger_engine(m5=_m5_long(close=1.1005), poi=None, now_utc=_dt(13))
    assert out["long"]["machine_state"] == "TRIGGER_READY"
    assert out["long"]["valid"] is True
    assert out["valid"] is True
    assert out["session"]["state"] == "OPEN"
    assert out["session"]["in_killzone"] is True


# 2
def test_waiting_pullback():
    # close muy por encima de hi + buffer -> fuera de zona
    out = trigger_engine(m5=_m5_long(close=1.1050), poi=None, now_utc=_dt(13))
    assert out["long"]["machine_state"] == "WAITING_PULLBACK"
    assert out["long"]["valid"] is False
    assert out["checks"]["pullback"] is False


# 3
def test_off_session():
    out = trigger_engine(m5=_m5_long(close=1.1005), poi=None, now_utc=_dt(5))
    assert out["long"]["machine_state"] == "TRIGGER_READY_OFF_SESSION"
    assert out["long"]["valid"] is False
    assert out["session"]["state"] == "CLOSED"


# 4
@pytest.mark.parametrize("h,m,expected", [
    (6, 59, ""),
    (7, 0, "London Open"),
    (9, 59, "London Open"),
    (12, 30, "New York AM"),
    (15, 0, ""),
    (17, 0, "New York PM"),
    (20, 0, ""),
])
def test_session_boundaries(h, m, expected):
    assert killzone_en(_dt(h, m)) == expected


# 5
def test_no_m5_pending():
    out = trigger_engine(m5=None, poi=None, now_utc=_dt(13))
    assert out["long"]["machine_state"] == "PENDING"
    assert out["short"]["machine_state"] == "PENDING"
    assert "pullback" in out["checks"]
    assert "reaction" in out["checks"]
    assert "session" in out["checks"]
    assert out["checks"]["pullback"] in (False, None)


# 6
def test_no_zone_en_construccion():
    m5 = _m5_long()
    m5["ob_dir"] = "-"
    m5["ob_top"] = 0.0
    m5["ob_bottom"] = 0.0
    poi = {"valid": False}
    out = trigger_engine(m5=m5, poi=poi, now_utc=_dt(13))
    assert out["long"]["machine_state"] == "STRUCTURE_READY"
    assert out["long"]["entry_zone"] is None


# 7
def test_no_clock_unknown():
    out = trigger_engine(m5=_m5_long(close=1.1005), poi=None, now_utc=None)
    assert out["long"]["machine_state"] != "TRIGGER_READY"
    assert out["session"]["state"] == "UNKNOWN"
    assert out["checks"]["session"] is None


# 8
def test_verdictbuilder_ignores_opposite():
    # short READY pero bias derivado LONG -> el VerdictBuilder no lo elige.
    d1 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1,
          "zone_low": 1.09, "zone_high": 1.11}
    h4 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1}
    h1 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1,
          "zone_low": 1.099, "zone_high": 1.101}
    m15 = {"ob_dir": "LONG", "bos_dir": 1, "bos_status": "active",
           "fvg_state": "bullish", "zone_low": 1.099, "zone_high": 1.101,
           "ote_long": (1.10, 1.101)}
    m5 = _m5_short(close=1.0995)
    out = run_pipeline(d1, h4, h1, m15, m5=m5)
    assert out["context_alignment"]["macro"] == "LONG"
    assert out["trigger"]["valid"] is False


# 9
def test_ui_contract():
    d1 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1,
          "zone_low": 1.09, "zone_high": 1.11}
    h4 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1}
    h1 = {"trend": "BULLISH", "bos_status": "active", "bos_dir": 1,
          "zone_low": 1.099, "zone_high": 1.101}
    m15 = {"ob_dir": "LONG", "bos_dir": 1, "bos_status": "active",
           "fvg_state": "bullish", "zone_low": 1.099, "zone_high": 1.101,
           "ote_long": (1.10, 1.101)}
    out = run_pipeline(d1, h4, h1, m15, m5=_m5_long())
    ca = out["context_alignment"]
    assert "trigger" in ca
    assert "stages" in ca
    assert "votes" in out
    assert ca["trigger"] in ("VALID", "PENDING")
    assert "trigger_machine" in ca


# 10
def test_purity():
    m5 = _m5_long(close=1.1005)
    poi = None
    now = _dt(13)
    a = trigger_engine(m5=m5, poi=poi, now_utc=now)
    b = trigger_engine(m5=m5, poi=poi, now_utc=now)
    assert a == b

"""tests/test_engine_plan_ltf.py — M5/M1 como capas de contexto top-down.

Tesis (docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md §5): la lectura humana es
D1 -> H4 -> H1 -> M15 -> M5 -> M1. M5 = ejecucion fina (momentum), M1 =
microestructura. NINGUNO redefine el sesgo mayor: solo CONFIRMAN a favor.

Este test fija:
  (a) M5/M1 aparecen en el stack cuando se piden via tfs=.
  (b) El gate usa M5/M1 para CONFIRMAR, y NUNCA veta contra el sesgo mayor
      (M5/M1 ausentes o en contra no bloquean D1/H4/H1).
  (c) Anti look-ahead: no se leen velas futuras (time > t).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.plan import (
    build_context_stack,
    ltf_confirms,
    ltf_structure_at,
    top_down_allows_trade,
)

STEP = {"D1": 86400, "H4": 14400, "H1": 3600, "M15": 900, "M5": 300, "M1": 60}
END = pd.Timestamp("2024-03-01 12:00:00", tz="UTC")


def _flat(tf: str, trend: str, close: float, hi: float, lo: float, *, end=END, n=30):
    step = STEP[tf]
    times = [end - pd.Timedelta(seconds=step * (n - 1 - i)) for i in range(n)]
    return pd.DataFrame(
        {
            "time": pd.to_datetime(times, utc=True),
            "open": np.full(n, close),
            "high": np.full(n, hi),
            "low": np.full(n, lo),
            "close": np.full(n, close),
            "trend": [trend] * n,
        }
    )


def _ramp(tf: str, trend: str, start: float, slope: float, *, end=END, n=40):
    """Rampa determinista: slope>0 -> momentum alcista, slope<0 -> bajista."""
    step = STEP[tf]
    times = [end - pd.Timedelta(seconds=step * (n - 1 - i)) for i in range(n)]
    closes = np.array([start + slope * i for i in range(n)], dtype=float)
    return pd.DataFrame(
        {
            "time": pd.to_datetime(times, utc=True),
            "open": closes - slope * 0.5,
            "high": closes + abs(slope),
            "low": closes - abs(slope),
            "close": closes,
            "trend": [trend] * n,
        }
    )


def _htf_bull():
    """D1/H4/H1 BULLISH y PD valido para long (EQ)."""
    return {
        "D1": _flat("D1", "BULLISH", 100.0, 110.0, 90.0),
        "H4": _flat("H4", "BULLISH", 95.0, 105.0, 85.0),  # eq=95 -> EQ
        "H1": _flat("H1", "BULLISH", 95.5, 96.0, 95.0),
        "M15": _flat("M15", "BULLISH", 95.5, 96.0, 95.0),
    }


TFS6 = ("D1", "H4", "H1", "M15", "M5", "M1")


# --------------------------------------------------------------------------- #
# (a) M5/M1 en el stack
# --------------------------------------------------------------------------- #
def test_m5_m1_present_in_stack_when_requested():
    ms = _htf_bull()
    ms["M5"] = _ramp("M5", "BULLISH", 95.0, 0.02)
    ms["M1"] = _ramp("M1", "BULLISH", 95.4, 0.005)
    stack = build_context_stack(ms, END, tfs=TFS6)
    for tf in ("M5", "M1"):
        assert tf in stack, stack.keys()
        assert stack[tf]["available"] is True
        assert stack[tf]["momentum"] == 1
        assert stack[tf]["bars"] > 0


def test_stack_unchanged_without_ltf_regression_zero():
    ms = _htf_bull()
    stack = build_context_stack(ms, END)  # tfs default, sin M5/M1
    assert set(stack) >= {"D1", "H4", "H1", "M15", "dealing"}
    assert "M5" not in stack and "M1" not in stack
    ok, reason = top_down_allows_trade(stack, +1)
    assert ok is True and reason == "ok"


def test_ltf_requested_but_absent_from_ms_is_neutral():
    ms = _htf_bull()  # sin M5/M1
    stack = build_context_stack(ms, END, tfs=TFS6)
    assert stack["M5"]["available"] is False
    assert stack["M1"]["available"] is False
    ok, reason = top_down_allows_trade(stack, +1, require_ltf=True)
    assert ok is True, reason  # ausencia NO veta


# --------------------------------------------------------------------------- #
# (b) el gate CONFIRMA con M5/M1, no veta el sesgo mayor
# --------------------------------------------------------------------------- #
def test_gate_confirms_long_when_ltf_with_direction():
    ms = _htf_bull()
    ms["M5"] = _ramp("M5", "BULLISH", 95.0, 0.02)
    ms["M1"] = _ramp("M1", "BULLISH", 95.4, 0.005)
    stack = build_context_stack(ms, END, tfs=TFS6)
    conf = ltf_confirms(stack, +1)
    assert conf["confirmed"] is True
    assert conf["score"] > 0
    ok, reason = top_down_allows_trade(stack, +1, require_ltf=True)
    assert ok is True and reason == "ok"


def test_ltf_against_does_not_redefine_major_bias():
    """M5/M1 en contra NO invierten ni bloquean el sesgo D1/H4/H1 por defecto."""
    ms = _htf_bull()
    ms["M5"] = _ramp("M5", "BEARISH", 96.0, -0.02)
    ms["M1"] = _ramp("M1", "BEARISH", 95.8, -0.005)
    stack = build_context_stack(ms, END, tfs=TFS6)
    # El sesgo mayor sigue intacto: M5/M1 no lo tocan.
    assert stack["D1"]["trend"] == "BULLISH"
    assert stack["H4"]["trend"] == "BULLISH"
    assert stack["H1"]["trend"] == "BULLISH"
    # Gate por defecto (require_ltf=False): pasa igual -> M5/M1 no vetan.
    ok, reason = top_down_allows_trade(stack, +1)
    assert ok is True, reason
    # Con require_ltf=True solo falta CONFIRMACION (razon explicita, no veto
    # de sesgo): nunca se reporta d1/h4/h1_against.
    ok2, reason2 = top_down_allows_trade(stack, +1, require_ltf=True)
    assert ok2 is False
    assert reason2 == "ltf_not_confirming"
    assert "d1_" not in reason2 and "h4_" not in reason2 and "h1_" not in reason2


def test_ltf_cannot_authorize_trade_against_major_bias():
    """M5/M1 alcistas no habilitan un short cuando D1/H4 son BULLISH."""
    ms = _htf_bull()
    ms["M5"] = _ramp("M5", "BULLISH", 95.0, 0.02)
    ms["M1"] = _ramp("M1", "BULLISH", 95.4, 0.005)
    stack = build_context_stack(ms, END, tfs=TFS6)
    ok, reason = top_down_allows_trade(stack, -1, require_ltf=True)
    assert ok is False
    assert reason == "d1_against_short"  # el sesgo mayor manda siempre


# --------------------------------------------------------------------------- #
# (c) anti look-ahead
# --------------------------------------------------------------------------- #
def test_ltf_structure_is_closed_only():
    """Cambiar SOLO las velas futuras no altera el snapshot al tiempo t."""
    ms = _htf_bull()
    m5 = _ramp("M5", "BULLISH", 95.0, 0.02, n=60)
    t = m5["time"].iloc[29]  # corte a mitad

    snap_a = ltf_structure_at({"M5": m5}, "M5", t)

    # Reventamos el futuro (index 30+) en direccion opuesta y con precios locos.
    m5_mut = m5.copy()
    fut = m5_mut.index >= 30
    m5_mut.loc[fut, ["open", "high", "low", "close"]] = -999.0
    m5_mut.loc[fut, "trend"] = "BEARISH"
    snap_b = ltf_structure_at({"M5": m5_mut}, "M5", t)

    assert snap_a == snap_b, (snap_a, snap_b)
    assert snap_a["time"] == str(t)
    assert snap_a["bars"] == 30  # exactamente las velas cerradas hasta t


def test_build_context_stack_ltf_no_future_leak():
    ms = _htf_bull()
    m5 = _ramp("M5", "BULLISH", 95.0, 0.02, n=60)
    ms["M5"] = m5
    t = m5["time"].iloc[29]
    stack_a = build_context_stack(ms, t, tfs=TFS6)["M5"]

    ms2 = dict(ms)
    mut = m5.copy()
    mut.loc[mut.index >= 30, ["open", "high", "low", "close"]] = -999.0
    ms2["M5"] = mut
    stack_b = build_context_stack(ms2, t, tfs=TFS6)["M5"]

    assert stack_a["trend"] == stack_b["trend"]
    assert stack_a["momentum"] == stack_b["momentum"]
    assert stack_a["bars"] == stack_b["bars"] == 30

"""tests/test_engine_plan_pd.py — Verifica que el gate top-down lee pd_side.

Bug hallado: top_down_allows_trade leia stack['dealing']['pd_side'], pero
build_context_stack poblaba pd_side en stack['D1']/stack['H4'], no en
'dealing'. Resultado: pd_unknown sistematico -> 0 trades en el backtest HTF.
Este test fija la regresion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.plan import build_context_stack, top_down_allows_trade


def _frame(tf: str, trend: str, close: float, hi: float, lo: float, *, end=None, n=30):
    # Genera n barras TERMINANDO en `end` (por defecto el cierre del TF
    # anterior al de la senal) para que el ventaneo premium/discount tenga
    # historia real (>=3 barras) al tiempo t de la senal M15.
    step = {"D1": 86400, "H4": 14400, "H1": 3600, "M15": 900}[tf]
    if end is None:
        end = pd.Timestamp("2024-01-01 00:00:00", tz="UTC") + pd.Timedelta(
            seconds=step * (n - 1)
        )
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


def _bull_stack():
    # D1/H4/H1 BULLISH, termina en el mismo end; M15 senal al cierre.
    end = pd.Timestamp("2024-03-01 12:00:00", tz="UTC")
    ms = {
        "D1": _frame("D1", "BULLISH", 100.0, 110.0, 90.0, end=end),
        "H4": _frame("H4", "BULLISH", 95.0, 105.0, 85.0, end=end),  # eq=95 -> close==eq => EQ
        "H1": _frame("H1", "BULLISH", 95.5, 96.0, 95.0, end=end),
        "M15": _frame("M15", "BULLISH", 95.5, 96.0, 95.0, end=end),
    }
    t = ms["M15"]["time"].iloc[-1]
    return ms, t


def test_pd_side_populated_in_dealing_key():
    ms, t = _bull_stack()
    stack = build_context_stack(ms, t)
    # La clave 'dealing' debe existir y no ser UNKNOWN cuando H4 lo resuelve.
    assert "dealing" in stack
    assert stack["dealing"]["pd_side"] in ("DISCOUNT", "PREMIUM", "EQ")
    # Tambien debe estar en D1/H4 (estructura original).
    assert stack["H4"]["pd_side"] in ("DISCOUNT", "PREMIUM", "EQ")


def test_gate_allows_long_when_pd_resolved():
    ms, t = _bull_stack()
    stack = build_context_stack(ms, t)
    ok, reason = top_down_allows_trade(stack, +1, require_pd=True)
    # Sin el bug, ya no debe dar pd_unknown. En EQ (close==eq) sigue siendo
    # valido para long (no esta en PREMIUM).
    assert reason != "pd_unknown", stack["dealing"]
    assert ok is True, (ok, reason)


def test_gate_blocks_long_in_premium():
    ms, t = _bull_stack()
    end = ms["H4"]["time"].iloc[-1]  # mismo end que el resto
    # Fuerza premium en H4 (close > eq) para probar el bloqueo direccional.
    ms["H4"] = _frame("H4", "BULLISH", 102.0, 105.0, 95.0, end=end)  # eq=100 -> PREMIUM
    st = build_context_stack(ms, t)
    ok, reason = top_down_allows_trade(st, +1, require_pd=True)
    assert ok is False
    assert reason == "long_in_premium"

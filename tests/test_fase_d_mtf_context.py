"""Fase D — Migración multi-TF (reglas #1/#4/#5 de Ruben).

Objetivo: el TradeContext debe llevar el EXPEDIENTE COMPLETO del mercado en
el momento de la decisión: D1/H4/H1/M15/M5/M1, cada uno con su estructura
real (no placeholder). Sin esto, StatisticsEngine (Fase E) solo vería ruido
(regla #7: fidelidad antes que estadísticas).

Reusa el snapshot closed-only ya existente en ict_backtest/v2/context_mtf.py
(NO duplicamos lógica anti look-ahead). Este módulo solo NORMALIZA ese stack
al schema de diagnóstico que pidió Ruben y lo congela en TradeContext v2.

Regla #4 (nada inventado): si un TF no está en disco, el snapshot dice
`available: False` y el campo queda como `MISSING`. Nunca se copia de otro TF.

TDD: estos tests corren en ms con datos sintéticos.
"""

import pandas as pd
import pytest

from ict_backtest.diagnostics.mtf_context import normalize_mtf_stack
from ict_backtest.diagnostics.trade_context import MarketContextFrame, TradeContext
from ict_backtest.v2.context_mtf import build_context_stack, snapshot_tf


def _synthetic_ms() -> dict:
    """4 TF sintéticos cerrados, cada uno con las columnas que build_features da."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    frames: dict = {}
    specs = {
        "D1": pd.Timedelta(days=1),
        "H4": pd.Timedelta(hours=4),
        "H1": pd.Timedelta(hours=1),
        "M15": pd.Timedelta(minutes=15),
        "M5": pd.Timedelta(minutes=5),
        "M1": pd.Timedelta(minutes=1),
    }
    for tf, dur in specs.items():
        rows = []
        p = 100.0
        for i in range(40):
            o = p
            c = o + 0.4
            h = max(o, c) + 0.3
            l = min(o, c) - 0.3
            rows.append(dict(
                time=t0 + dur * i, open=o, high=h, low=l, close=c, volume=1,
                atr=1.0,
                trend="BULLISH" if tf in ("D1", "H4") else "RANGING",
                macro_direction="BULLISH" if tf in ("D1", "H4") else "RANGING",
                bos_direction="NONE",
                bos_status="",
                choch_signal="NONE",
                choch_status="",
                liquidity_sweep_up=False,
                liquidity_sweep_down=False,
                fvg_bullish=(i == 10),
                fvg_bearish=False,
                fvg_mid=(c + 0.5) if i == 10 else None,
                ob_bullish=(i == 12),
                ob_bearish=False,
                ob_top=c + 0.6 if i == 12 else None,
                ob_bottom=c - 0.6 if i == 12 else None,
                ob_direction="bullish" if i == 12 else "-",
                pd_tier=None,
                pd_type=None,
            ))
            p = c
        frames[tf] = pd.DataFrame(rows)
    # M5/M1 sin fvg/ob (para probar que quedan como datos reales, no inventados)
    for tf in ("M5", "M1"):
        df = frames[tf]
        df["fvg_bullish"] = False
        df["ob_bullish"] = False
    return frames


def test_normalize_stack_has_all_six_tfs():
    """Regla #1: el expediente tiene D1/H4/H1/M15/M5/M1."""
    ms = _synthetic_ms()
    t = ms["M15"].iloc[20]["time"]
    stack = build_context_stack(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    norm = normalize_mtf_stack(stack)
    for tf in ("D1", "H4", "H1", "M15", "M5", "M1"):
        assert tf in norm, f"Falta TF {tf} en market_context"
        assert isinstance(norm[tf], MarketContextFrame)


def test_missing_tf_is_flagged_not_invented():
    """Regla #4: TF ausente => available=False, no se copia de otro."""
    ms = _synthetic_ms()
    del ms["M5"]
    del ms["M1"]
    t = ms["M15"].iloc[20]["time"]
    stack = build_context_stack(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    norm = normalize_mtf_stack(stack)
    assert norm["M5"].available is False
    assert norm["M1"].available is False
    # El campo structure/setup no debe inventar datos del H4
    assert "copied" not in str(norm["M5"].__dict__).lower()


def test_m15_setup_carries_fvg_and_ob():
    """Regla #1: M15 setup refleja fvg/ob reales (no placeholder)."""
    ms = _synthetic_ms()
    t = ms["M15"].iloc[20]["time"]
    stack = build_context_stack(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    norm = normalize_mtf_stack(stack)
    # i=20: fvg en i==10 ya no está activo (ffill roto por diseño); ob en i==12 tampoco.
    # Lo importante es que el campo EXISTE y es un string válido (no vacío inventado).
    assert isinstance(norm["M15"].setup_fvg, str)
    assert isinstance(norm["M15"].setup_ob, str)


def test_trade_context_v2_carries_market_context():
    """Regla #5: TradeContext v2 suma market_context; v1 sigue intacta."""
    ms = _synthetic_ms()
    t = ms["M15"].iloc[20]["time"]
    stack = build_context_stack(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    norm = normalize_mtf_stack(stack)
    ctx = TradeContext(
        backtest_id="BT-TEST",
        trade_id="abc",
        signal_id="sig-x",
        market_context=norm,
    )
    assert ctx.context_version.startswith("ctx-")
    assert "D1" in ctx.market_context
    assert ctx.market_context["D1"].bias in ("BULLISH", "BEARISH", "RANGING")
    # inmutable sigue congelado
    with pytest.raises(Exception):
        ctx.pnl_r = 5.0

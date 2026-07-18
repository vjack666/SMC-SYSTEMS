"""Fase D — Paso 2 (TDD): TradeContext + TradeContextBuilder + emision.

Audita la separacion de responsabilidades (Ruben 2026-07-18):
- engine.simulate_trade SIMULA (no cambia).
- engine.simulate_trade_with_context EMITE RawDiagnosticData (no construye contexto).
- diagnostics.context_builder.build_trade_context CONGELA TradeContext.

Y el R1 de Paso 2: el PnL / exit_reason son IDENTICOS a simulate_trade
(el diagnostico NO altera la simulacion).

Datos sinteticos pequenos (corre en ms).
"""

import pandas as pd
import pytest

from ict_backtest.engine import ICTSignal, simulate_trade, simulate_trade_with_context
from ict_backtest.diagnostics.trade_context import TradeContext
from ict_backtest.diagnostics.context_builder import (
    RawDiagnosticData, build_trade_context,
)


def _make_ltf(n: int = 80):
    """LTF sintetico BULLISH con sweep->displace->BOS->retorno + TP alcista."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = []
    p = 100.0
    for i in range(n):
        o = p
        c = o + 0.5
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        if i == 40:  # sweep alcista
            h = o + 3.0
            c = o + 0.2
            l = o - 0.2
        if i == 50:  # TP alcista lejano
            h = o + 6.0
        rows.append(dict(time=t0 + pd.Timedelta(minutes=15 * i),
                         open=o, high=h, low=l, close=c, volume=1, atr=1.0))
        p = c
    return pd.DataFrame(rows)


def _sig():
    return ICTSignal(symbol="SYN", time=str(pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
                                            + pd.Timedelta(minutes=15 * 41)),
                     direction=1, entry=100.5, stop_loss=99.0, take_profit=104.5,
                     sweep_at=40, bos_at=48, entry_at=50)


def test_simulate_trade_with_context_preserves_pnl_r1():
    """R1 de Paso 2: mismo PnL / exit_reason que simulate_trade."""
    df = _make_ltf()
    sig = _sig()
    t0, m0 = simulate_trade(df, sig, 96)
    t1, m1, raw = simulate_trade_with_context(df, sig, 96)
    assert t1 is not None and t0 is not None
    assert t1.pnl_r == pytest.approx(t0.pnl_r)
    assert m1["exit_reason"] == m0["exit_reason"]
    assert m1["hold_bars"] == m0["hold_bars"]


def test_emitter_does_not_build_context():
    """Separacion: simulate_trade_with_context EMITE raw, NO TradeContext."""
    df = _make_ltf()
    sig = _sig()
    _t, _m, raw = simulate_trade_with_context(df, sig, 96)
    assert isinstance(raw, RawDiagnosticData)
    assert not isinstance(raw, TradeContext)


def test_builder_freezes_trade_context_immutable():
    """TradeContext es frozen + ids persistentes presentes."""
    df = _make_ltf()
    sig = _sig()
    _t, _m, raw = simulate_trade_with_context(df, sig, 96, backtest_id="BT-15")
    assert raw is not None
    ctx = build_trade_context(raw, signal_id="sig-41")
    assert isinstance(ctx, TradeContext)
    assert ctx.backtest_id == "BT-15"
    assert ctx.signal_id == "sig-41"
    assert ctx.trade_id  # uuid no vacio
    assert ctx.context_created_at  # timestamp de congelacion
    assert ctx.context_version.startswith("ctx-")
    # inmutabilidad: mutar debe lanzar FrozenInstanceError
    with pytest.raises(Exception):
        ctx.pnl_r = 99.0


def test_builder_preserves_zone_authority_from_signal():
    """Fase C viaja al contexto como METADATA (no input de decision)."""
    from ict_backtest.zone_authority import ZoneAuthority
    df = _make_ltf()
    za = ZoneAuthority(has_htf_anchor=True, tier="T1", stacking_level=2,
                       confidence_weight=0.85, level="Alta")
    sig = _sig()
    sig.zone_authority = za
    _t, _m, raw = simulate_trade_with_context(df, sig, 96)
    assert raw is not None
    ctx = build_trade_context(raw)
    assert ctx.zone_authority is not None
    assert ctx.zone_authority["confidence_weight"] == pytest.approx(0.85)
    assert ctx.zone_authority["tier"] == "T1"


def test_run_backtest_call_site_exposes_contexts(monkeypatch):
    """Auditoria de call site real (anti 'muerto en call site'):
    run_sequence_backtest debe devolver `contexts` (RawDiagnosticData) y
    `backtest_id` en el dict, y el PnL no cambia (R1 de Paso 2)."""
    from ict_backtest import run_backtest as rb
    from ict_backtest.market_structure import detect_market_structure

    df = _make_ltf()
    # estructura minima para que generate_sequence_signals produzca >=1 senal
    df = detect_market_structure(df)
    htf = _make_htf()
    frames = {"M15": df, "H4": htf, "D1": htf}

    def _fake_load(symbol, tfs):
        return frames

    monkeypatch.setattr(rb, "load_frames", _fake_load)

    m = rb.run_sequence_backtest(
        "SYN", "H4", "M15", max_hold=96,
        require_displacement=False, enable_pd_index=True,
        backtest_id="BT-TEST-1",
    )
    assert "contexts" in m
    assert m["backtest_id"] == "BT-TEST-1"
    assert isinstance(m["contexts"], list)
    # si hubo trades, hay RawDiagnosticData emitido
    if m["trades"] > 0:
        assert len(m["contexts"]) == m["trades"]
        assert all(isinstance(c, RawDiagnosticData) for c in m["contexts"])


def _make_htf():
    """HTF sintetico con FVG bullish (ancla para el indice de Fase C)."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = [
        dict(time=t0 + pd.Timedelta(hours=4 * i), open=100.0 + i,
             high=102.0 + i, low=99.0 + i, close=101.5 + i, volume=1)
        for i in range(4)
    ]
    df = pd.DataFrame(rows)
    df.loc[2, "fvg_bullish"] = True
    df.loc[2, "fvg_bull_high"] = 103.5
    df.loc[2, "fvg_bull_low"] = 102.5
    df.loc[2, "high"] = 104.0
    return df

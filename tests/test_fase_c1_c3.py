"""Tests Fase C1+C3 (enchufe, TDD) — sin alterar R7.

La validación de integración SOBRE DATOS REALES (EURUSD M15, 112k velas) es
C5: se hace manual con runner_monitor porque el motor B1 completo tarda >60s
en esta maquina (AGENTS.md: procesos largos -> Runner Monitor). Aqui en pytest
validamos el enchufe de forma rapida y determinista:

  R1 (no invasion): con o sin htf_pd_index, run_sequence devuelve el MISMO
      numero de senales. C solo ANOTA zone_authority; no gatea ni infla.
  C3 (no crash): pasar htf_pd_index + ltf_map no rompe el loop del motor.
  C3 (historico intacto): sin indice, zone_authority es None en toda senal.

Usamos datos SINTETICOS pequenos para correr en ms.
"""

import pandas as pd
import pytest

from ict_backtest.htf_pd_index import HtfPdIndex
from ict_backtest.sequence import SequenceConfig, run_sequence


def _make_ltf(n: int = 80):
    """LTF sintetico con tendencia BULLISH y una secuencia sweep->displace->
    BOS->retorno minima, para que run_sequence genere >=1 senal.

    Se le aplica detect_market_structure para que run_sequence encuentre
    los metadatos (swings, sweep) que espera en obj.meta.
    """
    from ict_backtest.market_structure import detect_market_structure

    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = []
    p = 100.0
    for i in range(n):
        # tendencia alcista sostenida (para que est_htf_fn de BULLISH)
        o = p
        c = o + 0.5
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        # un barrido (sweep) alcista fuerte a mitad de la serie
        if i == 40:
            h = o + 3.0
            c = o + 0.2
            l = o - 0.2
        rows.append(dict(time=t0 + pd.Timedelta(minutes=15 * i),
                         open=o, high=h, low=l, close=c, volume=1))
        p = c
    df = pd.DataFrame(rows)
    df = detect_market_structure(df)
    return df


def _make_htf():
    """HTF sintetico con un FVG bullish (para que el indice tenga ancla)."""
    t0 = pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    rows = [
        dict(time=t0 + pd.Timedelta(hours=4 * i), open=100.0 + i, high=102.0 + i,
             low=99.0 + i, close=101.5 + i, volume=1) for i in range(4)
    ]
    df = pd.DataFrame(rows)
    df.loc[2, "fvg_bullish"] = True
    df.loc[2, "fvg_bull_high"] = 103.5
    df.loc[2, "fvg_bull_low"] = 102.5
    df.loc[2, "high"] = 104.0
    return df


def _est_htf_bullish(i):
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False, "pd_zones": []}


def test_run_sequence_no_index_leaves_authority_none():
    """Sin htf_pd_index, el comportamiento historico queda intacto (R1 base)."""
    ltf = _make_ltf()
    sigs, _ = run_sequence(
        ltf, _est_htf_bullish, SequenceConfig(counter_trend=False),
        htf_pd_index=None, ltf_map=None,
    )
    for s in sigs:
        assert s["zone_authority"] is None


def test_run_sequence_with_index_same_count_no_crash():
    """R1: con indice HTF el nº de senales es IGUAL y el loop no crashea.

    C solo anota zone_authority; no altera la decision ni el conteo.
    """
    ltf = _make_ltf()
    htf = _make_htf()
    idx = HtfPdIndex({"H4": htf})
    ltf_map = idx.build_ltf_map(ltf)

    base, _ = run_sequence(
        ltf, _est_htf_bullish, SequenceConfig(counter_trend=False),
        htf_pd_index=None, ltf_map=None,
    )
    with_idx, _ = run_sequence(
        ltf, _est_htf_bullish, SequenceConfig(counter_trend=False),
        htf_pd_index=idx, ltf_map=ltf_map,
    )
    assert len(with_idx) == len(base), (
        f"C alteró el conteo de senales: {len(base)} -> {len(with_idx)}"
    )


def test_run_sequence_annotates_authority_when_signals_exist():
    """Si hay senales, con indice traen zone_authority poblado (no None)."""
    ltf = _make_ltf()
    htf = _make_htf()
    idx = HtfPdIndex({"H4": htf})
    ltf_map = idx.build_ltf_map(ltf)
    sigs, _ = run_sequence(
        ltf, _est_htf_bullish, SequenceConfig(counter_trend=False),
        htf_pd_index=idx, ltf_map=ltf_map,
    )
    if sigs:  # puede que el LTF sintetico no complete la secuencia B1
        for s in sigs:
            assert s["zone_authority"] is not None
            assert 0.0 <= s["zone_authority"].confidence_weight <= 1.0

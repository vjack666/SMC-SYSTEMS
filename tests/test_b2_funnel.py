"""B2 (Ley 11) — Embudo de fases sweep -> displace -> BOS -> entry.

Verifica que ``phase_seen`` (el embudo de fases del motor sequence) se propaga
correctamente a traves de:

  run_sequence (2-tuple)  ->  evaluate_signals(return_phase_seen=True)
  ->  generate_sequence_signals(return_phase_seen=True)  ->  run_sequence_backtest
  ->  m["funnel"]  /  run_summary.json / orchestrator payload

Contrato del embudo (Ley 11 monotonicidad):
  SWEEP >= DISPLACE >= BOS >= ENTRY
y debe tener exactamente las 4 claves {"SWEEP","DISPLACE","BOS","ENTRY"}.

Sin datos reales: se construye un ltf_df minimo con detect_market_structure y se
corre run_sequence directamente (motor canonico) para obtener phase_seen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.sequence import SequenceConfig, run_sequence
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.canonical import evaluate_signals
from ict_backtest.run_backtest import generate_sequence_signals


_PHASES = ("SWEEP", "DISPLACE", "BOS", "ENTRY")


def _ohlc(times, base, sweep_low=None, sweep_high=None):
    n = len(times)
    close = np.full(n, float(base))
    df = pd.DataFrame({
        "time": times,
        "open": close,
        "high": close + 0.0003,
        "low": close - 0.0003,
        "close": close,
        "volume": 100.0,
    })
    df["sweep_low"] = np.nan
    df["sweep_high"] = np.nan
    df["bsl_price"] = np.nan
    df["ssl_price"] = np.nan
    if sweep_low is not None:
        df["sweep_low"] = sweep_low
        df["ssl_price"] = sweep_low - 0.0001
    if sweep_high is not None:
        df["sweep_high"] = sweep_high
        df["bsl_price"] = sweep_high + 0.0001
    return df


def _make_ltf_df(n: int = 80):
    """ltf_df minimo (M15) con un sweep en el indice 0 y lateralidad plana.

    avg_candle_range necesita >=25 velas para no dar NaN; 80 es sobrado.
    """
    base = pd.Timestamp("2026-01-05 09:00", tz="UTC")
    times = pd.date_range(base, periods=n, freq="15min", tz="UTC")
    df = _ohlc(times, 1.1000, sweep_low=1.0990)
    ms = detect_market_structure(df)
    return ms


def _no_htf_fn(i: int) -> dict:
    """est_htf_fn legacy: dict plano vacio (sin capa HTF para datos sinteticos)."""
    return {
        "htf_bias": None, "htf_aligned": False, "htf_reason": "",
        "poi_present": False, "htf_pois": [], "swing_high": None,
        "swing_low": None, "recent_fvg": None, "recent_ob": None,
    }


# --- Tests de unidad del embudo (run_sequence directo) -------------------
def test_run_sequence_returns_2tuple_with_funnel():
    ltf_df = _make_ltf_df()
    cfg = SequenceConfig(counter_trend=False, require_displacement=True)
    out = run_sequence(ltf_df, _no_htf_fn, cfg, ltf_tf="M15")
    assert isinstance(out, tuple) and len(out) == 2, (
        f"run_sequence debe devolver (signals, phase_seen): {out!r}"
    )
    signals, phase_seen = out
    assert isinstance(phase_seen, dict)


def test_funnel_has_four_keys_and_is_monotonic():
    ltf_df = _make_ltf_df()
    cfg = SequenceConfig(counter_trend=False, require_displacement=True)
    _, phase_seen = run_sequence(ltf_df, _no_htf_fn, cfg, ltf_tf="M15")

    # Exactamente las 4 claves.
    assert set(phase_seen.keys()) == set(_PHASES), (
        f"phase_seen debe tener claves {_PHASES}: {list(phase_seen)}"
    )
    # Monotonicidad (Ley 11): el embudo solo pierde o mantiene senales.
    assert phase_seen["SWEEP"] >= phase_seen["DISPLACE"], (
        f"SWEEP>=DISPLACE roto: {phase_seen}"
    )
    assert phase_seen["DISPLACE"] >= phase_seen["BOS"], (
        f"DISPLACE>=BOS roto: {phase_seen}"
    )
    assert phase_seen["BOS"] >= phase_seen["ENTRY"], (
        f"BOS>=ENTRY roto: {phase_seen}"
    )


# --- Tests de propagacion (regresion cero + aditivo) --------------------
def test_evaluate_signals_default_returns_list():
    """REGRESION CERO: sin return_phase_seen devuelve SOLO la lista."""
    ltf_df = _make_ltf_df()
    cfg = SequenceConfig(counter_trend=False, require_displacement=False)
    out = evaluate_signals(
        "SYN", "D1", "M15", frames={"D1": ltf_df, "M15": ltf_df},
        enable_pd_index=False,
    )
    assert isinstance(out, list), (
        f"evaluate_signals() por defecto debe ser lista, no {type(out)}"
    )


def test_evaluate_signals_return_phase_seen_includes_funnel():
    ltf_df = _make_ltf_df()
    out = evaluate_signals(
        "SYN", "D1", "M15", frames={"D1": ltf_df, "M15": ltf_df},
        enable_pd_index=False, return_phase_seen=True,
    )
    assert isinstance(out, tuple) and len(out) == 2, (
        f"evaluate_signals(return_phase_seen=True) debe ser (signals, funnel): {out!r}"
    )
    signals, funnel = out
    assert set(funnel.keys()) == set(_PHASES)
    assert funnel["SWEEP"] >= funnel["DISPLACE"] >= funnel["BOS"] >= funnel["ENTRY"]


def test_generate_sequence_signals_default_returns_list():
    """REGRESION CERO: generate_sequence_signals por defecto es lista."""
    ltf_df = _make_ltf_df()
    out = generate_sequence_signals(
        "SYN", "D1", "M15", require_displacement=False,
        frames={"D1": ltf_df, "M15": ltf_df}, enable_pd_index=False,
    )
    assert isinstance(out, list), (
        f"generate_sequence_signals() por defecto debe ser lista, no {type(out)}"
    )


def test_generate_sequence_signals_return_phase_seen_includes_funnel():
    ltf_df = _make_ltf_df()
    out = generate_sequence_signals(
        "SYN", "D1", "M15", require_displacement=False,
        frames={"D1": ltf_df, "M15": ltf_df}, enable_pd_index=False,
        return_phase_seen=True,
    )
    assert isinstance(out, tuple) and len(out) == 2, (
        f"generate_sequence_signals(return_phase_seen=True) debe ser (signals, funnel): {out!r}"
    )
    signals, funnel = out
    assert set(funnel.keys()) == set(_PHASES)
    assert funnel["SWEEP"] >= funnel["DISPLACE"] >= funnel["BOS"] >= funnel["ENTRY"]

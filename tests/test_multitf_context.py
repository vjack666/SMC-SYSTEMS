"""Fase 1 — Lectura multitemporal: MultiTFContext (Opción A, sin cambio de estrategia).

RED: estos tests fallan porque ict_backtest/multitf_context.py no existe.
Objetivo único de la fase: infraestructura de lectura D1->H4->H1->M15->M5->M1
consistente y libre de look-ahead, SIN alterar la lógica de decisión.

El motor (run_sequence) debe seguir usando exactamente el mismo HTF que hoy
(Opción A): extract_htf_layer(context, htf) entrega el dict plano con las
mismas claves que hoy consume run_sequence (trend / sweep_up / sweep_down /
pd_zones). Los demás TF viajan disponibles en context pero run_sequence no
los mira todavía.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.multitf_context import (
    MultiTFContext,
    build_multitf_context,
    extract_htf_layer,
)


# ---- fixtures sintéticos (sin datos reales) -------------------------------
def _make_ms(n_per_tf: int = 8) -> dict:
    """ms[tf] = DataFrame con OHLC + columnas de market_structure.

    Pasa por detect_market_structure para que run_sequence tenga todas
    las columnas que lee (bos_dir/bos_status/choch/etc) sin NaN.
    NO usa parquet real.
    """
    from ict_backtest.market_structure import detect_market_structure

    tfs = ("D1", "H4", "H1", "M15", "M5", "M1")
    base = pd.Timestamp("2026-01-01 00:00", tz="UTC")
    ms = {}
    for tf in tfs:
        if tf == "D1":
            freq = "1D"
        elif tf == "H4":
            freq = "4h"
        elif tf == "H1":
            freq = "1h"
        elif tf == "M15":
            freq = "15min"
        elif tf == "M5":
            freq = "5min"
        else:
            freq = "1min"
        times = pd.date_range(base, periods=n_per_tf, freq=freq, tz="UTC")
        # OHLC con leve variación para que haya swings (sin NaN en detect).
        close = 1.0 + 0.001 * pd.Series(range(n_per_tf), dtype=float)
        df = pd.DataFrame(
            {
                "time": times,
                "open": close,
                "high": close + 0.002,
                "low": close - 0.002,
                "close": close,
                "volume": 100.0,
            }
        )
        ms[tf] = detect_market_structure(df)
    return ms


def test_build_multitf_context_has_all_six_tfs():
    """Evidencia 1/7: los 6 TF llegan al contexto."""
    ms = _make_ms()
    t = ms["M15"]["time"].iloc[3]
    ctx = build_multitf_context(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    assert isinstance(ctx, MultiTFContext)
    # B6 (Ley 3): los 6 TF deben llegar; se aceptan claves adicionales
    # (p.ej. "dealing" inyectada por build_context_stack del motor).
    assert set(ctx.keys()) >= {"D1", "H4", "H1", "M15", "M5", "M1"}
    assert "dealing" in ctx  # publicada por build_context_stack (engine/plan.py)
    for tf in ("D1", "H4", "H1", "M15", "M5", "M1"):
        assert ctx[tf]["available"] is True


def test_build_multitf_context_is_closed_only_no_lookahead():
    """Evidencia 2/7: no hay look-ahead. Una vela 'futura' en M5 no aparece."""
    ms = _make_ms()
    # Inyectamos una vela M5 con time MUY posterior y trend distinto.
    future_time = ms["M15"]["time"].iloc[-1] + pd.Timedelta(minutes=5000)
    from ict_backtest.market_structure import detect_market_structure

    extra_raw = pd.DataFrame(
        {
            "time": [future_time],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.0],
            "volume": [100.0],
        }
    )
    ms_fut = dict(ms)
    ms_fut["M5"] = detect_market_structure(
        pd.concat([ms["M5"], extra_raw], ignore_index=True)
    )

    # t = un tiempo previo a la vela futura (usamos el M15[3], que está antes)
    t = ms["M15"]["time"].iloc[3]
    ctx = build_multitf_context(ms_fut, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    # El snapshot de M5 en t debe traer la última barra CERRADA <= t,
    # que es ANTERIOR a la vela futura (excluida por closed lookup).
    assert pd.to_datetime(ctx["M5"]["time"], utc=True) < pd.to_datetime(future_time, utc=True)
    assert ctx["M5"]["available"] is True


def test_extract_htf_layer_matches_current_consumption_contract():
    """Evidencia 4/7 (previa): extract_htf_layer entrega el dict plano que hoy
    consume run_sequence, con las mismas claves que est_htf_fn actual."""
    ms = _make_ms()
    t = ms["M15"]["time"].iloc[3]
    ctx = build_multitf_context(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    layer = extract_htf_layer(ctx, "D1")
    # Claves que run_sequence lee hoy de est_htf (sequence.py:147-204, 357):
    assert "trend" in layer
    assert "sweep_up" in layer
    assert "sweep_down" in layer
    assert "pd_zones" in layer
    # El valor trend del layer D1 debe coincidir con el snapshot D1.
    assert layer["trend"] == ctx["D1"]["trend"]


def test_run_sequence_receives_multitf_context_identical_behavior():
    """Evidencia 3/7 + 4/7: run_sequence recibe MultiTFContext y se comporta
    IGUAL que con el est_htf_fn de 1 nivel actual (Opción A).

    Construimos el est_htf_fn multinivel (devuelve context) y lo adaptamos
    con extract_htf_layer para que run_sequence use el MISMO HTF de hoy.
    El nº de señales debe coincidir con el baseline de 1 nivel.
    """
    from ict_backtest.sequence import run_sequence, SequenceConfig

    ms = _make_ms()
    ltf_df = ms["M15"]
    htf = "D1"  # HTF que usa el motor 'actual' en este arreglo

    def est_htf_fn_multilevel(i):
        t = ltf_df.iloc[i]["time"]
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))

    # Adaptador Opción A: run_sequence sigue usando extract_htf_layer(context, htf)
    def est_htf_fn_adapted(i):
        return extract_htf_layer(est_htf_fn_multilevel(i), htf)

    # Baseline: est_htf_fn de 1 nivel idéntico al comportamiento histórico.
    def est_htf_fn_baseline(i):
        t = ltf_df.iloc[i]["time"]
        d1row = ms["D1"].iloc[
            (pd.to_datetime(ms["D1"]["time"], utc=True) <= pd.to_datetime(t, utc=True)).values.argmax()
        ] if len(ms["D1"]) else None
        return {
            "trend": "BULLISH" if d1row is not None else "RANGING",
            "sweep_up": False,
            "sweep_down": True,
            "pd_zones": [],
        }

    sigs_multi, _ = run_sequence(ltf_df, est_htf_fn_adapted, SequenceConfig(), ltf_tf="M15")
    sigs_base, _ = run_sequence(ltf_df, est_htf_fn_baseline, SequenceConfig(), ltf_tf="M15")
    # Opción A: mismo HTF usado => mismo nº de señales, mismas entradas.
    assert len(sigs_multi) == len(sigs_base)
    assert [s["entry_at"] for s in sigs_multi] == [s["entry_at"] for s in sigs_base]

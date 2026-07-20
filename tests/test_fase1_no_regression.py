"""Fase 1 — No-regresión y call site real (Opción A, sin cambio de estrategia).

Evidencia 3/7 y 4/7: evaluate_signals debe pasarle a run_sequence un
est_htf_ctx_fn que produce MultiTFContext, y run_sequence debe reducirlo
con extract_htf_layer(context, htf) al MISMO dict que el est_htf_fn de 1
nivel histórico. El comportamiento del motor es 100% idéntico al baseline.

Sin datos reales: se inyectan frames sintéticos de 6 TF vía patch de
load_frames (no se toca parquet).
"""
from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.market_structure import detect_market_structure
from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.multitf_context import build_multitf_context, extract_htf_layer


_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")


def _make_frames(n: int = 40) -> dict:
    base = pd.Timestamp("2026-01-01 00:00", tz="UTC")
    frames = {}
    for tf in _TFS:
        freq = {"D1": "1D", "H4": "4h", "H1": "1h", "M15": "15min",
                "M5": "5min", "M1": "1min"}[tf]
        times = pd.date_range(base, periods=n, freq=freq, tz="UTC")
        close = 1.0 + 0.001 * pd.Series(range(n), dtype=float) \
            + 0.01 * pd.Series(range(n), dtype=float).pct_change().fillna(0.0)
        df = pd.DataFrame({
            "time": times,
            "open": close, "high": close + 0.002,
            "low": close - 0.002, "close": close, "volume": 100.0,
        })
        frames[tf] = detect_market_structure(df)
    return frames


def _legacy_htf_fn(ms, htf, ltf):
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    def fn(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")) if r is not None else "RANGING",
            "sweep_up": bool(r.get("liquidity_sweep_up", False)) if r is not None else False,
            "sweep_down": bool(r.get("liquidity_sweep_down", False)) if r is not None else False,
            "pd_zones": [],
        }
    return fn


def test_evaluate_signals_passes_multitf_context_to_run_sequence(monkeypatch):
    """Evidencia 3/7: evaluate_signals entrega est_htf_ctx_fn (MultiTFContext)
    a run_sequence, y run_sequence lo reduce idéntico al legacy 1-nivel."""
    from ict_backtest import sequence as seq_mod

    frames = _make_frames()
    captured = {}

    real_run = seq_mod.run_sequence

    def spy_run_sequence(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        captured["est_htf_ctx_fn"] = kwargs.get("est_htf_ctx_fn")
        captured["htf"] = kwargs.get("htf")
        captured["est_htf_fn_legacy"] = est_htf_fn
        return real_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs)

    monkeypatch.setattr(seq_mod, "run_sequence", spy_run_sequence)

    # Patch load_frames para devolver frames sintéticos (sin disco real).
    import ict_backtest.canonical as canon_mod
    import ict_backtest.data_feed as df_mod

    def fake_load(symbol, tfs, **kw):
        return {tf: frames[tf] for tf in tfs if tf in frames}

    monkeypatch.setattr(df_mod, "load_frames", fake_load)
    monkeypatch.setattr(canon_mod, "run_sequence", spy_run_sequence)

    sigs = evaluate_signals("SYN", "D1", "M15", enable_pd_index=False, frames=frames)

    # run_sequence recibió el contexto multinivel.
    assert captured["est_htf_ctx_fn"] is not None, "run_sequence NO recibió est_htf_ctx_fn"
    assert captured["htf"] == "D1"
    ctx_fn = captured["est_htf_ctx_fn"]

    # Por cada barra, el contexto reducido == legacy 1-nivel.
    ltf_df = frames["M15"]
    legacy_fn = _legacy_htf_fn(frames, "D1", "M15")
    for i in range(len(ltf_df)):
        ctx = ctx_fn(i)
        assert isinstance(ctx, __import__("ict_backtest.multitf_context", fromlist=["MultiTFContext"]).MultiTFContext)
        reduced = extract_htf_layer(ctx, "D1")
        legacy = legacy_fn(i)
        assert reduced == legacy, f"barra {i}: contexto reducido != legacy 1-nivel"


def test_evaluate_signals_behavior_identical_to_baseline(monkeypatch):
    """Evidencia 4/7: Fase 1 garantiza que el MOTOR (run_sequence) produce
    decisiones de secuencia idénticas con el lector MultiTFContext que con el
    legacy de 1 nivel.

    Para aislar el lector multitemporal del paquete de POST-FILTROS de
    evaluate_signals (killzone/atr/sl/risk), comparamos el RAW de
    run_sequence (entry_at de la secuencia CRUDO, sin post-filtros) en ambos
    caminos. Así medimos COMPONENTES EQUIVALENTES (motor vs motor), no
    etapa-filtrada vs etapa-cruda.

    Esto cierra la pregunta de regresión: si entry_at del raw nuevo == entry_at
    del raw legacy, MultiTFContext NO cambió el comportamiento del motor.
    """
    import ict_backtest.canonical as canon_mod
    import ict_backtest.data_feed as df_mod
    import ict_backtest.sequence as seq_mod
    from ict_backtest.sequence import run_sequence, SequenceConfig

    frames = _make_frames()

    def fake_load(symbol, tfs, **kw):
        return {tf: frames[tf] for tf in tfs if tf in frames}

    monkeypatch.setattr(df_mod, "load_frames", fake_load)

    # --- Captura del RAW de run_sequence dentro de evaluate_signals (nuevo path) ---
    captured_new = {}

    real_run = seq_mod.run_sequence

    def spy_run_new(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        raw, phases = real_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs)
        captured_new["raw"] = raw
        captured_new["est_htf_ctx_fn"] = kwargs.get("est_htf_ctx_fn")
        return raw, phases

    monkeypatch.setattr(seq_mod, "run_sequence", spy_run_new)
    monkeypatch.setattr(canon_mod, "run_sequence", spy_run_new)

    # Dispara el nuevo path (Fase 1: evaluate_signals con MultiTFContext).
    evaluate_signals("SYN", "D1", "M15", enable_pd_index=False, frames=frames)

    # --- Baseline legacy: run_sequence con est_htf_fn de 1 nivel sobre ms[D1] ---
    legacy_fn = _legacy_htf_fn(frames, "D1", "M15")
    raw_base, _ = run_sequence(frames["M15"], legacy_fn, SequenceConfig(), ltf_tf="M15")

    # --- Comparación de componentes equivalentes: RAW de run_sequence ---
    new_entries = [s["entry_at"] for s in captured_new["raw"]]
    base_entries = [s["entry_at"] for s in raw_base]

    assert new_entries == base_entries, (
        f"MOTOR diverge con lector MultiTFContext: "
        f"new={new_entries} base={base_entries}"
    )

    # El contexto reducido (D1) del MultiTFContext debe ser idéntico al legacy
    # en cada barra donde haya señal (redundante con test 3/7, pero cierra
    # el lazo: misma entrada => mismo raw => mismo entry_at).
    ctx_fn = captured_new["est_htf_ctx_fn"]
    for e in new_entries:
        reduced = extract_htf_layer(ctx_fn(e), "D1")
        legacy = legacy_fn(e)
        assert reduced == legacy, f"barra {e}: contexto reducido != legacy 1-nivel"

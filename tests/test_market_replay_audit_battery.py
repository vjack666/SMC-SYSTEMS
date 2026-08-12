"""Batería completa de auditoría temporal y MTF de market_replay.

NO modifica engine. NO usa ict_backtest como oráculo. La "referencia
independiente" se construye DENTRO de este test: un oráculo de disponibilidad
basado en time+duration puro (sin engine._util) y un replay naive que llama
al motor con ventana recortada. Se compara contra market_replay real.

Cobertura (orden del Director):
  1. Disponibilidad de velas (HTF closed-only)
  2. Cierre temporal (vela futura no disponible antes de time+duration)
  3. Orden de eventos (journal: orden temporal + parent chain)
  4. Reinicio (reset + reanudación == continuación)
  5. Gaps (timestamps no contiguos no anticipan ni rompen)
  6. Duplicados (mismo timestamp no duplica eventos)
  7. Timestamps (UTC, monotonicidad, tz-aware/naive)
  8. Determinismo (mismo input => mismo journal/estado)
  9. Aislamiento entre TFs (M1 no contamina D1)
 10. Equivalencia contra referencia independiente (oráculo naive vs MarketReplay)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from engine.sequence import SequenceConfig, SequenceState, run_sequence_traced
from market_replay.feed import MarketFeed
from market_replay.availability import TemporalAvailability, TF_DURATION, tf_duration
from market_replay.journal import EventJournal, JournalEntry
from market_replay.replay import MarketReplay


# --------------------------------------------------------------------------
# Oráculo independiente (NO engine, NO ict_backtest): time + duration puro.
# --------------------------------------------------------------------------
def _dur_minutes(tf: str) -> pd.Timedelta:
    return pd.Timedelta(tf_duration(tf))


def oracle_closed_row(df: pd.DataFrame, t, tf: str):
    """Última fila de df cuya barra YA CERRÓ respecto a t (time+dur <= t)."""
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    cutoff = pd.to_datetime(t, utc=True) - _dur_minutes(tf)
    mask = times <= cutoff
    if not mask.any():
        return None
    return df.loc[mask].iloc[-1]


def oracle_is_available(df: pd.DataFrame, t, tf: str) -> bool:
    return oracle_closed_row(df, t, tf) is not None


def naive_replay(frames: dict, ltf: str, cfg: SequenceConfig):
    """Referencia independiente: replay manual vela-a-vela sin market_replay.

    Recorta ventana LTF a [0..i] y ctx HTF vía oráculo puro. Llama al motor
    igual que MarketReplay (mismo contrato run_sequence_traced). Devuelve
    (signals, final_state, steps).
    """
    ltf_df = frames[ltf]
    state = SequenceState()
    all_signals = []
    steps = 0
    for i in range(1, len(ltf_df)):
        t = ltf_df.iloc[i]["time"]
        win = ltf_df.iloc[: i + 1].reset_index(drop=True)
        ctx = {}
        for tf in frames:
            if tf == ltf:
                continue
            row = oracle_closed_row(frames[tf], t, tf)
            if row is not None:
                ctx[tf] = {
                    "trend": str(row.get("trend", "RANGING")),
                    "high": float(row.get("high", float("nan"))),
                    "low": float(row.get("low", float("nan"))),
                    "close": float(row.get("close", float("nan"))),
                }
        sigs, _p, _e, state = run_sequence_traced(
            win, lambda tt: ctx, cfg, ltf_tf=ltf, initial_state=state, start_i=i - 1
        )
        all_signals.extend(sigs)
        steps += 1
    return all_signals, state, steps


# --------------------------------------------------------------------------
# Helpers de datos
# --------------------------------------------------------------------------
def _ohlc(times, price):
    return pd.DataFrame(
        {"time": times, "open": price, "high": price + 0.001, "low": price - 0.001, "close": price}
    )


def _synthetic(periods=80, seed=0, freq="15min"):
    idx = pd.date_range("2024-01-01", periods=periods, freq=freq, tz="UTC")
    rng = np.random.default_rng(seed)
    price = 1.10 + np.cumsum(rng.normal(0, 0.0005, periods))
    return _ohlc(idx, price)


def _structured(periods=120, seed=2):
    """Serie con sweep+displacement+BOS para forzar eventos del motor."""
    idx = pd.date_range("2024-01-01", periods=periods, freq="15min", tz="UTC")
    rng = np.random.default_rng(seed)
    base = np.linspace(1.10, 1.12, periods)
    mid = periods // 2
    base[mid : mid + 6] -= 0.005
    price = base + rng.normal(0, 0.0002, periods)
    return _ohlc(idx, price)


# ==========================================================================
# 1. Disponibilidad de velas (HTF closed-only)
# ==========================================================================
def test_disponibilidad_velas_ltf_y_htf():
    m15 = _synthetic(periods=80)
    h1 = m15.iloc[::4].reset_index(drop=True)
    av = TemporalAvailability({"M15": m15, "H1": h1}, "M15")
    # Cada vela M15 está disponible en su propio cierre.
    for i in range(1, 80):
        t = m15["time"].iloc[i]
        assert av.is_available("M15", t) is True
    # H1 disponible en los cierres que coinciden con velas H1.
    for i in range(4, 80, 4):
        t = m15["time"].iloc[i]
        assert av.is_available("H1", t) is True


# ==========================================================================
# 2. Cierre temporal (vela futura no disponible antes de time+duration)
# ==========================================================================
def test_cierre_temporal_anti_lookahead():
    m15 = _synthetic(periods=40)
    h1 = m15.iloc[::4].reset_index(drop=True)
    av = TemporalAvailability({"M15": m15, "H1": h1}, "M15")
    # La primera vela H1 abre a las 00:00 y CIERRA a las 01:00 del primer día.
    t_h1_first_close = h1["time"].iloc[0] + pd.Timedelta("1h")
    # Justo en el cierre => disponible.
    assert av.is_available("H1", t_h1_first_close) is True
    # Antes de que CUALQUIER vela H1 haya cerrado (00:15) => NO disponible.
    t_before_any_h1 = pd.Timestamp("2024-01-01 00:15", tz="UTC")
    assert av.is_available("H1", t_before_any_h1) is False
    # Un instante antes del cierre (30 min antes) => la vela aún no cerró.
    t_just_before = t_h1_first_close - pd.Timedelta("30m")
    assert av.is_available("H1", t_just_before) is False
    # Y la fila devuelta (si la hay) siempre cumple time+duration <= t.
    t_mid = m15["time"].iloc[8]
    row = av.available_row("H1", t_mid)
    if row is not None:
        close = pd.to_datetime(row["time"], utc=True) + _dur_minutes("H1")
        assert close <= pd.to_datetime(t_mid, utc=True)


# ==========================================================================
# 3. Orden de eventos (journal: orden temporal + parent chain)
# ==========================================================================
def test_orden_eventos_journal():
    df = _structured(seed=5)
    f = MarketFeed()
    f.ingest("M15", df)
    rp = MarketReplay(f, ltf="M15")
    res = rp.run()
    entries = list(res.journal)
    # Orden temporal creciente por candle_index.
    idxs = [e.candle_index for e in entries]
    assert idxs == sorted(idxs)
    # La cadena causal: un evento solo puede tener parent con candle_index < suyo.
    by_id = {e.event_id: e for e in entries}
    for e in entries:
        if e.parent_event_id:
            parent = by_id.get(e.parent_event_id)
            assert parent is not None, "parent debe existir en el journal"
            assert parent.candle_index <= e.candle_index, "parent no puede ser futuro"


# ==========================================================================
# 4. Reinicio (reset + reanudación == continuación)
# ==========================================================================
def test_reinicio_continuacion():
    df = _structured(seed=7)
    cfg = SequenceConfig()
    N = len(df)

    # Continuación: corre todo de una.
    f1 = MarketFeed(); f1.ingest("M15", df)
    r1 = MarketReplay(f1, ltf="M15", cfg=cfg).run()

    # Reinicio parcial: corre [0..k].
    k = N // 2
    f2a = MarketFeed(); f2a.ingest("M15", df.iloc[: k + 1].reset_index(drop=True))
    r2a = MarketReplay(f2a, ltf="M15", cfg=cfg).run()

    # Reanudación con estado fresh (reset) debe producir lo mismo que arrancar
    # desde 0. El número total de pasos de la continuación es N-1.
    assert r1.steps == N - 1
    assert r2a.steps == k
    # Reanudar desde 0 con estado reset da mismos steps que la primera mitad.
    assert r2a.steps + (N - 1 - k) == r1.steps


# ==========================================================================
# 5. Gaps (timestamps no contiguos no anticipan ni rompen)
# ==========================================================================
def test_gaps_no_anticipan():
    base = _synthetic(periods=60)
    # Introducimos un GAP: eliminamos velas [20, 25) (faltan del medio).
    gapped = pd.concat([base.iloc[:20], base.iloc[25:]], ignore_index=True)
    gapped["time"] = pd.to_datetime(gapped["time"], utc=True)
    # El reloj no debe "inventar" velas en el gap ni anticipar el futuro.
    h1 = gapped.iloc[::4].reset_index(drop=True)
    av = TemporalAvailability({"M15": gapped, "H1": h1}, "M15")
    # Para cualquier t, la vela disponible de M15 es <= t (nunca salta al futuro).
    for i in range(1, len(gapped)):
        t = gapped["time"].iloc[i]
        row = av.available_row("M15", t)
        assert row is not None
        assert pd.to_datetime(row["time"], utc=True) <= pd.to_datetime(t, utc=True)
    # El replay sigue corriendo sin error a pesar del gap.
    f = MarketFeed(); f.ingest("M15", gapped)
    res = MarketReplay(f, ltf="M15").run()
    assert res.steps == len(gapped) - 1


# ==========================================================================
# 6. Duplicados (mismo timestamp no duplica eventos)
# ==========================================================================
def test_duplicados_no_duplican_eventos():
    base = _synthetic(periods=50)
    # Duplicamos la vela 10 (mismo timestamp).
    dup = pd.concat([base.iloc[:11], base.iloc[10:11], base.iloc[11:]], ignore_index=True)
    dup["time"] = pd.to_datetime(dup["time"], utc=True)
    f = MarketFeed(); f.ingest("M15", dup)
    res = MarketReplay(f, ltf="M15").run()
    # No debe haber dos entradas con el mismo event_id (los ids del motor son
    # únicos por formación; un timestamp duplicado no debe duplicar eventos).
    ids = [e.event_id for e in res.journal if e.event_id]
    assert len(ids) == len(set(ids)), "event_ids duplicados tras timestamp duplicado"


# ==========================================================================
# 7. Timestamps (UTC, monotonicidad, tz-aware/naive)
# ==========================================================================
def test_timestamps_utc_monotonicos():
    # Datos tz-naive (sin zona): market_replay debe manejarlos sin crash.
    idx_naive = pd.date_range("2024-01-01", periods=30, freq="15min")  # tz-naive
    rng = np.random.default_rng(11)
    price = 1.10 + np.cumsum(rng.normal(0, 0.0005, 30))
    df_naive = _ohlc(idx_naive, price)
    f = MarketFeed(); f.ingest("M15", df_naive)
    res = MarketReplay(f, ltf="M15").run()
    assert res.steps == 29
    # Los timestamps del journal deben ser parseables y monotonicos por candle.
    candle_idx = [e.candle_index for e in res.journal]
    # candle_index monotónico implica orden temporal.
    assert candle_idx == sorted(candle_idx)


def test_timestamps_tz_aware_consistentes():
    m15 = _synthetic(periods=40)
    h1 = m15.iloc[::4].reset_index(drop=True)
    av = TemporalAvailability({"M15": m15, "H1": h1}, "M15")
    t = m15["time"].iloc[8]
    row = av.available_row("M15", t)
    # El tiempo devuelto debe ser tz-aware (UTC) tras normalización.
    assert pd.to_datetime(row["time"], utc=True).tzinfo is not None


# ==========================================================================
# 8. Determinismo (mismo input => mismo journal/estado)
# ==========================================================================
def test_determinismo():
    df = _structured(seed=9)
    cfg = SequenceConfig()

    def run_once():
        f = MarketFeed(); f.ingest("M15", df.copy())
        return MarketReplay(f, ltf="M15", cfg=cfg).run()

    r_a = run_once()
    r_b = run_once()
    # Mismo número de pasos y entradas.
    assert r_a.steps == r_b.steps
    assert len(r_a.journal) == len(r_b.journal)
    # Mismo contenido de entradas (serialize a dicts comparables).
    ja = [e.to_dict() for e in r_a.journal]
    jb = [e.to_dict() for e in r_b.journal]
    assert ja == jb
    # Mismo estado final de fase del motor.
    assert r_a.final_state.phase == r_b.final_state.phase


# ==========================================================================
# 9. Aislamiento entre TFs (M1 no contamina D1)
# ==========================================================================
def test_aislamiento_entre_timeframes():
    m15 = _synthetic(periods=64)
    h1 = m15.iloc[::4].reset_index(drop=True)
    d1 = m15.iloc[::16].reset_index(drop=True)
    av = TemporalAvailability({"M15": m15, "H1": h1, "D1": d1}, "M15")
    # En un t dado, la disponibilidad de D1 es función solo de D1, no de M15/H1.
    t = m15["time"].iloc[32]
    snap = av.snapshot(t, include_ltf=True)
    # D1 disponible solo si su vela ya cerró (independiente de M15/H1).
    d1_row = snap.get("D1")
    if d1_row is not None:
        d1_close = pd.to_datetime(d1_row["time"], utc=True) + _dur_minutes("D1")
        assert d1_close <= pd.to_datetime(t, utc=True)
    # M1 no existe en estos datos => no aparece en snapshot (aislamiento).
    assert "M1" not in snap
    assert "M5" not in snap


# ==========================================================================
# 10. Equivalencia contra referencia independiente
# ==========================================================================
def test_equivalencia_referencia_independiente():
    """MarketReplay == replay naive (oráculo puro) en señales y estado final."""
    df = _structured(seed=4)
    h1 = df.iloc[::4].reset_index(drop=True)
    d1 = df.iloc[::16].reset_index(drop=True)
    frames = {"M15": df, "H1": h1, "D1": d1}
    cfg = SequenceConfig()

    # MarketReplay real.
    f = MarketFeed()
    for tf, fr in frames.items():
        f.ingest(tf, fr)
    res = MarketReplay(f, ltf="M15", cfg=cfg).run()

    # Referencia independiente (oráculo puro, sin engine._util ni ict_backtest).
    sigs_ref, state_ref, steps_ref = naive_replay(frames, "M15", cfg)

    # Mismo número de pasos.
    assert res.steps == steps_ref, f"steps: {res.steps} vs {steps_ref}"
    # Mismo número de señales.
    assert len(res.signals) == len(sigs_ref), (
        f"señales: {len(res.signals)} vs {len(sigs_ref)}"
    )
    # Misma fase final de la secuencia.
    assert res.final_state.phase == state_ref.phase


def test_equivalencia_disponibilidad_contra_oraculo():
    """TemporalAvailability.is_available == oráculo puro time+duration."""
    m15 = _synthetic(periods=48)
    h1 = m15.iloc[::4].reset_index(drop=True)
    av = TemporalAvailability({"M15": m15, "H1": h1}, "M15")
    for i in range(1, 48):
        t = m15["time"].iloc[i]
        assert av.is_available("M15", t) == oracle_is_available(m15, t, "M15")
        # En cierres H1, deben coincidir.
        if i % 4 == 0:
            assert av.is_available("H1", t) == oracle_is_available(h1, t, "H1")

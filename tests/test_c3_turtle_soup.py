"""Fase C3 — Turtle Soup (sweep PDH/PDL dia previo + reversion).

TDD: este archivo se escribe PRIMERO (RED) y luego se implementa
ict_backtest/setups/turtle_soup.py (GREEN). Sin datos reales: frames
sinteticos de pd.DataFrame a mano. Sin tocar canonical/engine/sequence.

Contrato C3:
  - is_turtle_soup(sweep_ts, direction, frames, ltf) -> (bool, dict)
      True si el sweep rompe el extremo del DIA PREVIO (PDH/PDL) y luego
      hay reversion (displacement en la direccion del trade).
      meta = {"ts_broke_pdh": bool, "ts_broke_pdl": bool, "ts_reversal": bool}
      * direction == +1 (LONG)  -> busca barrer PDL (min previo) por debajo.
      * direction == -1 (SHORT) -> busca barrer PDH (max previo) por encima.
  - flag_turtle_soup(signals, frames, ltf='M15') -> list
      Setea sig.turtle_confirmed / sig.turtle_broke dinamicamente (no edita
      ICTSignal en engine.py).

Call-site real: evaluate_signals con run_sequence mockeado (patron
_inject_signal de test_b2_exec_tf.py), y se aplica el flag a las senales
devueltas afirmando el metadato.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.sequence import run_sequence
from ict_backtest.setups.turtle_soup import is_turtle_soup, flag_turtle_soup


# --- Frames sinteticos -------------------------------------------------
_PREV_DAY = pd.Timestamp("2026-01-04 00:00", tz="UTC")
_SIG_DAY = pd.Timestamp("2026-01-05 00:00", tz="UTC")


def _ohlc(times, base, spread=0.0006, sweep_low=None, sweep_high=None):
    n = len(times)
    close = np.full(n, float(base))
    df = pd.DataFrame({
        "time": times,
        "open": close,
        "high": close + spread / 2,
        "low": close - spread / 2,
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


def _make_turtle_frames():
    """M15 con 2 dias: 2026-01-04 (previo) y 2026-01-05 (senal).

    Previo: plano high=1.1050 low=1.1000 -> PDH=1.1050, PDL=1.1000.
    Senal: apertura plana ~1.1005; en idx 4 (01:00) el precio BARRE el
    PDL (low 1.0990 < 1.1000) y luego hay displacement alcista (idx 8
    cuerpo grande). Entry en idx 28 (07:00 = London Open).
    sweep_idx=4, entry_idx=28, entry=open(idx29)=1.1010.
    """
    # Dia previo: 96 velas M15 (00:00..23:45).
    prev_times = pd.date_range(_PREV_DAY, periods=96, freq="15min", tz="UTC")
    prev = _ohlc(prev_times, 1.1025, spread=0.0050)  # high 1.1050 low 1.1000

    # Dia de senal: 40 velas M15 (00:00..09:45).
    sig_times = pd.date_range(_SIG_DAY, periods=40, freq="15min", tz="UTC")
    sig = _ohlc(sig_times, 1.1005, spread=0.0006)
    # idx 4 (01:00): vela de sweep que rompe el PDL del dia previo (1.1000).
    sig.at[4, "low"] = 1.0990
    sig.at[4, "sweep_low"] = 1.0990
    sig.at[4, "ssl_price"] = 1.0989
    sig.at[4, "high"] = 1.1008
    sig.at[4, "open"] = 1.1006
    sig.at[4, "close"] = 1.1002
    # idx 5..27: rango plano ~1.1005.
    for i in range(5, 29):
        sig.at[i, "open"] = 1.1005
        sig.at[i, "high"] = 1.1008
        sig.at[i, "low"] = 1.1002
        sig.at[i, "close"] = 1.1005
    # Displacement alcista fuerte en sig idx 9 (= sweep 4 + 5, DENTRO de la
    # ventana de reversion +1..+20). En el df concatenado sera idx 105.
    sig.at[9, "open"] = 1.1005
    sig.at[9, "close"] = 1.1035
    sig.at[9, "high"] = 1.1038
    sig.at[9, "low"] = 1.1003
    # idx 28 (07:00 London Open): vela de entrada.
    sig.at[28, "open"] = 1.1010
    sig.at[28, "high"] = 1.1015
    sig.at[28, "low"] = 1.1005
    sig.at[28, "close"] = 1.1012
    # idx 29: open = entry (fill next_open).
    sig.at[29, "open"] = 1.1010

    m15 = pd.concat([prev, sig], ignore_index=True)
    # HTF dummy para que detect_market_structure no falle.
    d1_times = pd.date_range(_PREV_DAY, periods=2, freq="1D", tz="UTC")
    d1 = _ohlc(d1_times, 1.1025, spread=0.0050)
    frames = {"D1": d1, "H4": d1, "H1": d1, "M15": m15}
    # Indices DENTRO del dia de senal (despues de concatenar 96 previas).
    sweep_idx = 96 + 4   # = 100
    entry_idx = 96 + 28  # = 124
    sweep_ts = str(m15.iloc[sweep_idx]["time"])
    return frames, m15, sweep_idx, entry_idx, sweep_ts


# --- Inyeccion de senal sintetica (patron _inject_signal) ---------------
def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    import ict_backtest.canonical as canon_mod
    import ict_backtest.sequence as seq_mod

    fake_raw = [{
        "time": "t",
        "direction": direction,
        "entry": 0.0,
        "sweep_at": sweep_at,
        "displace_at": sweep_at,
        "bos_at": sweep_at,
        "entry_at": entry_at,
        "zone_authority": None,
        "htf_aligned": True,
        "htf_reason": "",
    }]

    def fake_run(ltf_df_or_objs, est_htf_fn, cfg, *args, **kwargs):
        return fake_raw, {"SWEEP": 1, "DISPLACE": 1, "BOS": 1, "ENTRY": 1}

    monkeypatch.setattr(seq_mod, "run_sequence", fake_run)
    monkeypatch.setattr(canon_mod, "run_sequence", fake_run)


# --- Tests unitarios de is_turtle_soup (RED luego GREEN) ----------------
def test_is_turtle_soup_long_detects_pdl_sweep_and_reversal():
    """LONG Turtle Soup: barre PDL del dia previo y revierte al alza."""
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    ok, meta = is_turtle_soup(sweep_ts, 1, frames, "M15")
    assert ok is True, f"debio detectar Turtle Soup long: {meta}"
    assert meta["ts_broke_pdl"] is True
    assert meta["ts_broke_pdh"] is False
    assert meta["ts_reversal"] is True


def test_is_turtle_soup_short_detects_pdh_sweep_and_reversal():
    """SHORT Turtle Soup: barre PDH del dia previo y revierte a la baja.

    Reusa el mismo frame pero invierte la direccion y el break: construimos
    un sweep que rompe el PDH por encima.
    """
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    # Trucamos la vela de sweep para que rompa el PDH (max previo 1.1050).
    m15.at[sweep_idx, "high"] = 1.1060
    m15.at[sweep_idx, "sweep_high"] = 1.1060
    m15.at[sweep_idx, "bsl_price"] = 1.1061
    m15.at[sweep_idx, "low"] = 1.1006
    m15.at[sweep_idx, "sweep_low"] = np.nan
    m15.at[sweep_idx, "ssl_price"] = np.nan
    # Displacement bajista fuerte en idx 105 (= sweep 100 + 5, dentro de
    # la ventana de reversion +1..+20) -> reversion a la baja.
    m15.at[105, "open"] = 1.1040
    m15.at[105, "close"] = 1.1005
    m15.at[105, "high"] = 1.1042
    m15.at[105, "low"] = 1.1003
    ts = str(m15.iloc[sweep_idx]["time"])
    ok, meta = is_turtle_soup(ts, -1, frames, "M15")
    assert ok is True, f"debio detectar Turtle Soup short: {meta}"
    assert meta["ts_broke_pdh"] is True
    assert meta["ts_broke_pdl"] is False
    assert meta["ts_reversal"] is True


def test_is_turtle_soup_false_when_no_prev_day():
    """Sin dia previo => no hay PDH/PDL => False (no filtra duro, solo ausente)."""
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    # Frame de un solo dia (sin previo): solo el dia de senal.
    only_sig = m15.iloc[96:].reset_index(drop=True)
    frames2 = {"D1": frames["D1"], "M15": only_sig}
    ts = str(only_sig.iloc[4]["time"])
    ok, meta = is_turtle_soup(ts, 1, frames2, "M15")
    assert ok is False
    assert meta["ts_broke_pdl"] is False


def test_is_turtle_soup_false_when_no_reversal():
    """Si barre el PDL pero NO hay reversion => confirmado False."""
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    # Eliminamos el displacement alcista: aplanamos idx 105 (la vela de
    # reversion dentro de la ventana +1..+20 del sweep).
    m15.at[105, "open"] = 1.1005
    m15.at[105, "close"] = 1.1005
    m15.at[105, "high"] = 1.1008
    m15.at[105, "low"] = 1.1002
    ok, meta = is_turtle_soup(sweep_ts, 1, frames, "M15")
    assert ok is False, f"sin reversion no es Turtle Soup: {meta}"
    assert meta["ts_broke_pdl"] is True  # rompio, pero sin reversion
    assert meta["ts_reversal"] is False


# --- Call-site real: evaluate_signals + flag_turtle_soup ----------------
def test_call_site_flags_turtle_soup_on_real_signals(monkeypatch):
    """Call-site real: run_sequence mockeado, evaluate_signals produce la
    senal y flag_turtle_soup anota turtle_confirmed/turtle_broke."""
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    _inject_signal(monkeypatch, entry_idx, sweep_idx, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
    )
    assert sigs, "evaluate_signals no produjo senal con frames sinteticos"
    # Aplicamos el flag C3 a las senales devueltas (call-site real).
    out = flag_turtle_soup(sigs, frames, ltf="M15")
    assert out is sigs, "flag_turtle_soup debe devolver la misma lista"
    sig = sigs[0]
    assert getattr(sig, "turtle_confirmed", None) is True, (
        f"senal no marcada como Turtle Soup: {sig.turtle_confirmed}"
    )
    assert getattr(sig, "turtle_broke", None) is True, (
        f"senal no marcada como broke PDL: {sig.turtle_broke}"
    )


def test_call_site_does_not_flag_non_turtle(monkeypatch):
    """Si el sweep NO rompe el dia previo, no se marca (principio Brecha D:
    no filtra duro, solo anota metadato)."""
    frames, m15, sweep_idx, entry_idx, sweep_ts = _make_turtle_frames()
    # Subimos el low del sweep para que NO rompa el PDL (1.1000).
    m15.at[sweep_idx, "low"] = 1.1005
    m15.at[sweep_idx, "sweep_low"] = 1.1005
    m15.at[sweep_idx, "ssl_price"] = 1.1004
    _inject_signal(monkeypatch, entry_idx, sweep_idx, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
    )
    assert sigs, "evaluate_signals no produjo senal"
    flag_turtle_soup(sigs, frames, ltf="M15")
    sig = sigs[0]
    assert getattr(sig, "turtle_confirmed", None) is False
    assert getattr(sig, "turtle_broke", None) is False

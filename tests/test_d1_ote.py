"""Tests D1-OTE (Optimal Trade Entry 62-79% Fib retrace).

TDD RED->GREEN con datos SINTETICOS. NO se tocan canonical/engine/sequence ni
datos reales. El call-site real usa evaluate_signals con run_sequence mockeado
(patron _inject_signal de tests/test_b2_exec_tf.py) y luego aplica flag_ote a
las senales, afirmando el metadato ote_confirmed / ote_zone.

Para que detect_market_structure produzca swings (el detector es event-driven
y exige un zig-zag, no rampas), el LTF (M15) se construye con una serie
oscilante de amplitud conocida; el precio de entry se fija en el open de la
vela entry_at+1 (fill 'next_open') a un nivel exactamente en la banda OTE o
fuera de ella, de modo de aislar la logica OTE del resto del pipeline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.sequence import run_sequence
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.setups.ote import (
    flag_ote,
    is_ote_entry,
    ote_zone,
    OTE_FIB_LOW,
    OTE_FIB_HIGH,
)

# --- Constantes del escenario sintetico ---------------------------------
# London Open base; entry_at=22 -> time 12:30 UTC (New York AM killzone).
_BASE = pd.Timestamp("2026-01-05 07:00", tz="UTC")
_FREQ = "15min"
_N = 40
_ENTRY_AT = 22          # indices con swing claro y dentro de killzone
_SWEEP_AT = 0
_HI_PAD = 0.0008
_LO_PAD = 0.0008


def _zigzag_closes():
    """Serie oscilante (zig-zag) que SI produce swings en market_structure."""
    closes: list[float] = []
    price = 1.0800
    for _ in range(8):
        for _ in range(5):
            price += 0.0020
            closes.append(round(price, 4))
        for _ in range(5):
            price -= 0.0020
            closes.append(round(price, 4))
    while len(closes) < _N:
        closes.append(closes[-1])
    return closes[:_N]


def _make_frames(sweep_low=None, sweep_high=None):
    """DataFrame M15 sintetico (sin columnas swing: flag_ote las calcula)."""
    times = pd.date_range(_BASE, periods=_N, freq=_FREQ, tz="UTC")
    closes = np.array(_zigzag_closes(), dtype=float)
    df = pd.DataFrame({
        "time": times,
        "open": closes,
        "high": closes + _HI_PAD,
        "low": closes - _LO_PAD,
        "close": closes,
        "volume": 100.0,
    })
    df["sweep_low"] = np.nan
    df["sweep_high"] = np.nan
    df["bsl_price"] = np.nan
    df["ssl_price"] = np.nan
    if sweep_low is not None:
        df["sweep_low"] = sweep_low
    if sweep_high is not None:
        df["sweep_high"] = sweep_high
    return df


def _ote_midpoint(df, entry_at, direction):
    """Nivel de entry en el punto medio de la banda OTE (valido para confirmar)."""
    ms = detect_market_structure(df)
    sh = float(ms["swing_high"].iloc[entry_at])
    sl = float(ms["swing_low"].iloc[entry_at])
    r = sh - sl
    if direction == 1:
        return sh - (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * r
    return sl + (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * r


def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    """Reemplaza run_sequence por un stub que devuelve UNA senal en crudo
    (patron de tests/test_b2_exec_tf.py, NO se toca run_sequence real)."""
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


# === Tests unitarios (sin evaluate_signals) =============================
def test_ote_zone_returns_fib_62_79_of_leg():
    sh, sl = 1.1000, 1.0800
    lo, hi = ote_zone(sh, sl)
    r = sh - sl
    assert abs(lo - (sh - OTE_FIB_HIGH * r)) < 1e-12
    assert abs(hi - (sh - OTE_FIB_LOW * r)) < 1e-12
    # la banda debe estar entre el high y el 50% del rango
    assert sl < lo < hi < sh


def test_is_ote_entry_long_inside_band():
    # pierna 1.0800->1.1000, retrace a 0.702*r esta DENTRO de [0.618,0.786]*r
    sh, sl = 1.1000, 1.0800
    r = sh - sl
    entry = sh - (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * r
    ok, meta = is_ote_entry(entry, sh, sl, direction=1)
    assert ok is True
    assert meta["ote_low"] <= entry <= meta["ote_high"]


def test_is_ote_entry_long_outside_band():
    sh, sl = 1.1000, 1.0800
    # retrace muy superficial (solo 30% del rango) -> FUERA de OTE
    entry = sh - 0.30 * (sh - sl)
    ok, meta = is_ote_entry(entry, sh, sl, direction=1)
    assert ok is False


def test_is_ote_entry_short_mirror():
    sh, sl = 1.1000, 1.0800
    # short: retrace hacia arriba en [sl+0.618r, sl+0.786r]
    entry = sl + (OTE_FIB_LOW + OTE_FIB_HIGH) / 2.0 * (sh - sl)
    ok, meta = is_ote_entry(entry, sh, sl, direction=-1)
    assert ok is True


def test_is_ote_entry_rejects_nonpositive_leg():
    ok, meta = is_ote_entry(1.09, 1.08, 1.10, direction=1)  # sh<sl
    assert ok is False
    assert meta["ote_confirmed"] is False


# === Call-site real: evaluate_signals + flag_ote =======================
def test_flag_ote_long_entry_in_ote_band(monkeypatch):
    """Call-site real: evaluate_signals (run_sequence mockeado) produce la
    senal; flag_ote la anota con ote_confirmed=True y la zona correcta."""
    frames = {"M15": _make_frames(sweep_low=1.0750, sweep_high=1.1025)}
    ltf_df = frames["M15"]
    # entry = open en entry_at+1, fijado al punto medio OTE (LONG).
    ote_entry = _ote_midpoint(ltf_df, _ENTRY_AT, direction=1)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = ote_entry

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
    )
    assert sigs, "evaluate_signals no produjo senal con run_sequence mockeado"
    assert abs(sigs[0].entry - ote_entry) < 1e-9

    flagged = flag_ote(sigs, frames, ltf="M15")
    sig = flagged[0]
    assert sig.ote_confirmed is True
    # zona debe coincidir con is_ote_entry sobre el swing del row de entry
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    _ok, meta = is_ote_entry(sig.entry, sh, sl, sig.direction)
    assert sig.ote_zone == (meta["ote_low"], meta["ote_high"])
    assert meta["ote_low"] <= sig.entry <= meta["ote_high"]


def test_flag_ote_short_entry_in_ote_band(monkeypatch):
    frames = {"M15": _make_frames(sweep_low=1.0790, sweep_high=1.0910)}
    ltf_df = frames["M15"]
    ote_entry = _ote_midpoint(ltf_df, _ENTRY_AT, direction=-1)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = ote_entry

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=-1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
    )
    assert sigs
    assert abs(sigs[0].entry - ote_entry) < 1e-9

    flagged = flag_ote(sigs, frames, ltf="M15")
    sig = flagged[0]
    assert sig.ote_confirmed is True
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    _ok, meta = is_ote_entry(sig.entry, sh, sl, sig.direction)
    assert sig.ote_zone == (meta["ote_low"], meta["ote_high"])


def test_flag_ote_entry_outside_ote_band_false(monkeypatch):
    """Entry en retrace superficial (no OTE) -> ote_confirmed=False."""
    frames = {"M15": _make_frames(sweep_low=1.0790, sweep_high=1.0910)}
    ltf_df = frames["M15"]
    # entry superficial: 30% del rango (claramente fuera de OTE).
    ms = detect_market_structure(ltf_df)
    sh = float(ms["swing_high"].iloc[_ENTRY_AT])
    sl = float(ms["swing_low"].iloc[_ENTRY_AT])
    shallow = sh - 0.30 * (sh - sl)
    ltf_df.loc[_ENTRY_AT + 1, "open"] = shallow

    _inject_signal(monkeypatch, _ENTRY_AT, _SWEEP_AT, direction=1)
    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
    )
    assert sigs
    flagged = flag_ote(sigs, frames, ltf="M15")
    assert flagged[0].ote_confirmed is False
    assert flagged[0].ote_zone is not None  # zona se calcula igual


# === Casos borde (sin tocar evaluate_signals) ==========================
def test_flag_ote_no_swing_returns_false():
    """Si el row de entry no tiene swing claro, NO se inventa: False."""
    flat_times = pd.date_range(_BASE, periods=_N, freq=_FREQ, tz="UTC")
    flat_df = pd.DataFrame({
        "time": flat_times, "open": 1.1000, "high": 1.1003,
        "low": 1.0997, "close": 1.1000, "volume": 100.0,
        "sweep_low": np.nan, "sweep_high": np.nan,
        "bsl_price": np.nan, "ssl_price": np.nan,
    })
    frames = {"M15": flat_df}
    ms = detect_market_structure(flat_df)
    assert ms["swing_high"].isna().all() and ms["swing_low"].isna().all()

    # senal cuya entry_at apunta a un row sin swing.
    from ict_backtest.engine import ICTSignal
    sig = ICTSignal(symbol="SYN", time="t", direction=1, entry=1.1000,
                    stop_loss=1.0990, take_profit=1.1050, entry_at=10)
    out = flag_ote([sig], frames, ltf="M15")
    assert out[0].ote_confirmed is False
    assert out[0].ote_zone is None


def test_flag_ote_empty_signals_returns_empty():
    frames = {"M15": _make_frames(sweep_low=1.0750)}
    assert flag_ote([], frames, ltf="M15") == []

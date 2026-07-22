"""TDD para ict_backtest/setups/rr_map.py — RR POR SETUP (MDS_RR_POR_SETUP).

Objetivo: mapear cada senal ICT a su RR objetivo segun el setup detectado,
SIN tocar canonical.py / engine.py / sequence.py / poi_filter.py ni datos
reales (.parquet). Solo anota ``sig.rr_target``; la APLICACION del RR al
calculo del TP queda para la integracion del orquestador (ver docstring de
rr_map.py).

TDD RED->GREEN:
  - RED:   este archivo existe antes que ict_backtest/setups/rr_map.py y
           falla con ModuleNotFoundError.
  - GREEN: se implementa rr_map.py y todos los tests pasan.

Call-site real: se corre evaluate_signals con run_sequence mockeado (patron
_inject_signal de tests/test_b2_exec_tf.py) y se usa rr_map.flag_rr para
resolver el RR de la senal segun su setup detectado (simulado con setattr).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Garantiza que el repo este en el path (entorno de test).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.canonical import evaluate_signals
from ict_backtest.sequence import run_sequence
import ict_backtest.canonical as canon_mod
import ict_backtest.sequence as seq_mod
from ict_backtest.market_structure import detect_market_structure


# === Helpers sinteticos (NO se toca parquet) =============================
_BASE = pd.Timestamp("2026-01-05 09:00", tz="UTC")


def _ohlc(times, base, sweep_low=None, sweep_high=None):
    close = np.full(len(times), float(base))
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


def _make_frames():
    m15_times = pd.date_range(_BASE, periods=40, freq="15min", tz="UTC")
    m15 = _ohlc(m15_times, 1.1000, sweep_low=1.0990)
    ms_m15 = detect_market_structure(m15)
    d1_times = pd.date_range(_BASE, periods=2, freq="1D", tz="UTC")
    d1 = _ohlc(d1_times, 1.1000)
    ms_d1 = detect_market_structure(d1)
    frames = {"D1": ms_d1, "H4": ms_d1, "H1": ms_d1, "M15": ms_m15}
    return frames, m15


def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    """Reemplaza run_sequence por un stub que devuelve UNA senal en crudo
    (patron de tests/test_b2_exec_tf.py) para aislar la logica de rr_map del
    detector de setup en datos sinteticos planos."""
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


# === Senal sintetica minima para tests unitarios de flag_rr ==============
class _MinSig:
    """Imita la interfaz relevante de ICTSignal para los tests unitarios:
    flags de setup opcionales (sb/turtle/ote) y un rr_target anotable."""
    def __init__(self, sb=False, turtle=False, ote=False):
        self.sb_confirmed = sb
        self.turtle_confirmed = turtle
        self.ote_confirmed = ote
        self.rr_target = None


# === RED / GREEN: rr_for =================================================
def test_rr_for_known_setups():
    from ict_backtest.setups.rr_map import rr_for
    assert rr_for("silver_bullet") == 2.0
    assert rr_for("turtle_soup") == 1.5
    assert rr_for("ote") == 3.0


def test_rr_for_default_and_unknown():
    from ict_backtest.setups.rr_map import rr_for
    assert rr_for(None) == 3.0
    assert rr_for("po3") == 3.0          # desconocido -> default
    assert rr_for("") == 3.0             # vacio -> default


# === flag_rr sobre senales sinteticas ====================================
def test_flag_rr_sets_target_by_setup():
    from ict_backtest.setups.rr_map import flag_rr
    sigs = [
        _MinSig(sb=True),     # silver_bullet -> 2.0
        _MinSig(turtle=True), # turtle_soup  -> 1.5
        _MinSig(ote=True),    # ote          -> 3.0
        _MinSig(),            # ninguno      -> 3.0 (default)
    ]
    out = flag_rr(sigs)
    assert out is sigs  # retorna la misma lista (mutacion in-place)
    assert [s.rr_target for s in sigs] == [2.0, 1.5, 3.0, 3.0]


def test_flag_rr_precedence_sb_over_ote():
    from ict_backtest.setups.rr_map import flag_rr
    # Si varios flags coincidieran, SB gana por precedencia declarada.
    sig = _MinSig(sb=True, turtle=True, ote=True)
    flag_rr([sig])
    assert sig.rr_target == 2.0  # silver_bullet


def test_flag_rr_empty_list():
    from ict_backtest.setups.rr_map import flag_rr
    assert flag_rr([]) == []


# === Call-site real: evaluate_signals + flag_rr =========================
def test_call_site_flag_rr_on_real_signal(monkeypatch):
    """Corre evaluate_signals (run_sequence mockeado) para obtener una senal
    ICTSignal REAL, simula la deteccion de setup con setattr y resuelve el
    RR con flag_rr."""
    from ict_backtest.setups import rr_map

    frames, _ = _make_frames()
    _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False,
        use_semantic=False,
    )
    assert sigs, "evaluate_signals no produjo senal con run_sequence mockeado"
    sig = sigs[0]
    assert type(sig).__name__ == "ICTSignal"  # es la senal real del motor

    # Simulamos que el orquestador detecto Silver Bullet en esta senal.
    # (ICTSignal hoy no tiene el flag; el futuro detector lo seteara. Aqui
    #  lo inyectamos para ejercitar el call-site real de rr_map.)
    setattr(sig, "sb_confirmed", True)

    out = rr_map.flag_rr(sigs)
    assert out is sigs
    assert sig.rr_target == 2.0  # RR de Silver Bullet

    # Y el mapa sigue siendo consultable de forma aislada.
    assert rr_map.rr_for("silver_bullet") == 2.0

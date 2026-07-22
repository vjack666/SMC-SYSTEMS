"""Fase B2 — Anclar entry/SL/TP al EXECUTION TF (M5/M1), no al LTF (M15).

Libro 18 ICT: SL y entry SIEMPRE en el exec TF (el mas fino disponible),
nunca en un TF mayor. El SETUP sigue detectandose en el LTF (run_sequence
no se toca); lo que cambia es DONDE se anclan entry/SL/TP una vez que el
toque de zona ocurre en el LTF.

Sin datos reales: se inyectan frames sinteticos de M15/M5/M1 via el kwarg
`frames` (no se toca parquet). Los sweep_low/bsl_price/ssl_price los
inyectamos a mano porque los produce build_features (data_feed), no
detect_market_structure.

Contrato:
  - exec_tf=None  o  exec_tf==ltf  -> comportamiento IDENTICO al historico
    (regresion cero: mismos entry/SL/TP).
  - exec_tf distinto (M5/M1) -> entry/SL/TP/liq/killzone se recalculan sobre
    el exec_df en la vela cuyo time <= timestamp del toque LTF (cerrado,
    anti look-ahead). El SL se ancla a la mecha del sweep del exec TF.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.sequence import run_sequence
from ict_backtest.market_structure import detect_market_structure
from ict_backtest._util import tf_duration


# --- Frames sinteticos ---------------------------------------------------
# M15 = LTF (donde run_sequence detecta el setup).
# M15 tiene un sweep "suave" (low 1.0990) y entry en t=09:45 (London Open).
# M5  = exec TF con sweep de MECHA DISTINTA (low 1.0980, mas profundo).
# El SL estructural debe anclarse al 1.0980 del M5, NO al 1.0990 del M15.
_M15_FREQ = "15min"
_M5_FREQ = "5min"
_M1_FREQ = "1min"

_BASE = pd.Timestamp("2026-01-05 09:00", tz="UTC")  # London Open window


def _ohlc(times, base, sweep_low=None, sweep_high=None):
    n = len(times)
    # Precio FLAT: entry (open siguiente al toque) y sweep deben estar CERCA
    # (el toque de zona vuelve al cuadro justo tras el sweep), como en datos
    # reales. Si derivara, el sweep fijo quedaria lejos del entry y el risk
    # romperia el filtro STRUCT_SL_MAX_RANGE (artefacto de data sintetica).
    close = np.full(n, float(base))
    df = pd.DataFrame({
        "time": times,
        "open": close,
        "high": close + 0.0003,
        "low": close - 0.0003,
        "close": close,
        "volume": 100.0,
    })
    # sweep_low/bsl_price/ssl_price: los inyecta build_features, no ms.
    df["sweep_low"] = np.nan
    df["sweep_high"] = np.nan
    df["bsl_price"] = np.nan
    df["ssl_price"] = np.nan
    if sweep_low is not None:
        df["sweep_low"] = sweep_low
        # SSL un pelo bajo la mecha del sweep.
        df["ssl_price"] = sweep_low - 0.0001
    if sweep_high is not None:
        df["sweep_high"] = sweep_high
        df["bsl_price"] = sweep_high + 0.0001
    return df


def _make_frames():
    # M15 (LTF): 40 velas 09:00..19:00. avg_candle_range(window=50) necesita
    # >=25 velas para no dar NaN (igual que los tests de regresion existentes).
    # Entry (toque de zona) en idx 3 -> 09:45 (London Open). Sweep en idx 0.
    m15_times = pd.date_range(_BASE, periods=40, freq=_M15_FREQ, tz="UTC")
    m15 = _ohlc(m15_times, 1.1000, sweep_low=1.0990)  # sweep M15 en low 1.0990
    ms_m15 = detect_market_structure(m15)

    # M5 (exec): 3 velas por M15 = 120. Misma ventana que el M15.
    m5_times = pd.date_range(_BASE, periods=120, freq=_M5_FREQ, tz="UTC")
    m5 = _ohlc(m5_times, 1.1000, sweep_low=1.0980)  # sweep M5 en low 1.0980 (DISTINTO, mas fino)
    ms_m5 = detect_market_structure(m5)

    # M1 (exec): 15 velas por M15 = 600. Sweep aun mas profundo (1.0975) y
    # coherente: cada TF mas fino barre un poco mas abajo (mecha mas fina).
    m1_times = pd.date_range(_BASE, periods=600, freq=_M1_FREQ, tz="UTC")
    m1 = _ohlc(m1_times, 1.1000, sweep_low=1.0975)
    ms_m1 = detect_market_structure(m1)

    # HTF dummy (D1) para que ms tenga la cadena; no influye en el SL.
    d1_times = pd.date_range(_BASE, periods=2, freq="1D", tz="UTC")
    d1 = _ohlc(d1_times, 1.1000)
    ms_d1 = detect_market_structure(d1)

    frames = {
        "D1": ms_d1, "H4": ms_d1, "H1": ms_d1,
        "M15": ms_m15, "M5": ms_m5, "M1": ms_m1,
    }
    return frames, m15, m5, m1


# --- Inyeccion de senal sintetica ---------------------------------------
def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    """Reemplaza run_sequence por un stub que devuelve UNA senal en crudo.

    Solo se usa para aislar la logica B2 de canonical (el mapeo entry/SL/TP
    al exec TF) sin depender de que run_sequence detecte el setup en datos
    sinteticos planos.
    """
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


# --- Tests ---------------------------------------------------------------
def test_exec_tf_kwarg_anchors_sl_to_exec_tf(monkeypatch):
    """RED/GREEN: con exec_tf='M5', el SL se ancla a la mecha del M5 (1.0980),
    NO a la del M15 (1.0990)."""
    frames, m15, m5, m1 = _make_frames()
    # entry (toque) en M15 idx 3 (09:45); sweep M15 idx 0 (09:00).
    entry_at = 3
    sweep_at = 0
    _inject_signal(monkeypatch, entry_at, sweep_at, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf="M5",
        use_semantic=False,
    )
    assert sigs, "no se produjo senal con exec_tf=M5"
    sl = sigs[0].stop_loss
    # SL = sweep_low(M5) - buf. buf = 0.3 * rango(M5) ~ 0.3*0.0006 = 0.00018.
    # => SL ~ 1.0980 - 0.00018 = 1.09782, claramente < 1.0990 (M15).
    assert sl < 1.0990, f"SL NO se anclo al M5: sl={sl} (esperado < 1.0990 de M15)"
    # Y debe ser cercano al sweep del M5 (1.0980 - buf), no al del M1 (1.0975).
    assert sl > 1.0975, f"SL cayo al sweep del M1 en vez del M5: sl={sl}"


def test_exec_tf_none_is_identical_to_ltf(monkeypatch):
    """REGRESION: exec_tf=None debe producir el MISMO SL que exec_tf='M15'
    (comportamiento historico intacto)."""
    frames, m15, m5, m1 = _make_frames()
    entry_at = 3
    sweep_at = 0
    _inject_signal(monkeypatch, entry_at, sweep_at, direction=1)

    sigs_none = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf=None,
        use_semantic=False,
    )
    sigs_ltf = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf="M15",
        use_semantic=False,
    )
    assert sigs_none and sigs_ltf, "no se produjo senal"
    assert sigs_none[0].stop_loss == sigs_ltf[0].stop_loss, (
        f"exec_tf=None difiere de exec_tf=M15: "
        f"{sigs_none[0].stop_loss} != {sigs_ltf[0].stop_loss}"
    )
    # Y ambos se anclan al sweep del M15 (1.0990).
    assert sigs_none[0].stop_loss > 1.0990 - 0.001, "SL historico no usa sweep M15"


def test_exec_tf_m1_uses_m1_sweep(monkeypatch):
    """El exec TF mas fino (M1, sweep 1.0970) debe anclar el SL a su mecha."""
    frames, m15, m5, m1 = _make_frames()
    entry_at = 3
    sweep_at = 0
    _inject_signal(monkeypatch, entry_at, sweep_at, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf="M1",
        use_semantic=False,
    )
    assert sigs, "no se produjo senal con exec_tf=M1"
    sl = sigs[0].stop_loss
    # SL = sweep_low(M1) - buf ~ 1.0975 - 0.00018 = 1.09732, mas fino que M5.
    assert sl < 1.0975, f"SL M1 NO se anclo a mecha M1 (1.0975): sl={sl}"
    assert sl > 1.0970, f"SL M1 fuera de rango esperado: sl={sl}"


def test_call_site_uses_exec_tf_for_po3_config(monkeypatch):
    """El call site pasa exec_tf al Po3MotorConfig (demostracion de cableado)."""
    frames, m15, m5, m1 = _make_frames()
    entry_at = 3
    sweep_at = 0
    _inject_signal(monkeypatch, entry_at, sweep_at, direction=1)

    # Capturamos el config que recibe compute_po3_complete DENTRO de canonical
    # (se importa por nombre, asi que espiamos el attr de canonical).
    import ict_backtest.canonical as canon_mod
    captured = {}

    real_compute = canon_mod.compute_po3_complete

    def spy(tfm, config=None):
        captured["exec_tf"] = config.exec_tf if config else None
        return real_compute(tfm, config)

    monkeypatch.setattr(canon_mod, "compute_po3_complete", spy)

    evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf="M5",
        use_semantic=False,
    )
    assert captured.get("exec_tf") == "M5", (
        f"Po3MotorConfig no recibio exec_tf=M5: {captured.get('exec_tf')}"
    )

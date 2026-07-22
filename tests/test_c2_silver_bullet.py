"""C2 — Silver Bullet (SB): setup de 'hora limpia' en London Killzone o NY AM Killzone.

Libro 07 / 18 ICT: el precio barre (sweep) un maximo/minimo reciente, lo rechaza
(displacement) y la ENTRADA es un retorno a la zona (FVG/OB) DENTRO de la
killzone. Fuera de London Open (07:00-10:00 UTC) o New York AM (12:30-15:00 UTC)
NO opera.

TDD: este archivo es el test RED primero (el modulo ict_backtest/setups/
silver_bullet.py NO existe aun -> ImportError -> FAILED). Luego se implementa
GREEN.

Principio Brecha D / leccion A'': se ANOTA (sb_confirmed / sb_killzone), no se
veta ciego. El filtro duro queda como knob apagado.

NO se tocan canonical.py / engine.py / sequence.py / poi_filter.py ni .parquet.
Datos 100% sinteticos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.canonical import evaluate_signals
from ict_backtest.sequence import run_sequence
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.engine import ICTSignal
from ict_backtest.rules import killzone_en

from ict_backtest.setups.silver_bullet import is_silver_bullet, flag_silver_bullet


# --- Frames sinteticos (reusa el patron de test_b2_exec_tf.py) ------------
_M15_FREQ = "15min"
_BASE = pd.Timestamp("2026-01-05 09:00", tz="UTC")  # London Open window


def _ohlc(times, base, sweep_low=None):
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
    return df


def _make_frames():
    m15_times = pd.date_range(_BASE, periods=40, freq=_M15_FREQ, tz="UTC")
    m15 = _ohlc(m15_times, 1.1000, sweep_low=1.0990)
    ms_m15 = detect_market_structure(m15)

    m5_times = pd.date_range(_BASE, periods=120, freq="5min", tz="UTC")
    m5 = _ohlc(m5_times, 1.1000, sweep_low=1.0980)
    ms_m5 = detect_market_structure(m5)

    m1_times = pd.date_range(_BASE, periods=600, freq="1min", tz="UTC")
    m1 = _ohlc(m1_times, 1.1000, sweep_low=1.0975)
    ms_m1 = detect_market_structure(m1)

    d1_times = pd.date_range(_BASE, periods=2, freq="1D", tz="UTC")
    d1 = _ohlc(d1_times, 1.1000)
    ms_d1 = detect_market_structure(d1)

    frames = {
        "D1": ms_d1, "H4": ms_d1, "H1": ms_d1,
        "M15": ms_m15, "M5": ms_m5, "M1": ms_m1,
    }
    return frames, m15, m5, m1


def _inject_signal(monkeypatch, entry_at, sweep_at, direction):
    """Reemplaza run_sequence por un stub que devuelve UNA senal en crudo.

    Reusa el patron de tests/test_b2_exec_tf.py:_inject_signal: monkeypatchea
    run_sequence en sequence y canonical para que evaluate_signals produzca una
    senal aislada, sin depender de que el detector encadene el setup en datos
    planos sinteticos.
    """
    import ict_backtest.canonical as canon_mod
    import ict_backtest.sequence as seq_mod

    fake_raw = [{
        "time": str(_BASE),
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


# --- is_silver_bullet: tests unitarios -----------------------------------
def test_is_silver_bullet_london_open():
    """Sweep y retorno DENTRO de London Open -> confirmado, sb_killzone='L'."""
    sweep = pd.Timestamp("2026-01-05 08:30", tz="UTC")
    ret = pd.Timestamp("2026-01-05 09:15", tz="UTC")
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is True
    assert meta["sb_killzone"] == "L"


def test_is_silver_bullet_ny_am():
    """Sweep y retorno DENTRO de New York AM -> confirmado, sb_killzone='NY_AM'."""
    sweep = pd.Timestamp("2026-01-05 13:00", tz="UTC")
    ret = pd.Timestamp("2026-01-05 14:00", tz="UTC")
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is True
    assert meta["sb_killzone"] == "NY_AM"


def test_is_silver_bullet_return_outside_window():
    """Sweep en London Open pero retorno FUERA de toda ventana -> NO SB."""
    sweep = pd.Timestamp("2026-01-05 08:30", tz="UTC")
    ret = pd.Timestamp("2026-01-05 11:00", tz="UTC")  # fuera de London Open/NY AM
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is False
    assert meta["sb_killzone"] is None


def test_is_silver_bullet_different_killzone():
    """Sweep en London Open pero retorno en NY AM (ventanas distintas) -> NO SB."""
    sweep = pd.Timestamp("2026-01-05 08:30", tz="UTC")
    ret = pd.Timestamp("2026-01-05 13:30", tz="UTC")
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is False
    assert meta["sb_killzone"] is None


def test_is_silver_bullet_ny_pm_rejected():
    """NY PM NO es killzone SB (solo L / NY_AM) -> NO SB aunque todo en NY PM."""
    sweep = pd.Timestamp("2026-01-05 15:30", tz="UTC")
    ret = pd.Timestamp("2026-01-05 16:00", tz="UTC")
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is False
    assert meta["sb_killzone"] is None


def test_is_silver_bullet_return_before_sweep_rejected():
    """Retorno cronologicamente ANTES del sweep -> NO SB (estructura invalida)."""
    sweep = pd.Timestamp("2026-01-05 09:15", tz="UTC")
    ret = pd.Timestamp("2026-01-05 08:30", tz="UTC")
    ok, meta = is_silver_bullet(sweep, ret, 1, killzone_en)
    assert ok is False


# --- flag_silver_bullet: tests unitarios sobre ICTSignal sinteticos ------
def _make_ltf_df(base_hour=9):
    start = pd.Timestamp("2026-01-05", tz="UTC") + pd.Timedelta(hours=base_hour)
    times = pd.date_range(start, periods=40, freq="15min", tz="UTC")
    return pd.DataFrame({"time": times})


def test_flag_silver_bullet_annotates_confirmed():
    """Senal con sweep/entry en London Open -> sb_confirmed=True, sb_killzone='L'."""
    df = _make_ltf_df(9)  # 09:00.. London Open
    sig = ICTSignal(
        symbol="SYN", time="t", direction=1, entry=1.1,
        stop_loss=1.09, take_profit=1.12, sweep_at=0, entry_at=3,
    )
    out = flag_silver_bullet([sig], df, killzone_fn=killzone_en)
    assert out[0].sb_confirmed is True
    assert out[0].sb_killzone == "L"


def test_flag_silver_bullet_annotates_rejected():
    """Senal con sweep/entry FUERA de ventana -> sb_confirmed=False."""
    df = _make_ltf_df(11)  # 11:00.. fuera de London Open/NY AM
    sig = ICTSignal(
        symbol="SYN", time="t", direction=1, entry=1.1,
        stop_loss=1.09, take_profit=1.12, sweep_at=0, entry_at=3,
    )
    out = flag_silver_bullet([sig], df, killzone_fn=killzone_en)
    assert out[0].sb_confirmed is False
    assert out[0].sb_killzone is None


def test_flag_silver_bullet_no_hard_filter():
    """Principio Brecha D: NO se descartan senales, solo se anotan (len intacta)."""
    df = _make_ltf_df(9)
    sigs = [
        ICTSignal(symbol="SYN", time="t", direction=1, entry=1.1,
                  stop_loss=1.09, take_profit=1.12, sweep_at=0, entry_at=3),
        ICTSignal(symbol="SYN", time="t", direction=-1, entry=1.1,
                  stop_loss=1.11, take_profit=1.08, sweep_at=0, entry_at=3),
    ]
    out = flag_silver_bullet(sigs, df, killzone_fn=killzone_en)
    assert len(out) == 2  # no se filtra, se anota


# --- Call-site real: evaluate_signals + flag ----------------------------
def test_call_site_real_silver_bullet(monkeypatch):
    """Call-site real: evaluate_signals (run_sequence mockeado) produce la
    senal; flag_silver_bullet anota sb_confirmed=True en la senal devuelta.

    Esto prueba integracion REAL con canonical.evaluate_signals sin editar
    canonical.py: el atributo se setea dinamicamente en el ICTSignal.
    """
    frames, m15, m5, m1 = _make_frames()
    # sweep (idx 0 -> 09:00) y entry (idx 3 -> 09:45) DENTRO de London Open.
    _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)

    sigs = evaluate_signals(
        "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf=None,
        use_semantic=False,
    )
    assert sigs, "evaluate_signals no produjo senal con run_sequence mockeado"

    # flag sobre el frame LTF que contiene los indices sweep_at/entry_at.
    out = flag_silver_bullet(sigs, frames["M15"], killzone_fn=killzone_en)
    assert len(out) == len(sigs)
    assert out[0].sb_confirmed is True, "sb_confirmed no se anoto en call-site real"
    assert out[0].sb_killzone == "L", f"sb_killzone erroneo: {out[0].sb_killzone}"


def test_call_site_real_silver_bullet_outside_window(monkeypatch):
    """Call-site real en NY PM: canonical EMITE la senal (NY PM esta en su lista
    permitida), pero Silver Bullet la ANOTA como NO-SB (NY PM no es killzone SB).

    Esto prueba el principio Brecha D: se anota, no se veta ciego. canonical no
    se toca; solo el flag decide que NY PM != SB.
    """
    global _BASE
    saved = _BASE
    _BASE = pd.Timestamp("2026-01-05 15:00", tz="UTC")  # NY PM (canonical la emite)
    try:
        frames, m15, m5, m1 = _make_frames()
        _inject_signal(monkeypatch, entry_at=3, sweep_at=0, direction=1)
        sigs = evaluate_signals(
            "SYN", "D1", "M15", frames=frames, enable_pd_index=False, exec_tf=None,
            use_semantic=False,
        )
        assert sigs, "canonical no emitio senal en NY PM (inesperado)"
        out = flag_silver_bullet(sigs, frames["M15"], killzone_fn=killzone_en)
        assert out[0].sb_confirmed is False, "NY PM NO debe confirmarse como SB"
        assert out[0].sb_killzone is None
    finally:
        _BASE = saved

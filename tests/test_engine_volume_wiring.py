"""tests/test_engine_volume_wiring.py — MDS_VOLUMEN: cableado del volumen.

Verifica que los 3 módulos del motor ANOTAN un ratio de volumen (float) cuando
existe la columna 'volume', y que SIN esa columna el resultado geométrico es
IDÉNTICO (regresión cero) con el campo en None/NaN.

Regla dura: el volumen NUNCA es gate. Un volumen ridículamente bajo no puede
cambiar ninguna decisión geométrica.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine._volume import volume_confirm
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.liquidity_levels import detect_liquidity_htf
from engine.trade_mgmt import apply_trade_management

GEOM_COLS_LIQ = ["bsl_level", "ssl_level", "target_liquidity"]
GEOM_COLS_BOS = [
    "bos_dir", "bos_level", "bos_status", "choch_dir", "choch_status",
    "trend", "mss_dir", "bos_quality_score", "bos_real",
]


# --------------------------------------------------------------------------
# Datos sintéticos
# --------------------------------------------------------------------------
def _zigzag(n: int = 80) -> pd.DataFrame:
    """Serie con swings claros (BOS/CHOCH y sweeps de BSL/SSL garantizados)."""
    rng = np.arange(n)
    base = 100.0 + np.sin(rng / 4.0) * 5.0 + rng * 0.05
    high = base + 0.8
    low = base - 0.8
    open_ = base - 0.2
    close = base + 0.2
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close}
    )


def _with_volume(df: pd.DataFrame, spike: bool = False) -> pd.DataFrame:
    out = df.copy()
    vol = np.full(len(out), 1000.0)
    if spike:
        vol[len(out) // 2:] = 5000.0
    out["volume"] = vol
    return out


def _tiny_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Volumen absurdamente bajo: si fuese gate, mataría las detecciones."""
    out = df.copy()
    vol = np.full(len(out), 1000.0)
    vol[5:] = 0.0001
    out["volume"] = vol
    return out


# --------------------------------------------------------------------------
# Helper central
# --------------------------------------------------------------------------
def test_helper_none_sin_columna_volume():
    df = _zigzag(30)
    assert volume_confirm(df, 20) is None


def test_helper_ratio_correcto():
    df = _with_volume(_zigzag(30))
    df.loc[25, "volume"] = 2000.0
    r = volume_confirm(df, 25, window=20)
    assert r == pytest.approx(2.0)


def test_helper_indices_fuera_de_rango():
    df = _with_volume(_zigzag(30))
    assert volume_confirm(df, -1) is None
    assert volume_confirm(df, 999) is None


def test_helper_es_unica_fuente():
    """silver_bullet / turtle_soup / liquidity_internal_external reexportan."""
    from engine.liquidity_internal_external import volume_confirm as vc_liq
    from engine.silver_bullet import volume_confirm as vc_sb
    from engine.turtle_soup import _volume_on_sweep as vc_ts

    df = _with_volume(_zigzag(40))
    df.loc[30, "volume"] = 3000.0
    ref = volume_confirm(df, 30)
    assert vc_sb(df, 30) == pytest.approx(ref)
    assert vc_ts(df, 30) == pytest.approx(ref)
    assert vc_liq(df, 30) == pytest.approx(ref)


# --------------------------------------------------------------------------
# a) engine/liquidity_levels.py -> sweep_volume_ratio
# --------------------------------------------------------------------------
def test_liquidity_anota_sweep_volume_ratio():
    df = _with_volume(_zigzag(), spike=True)
    out = detect_liquidity_htf(df, "BULLISH")
    assert "sweep_volume_ratio" in out.columns
    ratios = out["sweep_volume_ratio"].dropna()
    assert len(ratios) > 0, "debe anotarse al menos un sweep con volumen"
    assert all(isinstance(float(v), float) for v in ratios)
    assert (ratios > 0).all()


def test_liquidity_sin_volume_ratio_nan_y_geometria_identica():
    df = _zigzag()
    out_sin = detect_liquidity_htf(df, "BULLISH")
    out_con = detect_liquidity_htf(_with_volume(df, spike=True), "BULLISH")

    assert "sweep_volume_ratio" in out_sin.columns
    assert out_sin["sweep_volume_ratio"].isna().all()
    # Regresión cero: la geometría no cambia por tener o no volumen.
    for col in GEOM_COLS_LIQ:
        pd.testing.assert_series_equal(
            out_sin[col], out_con[col], check_names=False
        )


def test_liquidity_volumen_nunca_gatea():
    df = _zigzag()
    base = detect_liquidity_htf(df, "BULLISH")
    tiny = detect_liquidity_htf(_tiny_volume(df), "BULLISH")
    for col in GEOM_COLS_LIQ:
        pd.testing.assert_series_equal(base[col], tiny[col], check_names=False)


def test_liquidity_frame_vacio_tiene_columna():
    empty = pd.DataFrame({"open": [], "high": [], "low": [], "close": []})
    out = detect_liquidity_htf(empty, "BULLISH")
    assert "sweep_volume_ratio" in out.columns and out.empty


# --------------------------------------------------------------------------
# b) engine/bos/structure.py -> bos_volume_ratio
# --------------------------------------------------------------------------
def test_bos_anota_bos_volume_ratio():
    df = _with_volume(_zigzag(), spike=True)
    ms = detect_market_structure(df, StructureConfig())
    assert "bos_volume_ratio" in ms.frame.columns
    eventos = (ms.frame["bos_dir"] != 0) | (ms.frame["choch_dir"] != 0)
    assert eventos.any(), "el fixture debe generar BOS/CHOCH"
    ratios = ms.frame.loc[eventos, "bos_volume_ratio"].dropna()
    assert len(ratios) > 0
    assert (ratios > 0).all()
    # Nunca se anota fuera de los eventos.
    assert ms.frame.loc[~eventos, "bos_volume_ratio"].isna().all()


def test_bos_sin_volume_ratio_nan_y_geometria_identica():
    df = _zigzag()
    sin = detect_market_structure(df, StructureConfig()).frame
    con = detect_market_structure(
        _with_volume(df, spike=True), StructureConfig()
    ).frame
    assert sin["bos_volume_ratio"].isna().all()
    for col in GEOM_COLS_BOS:
        pd.testing.assert_series_equal(sin[col], con[col], check_names=False)


def test_bos_volumen_nunca_gatea():
    df = _zigzag()
    base = detect_market_structure(df, StructureConfig()).frame
    tiny = detect_market_structure(_tiny_volume(df), StructureConfig()).frame
    for col in GEOM_COLS_BOS:
        pd.testing.assert_series_equal(base[col], tiny[col], check_names=False)


# --------------------------------------------------------------------------
# c) engine/trade_mgmt.py -> touch_volume_ratio
# --------------------------------------------------------------------------
def _trade_frame(with_volume: bool, spike: bool = True) -> pd.DataFrame:
    # Long: entry 100, sl 99 (risk=1), tp1=101, tp=105. Sube monotónico.
    closes = [100.2, 100.6, 101.5, 102.5, 103.5, 105.5]
    rows = [(c - 0.3, c + 0.3, c - 0.4, c) for c in closes]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    if with_volume:
        vol = [1000.0] * len(df)
        if spike:
            vol[2] = 9000.0
        df["volume"] = vol
    return df


def test_trade_mgmt_anota_touch_volume_ratio():
    res = apply_trade_management(100.0, 99.0, 105.0, 1, _trade_frame(True))
    assert res["partial_done"] is True
    assert isinstance(res["touch_volume_ratio"], float)
    assert res["touch_volume_ratio"] > 1.0


def test_trade_mgmt_sin_volume_es_none_y_resultado_identico():
    con = apply_trade_management(100.0, 99.0, 105.0, 1, _trade_frame(True))
    sin = apply_trade_management(100.0, 99.0, 105.0, 1, _trade_frame(False))
    assert sin["touch_volume_ratio"] is None
    for k in ("exit_reason", "exit_price", "pnl_r", "partial_done", "risk"):
        assert sin[k] == con[k], f"regresión en {k}"


def test_trade_mgmt_volumen_nunca_gatea():
    """Volumen ínfimo en el toque: el parcial y la salida no cambian."""
    df_low = _trade_frame(True, spike=False)
    df_low.loc[2, "volume"] = 0.0001
    base = apply_trade_management(100.0, 99.0, 105.0, 1, _trade_frame(False))
    low = apply_trade_management(100.0, 99.0, 105.0, 1, df_low)
    for k in ("exit_reason", "exit_price", "pnl_r", "partial_done", "risk"):
        assert low[k] == base[k]
    assert low["touch_volume_ratio"] is not None


def test_trade_mgmt_sin_toque_ratio_none():
    """Trade que va directo a SL sin tocar tp1 -> ratio None."""
    rows = [(100.0, 100.1, 98.5, 98.6)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["volume"] = [1000.0]
    res = apply_trade_management(100.0, 99.0, 105.0, 1, df)
    assert res["partial_done"] is False
    assert res["touch_volume_ratio"] is None

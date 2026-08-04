"""Tests de engine/fvg_poi.py — FVG como POI anclado a narrativa HTF (Deuda 3)."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from engine.bias.narrative import HtfBias
from engine.fvg_poi import detect_fvg_htf, fvg_for_bos

warnings.simplefilter("ignore")


def _frame_fvg_alcista_con_bos() -> pd.DataFrame:
    """OHLC sintético: rango, FVG alcista de ruptura (idx 5) y BOS alcista."""
    rows = [
        # o, h, l, c
        (100.0, 101.0, 99.0, 100.5),
        (100.5, 101.5, 100.0, 101.0),
        (101.0, 102.0, 100.5, 101.5),
        (101.5, 102.0, 101.0, 101.2),
        # idx 4: vela de desplazamiento
        (101.2, 106.5, 101.1, 102.9),
        # idx 5: FVG ALCISTA -> low(105.0) > high(idx3)=102.0
        (105.0, 107.0, 105.0, 106.5),
        (106.5, 108.0, 106.0, 107.5),
        (107.5, 109.0, 107.0, 108.5),
        (108.5, 110.0, 108.0, 109.5),
    ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


BULL_BIAS = HtfBias(d1="BULLISH", h4="BULLISH", h1="BULLISH")
BEAR_BIAS = HtfBias(d1="BEARISH", h4="BEARISH", h1="BEARISH")
NEUTRAL_BIAS = HtfBias(d1="NEUTRAL", h4="NEUTRAL", h1="NEUTRAL")


def test_engine_fvg_detecta_gap_alcista():
    """El FVG alcista sintético se detecta en el índice esperado con sus límites."""
    out = detect_fvg_htf(_frame_fvg_alcista_con_bos(), BULL_BIAS)
    assert bool(out["fvg_bullish"].iloc[5]) is True
    assert float(out["fvg_bottom"].iloc[5]) == pytest.approx(102.0)
    assert float(out["fvg_top"].iloc[5]) == pytest.approx(105.0)
    assert float(out["fvg_size"].iloc[5]) == pytest.approx(3.0)
    assert float(out["fvg_mid"].iloc[5]) == pytest.approx(103.5)
    for col in ("fvg_bullish", "fvg_bearish", "fvg_mid", "fvg_size", "fvg_fill_status"):
        assert col in out.columns


def test_engine_fvg_anchored_con_sesgo_bullish():
    """Sesgo BULLISH + FVG alcista -> fvg_anchored_htf True."""
    out = detect_fvg_htf(_frame_fvg_alcista_con_bos(), BULL_BIAS)
    assert bool(out["fvg_anchored_htf"].iloc[5]) is True
    assert int(out["fvg_anchored_htf"].sum()) == int(out["fvg_bullish"].sum())


def test_engine_fvg_no_anchored_con_sesgo_bearish():
    """Sesgo BEARISH + FVG alcista -> anchored False (contra narrativa)."""
    out = detect_fvg_htf(_frame_fvg_alcista_con_bos(), BEAR_BIAS)
    assert bool(out["fvg_anchored_htf"].iloc[5]) is False
    assert int(out["fvg_anchored_htf"].sum()) == 0


def test_engine_fvg_neutral_no_ancla_nada():
    """Sesgo NEUTRAL -> ningún FVG anclado."""
    out = detect_fvg_htf(_frame_fvg_alcista_con_bos(), NEUTRAL_BIAS)
    assert int(out["fvg_anchored_htf"].sum()) == 0


def test_engine_fvg_for_bos_encuentra_gap_previo():
    """fvg_for_bos localiza el FVG anterior al BOS alcista y lo marca anclado."""
    frame = _frame_fvg_alcista_con_bos()
    poi = fvg_for_bos(frame, {"index": 7, "direction": "BULLISH"}, BULL_BIAS)
    assert poi is not None
    assert poi["fvg_index"] == 5
    assert poi["fvg_top"] == pytest.approx(105.0)
    assert poi["fvg_bottom"] == pytest.approx(102.0)
    assert poi["anchored"] is True
    assert isinstance(poi["fvg_status"], str)


def test_engine_fvg_for_bos_acepta_clave_i_y_bos_dir():
    """Acepta 'i' como índice y bos_dir numérico como dirección."""
    frame = _frame_fvg_alcista_con_bos()
    poi = fvg_for_bos(frame, {"i": 7, "bos_dir": 1}, BULL_BIAS)
    assert poi is not None and poi["fvg_index"] == 5


def test_engine_fvg_for_bos_sin_gap_en_direccion_devuelve_none():
    """No hay FVG bajista previo -> None. Y evento None -> None."""
    frame = _frame_fvg_alcista_con_bos()
    assert fvg_for_bos(frame, {"index": 8, "direction": "BEARISH"}, BEAR_BIAS) is None
    assert fvg_for_bos(frame, None, BULL_BIAS) is None
    assert fvg_for_bos(frame, {"direction": "BULLISH"}, BULL_BIAS) is None


def test_engine_fvg_frame_corto_no_rompe():
    """Frame con menos de 3 velas: contrato de columnas intacto, sin FVG."""
    short = pd.DataFrame(
        [(100.0, 101.0, 99.0, 100.5), (100.5, 101.5, 100.0, 101.0)],
        columns=["open", "high", "low", "close"],
    )
    out = detect_fvg_htf(short, BULL_BIAS)
    assert int(out["fvg_bullish"].sum()) == 0
    assert int(out["fvg_anchored_htf"].sum()) == 0

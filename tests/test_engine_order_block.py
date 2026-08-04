"""Tests del módulo engine/order_block.py — OB anclado a narrativa HTF (Deuda 2)."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from engine.bias.narrative import HtfBias
from engine.order_block import detect_order_blocks_htf, order_block_for_bos

warnings.simplefilter("ignore")


def _frame_ob_alcista_con_bos() -> pd.DataFrame:
    """OHLC sintético: acumulación, OB alcista (vela bajista de cuerpo fuerte),
    desplazamiento al alza que rompe el máximo previo (BOS alcista)."""
    rows = [
        # o, h, l, c
        (100.0, 101.0, 99.0, 100.5),
        (100.5, 101.5, 100.0, 101.0),
        (101.0, 102.0, 100.5, 101.5),
        (101.5, 102.0, 101.0, 101.2),
        # idx 4: OB ALCISTA -> vela bajista, cuerpo >70% del rango
        (101.2, 101.3, 99.2, 99.3),
        # idx 5: follow-through, cierra por encima del high del OB
        (99.4, 104.0, 99.4, 103.8),
        (103.8, 105.5, 103.5, 105.2),
        (105.2, 106.5, 105.0, 106.2),
        (106.2, 107.0, 105.8, 106.8),
    ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


BULL_BIAS = HtfBias(d1="BULLISH", h4="BULLISH", h1="BULLISH")
BEAR_BIAS = HtfBias(d1="BEARISH", h4="BEARISH", h1="BEARISH")
NEUTRAL_BIAS = HtfBias(d1="NEUTRAL", h4="NEUTRAL", h1="NEUTRAL")


def test_engine_ob_htf_detecta_ob_alcista():
    """El OB alcista sintético se detecta en el índice esperado."""
    out = detect_order_blocks_htf(_frame_ob_alcista_con_bos(), BULL_BIAS)
    assert bool(out["ob_bullish"].iloc[4]) is True
    assert float(out["ob_top"].iloc[4]) == pytest.approx(101.3)
    assert float(out["ob_bottom"].iloc[4]) == pytest.approx(99.2)
    # Conserva el contrato de columnas.
    for col in ("ob_bullish", "ob_bearish", "ob_top", "ob_bottom", "ob_status"):
        assert col in out.columns


def test_engine_ob_htf_anclado_cuando_sesgo_bullish():
    """Sesgo BULLISH + OB alcista -> ob_anchored_htf True."""
    out = detect_order_blocks_htf(_frame_ob_alcista_con_bos(), BULL_BIAS)
    assert bool(out["ob_anchored_htf"].iloc[4]) is True
    assert out["ob_anchored_htf"].sum() == int(out["ob_bullish"].sum())


def test_engine_ob_htf_no_anclado_con_sesgo_bearish():
    """Sesgo BEARISH + OB alcista -> ob_anchored_htf False (contra narrativa)."""
    out = detect_order_blocks_htf(_frame_ob_alcista_con_bos(), BEAR_BIAS)
    assert bool(out["ob_anchored_htf"].iloc[4]) is False
    assert not out["ob_anchored_htf"].any()


def test_engine_ob_htf_neutral_apaga_todo():
    """Sesgo NEUTRAL -> ningún OB queda anclado (filtro de ruido)."""
    out = detect_order_blocks_htf(_frame_ob_alcista_con_bos(), NEUTRAL_BIAS)
    assert not out["ob_anchored_htf"].any()


def test_engine_ob_para_bos_encuentra_el_ob_previo():
    """Dado un BOS alcista, devuelve el OB alcista inmediatamente anterior."""
    frame = _frame_ob_alcista_con_bos()
    bos = {"index": 6, "direction": "BULLISH"}
    res = order_block_for_bos(frame, bos, BULL_BIAS)
    assert res is not None
    assert res["ob_index"] == 4
    assert res["ob_top"] == pytest.approx(101.3)
    assert res["ob_bottom"] == pytest.approx(99.2)
    assert res["anchored"] is True
    assert res["ob_status"] in ("active", "invalidated")


def test_engine_ob_para_bos_acepta_clave_i_y_bos_dir():
    """Acepta el formato alternativo del evento ('i' + bos_dir=±1)."""
    frame = _frame_ob_alcista_con_bos()
    res = order_block_for_bos(frame, {"i": 6, "bos_dir": 1}, BULL_BIAS)
    assert res is not None and res["ob_index"] == 4


def test_engine_ob_para_bos_sin_ob_previo_devuelve_none():
    """BOS bajista sin OB bajista previo -> None."""
    frame = _frame_ob_alcista_con_bos()
    assert order_block_for_bos(frame, {"index": 6, "direction": "BEARISH"}, BULL_BIAS) is None
    # BOS antes de que exista el OB.
    assert order_block_for_bos(frame, {"index": 2, "direction": "BULLISH"}, BULL_BIAS) is None
    assert order_block_for_bos(frame, None, BULL_BIAS) is None


def test_engine_ob_para_bos_no_anclado_si_sesgo_opuesto():
    """El OB se encuentra igual, pero anchored=False si el sesgo no acompaña."""
    res = order_block_for_bos(
        _frame_ob_alcista_con_bos(), {"index": 6, "direction": "BULLISH"}, BEAR_BIAS
    )
    assert res is not None
    assert res["anchored"] is False

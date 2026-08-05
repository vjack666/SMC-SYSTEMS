"""Tests de engine/htf_narrative.py — Narrativa Unificada HTF (Deuda 5)."""

from __future__ import annotations

import warnings

import pandas as pd

from engine.htf_narrative import build_htf_narrative, narrative_ready_for_trade

warnings.simplefilter("ignore")


def _ohlc(closes: list[float], start: float = 99.0) -> pd.DataFrame:
    """OHLC sintético coherente a partir de una serie de cierres."""
    opens, highs, lows = [], [], []
    prev = start
    for c in closes:
        opens.append(prev)
        highs.append(max(prev, c) + 1.0)
        lows.append(min(prev, c) - 1.0)
        prev = c
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, dtype=float
    )


def _frame_narrativa_alcista() -> pd.DataFrame:
    # Tendencia alcista clara (HH/HL) y pullback final -> precio en discount.
    closes = [
        100, 101, 103, 102, 105, 107, 106, 110, 112, 111,
        115, 118, 117, 122, 125, 124, 128, 131, 130, 120, 118,
    ]
    return _ohlc([float(c) for c in closes])


def _frame_narrativa_rango() -> pd.DataFrame:
    # Rango estrecho alternante -> sin sesgo direccional utilizable.
    closes = [100.0, 100.2, 100.0, 100.2, 100.0, 100.2, 100.0, 100.2]
    return _ohlc(closes, start=100.1)


def test_htf_narrative_estructura_del_dict():
    narr = build_htf_narrative(_frame_narrativa_alcista())
    esperado = {"bias", "is_favorable", "zone", "liquidity_target", "poi", "summary"}
    assert esperado <= set(narr)
    assert isinstance(narr["summary"], str) and narr["summary"]


def test_htf_narrative_bullish_discount_ready_para_operar():
    frame = _frame_narrativa_alcista()
    # pasamos los TF padre (mismo frame como proxy) para que el ancla se evalue
    htf_frames = {"D1": frame, "H4": frame, "H1": frame}
    narr = build_htf_narrative(frame, htf_frames=htf_frames)
    assert narr["bias"] == "BULLISH"
    assert narr["is_favorable"] is True
    assert narr["zone"] in ("DISCOUNT", "OTE_LONG")
    assert narr["liquidity_target"]["side"] == "BSL"
    assert narr["poi"] is not None
    # el POI ahora lleva marca de ancla (bool) cuando se pasan TF padre
    assert "anchored" in narr["poi"]
    assert isinstance(narr["poi"]["anchored"], bool)
    assert narrative_ready_for_trade(narr) is True


def test_htf_narrative_summary_es_legible_en_espanol():
    narr = build_htf_narrative(_frame_narrativa_alcista())
    summary = narr["summary"]
    assert summary.startswith("Sesgo BULLISH")
    assert "BSL" in summary
    assert "POI" in summary


def test_htf_narrative_rango_no_esta_listo():
    narr = build_htf_narrative(_frame_narrativa_rango())
    assert narrative_ready_for_trade(narr) is False
    assert narr["summary"]


def test_htf_narrative_frame_vacio_no_rompe():
    vacio = pd.DataFrame(columns=["open", "high", "low", "close"], dtype=float)
    narr = build_htf_narrative(vacio)
    assert narr["bias"] == "NEUTRAL"
    assert narr["poi"] is None
    assert narrative_ready_for_trade(narr) is False


def test_htf_narrative_ready_exige_las_cuatro_condiciones():
    base = {
        "bias": "BULLISH",
        "is_favorable": True,
        "zone": "DISCOUNT",
        "liquidity_target": {"side": "BSL", "level": 1.085, "distance": 0.001},
        "poi": {"ob_top": 1.0735, "ob_bottom": 1.072, "anchored": True},
        "summary": "x",
    }
    assert narrative_ready_for_trade(base) is True
    assert narrative_ready_for_trade({**base, "bias": "NEUTRAL"}) is False
    assert narrative_ready_for_trade({**base, "is_favorable": False}) is False
    assert narrative_ready_for_trade({**base, "poi": None}) is False
    assert (
        narrative_ready_for_trade({**base, "liquidity_target": {"side": "NONE"}})
        is False
    )
    assert narrative_ready_for_trade({}) is False

"""Tests del módulo engine/liquidity_levels.py (Deuda 4: liquidez BSL/SSL)."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from engine.liquidity_levels import detect_liquidity_htf, nearest_liquidity_target

warnings.simplefilter("ignore")


class _FakeBias:
    """Doble de HtfBias: solo expone .direction/.aligned."""

    def __init__(self, direction: str) -> None:
        self.direction = direction
        self.aligned = direction != "NEUTRAL"


def _frame_pico_y_valle() -> pd.DataFrame:
    # Serie sintética: máximo claro arriba (122) y mínimo claro abajo (85)
    closes = [100, 105, 110, 120, 115, 110, 105, 90, 95, 100]
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    highs[3] = 122.0  # pico
    lows[7] = 85.0    # valle
    return pd.DataFrame(
        {
            "high": np.array(highs, dtype="float64"),
            "low": np.array(lows, dtype="float64"),
            "close": np.array(closes, dtype="float64"),
        }
    )


def test_engine_liq_levels_columnas_y_target_bullish():
    frame = _frame_pico_y_valle()
    out = detect_liquidity_htf(frame, _FakeBias("BULLISH"), left=3)
    assert {"bsl_level", "ssl_level", "target_liquidity"} <= set(out.columns)
    assert (out["target_liquidity"] == "BSL").all()
    assert len(out) == len(frame)


def test_engine_liq_levels_target_bearish_y_neutral():
    frame = _frame_pico_y_valle()
    assert (
        detect_liquidity_htf(frame, _FakeBias("BEARISH"))["target_liquidity"] == "SSL"
    ).all()
    assert (
        detect_liquidity_htf(frame, _FakeBias("NEUTRAL"))["target_liquidity"] == "NONE"
    ).all()


def test_engine_liq_levels_niveles_respetan_geometria():
    frame = _frame_pico_y_valle()
    out = detect_liquidity_htf(frame, _FakeBias("BULLISH"), left=3)
    bsl = out.dropna(subset=["bsl_level"])
    ssl = out.dropna(subset=["ssl_level"])
    # BSL siempre por encima del close; SSL siempre por debajo
    assert (bsl["bsl_level"] > bsl["close"]).all()
    assert (ssl["ssl_level"] < ssl["close"]).all()
    # sin look-ahead: las primeras `left` velas no tienen nivel
    assert out["bsl_level"].iloc[:3].isna().all()
    assert out["ssl_level"].iloc[:3].isna().all()


def test_engine_liq_levels_nearest_bullish_apunta_arriba():
    frame = _frame_pico_y_valle()
    res = nearest_liquidity_target(frame, _FakeBias("BULLISH"), left=3)
    close = float(frame["close"].iloc[-1])
    assert res["side"] == "BSL"
    assert res["level"] is not None and res["level"] > close
    assert res["distance"] == pytest.approx(abs(res["level"] - close))


def test_engine_liq_levels_nearest_bearish_apunta_abajo():
    frame = _frame_pico_y_valle()
    res = nearest_liquidity_target(frame, _FakeBias("BEARISH"), left=3)
    close = float(frame["close"].iloc[-1])
    assert res["side"] == "SSL"
    assert res["level"] is not None and res["level"] < close
    assert res["distance"] == pytest.approx(abs(res["level"] - close))


def test_engine_liq_levels_neutral_y_vacio():
    frame = _frame_pico_y_valle()
    res = nearest_liquidity_target(frame, _FakeBias("NEUTRAL"))
    assert res == {"side": "NONE", "level": None, "distance": pytest.approx(float("nan"), nan_ok=True)}
    vacio = pd.DataFrame({"high": [], "low": [], "close": []})
    assert nearest_liquidity_target(vacio, _FakeBias("BULLISH"))["side"] == "NONE"
    out = detect_liquidity_htf(vacio, _FakeBias("BULLISH"))
    assert out.empty and "bsl_level" in out.columns


def test_engine_liq_levels_acepta_str_y_valida_entrada():
    frame = _frame_pico_y_valle()
    assert nearest_liquidity_target(frame, "BULLISH")["side"] == "BSL"
    with pytest.raises(ValueError):
        detect_liquidity_htf(frame, "BULLISH", left=0)
    with pytest.raises(KeyError):
        detect_liquidity_htf(frame.drop(columns=["low"]), "BULLISH")

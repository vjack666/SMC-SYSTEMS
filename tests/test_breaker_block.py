"""Breaker Block / MMXM detector — tests (TDD).

Mínimo 10 tests: unitarios de is_breaker_block + call site real con datos
sintéticos que cubran bullish / bearish / mitigación.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.setups.breaker_block import (
    is_breaker_block,
    flag_breaker_block,
    _ob_dicts_from_frame,
    _fvgs_from_frame,
)


# ---------------------------------------------------------------------------
# Helpers de frame
# ---------------------------------------------------------------------------
_BASE = pd.Timestamp("2026-01-05 09:00", tz="UTC")


def _base_ohlc(times, base=1.1000, spread=0.0030):
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
    return df


def _frame_with_obs(ob_rows):
    """Crea un frame y marca columnas ob_bullish/ob_bearish/top/bottom según `ob_rows`.

    `ob_rows`: lista de tuplas (idx, type, top, bottom).
    """
    max_idx = max((r[0] for r in ob_rows), default=0)
    times = pd.date_range(_BASE, periods=max_idx + 12, freq="15min", tz="UTC")
    df = _base_ohlc(times, 1.1000)
    df["ob_bullish"] = False
    df["ob_bearish"] = False
    df["ob_top"] = np.nan
    df["ob_bottom"] = np.nan
    for idx, ob_type, top, bottom in ob_rows:
        if ob_type == "bearish":
            df.at[idx, "ob_bearish"] = True
        else:
            df.at[idx, "ob_bullish"] = True
        df.at[idx, "ob_top"] = top
        df.at[idx, "ob_bottom"] = bottom

    # columnas de mercado mínimas por si algo las usa
    from ict_backtest.market_structure import detect_market_structure
    df = detect_market_structure(df)
    return df


# =========================== BULLISH BREAKER ================================
def _build_bullish_breaker_frame() -> pd.DataFrame:
    """bearish OB idx 4 y breakout bullish inequívoco en idx 10.

    Diseño de fixture robusto: velas 5-14 quedan por ENCIMA del OB (low > top)
    para que no falle por mitigación falsa tras detect_market_structure().
    """
    times = pd.date_range(_BASE, periods=25, freq="15min", tz="UTC")
    df = _base_ohlc(times, base=1.1000, spread=0.0010)
    df.loc[4, ["open", "high", "low", "close"]] = 1.0990, 1.1025, 1.0985, 1.1024
    df.loc[4, "ob_bearish"] = True
    df.loc[4, "ob_top"] = 1.1025
    df.loc[4, "ob_bottom"] = 1.0990
    # idx 10: breakout bullish explícito
    df.loc[10, ["open", "high", "low", "close"]] = 1.1026, 1.1035, 1.1024, 1.1034
    # Todas las velas tras el OB (5..24) quedan por ENCIMA de la zona del OB:
    # low (1.1030) > top (1.1025) => breakout válido y SIN mitigación (MMXM=1 toque).
    df.loc[5:24, ["open", "high", "low", "close"]] = 1.1030, 1.1040, 1.1030, 1.1036
    return df


# =========================== BEARISH BREAKER =================================
def _build_bearish_breaker_frame():
    """bullish OB idx 4 (top=1.1050, bottom=1.1020). Rotura bearish en idx 9."""
    return _frame_with_obs([
        (4, "bullish", 1.1050, 1.1020),
    ])


# =========================== MITIGATED BREAKER ================================
def _build_mitigated_breaker_frame():
    """bearish OB idx 4, rotura idx 10, mitigación idx 11."""
    df = _frame_with_obs([
        (4, "bearish", 1.1025, 1.0990),
    ])
    # idx 11: close entra en la zona del breaker (1.0990..1.1025)
    df.at[11, "open"] = 1.1015
    df.at[11, "close"] = 1.1018
    df.at[11, "high"] = 1.1022
    df.at[11, "low"] = 1.1010
    return df


# =========================== SIN OB ==========================================
def _build_no_ob_frame():
    times = pd.date_range(_BASE, periods=8, freq="15min", tz="UTC")
    return _base_ohlc(times, 1.1000)


# =========================== HELPERS DE OB/FVG ==============================
def _fake_obs_from_rows(ob_rows):
    return [
        {
            "type": ob_type,
            "top": top,
            "bottom": bottom,
            "start_idx": idx,
            "end_idx": idx,
        }
        for idx, ob_type, top, bottom in ob_rows
    ]


# ---------------------------------------------------------------------------
# Tests unitarios is_breaker_block
# ---------------------------------------------------------------------------
def test_no_breaker_when_no_obs():
    df = _build_no_ob_frame()
    res = is_breaker_block(df, 4, [], [])
    assert res["breaker_active"] is False
    assert res["breaker_type"] is None
    assert res["strength"] == 0.0


def test_bullish_breaker_from_bearish_ob():
    df = _build_bullish_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    # idx 10: close 1.1035 > top 1.1025 -> bullish breaker
    df.at[10, "close"] = 1.1035
    res = is_breaker_block(df, 10, [], obs)
    assert res["breaker_active"] is True, res
    assert res["breaker_type"] == "bullish"
    assert res["mitigation_level"] > 1.1024
    assert 0.0 <= res["strength"] <= 1.0


def test_bearish_breaker_from_bullish_ob():
    df = _build_bearish_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bullish", 1.1050, 1.1020)])
    # idx 9: close 1.1015 < bottom 1.1020 -> bearish breaker
    df.at[9, "close"] = 1.1015
    res = is_breaker_block(df, 9, [], obs)
    assert res["breaker_active"] is True, res
    assert res["breaker_type"] == "bearish"
    assert res["mitigation_level"] < 1.1021
    assert 0.0 <= res["strength"] <= 1.0


def test_strength_bounded():
    df = _build_bullish_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    df.at[10, "close"] = 1.1035
    res = is_breaker_block(df, 10, [], obs)
    assert 0.0 <= res["strength"] <= 1.0


def test_returns_none_on_invalid_index():
    df = _build_no_ob_frame()
    res = is_breaker_block(df, 999, [], [])
    assert res["breaker_active"] is False


def test_no_breaker_when_close_inside_ob():
    df = _build_bullish_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    # close no sale del OB -> False
    res = is_breaker_block(df, 4, [], obs)
    assert res["breaker_active"] is False


# ---------------------------------------------------------------------------
# Mitigación MMXM
# ---------------------------------------------------------------------------
def test_breaker_disappears_after_mitigation():
    df = _build_mitigated_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    # current_idx 12 más allá de la mitigación en 11
    res = is_breaker_block(df, 12, [], obs)
    assert res["breaker_active"] is False


def test_no_false_breaker_before_rotation():
    df = _build_bullish_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    # idx 4 es justo el OB; close == base (1.1000) dentro del rango, no roto
    res = is_breaker_block(df, 4, [], obs)
    assert res["breaker_active"] is False


# ---------------------------------------------------------------------------
# Helpers del módulo
# ---------------------------------------------------------------------------
def test_ob_dicts_from_frame_extracts_rows():
    df = _build_bullish_breaker_frame()
    recs = _ob_dicts_from_frame(df)
    assert any(r["type"] == "bearish" for r in recs)
    bear = next(r for r in recs if r["type"] == "bearish")
    assert bear["top"] == pytest.approx(1.1025)
    assert bear["bottom"] == pytest.approx(1.0990)
    assert bear["start_idx"] == 4


def test_fvgs_from_frame_extracts_bullish():
    df = _build_no_ob_frame()
    recs = _fvgs_from_frame(df)
    assert recs == []


# ---------------------------------------------------------------------------
# Call-site con flag_breaker_block sobre un stub de señal
# ---------------------------------------------------------------------------
class _FakeSignal:
    def __init__(self, entry_at, direction):
        self.entry_at = entry_at
        self.direction = direction


def test_call_site_flag_bullish_breaker():
    df = _build_bullish_breaker_frame()
    df.at[10, "close"] = 1.1035
    frames = {"D1": df, "H4": df, "H1": df, "M15": df}
    sigs = [_FakeSignal(entry_at=10, direction=1)]
    out = flag_breaker_block(sigs, frames, ltf="M15")
    assert out is sigs
    assert sigs[0].breaker_active is True
    assert sigs[0].breaker_type == "bullish"
    assert sigs[0].mitigation_level > 1.1024
    assert 0.0 <= sigs[0].breaker_strength <= 1.0


def test_call_site_flag_bearish_breaker():
    df = _build_bearish_breaker_frame()
    df.at[9, "close"] = 1.1015
    frames = {"D1": df, "H4": df, "H1": df, "M15": df}
    sigs = [_FakeSignal(entry_at=9, direction=-1)]
    out = flag_breaker_block(sigs, frames, ltf="M15")
    assert out is sigs
    assert sigs[0].breaker_active is True
    assert sigs[0].breaker_type == "bearish"
    assert sigs[0].mitigation_level < 1.1021


def test_call_site_flag_mitigated_breaker():
    df = _build_mitigated_breaker_frame()
    obs = _fake_obs_from_rows([(4, "bearish", 1.1025, 1.0990)])
    frames = {"D1": df, "H4": df, "H1": df, "M15": df}
    sigs = [_FakeSignal(entry_at=12, direction=1)]
    out = flag_breaker_block(sigs, frames, ltf="M15")
    assert out is sigs
    assert sigs[0].breaker_active is False
    assert sigs[0].breaker_type is None
    assert sigs[0].mitigation_level is None
    assert sigs[0].breaker_strength == 0.0


def test_call_site_no_false_breaker():
    df = _build_no_ob_frame()
    frames = {"D1": df, "H4": df, "H1": df, "M15": df}
    sigs = [_FakeSignal(entry_at=4, direction=1)]
    out = flag_breaker_block(sigs, frames, ltf="M15")
    assert out is sigs
    assert sigs[0].breaker_active is False
    assert sigs[0].breaker_type is None
    assert sigs[0].breaker_strength == 0.0

"""Tests BPR: solape, invalidación y decay temporal de score."""
from __future__ import annotations

import pandas as pd
import pytest

from ict_backtest.bpr import (
    BprConfig,
    bpr_score_at_age,
    detect_bpr,
    overlap_interval,
    validate_bpr_invalidation,
)


def test_overlap_interval_basic():
    assert overlap_interval(1.0, 2.0, 1.5, 2.5) == (1.5, 2.0)
    assert overlap_interval(1.0, 2.0, 2.0, 3.0) is None
    assert overlap_interval(1.0, 2.0, 3.0, 4.0) is None
    assert overlap_interval(1.0, 5.0, 2.0, 3.0) == (2.0, 3.0)


def test_bpr_score_at_age_half_life():
    assert bpr_score_at_age(0, base=1.0, half_life_bars=10, floor=0.1) == pytest.approx(1.0)
    assert bpr_score_at_age(10, base=1.0, half_life_bars=10, floor=0.1) == pytest.approx(0.5)
    assert bpr_score_at_age(20, base=1.0, half_life_bars=10, floor=0.1) == pytest.approx(0.25)
    # floor
    assert bpr_score_at_age(1000, base=1.0, half_life_bars=10, floor=0.15) == pytest.approx(0.15)
    # frozen
    assert bpr_score_at_age(50, base=1.0, half_life_bars=10, floor=0.1, frozen=True, frozen_score=0.7) == pytest.approx(0.7)


def _ohlc_row(o, h, l, c, **extra):
    d = {"open": o, "high": h, "low": l, "close": c}
    d.update(extra)
    return d


def _bpr_lifecycle_rows(n_active: int = 5):
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
    ]
    # barras lejos del BPR (sin tocar, sin invalidar): high/low por encima
    for _ in range(n_active):
        rows.append(_ohlc_row(1.15, 1.16, 1.145, 1.15))
    return rows


def test_bpr_created_on_fvg_ob_overlap():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.095, 1.12, 1.09, 1.11),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
    ]
    rows[1]["ob_bullish"] = True
    rows[1]["ob_bearish"] = False
    rows[1]["open"] = 1.14
    rows[1]["close"] = 1.12
    rows[1]["high"] = 1.145
    rows[1]["low"] = 1.115
    rows[1]["ob_status"] = "active"

    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5, use_ob_body=True))
    assert bool(out.loc[2, "bpr_bullish"])
    assert out.loc[2, "bpr_status"] == "just_created"
    assert abs(float(out.loc[2, "bpr_low"]) - 1.12) < 1e-9
    assert abs(float(out.loc[2, "bpr_high"]) - 1.14) < 1e-9
    assert out.loc[2, "pd_type"] == "BPR"
    assert float(out.loc[2, "bpr_score"]) == pytest.approx(1.0)


def test_no_bpr_without_overlap():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.05, 1.06, 1.04, 1.05, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
    ]
    rows[1]["open"] = 1.055
    rows[1]["close"] = 1.045
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert not bool(out.loc[2, "bpr_bullish"])
    assert out.loc[2, "bpr_status"] == "none"
    assert float(out.loc[2, "bpr_score"]) == 0.0


def test_bpr_invalidation_on_close_beyond():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
        _ohlc_row(1.15, 1.16, 1.13, 1.14),
        _ohlc_row(1.13, 1.135, 1.10, 1.11),
    ]
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert out.loc[2, "bpr_status"] == "just_created"
    assert out.loc[3, "bpr_status"] in ("active", "mitigated_touch")
    assert out.loc[4, "bpr_status"] == "invalidated"
    assert float(out.loc[4, "bpr_score"]) == 0.0
    report = validate_bpr_invalidation(out)
    assert report["ok"], report["violations"]


def test_mitigated_touch_without_invalidation():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
        _ohlc_row(1.145, 1.15, 1.125, 1.14),
    ]
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert out.loc[3, "bpr_status"] == "mitigated_touch"
    assert float(out.loc[3, "bpr_score"]) > 0.0
    report = validate_bpr_invalidation(out)
    assert report["ok"], report["violations"]


def test_score_decays_with_age_not_invalidate():
    """Edad baja el score pero NO invalida por tiempo."""
    rows = _bpr_lifecycle_rows(n_active=10)
    cfg = BprConfig(lookback=5, half_life_bars=10, score_base=1.0, score_floor=0.15)
    out = detect_bpr(pd.DataFrame(rows), cfg)
    assert out.loc[2, "bpr_status"] == "just_created"
    assert float(out.loc[2, "bpr_score"]) == pytest.approx(1.0)
    # age=10 → half life → ~0.5
    assert out.loc[12, "bpr_status"] == "active"
    assert int(out.loc[12, "bpr_age"]) == 10
    assert float(out.loc[12, "bpr_score"]) == pytest.approx(0.5)
    # monótono no creciente
    scores = [float(out.loc[i, "bpr_score"]) for i in range(2, 13)]
    assert all(scores[k] >= scores[k + 1] - 1e-12 for k in range(len(scores) - 1))
    report = validate_bpr_invalidation(out, cfg=cfg)
    assert report["ok"], report["violations"]


def test_score_hits_floor_still_active():
    rows = _bpr_lifecycle_rows(n_active=100)
    cfg = BprConfig(lookback=5, half_life_bars=5, score_floor=0.2, score_base=1.0)
    out = detect_bpr(pd.DataFrame(rows), cfg)
    last = out.index[-1]
    assert out.loc[last, "bpr_status"] == "active"
    assert float(out.loc[last, "bpr_score"]) == pytest.approx(0.2)


def test_validate_report_counts():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
        _ohlc_row(1.15, 1.16, 1.13, 1.14),
        _ohlc_row(1.13, 1.135, 1.10, 1.11),
    ]
    out = detect_bpr(pd.DataFrame(rows), BprConfig(lookback=5))
    report = validate_bpr_invalidation(out)
    assert "just_created" in report["counts"]
    assert "invalidated" in report["counts"]
    assert report["n_violations"] == 0

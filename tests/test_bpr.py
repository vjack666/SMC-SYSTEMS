"""Tests BPR: solape geométrico + máquina de estados de invalidación."""
from __future__ import annotations

import pandas as pd

from ict_backtest.bpr import (
    BprConfig,
    detect_bpr,
    overlap_interval,
    validate_bpr_invalidation,
)


def test_overlap_interval_basic():
    assert overlap_interval(1.0, 2.0, 1.5, 2.5) == (1.5, 2.0)
    assert overlap_interval(1.0, 2.0, 2.0, 3.0) is None  # roce, no estricto
    assert overlap_interval(1.0, 2.0, 3.0, 4.0) is None
    assert overlap_interval(1.0, 5.0, 2.0, 3.0) == (2.0, 3.0)


def _ohlc_row(o, h, l, c, **extra):
    d = {"open": o, "high": h, "low": l, "close": c}
    d.update(extra)
    return d


def test_bpr_created_on_fvg_ob_overlap():
    """FVG bull gap [1.10, 1.15] y OB cuerpo [1.12, 1.14] → BPR."""
    rows = [
        # i-2 high=1.10 → techo inferior del gap bull
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.095, 1.12, 1.09, 1.11),  # displacement
        # i: low=1.15 → FVG bull; también marcamos OB bull en barra previa estilo simple
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
    ]
    # Insertar OB en barra 1 (cuerpo solapa gap)
    rows[1]["ob_bullish"] = True
    rows[1]["ob_bearish"] = False
    rows[1]["open"] = 1.14
    rows[1]["close"] = 1.12  # cuerpo [1.12, 1.14]
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
    assert out.loc[2, "pd_tier"] == "T1"


def test_no_bpr_without_overlap():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.05, 1.06, 1.04, 1.05, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
    ]
    # OB cuerpo lejos del gap [1.10, 1.15]
    rows[1]["open"] = 1.055
    rows[1]["close"] = 1.045
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert not bool(out.loc[2, "bpr_bullish"])
    assert out.loc[2, "bpr_status"] == "none"


def test_bpr_invalidation_on_close_beyond():
    """BPR bull active → close debajo de bpr_low → invalidated."""
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
        # active bars
        _ohlc_row(1.15, 1.16, 1.13, 1.14),
        # invalidate: close below bpr_low (~1.12)
        _ohlc_row(1.13, 1.135, 1.10, 1.11),
    ]
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert out.loc[2, "bpr_status"] == "just_created"
    assert out.loc[3, "bpr_status"] in ("active", "mitigated_touch")
    assert out.loc[4, "bpr_status"] == "invalidated"

    report = validate_bpr_invalidation(out)
    assert report["ok"], report["violations"]


def test_mitigated_touch_without_invalidation():
    rows = [
        _ohlc_row(1.09, 1.10, 1.08, 1.095),
        _ohlc_row(1.14, 1.145, 1.115, 1.12, ob_bullish=True, ob_bearish=False, ob_status="active"),
        _ohlc_row(1.14, 1.16, 1.15, 1.155, fvg_bullish=True, fvg_bearish=False),
        # toca el BPR [1.12, 1.14] sin cerrar debajo
        _ohlc_row(1.145, 1.15, 1.125, 1.14),
    ]
    df = pd.DataFrame(rows)
    out = detect_bpr(df, BprConfig(lookback=5))
    assert out.loc[3, "bpr_status"] == "mitigated_touch"
    report = validate_bpr_invalidation(out)
    assert report["ok"], report["violations"]


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

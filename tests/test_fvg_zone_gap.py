from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from detectors.fvg import detect_fvg
from ict_backtest.market_object import MarketObject, ObjectType, Role


def _obj(meta, direction=0, role=None):
    return MarketObject(
        type=ObjectType.CANDLE,
        role=role or Role.REFINEMENT,
        origin_tf="M5",
        direction=direction,
        meta=meta,
    )
from ict_backtest.sequence import _latest_fvg_zone, _latest_ob_zone, _touches_zone


def _frame(time, o, h, l, c):
    return pd.DataFrame({
        "time": pd.to_datetime(time, utc=True),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "tick_volume": [1] * len(time),
    })


def test_fvg_bullish_gap_edges_are_gap_not_impulse_candle():
    # 3-candle bull FVG: low_i > high_{i-2}
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],  # low_i=1.1055 > high_{i-2}=1.1010
        [1.1005, 1.1015, 1.1058],
    )
    out = detect_fvg(df)
    assert bool(out.loc[2, "fvg_bullish"]) is True
    assert out.loc[2, "fvg_zone_low"] == pytest.approx(1.1010)
    assert out.loc[2, "fvg_zone_high"] == pytest.approx(1.1055)
    assert out.loc[2, "fvg_mid"] == pytest.approx((1.1010 + 1.1055) / 2)


def test_fvg_bearish_gap_edges_are_gap_not_impulse_candle():
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1060, 1.1050, 1.0990],
        [1.1070, 1.1060, 1.1000],
        [1.1055, 1.1045, 1.0985],  # high_i=1.1000 < low_{i-2}=1.1055
        [1.1058, 1.1048, 1.0988],
    )
    out = detect_fvg(df)
    assert bool(out.loc[2, "fvg_bearish"]) is True
    assert out.loc[2, "fvg_zone_low"] == pytest.approx(1.1000)
    assert out.loc[2, "fvg_zone_high"] == pytest.approx(1.1055)
    assert out.loc[2, "fvg_mid"] == pytest.approx((1.1000 + 1.1055) / 2)


def test_latest_fvg_zone_returns_gap_not_impulse_high_low():
    # sequence helper must use fvg_zone_*, not meta.high/meta.low
    obj = _obj({
        "fvg_bullish": True,
        "fvg_zone_low": 1.1010,
        "fvg_zone_high": 1.1055,
        "high": 1.1060,
        "low": 1.1055,
    })
    zone = _latest_fvg_zone(obj, 1)
    assert zone == pytest.approx((1.1055, 1.1010))


def test_touches_zone_true_when_price_reaches_gap():
    meta = {"low": 1.1050, "high": 1.1056}
    obj = _obj(meta)
    zone_high, zone_low = 1.1055, 1.1010
    assert _touches_zone(obj, zone_high, zone_low) is True


def test_touches_zone_false_when_only_wick_outside_gap():
    # wick above gap, but low still below zone_low and high above zone_high
    # actually this still intersects the interval [zone_low, zone_high]
    # For false, candle must be completely outside the zone.
    meta = {"low": 1.1005, "high": 1.1008}
    obj = _obj(meta)
    zone_high, zone_low = 1.1010, 1.1055
    assert _touches_zone(obj, zone_high, zone_low) is False


def test_latest_fvg_zone_none_when_gap_fields_missing():
    meta = {"fvg_bullish": True, "high": 1.1060, "low": 1.1055}
    obj = _obj(meta)
    assert _latest_fvg_zone(obj, 1) is None

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ict_backtest.fvg_authority import FvgAuthorityResult, rank_fvg


def _frame(time, o, h, l, c, fvg_bullish=None, fvg_bearish=None, fvg_mid=None,
           bos_dir=None, choch_dir=None):
    n = len(time)
    data = {
        "time": pd.to_datetime(time, utc=True),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "tick_volume": [1] * n,
        "fvg_bullish": fvg_bullish or [False] * n,
        "fvg_bearish": fvg_bearish or [False] * n,
        "fvg_mid": fvg_mid or [np.nan] * n,
        "bos_dir": bos_dir or [0] * n,
        "choch_dir": choch_dir or [0] * n,
    }
    df = pd.DataFrame(data)
    if "fvg_zone_low" not in df.columns:
        df["fvg_zone_low"] = np.where(df["fvg_bullish"], df["high"].shift(2).fillna(df["high"]), np.nan)
        df["fvg_zone_high"] = np.where(df["fvg_bullish"], df["low"], np.nan)
        df["fvg_zone_low"] = np.where(df["fvg_bearish"], df["high"], df["fvg_zone_low"])
        df["fvg_zone_high"] = np.where(df["fvg_bearish"], df["low"].shift(2).fillna(df["low"]), df["fvg_zone_high"])
    return df


def test_gap_only_returns_s3():
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],
        [1.1005, 1.1015, 1.1058],
        fvg_bullish=[False, False, True],
        fvg_mid=[np.nan, np.nan, 1.10325],
    )
    res = rank_fvg(df, 2, 1)
    assert res.tier == "S3"
    assert res.supreme is False
    assert res.reason == "gap only"


def test_gap_with_displacement_and_same_dir_structure_returns_s2():
    # i=2 FVG bull + strong impulse + bos_dir=1 within lookback => S2.
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z", "2024-01-01 00:15Z", "2024-01-01 00:20Z"],
        [1.1000, 1.1010, 1.1050, 1.1055, 1.1058],
        [1.1010, 1.1020, 1.1070, 1.1075, 1.1080],  # impulse candle at i=2
        [1.0995, 1.1005, 1.1040, 1.1050, 1.1052],  # low[2]=1.1040 > high[0]=1.1010 -> bull FVG
        [1.1005, 1.1015, 1.1063, 1.1053, 1.1055],
        fvg_bullish=[False, False, True, False, False],
        fvg_mid=[np.nan, np.nan, 1.10505, np.nan, np.nan],
        bos_dir=[0, 0, 1, 0, 0],
    )
    # Explicit gap rectangle for the ranker; synthetic helper fallback is not exact here.
    df.loc[2, ["fvg_zone_low", "fvg_zone_high"]] = (1.1010, 1.1040)
    res = rank_fvg(df, 2, 1, displacement_ratio_min=0.5, structure_lookback=10)
    assert res.tier == "S2"
    assert res.displacement_ok is True
    assert res.narrative_ok is True
    assert res.supreme is False
    assert "displacement+narrative" in res.reason


def test_gap_with_ob_overlap_returns_s1():
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],
        [1.1005, 1.1015, 1.1058],
        fvg_bullish=[False, False, True],
        fvg_mid=[np.nan, np.nan, 1.10325],
    )
    ob_zone = (1.1030, 1.1045)
    res = rank_fvg(df, 2, 1, active_ob_zone=ob_zone)
    assert res.tier == "S1"
    assert res.bpr_overlap is True
    assert res.supreme is True
    assert res.depth > 0.0


def test_wrong_direction_returns_none():
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],
        [1.1005, 1.1015, 1.1058],
        fvg_bullish=[False, False, True],
    )
    res = rank_fvg(df, 2, -1)
    assert res.tier == "NONE"
    assert "direction mismatch" in res.reason


def test_missing_zone_fields_returns_none():
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],
        [1.1005, 1.1015, 1.1058],
        fvg_bullish=[False, False, True],
    )
    df.loc[2, ["fvg_zone_low", "fvg_zone_high"]] = (np.nan, np.nan)
    res = rank_fvg(df, 2, 1)
    assert res.tier == "NONE"
    assert "invalid gap rectangle" in res.reason


def test_p2_dealing_side_ok_annotates_quality():
    # EQ=1.1030, FVG bull zone=1.1010-1.1040 -> mid=1.1025 < EQ => side_ok=True.
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z"],
        [1.1000, 1.1010, 1.1050],
        [1.1010, 1.1020, 1.1060],
        [1.0995, 1.1005, 1.1055],
        [1.1005, 1.1015, 1.1058],
        fvg_bullish=[False, False, True],
    )
    df.loc[2, ["fvg_zone_low", "fvg_zone_high", "fvg_mid"]] = (1.1010, 1.1040, 1.1025)
    res = rank_fvg(df, 2, 1, dealing_eq=1.1030)
    assert res.side_ok is True
    assert res.dealing_side_ok is True


def test_p2_stack_count_without_gate_hard_block():
    # 3 FVG bull in lookback including current -> stack_count=2, stack_ok=True.
    # Current tier must stay S3 (no gate), metadata only.
    df = _frame(
        ["2024-01-01 00:00Z", "2024-01-01 00:05Z", "2024-01-01 00:10Z",
         "2024-01-01 00:15Z", "2024-01-01 00:20Z", "2024-01-01 00:25Z", "2024-01-01 00:30Z"],
        [1.1000, 1.1010, 1.1050, 1.1060, 1.1070, 1.1080, 1.1090],
        [1.1010, 1.1020, 1.1060, 1.1070, 1.1080, 1.1090, 1.1100],
        [1.0995, 1.1005, 1.1055, 1.1065, 1.1075, 1.1085, 1.1095],
        [1.1005, 1.1015, 1.1058, 1.1068, 1.1078, 1.1088, 1.1098],
        fvg_bullish=[False, True, False, True, False, True, False],
    )
    for idx in (1, 3, 5):
        df.loc[idx, ["fvg_zone_low", "fvg_zone_high", "fvg_mid"]] = (float(df.loc[idx, "low"]), float(df.loc[idx, "high"]), (float(df.loc[idx, "low"]) + float(df.loc[idx, "high"])) / 2.0)
    res = rank_fvg(df, 5, 1)
    assert res.tier == "S3"
    assert res.stack_count == 2
    assert res.stack_ok is True

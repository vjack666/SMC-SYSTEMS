"""tests/test_engine_b3_iirl_erl.py — IRL/ERL (liquidez interna/externa)."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.fvg_poi import detect_fvg
from engine.liquidity_internal_external import (
    LiquidityModelConfig,
    classify_liquidity,
    volume_confirm,
)


def _candle(o, h, l, c, v=1000.0):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _frame_with_sweep_and_fvg() -> pd.DataFrame:
    rows = []
    # 1) Rango lateral 100-110 (20 velas).
    for i in range(20):
        if i % 2 == 0:
            rows.append(_candle(102, 110, 100, 108))
        else:
            rows.append(_candle(108, 109, 101, 102))
    # 2) Sweep de la BSL (swing high previo = 110) -> ERL externo.
    rows.append(_candle(108, 115, 107, 114, v=5000.0))
    # 3) Desplazamiento bajista que deja un FVG bajista interno.
    rows.append(_candle(114, 114, 112, 112))  # i-2 low = 112
    rows.append(_candle(112, 112, 108, 108))
    rows.append(_candle(108, 105, 103, 104))  # high 105 < 112 -> FVG bajista
    # 4) Retorno al IRL (mid = 108.5) sin llenar el gap (no toca 112).
    rows.append(_candle(104, 109, 103, 108, v=3000.0))
    rows.append(_candle(108, 108.5, 104, 105))
    return pd.DataFrame(rows)


def _frame_without_internal_fvg() -> pd.DataFrame:
    rows = []
    for i in range(20):
        if i % 2 == 0:
            rows.append(_candle(102, 110, 100, 108))
        else:
            rows.append(_candle(108, 109, 101, 102))
    rows.append(_candle(108, 115, 107, 114))
    rows.append(_candle(114, 114, 110, 111))
    rows.append(_candle(111, 113, 109, 110))
    return pd.DataFrame(rows)


def test_erl_sweep_and_irl_target_sequence():
    df = _frame_with_sweep_and_fvg()
    fvg = detect_fvg(df)
    res = classify_liquidity(df, -1, fvg_df=fvg)

    assert res["erl_sweep"] is True
    assert res["erl_level"] is not None
    assert res["irl_target"] is not None
    assert res["irl_fvg_idx"] is not None
    assert res["seq_erl_then_irl"] is True
    # Sin volume_confirm_fn: los ratios no se reportan.
    assert res["erl_volume_ratio"] is None
    assert res["irl_volume_ratio"] is None


def test_no_internal_fvg_gives_none_target():
    df = _frame_without_internal_fvg()
    fvg = detect_fvg(df)
    res = classify_liquidity(df, -1, fvg_df=fvg)

    assert res["erl_sweep"] is True
    assert res["irl_target"] is None
    assert res["irl_fvg_idx"] is None
    assert res["seq_erl_then_irl"] is False


def test_volume_is_reported_but_never_decides():
    df = _frame_with_sweep_and_fvg()
    fvg = detect_fvg(df)

    base = classify_liquidity(df, -1, fvg_df=fvg)
    with_vol = classify_liquidity(df, -1, fvg_df=fvg, volume_confirm_fn=volume_confirm)

    assert with_vol["erl_volume_ratio"] is not None
    assert with_vol["irl_volume_ratio"] is not None
    for key in ("erl_sweep", "erl_level", "irl_target", "irl_fvg_idx", "seq_erl_then_irl"):
        assert base[key] == with_vol[key]


def test_config_min_size_filters_irl():
    df = _frame_with_sweep_and_fvg()
    fvg = detect_fvg(df)
    cfg = LiquidityModelConfig(irl_fvg_min_size=1000.0)
    res = classify_liquidity(df, -1, fvg_df=fvg, config=cfg)
    assert res["irl_target"] is None


def test_empty_frame_is_safe():
    res = classify_liquidity(pd.DataFrame(columns=["open", "high", "low", "close"]), 1)
    assert res["erl_sweep"] is False
    assert res["irl_target"] is None

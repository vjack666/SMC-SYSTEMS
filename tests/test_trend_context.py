from __future__ import annotations

from pathlib import Path

import pytest

from data import load_frame
from trend_context import build_trend_context_frame


@pytest.mark.skipif(
    not Path("data/raw/EURUSD_M15.parquet").exists(),
    reason="requires EURUSD parquet data",
)
def test_build_trend_context_frame_output_columns():
    ltf = load_frame(Path("data/raw"), "EURUSD", "M15").tail(200)
    ctx = build_trend_context_frame("EURUSD", ltf, data_dir=Path("data/raw"))
    for col in ("htf_bias", "ltf_bias", "trend_alignment", "regime_state"):
        assert col in ctx.columns


@pytest.mark.skipif(
    not Path("data/raw/EURUSD_M15.parquet").exists(),
    reason="requires EURUSD parquet data",
)
def test_build_trend_context_frame_bias_values_valid():
    ltf = load_frame(Path("data/raw"), "EURUSD", "M15").tail(200)
    ctx = build_trend_context_frame("EURUSD", ltf, data_dir=Path("data/raw"))
    valid = {"BULLISH", "BEARISH", "RANGING"}
    assert set(ctx["htf_bias"].dropna().unique()).issubset(valid)
    assert set(ctx["ltf_bias"].dropna().unique()).issubset(valid)


@pytest.mark.skipif(
    not Path("data/raw/EURUSD_M15.parquet").exists(),
    reason="requires EURUSD parquet data",
)
def test_build_trend_context_frame_row_count():
    ltf = load_frame(Path("data/raw"), "EURUSD", "M15").tail(100)
    ctx = build_trend_context_frame("EURUSD", ltf, data_dir=Path("data/raw"))
    assert len(ctx) == len(ltf)
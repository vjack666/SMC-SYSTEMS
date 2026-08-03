"""T9 — Medición de BOS/CHOCH."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.measure_structure import run_structure


def test_structure_report_shape() -> None:
    report = run_structure(symbol="EURUSD", max_bars=800)
    assert "symbol" in report
    assert report["symbol"] == "EURUSD"
    assert "bos_bullish" in report
    assert "choch_bearish" in report
    assert report["total_bars"] > 0


def test_structure_counts_are_non_negative() -> None:
    report = run_structure(symbol="EURUSD", max_bars=1200)
    for key in [
        "bos_bullish",
        "bos_bearish",
        "choch_bullish",
        "choch_bearish",
        "bos_active",
        "bos_invalidated",
        "choch_active",
        "choch_invalidated",
        "trend_bullish",
        "trend_bearish",
        "trend_ranging",
    ]:
        assert report[key] >= 0


def test_structure_trend_majority() -> None:
    report = run_structure(symbol="EURUSD", max_bars=2000)
    trend_total = report["trend_bullish"] + report["trend_bearish"] + report["trend_ranging"]
    assert trend_total == report["total_bars"]

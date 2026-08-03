"""T9 — Runner de backtest de estructura."""

from __future__ import annotations

import json
import os

import pytest

from scripts.measure_structure import run_structure


def test_run_structure_json_output() -> None:
    report = run_structure(symbol="EURUSD", max_bars=800)
    payload = json.dumps(report)
    assert "EURUSD" in payload
    assert "H4" in payload
    assert "bos_bullish" in payload


def test_run_structure_env_override() -> None:
    report = run_structure(symbol="EURUSD", max_bars=1200)
    assert report["max_bars"] == 1200

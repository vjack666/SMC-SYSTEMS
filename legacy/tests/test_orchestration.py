from __future__ import annotations

from pathlib import Path

import pytest

from orchestration.backtest_validation_graph import _compute_atr, build_validation_graph


def test_build_validation_graph_compiles():
    graph = build_validation_graph()
    assert graph is not None


def test_compute_atr_returns_positive_value():
    records = [
        {"high": 1.10 + i * 0.001, "low": 1.09 + i * 0.001, "close": 1.095 + i * 0.001}
        for i in range(30)
    ]
    atr = _compute_atr(records, 14)
    assert atr > 0


@pytest.mark.skipif(
    not Path("data/raw/EURUSD_M15.parquet").exists(),
    reason="requires EURUSD M15 parquet",
)
def test_run_validation_with_real_data_smoke():
    from orchestration.backtest_validation_graph import run_validation

    result = run_validation(symbol="EURUSD", data_dir="data/raw", timeframe="M15")
    assert result["status"] == "report_generated"
    assert result["total_bars"] > 0
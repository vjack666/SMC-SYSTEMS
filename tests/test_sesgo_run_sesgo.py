"""T8 — Runner real del backtest del sesgo."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.reloj.reloj import EventoReloj


def _make_evento():
    return EventoReloj(
        m15_index=0,
        m15_timestamp=pd.Timestamp("2026-01-05", tz="UTC"),
        tf_closures=[],
    )


def test_run_sesgo_stub_exit_code():
    mock_validated = MagicMock()
    mock_validated.df = pd.DataFrame(
        {
            "open": [1.0] * 500,
            "high": [1.0001] * 500,
            "low": [0.9999] * 500,
            "close": [1.0] * 500,
        }
    )

    mock_report = {
        "report_path": "fake.json",
        "summary": [],
    }

    with patch(
        "ict_backtest.sesgo.run_sesgo.validate_m15_parquet",
        return_value=mock_validated,
    ), patch(
        "ict_backtest.sesgo.run_sesgo.RelojSesgo",
        return_value=MagicMock(iter_eventos=MagicMock(return_value=[_make_evento()])),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.CableBias",
        return_value=MagicMock(),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.build_demo_report",
        return_value=mock_report,
    ), patch(
        "ict_backtest.sesgo.run_sesgo.save_demo_report",
        return_value=MagicMock(),
    ):
        from ict_backtest.sesgo.run_sesgo import main

        assert main() == 0


def test_run_demo_report_summary_shape():
    mock_validated = MagicMock()
    mock_validated.df = pd.DataFrame(
        {
            "open": [1.0] * 500,
            "high": [1.0001] * 500,
            "low": [0.9999] * 500,
            "close": [1.0] * 500,
        }
    )

    mock_report = {
        "symbol": "EURUSD",
        "k": 48,
        "summary": [
            {"category": "ALIGNED", "total": 10, "aligned": 8, "pct": 80.0},
            {"category": "PARCIAL", "total": 5, "aligned": 2, "pct": 40.0},
            {"category": "NO_DISPONIBLE", "total": 3, "aligned": 0, "pct": 0.0},
        ],
    }

    with patch(
        "ict_backtest.sesgo.run_sesgo.validate_m15_parquet",
        return_value=mock_validated,
    ), patch(
        "ict_backtest.sesgo.run_sesgo.RelojSesgo",
        return_value=MagicMock(iter_eventos=MagicMock(return_value=[_make_evento()])),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.CableBias",
        return_value=MagicMock(),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.build_demo_report",
        return_value=mock_report,
    ), patch(
        "ict_backtest.sesgo.run_sesgo.save_demo_report",
        return_value=MagicMock(),
    ):
        from ict_backtest.sesgo.run_sesgo import run_demo

        report = run_demo(symbol="EURUSD", k=48)
        assert report["symbol"] == "EURUSD"
        assert report["k"] == 48
        assert len(report["summary"]) == 3
        assert report["summary"][0]["category"] == "ALIGNED"
        assert report["summary"][2]["category"] == "NO_DISPONIBLE"

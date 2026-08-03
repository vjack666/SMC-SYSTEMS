"""T1: estructura base del paquete sesgo."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SESGO_DIR = REPO_ROOT / "ict_backtest" / "sesgo"


def test_sesgo_package_importable() -> None:
    import ict_backtest.sesgo  # noqa: F401

    assert ict_backtest.sesgo.__name__ == "ict_backtest.sesgo"


def test_sesgo_structure_exists() -> None:
    assert (SESGO_DIR / "__init__.py").exists()
    assert (SESGO_DIR / "run_sesgo.py").exists()
    assert (SESGO_DIR / "reloj" / "__init__.py").exists()
    assert (SESGO_DIR / "motor_cable" / "__init__.py").exists()
    assert (SESGO_DIR / "medicion" / "__init__.py").exists()


def test_run_sesgo_stub_exit_code() -> None:
    from unittest.mock import MagicMock, patch

    mock_validated = MagicMock()
    mock_validated.df = pd.DataFrame(
        {
            "open": [1.0] * 500,
            "high": [1.0001] * 500,
            "low": [0.9999] * 500,
            "close": [1.0] * 500,
        }
    )

    with patch(
        "ict_backtest.sesgo.run_sesgo.validate_m15_parquet",
        return_value=mock_validated,
    ), patch(
        "ict_backtest.sesgo.run_sesgo.RelojSesgo",
        return_value=MagicMock(iter_eventos=MagicMock(return_value=[])),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.CableBias",
        return_value=MagicMock(),
    ), patch(
        "ict_backtest.sesgo.run_sesgo.build_demo_report",
        return_value={"report_path": "fake.json", "summary": []},
    ), patch(
        "ict_backtest.sesgo.run_sesgo.save_demo_report",
        return_value=MagicMock(),
    ):
        from ict_backtest.sesgo.run_sesgo import main

        assert main() == 0

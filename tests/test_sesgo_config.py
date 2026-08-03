"""T3 — Configuración única del backtest del sesgo."""

from __future__ import annotations

from typing import Dict, Tuple

import pytest

from ict_backtest.sesgo.config import SesgoConfig


def test_default_config_matches_plan():
    config = SesgoConfig()

    assert config.symbol_default == "EURUSD"
    assert config.m15_step_minutes == 15
    assert config.m15_k_future == 48
    assert config.aggregation == {"H1": 4, "H4": 16, "D1": 96}
    assert config.warmup == {"D1": 20, "H4": 60, "H1": 100}


def test_aggregation_helpers():
    config = SesgoConfig()

    assert config.aggregation_buckets() == ("H1", "H4", "D1")
    assert config.warmup_for("D1") == 20
    assert config.warmup_for("H4") == 60
    assert config.warmup_for("H1") == 100
    assert config.aggregation_ratio("D1") == 96
    assert config.aggregation_ratio("H4") == 16
    assert config.aggregation_ratio("H1") == 4


def test_config_is_single_source_of_truth():
    config = SesgoConfig()

    assert config.aggregation_ratio("D1") == config.aggregation_ratio("H4") * 6
    assert config.aggregation_ratio("D1") == config.aggregation_ratio("H1") * 24
    assert config.aggregation_ratio("H4") == config.aggregation_ratio("H1") * 4


def test_config_importable_from_package():
    import ict_backtest.sesgo.config as config_module  # noqa: F401

    assert hasattr(config_module, "SesgoConfig")

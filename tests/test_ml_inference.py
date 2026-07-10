"""Tests for ML quality-filter inference wiring."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ml.inference import QualityFilter, QualityFilterConfig
from signals.pipeline import ScalpingConfig


def test_scalping_config_has_ml_flags():
    cfg = ScalpingConfig()
    # ML quality filter is OFF by default (roadmap A9: "ML filter off por defecto").
    assert cfg.use_ml_quality_filter is False
    assert cfg.ml_model_path.endswith("quality_filter.pkl")


def test_quality_filter_disabled_allows_trade():
    qf = QualityFilter(QualityFilterConfig(enabled=False))
    context = pd.DataFrame({"market_regime": ["RANGING"], "time": ["2024-01-01T00:00:00Z"]})
    allow, prob, threshold = qf.evaluate_signal(
        context,
        0,
        timestamp="2024-01-01T00:00:00Z",
        entry=1.1,
        stop_loss=1.09,
        take_profit=1.12,
        signal_confidence=0.7,
    )
    assert allow is True
    assert threshold == 0.0


@pytest.mark.skipif(
    not Path("ml/models/quality_filter.pkl").exists(),
    reason="production model not built yet",
)
def test_quality_filter_loads_production_model():
    qf = QualityFilter.load()
    assert qf.is_active
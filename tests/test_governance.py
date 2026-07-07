from __future__ import annotations

from governance.model_registry import ModelRegistry
from governance.retraining_scheduler import RetrainingScheduler


def test_model_registry_register_and_get_latest(tmp_path):
    path = tmp_path / "registry.json"
    reg = ModelRegistry(filepath=str(path))
    reg.register("quality_filter", "v1", {"roc_auc": 0.5}, "m1.pkl", timestamp="2026-01-01T00:00:00")
    reg.register("quality_filter", "v2", {"roc_auc": 0.55}, "m2.pkl", timestamp="2026-02-01T00:00:00")
    latest = reg.get_latest("quality_filter")
    assert latest is not None
    assert latest["version"] == "v2"


def test_retraining_scheduler_triggers_on_trade_threshold(tmp_path):
    sched = RetrainingScheduler(
        min_trades=50,
        persistence_file=str(tmp_path / "retrain.json"),
    )
    result = sched.check(
        registry=None,
        performance_metrics={"total_trades": 120, "last_retraining_trades": 50},
    )
    assert result["needs_retraining"] is True


def test_retraining_scheduler_no_trigger_below_threshold(tmp_path):
    sched = RetrainingScheduler(
        min_trades=50,
        persistence_file=str(tmp_path / "retrain.json"),
    )
    result = sched.check(
        registry=None,
        performance_metrics={"total_trades": 60, "last_retraining_trades": 40},
    )
    assert result["needs_retraining"] is False
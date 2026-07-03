from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GovernanceConfig:
    model_registry_file: str = "data/governance/model_registry.json"
    retraining_check_interval_hours: int = 24
    retraining_min_trades: int = 50
    performance_degradation_threshold: float = -0.15
    auto_report_dir: str = "data/governance/reports"
    auto_report_schedule_hours: int = 168
    max_models_stored: int = 20
    deployment_script_path: str = "scripts/deploy_model.sh"

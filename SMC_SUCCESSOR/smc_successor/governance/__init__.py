from smc_successor.governance.config import GovernanceConfig
from smc_successor.governance.model_registry import ModelRegistry
from smc_successor.governance.retraining_scheduler import RetrainingScheduler
from smc_successor.governance.auto_report_generator import AutoReportGenerator


def build_governance_system(config: GovernanceConfig | None = None) -> dict:
    cfg = config or GovernanceConfig()
    return {
        "model_registry": ModelRegistry(filepath=cfg.model_registry_file),
        "retraining_scheduler": RetrainingScheduler(
            check_interval_hours=cfg.retraining_check_interval_hours,
            min_trades=cfg.retraining_min_trades,
            degradation_threshold=cfg.performance_degradation_threshold,
        ),
        "auto_report_generator": AutoReportGenerator(
            report_dir=cfg.auto_report_dir,
            schedule_hours=cfg.auto_report_schedule_hours,
        ),
    }


__all__ = [
    "build_governance_system",
    "GovernanceConfig",
    "ModelRegistry",
    "RetrainingScheduler",
    "AutoReportGenerator",
]

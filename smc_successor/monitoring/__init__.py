from smc_successor.monitoring.alerter import Alerter
from smc_successor.monitoring.config import MonitoringConfig
from smc_successor.monitoring.dashboard import generate_dashboard
from smc_successor.monitoring.drift_detector import DriftDetector
from smc_successor.monitoring.equity_telemetry import EquityTelemetry
from smc_successor.monitoring.harness_adapter import MonitoringHarnessAdapter
from smc_successor.monitoring.performance_tracker import PerformanceTracker


def build_monitoring_system(config: MonitoringConfig | None = None) -> dict:
    cfg = config or MonitoringConfig()
    return {
        "drift_detector": DriftDetector(threshold=cfg.drift_threshold_psi),
        "alerter": Alerter(max_history=cfg.max_alert_history, config=cfg),
        "equity_telemetry": EquityTelemetry(filepath=cfg.equity_telemetry_file),
    }


__all__ = [
    "build_monitoring_system",
    "MonitoringConfig",
    "DriftDetector",
    "Alerter",
    "EquityTelemetry",
    "MonitoringHarnessAdapter",
    "PerformanceTracker",
    "generate_dashboard",
]

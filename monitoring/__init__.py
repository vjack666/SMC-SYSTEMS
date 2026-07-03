from monitoring.alerter import Alerter
from monitoring.config import MonitoringConfig
from monitoring.dashboard import generate_dashboard
from monitoring.drift_detector import DriftDetector
from monitoring.equity_telemetry import EquityTelemetry
from monitoring.harness_adapter import MonitoringHarnessAdapter
from monitoring.performance_tracker import PerformanceTracker


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

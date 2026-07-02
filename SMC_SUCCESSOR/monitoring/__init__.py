from monitoring.config import MonitoringConfig
from monitoring.drift_detector import DriftDetector
from monitoring.alerter import Alerter
from monitoring.equity_telemetry import EquityTelemetry
from monitoring.harness_adapter import MonitoringHarnessAdapter


def build_monitoring_system(config: MonitoringConfig | None = None) -> dict:
    cfg = config or MonitoringConfig()
    return {
        "drift_detector": DriftDetector(threshold=cfg.drift_threshold_psi),
        "alerter": Alerter(max_history=cfg.max_alert_history),
        "equity_telemetry": EquityTelemetry(filepath=cfg.equity_telemetry_file),
    }


__all__ = [
    "build_monitoring_system",
    "MonitoringConfig",
    "DriftDetector",
    "Alerter",
    "EquityTelemetry",
    "MonitoringHarnessAdapter",
]

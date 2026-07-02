from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MonitoringConfig:
    drift_check_interval_min: int = 60
    alert_cooldown_sec: int = 300
    equity_telemetry_file: str = "data/monitoring/equity_telemetry.json"
    drift_threshold_psi: float = 0.2
    max_alert_history: int = 100

from __future__ import annotations

from typing import Any

from monitoring.config import MonitoringConfig
from monitoring.dashboard import generate_dashboard
from monitoring.drift_detector import DriftDetector
from monitoring.equity_telemetry import EquityTelemetry
from monitoring.performance_tracker import PerformanceTracker


class MonitoringHarnessAdapter:
    name = "monitoring"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            config = MonitoringConfig()
            drift_features = parameters.get("drift_features", {})
            drift_reference = parameters.get("drift_reference", {})

            detector = DriftDetector()
            psi_values = detector.check(drift_features, drift_reference)
            drift_detected = detector.is_drift(psi_values)

            equity_entries = parameters.get("equity_entries", [])

            telemetry = EquityTelemetry()
            for entry in equity_entries:
                telemetry.record(
                    equity=entry["equity"],
                    balance=entry["balance"],
                    timestamp=entry.get("timestamp", ""),
                )

            tracker = PerformanceTracker(config=config)
            trades = parameters.get("trades", [])
            for trade in trades:
                tracker.record_trade(
                    entry_price=trade["entry_price"],
                    exit_price=trade["exit_price"],
                    volume=trade["volume"],
                    direction=trade["direction"],
                    timestamp=trade.get("timestamp"),
                )

            dashboard = generate_dashboard(
                equity=telemetry,
                tracker=tracker,
                drift=detector,
            )

            return {
                "module": self.name,
                "event_names": [],
                "status": "completed",
                "drift_psi": psi_values,
                "drift_detected": drift_detected,
                "drawdown": telemetry.compute_drawdown(),
                "performance": telemetry.compute_performance(),
                "equity_count": len(equity_entries),
                "dashboard": dashboard,
                "tracker_metrics": tracker.get_metrics(),
            }
        except Exception as exc:
            return {
                "module": self.name,
                "event_names": [],
                "status": "error",
                "error": str(exc),
            }

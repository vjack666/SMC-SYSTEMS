from __future__ import annotations

from typing import Any

from monitoring.alerter import Alerter
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

            alerter = Alerter(config=config)
            equity_entries = parameters.get("equity_entries", [])

            if drift_detected:
                for feature, psi in psi_values.items():
                    if psi > 0.2:
                        alerter.send(
                            "WARN",
                            f"Drift detected on {feature}: PSI={psi:.4f}",
                            self.name,
                        )

            telemetry = EquityTelemetry()
            for entry in equity_entries:
                telemetry.record(
                    equity=entry["equity"],
                    balance=entry["balance"],
                    timestamp=entry.get("timestamp", ""),
                )

            alert_trigger = parameters.get("alert_trigger")
            if alert_trigger:
                alerter.send(
                    alert_trigger.get("level", "INFO"),
                    alert_trigger.get("message", ""),
                    alert_trigger.get("source", self.name),
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
                alerter=alerter,
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
                "recent_alerts": alerter.get_recent(10),
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

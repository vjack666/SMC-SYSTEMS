from __future__ import annotations

from typing import Any

from monitoring.alerter import Alerter
from monitoring.drift_detector import DriftDetector
from monitoring.equity_telemetry import EquityTelemetry


class MonitoringHarnessAdapter:
    name = "monitoring"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        drift_features = parameters.get("drift_features", {})
        drift_reference = parameters.get("drift_reference", {})

        detector = DriftDetector()
        psi_values = detector.check(drift_features, drift_reference)
        drift_detected = detector.is_drift(psi_values)

        alerter = Alerter()
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

        alerts = alerter.get_recent(10)
        drawdown = telemetry.compute_drawdown()

        return {
            "module": self.name,
            "event_names": [],
            "status": "completed",
            "drift_psi": psi_values,
            "drift_detected": drift_detected,
            "recent_alerts": alerts,
            "drawdown": drawdown,
            "equity_count": len(equity_entries),
        }

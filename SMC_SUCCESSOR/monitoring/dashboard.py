from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from monitoring.alerter import Alerter
from monitoring.drift_detector import DriftDetector
from monitoring.equity_telemetry import EquityTelemetry
from monitoring.performance_tracker import PerformanceTracker


def generate_dashboard(
    alerter: Alerter,
    equity: EquityTelemetry,
    tracker: PerformanceTracker | None = None,
    drift: DriftDetector | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": alerter.get_summary(),
        "drawdown": equity.compute_drawdown(),
        "performance": equity.compute_performance(),
    }

    if tracker is not None:
        result["trades"] = tracker.get_metrics()

    if drift is not None:
        psi_summary: dict[str, Any] = {"features": {}}
        result["drift"] = psi_summary

    return result

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any


class AutoReportGenerator:
    def __init__(
        self,
        report_dir: str = "data/governance/reports",
        schedule_hours: int = 168,
    ) -> None:
        self.report_dir = report_dir
        self.schedule_hours = schedule_hours

    def generate(
        self,
        monitoring_data: dict[str, Any],
        registry_data: dict[str, Any],
        scheduler_data: dict[str, Any],
    ) -> str:
        lines: list[str] = []
        sep = "=" * 72
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines.append(sep)
        lines.append(f"GOVERNANCE AUTO-REPORT — {now}")
        lines.append(sep)

        # Section 1: Executive Summary
        lines.append("\n1. EXECUTIVE SUMMARY")
        lines.append("-" * 40)
        active_alerts = monitoring_data.get("recent_alerts", [])
        alert_count = len(active_alerts)
        drift_detected = monitoring_data.get("drift_detected", False)
        needs_retraining = scheduler_data.get("needs_retraining", False)
        overall = "DEGRADED" if drift_detected or needs_retraining else "NORMAL"
        lines.append(f"  Overall Status:       {overall}")
        lines.append(f"  Active Alerts:        {alert_count}")
        lines.append(f"  Drift Detected:       {drift_detected}")
        lines.append(f"  Retraining Needed:    {needs_retraining}")

        # Section 2: Performance
        lines.append("\n2. PERFORMANCE")
        lines.append("-" * 40)
        perf = monitoring_data.get("performance", {})
        lines.append(f"  Sharpe Ratio:         {perf.get('sharpe', 'N/A')}")
        lines.append(f"  Sortino Ratio:        {perf.get('sortino', 'N/A')}")
        lines.append(f"  Max Drawdown:         {perf.get('drawdown', 'N/A')}")
        lines.append(f"  Win Rate:             {perf.get('win_rate', 'N/A')}")
        lines.append(f"  Profit Factor:        {perf.get('profit_factor', 'N/A')}")

        # Section 3: Drift
        lines.append("\n3. DRIFT ANALYSIS")
        lines.append("-" * 40)
        psi_values = monitoring_data.get("drift_psi", {})
        if psi_values:
            for feature, psi in psi_values.items():
                flag = " *** HIGH" if isinstance(psi, (int, float)) and psi > 0.2 else ""
                lines.append(f"  {feature:<20} PSI={psi:.4f}{flag}")
        else:
            lines.append("  No drift features reported.")

        # Section 4: Models
        lines.append("\n4. MODEL REGISTRY")
        lines.append("-" * 40)
        models = registry_data.get("models", [])
        if models:
            for m in models:
                lines.append(
                    f"  {m.get('name', '?')} v{m.get('version', '?')}  "
                    f"sharpe={m.get('metrics', {}).get('sharpe', '?'):<8}  "
                    f"created={m.get('created_at', '?')}"
                )
        else:
            lines.append("  No registered models.")
        last_retrain = scheduler_data.get("last_retraining", {})
        if last_retrain:
            lines.append(
                f"  Last Retraining:      {last_retrain.get('timestamp', 'N/A')} "
                f"({last_retrain.get('model_id', '?')})"
            )

        # Section 5: Alerts
        lines.append("\n5. RECENT ALERTS (last 10)")
        lines.append("-" * 40)
        if active_alerts:
            for alert in active_alerts[-10:]:
                if isinstance(alert, dict):
                    lines.append(
                        f"  [{alert.get('level', '?')}] {alert.get('message', '?')} "
                        f"({alert.get('timestamp', '?')})"
                    )
                else:
                    lines.append(f"  {alert}")
        else:
            lines.append("  No recent alerts.")

        # Section 6: Recommendations
        lines.append("\n6. RECOMMENDATIONS")
        lines.append("-" * 40)
        recs: list[str] = []
        if drift_detected:
            recs.append("  - Investigate feature drift and consider feature re-engineering.")
        if needs_retraining:
            recs.append("  - Trigger model retraining based on degradation or trade volume.")
        if not recs:
            recs.append("  - No action required. System is operating within acceptable parameters.")
        for r in recs:
            lines.append(r)

        lines.append(f"\n{sep}")
        return "\n".join(lines)

    def write_report(
        self,
        content: str,
        filename: str | None = None,
    ) -> Path:
        os.makedirs(self.report_dir, exist_ok=True)
        if filename is None:
            filename = f"governance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = Path(self.report_dir) / filename
        path.write_text(content)
        return path

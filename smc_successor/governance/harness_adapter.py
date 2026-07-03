from __future__ import annotations

from typing import Any

from smc_successor.governance.config import GovernanceConfig
from smc_successor.governance.model_registry import ModelRegistry
from smc_successor.governance.retraining_scheduler import RetrainingScheduler
from smc_successor.governance.auto_report_generator import AutoReportGenerator


class GovernanceHarnessAdapter:
    name = "governance"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            config = GovernanceConfig()
            registry = ModelRegistry(filepath=config.model_registry_file)
            scheduler = RetrainingScheduler(
                check_interval_hours=config.retraining_check_interval_hours,
                min_trades=config.retraining_min_trades,
                degradation_threshold=config.performance_degradation_threshold,
            )
            reporter = AutoReportGenerator(
                report_dir=config.auto_report_dir,
                schedule_hours=config.auto_report_schedule_hours,
            )

            registered_models = parameters.get("register_models", [])
            for model in registered_models:
                registry.register(
                    name=model["name"],
                    version=model["version"],
                    metrics=model["metrics"],
                    path=f"models/{model['name']}/{model['version']}",
                )

            perf = parameters.get("performance_current", {})
            check_result = scheduler.check(registry, perf)

            if check_result["needs_retraining"]:
                latest = registry.get_latest("smc_v1")
                if latest:
                    scheduler.record_retraining(latest["model_id"])

            registry_data = {"models": registry.list_models()}
            monitoring_data = {
                "drift_psi": parameters.get("drift_psi", {}),
                "drift_detected": parameters.get("drift_detected", False),
                "recent_alerts": parameters.get("recent_alerts", []),
                "performance": perf,
            }
            scheduler_data = check_result

            report_content = reporter.generate(monitoring_data, registry_data, scheduler_data)
            report_path = reporter.write_report(report_content)

            return {
                "module": self.name,
                "event_names": [],
                "status": "completed",
                "models_count": len(registered_models),
                "needs_retraining": check_result["needs_retraining"],
                "retraining_reason": check_result["reason"],
                "report_path": str(report_path),
            }
        except Exception as exc:
            return {
                "module": self.name,
                "event_names": [],
                "status": "error",
                "models_count": 0,
                "needs_retraining": False,
                "error": str(exc),
            }

from __future__ import annotations

import argparse
from typing import Any

from harness.contracts import HarnessEvent
from harness.reports.json_report import write_json_report
from harness.runners.scenario_runner import ScenarioRunner
from harness.scenarios.loader import load_scenarios
from smc_successor.integration.mt5_bridge.harness_adapter import MT5BridgeHarnessAdapter
from smc_successor.adapters.mt5_ea_harness import MQL5EAHarnessAdapter
from smc_successor.governance.harness_adapter import GovernanceHarnessAdapter
from smc_successor.monitoring.harness_adapter import MonitoringHarnessAdapter
from smc_successor.orchestration.harness_adapter import LangGraphBacktestAdapter
from smc_successor.adapters import BacktestAdapter, FeatureEnrichmentAdapter, RiskGovernorAdapter, SignalAdapter


class EchoAdapter:
    name = "echo"

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "module": self.name,
            "event_names": [event.name for event in events],
            "parameters": parameters,
            "events": [{"name": event.name, "payload": event.payload} for event in events],
            "errors": [],
        }


ADAPTERS: dict[str, Any] = {
    "echo": EchoAdapter(),
    "signal_pipeline": SignalAdapter(),
    "risk_governor": RiskGovernorAdapter(),
    "backtest": BacktestAdapter(),
    "feature_enrichment": FeatureEnrichmentAdapter(),
    "mt5_bridge": MT5BridgeHarnessAdapter(),
    "mt5_ea": MQL5EAHarnessAdapter(),
    "langgraph_validation": LangGraphBacktestAdapter(),
    "monitoring": MonitoringHarnessAdapter(),
    "governance": GovernanceHarnessAdapter(),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run harness scenarios.")
    parser.add_argument(
        "--scenarios",
        default="harness/scenarios",
        help="Scenario YAML file or directory.",
    )
    parser.add_argument(
        "--report",
        default="harness/reports/out/harness_report.json",
        help="JSON report output path.",
    )
    parser.add_argument(
        "--adapters",
        default="echo,signal_pipeline,risk_governor,backtest,feature_enrichment,mt5_bridge,mt5_ea,langgraph_validation,monitoring,governance",
        help="Comma-separated list of adapters to enable.",
    )
    args = parser.parse_args()

    enabled = {name: ADAPTERS[name] for name in args.adapters.split(",") if name in ADAPTERS}
    scenarios = load_scenarios(args.scenarios)
    runner = ScenarioRunner(enabled)
    results = [runner.run(scenario) for scenario in scenarios]
    write_json_report(results, args.report)

    failed = [result for result in results if result.status != "passed"]
    for result in results:
        print(f"{result.status.value}: {result.scenario.name} ({result.elapsed_ms:.2f} ms)")
        for error in result.errors:
            print(f"  - {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

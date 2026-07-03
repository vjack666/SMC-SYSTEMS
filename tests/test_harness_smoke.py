from __future__ import annotations

from typing import Any

from pathlib import Path

from harness.contracts import HarnessEvent
from harness.__main__ import main
from harness.runners.scenario_runner import ScenarioRunner
from harness.scenarios.loader import load_scenario

HARNESS_SCENARIOS = Path(__file__).resolve().parent.parent / "harness" / "scenarios"


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


def test_harness_runs_isolated_module_scenario() -> None:
    scenario = load_scenario(HARNESS_SCENARIOS / "echo_smoke.yaml")
    runner = ScenarioRunner({"echo": EchoAdapter()})

    result = runner.run(scenario)

    assert result.status == "passed"
    assert result.metrics["event_count"] == 1
    assert result.errors == ()


def test_harness_cli_writes_report(tmp_path, monkeypatch) -> None:
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "harness",
            "--scenarios",
            str(HARNESS_SCENARIOS / "echo_smoke.yaml"),
            "--report",
            str(report_path),
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert report_path.exists()

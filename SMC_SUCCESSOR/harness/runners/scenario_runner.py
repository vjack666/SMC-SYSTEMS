from __future__ import annotations

from time import perf_counter

from harness.assertions.core import assert_expected_subset
from harness.contracts import HarnessEvent, ModuleAdapter, Scenario, ScenarioResult, ScenarioStatus
from harness.fixtures.loader import load_fixture
from harness.metrics.collector import collect_run_metrics


class ScenarioRunner:
    def __init__(self, adapters: dict[str, ModuleAdapter]) -> None:
        self._adapters = adapters

    def run(self, scenario: Scenario) -> ScenarioResult:
        started = perf_counter()
        errors: list[str] = []

        try:
            adapter = self._adapters[scenario.module]
            fixture = load_fixture(scenario.fixture)
            events = [HarnessEvent(**event) for event in fixture.get("events", [])]
            parameters = fixture.get("parameters", {})
            output = adapter.run(events, parameters)
            errors = assert_expected_subset(output, scenario.expected)
            status = ScenarioStatus.FAILED if errors else ScenarioStatus.PASSED
            metrics = collect_run_metrics(output)
        except KeyError:
            status = ScenarioStatus.ERROR
            metrics = {}
            errors = [f"Missing adapter for module: {scenario.module}"]
        except Exception as exc:
            status = ScenarioStatus.ERROR
            metrics = {}
            errors = [f"{type(exc).__name__}: {exc}"]

        elapsed_ms = (perf_counter() - started) * 1000
        return ScenarioResult(
            scenario=scenario,
            status=status,
            elapsed_ms=elapsed_ms,
            metrics=metrics,
            errors=tuple(errors),
        )

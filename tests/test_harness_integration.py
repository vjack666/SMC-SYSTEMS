from __future__ import annotations

from pathlib import Path

import pytest

from harness.contracts import HarnessEvent, Scenario
from harness.runners.scenario_runner import ScenarioRunner
from harness.scenarios.loader import load_scenarios
from smc_successor.adapters import RiskGovernorAdapter, SignalAdapter


class TestRiskGovernorHarness:
    @pytest.fixture
    def adapter(self):
        return RiskGovernorAdapter()

    def test_normal_state(self, adapter):
        result = adapter.run([], {"consecutive_losses": 0})
        assert result["status"] == "ok"
        assert result["mode"] == "NORMAL"
        assert result["risk_multiplier"] == 1.0

    def test_caution_state(self, adapter):
        result = adapter.run([], {"consecutive_losses": 2})
        assert result["mode"] == "CAUTION"
        assert result["risk_multiplier"] == 0.75

    def test_defensive_state(self, adapter):
        result = adapter.run([], {"consecutive_losses": 3})
        assert result["mode"] == "DEFENSIVE"
        assert result["risk_multiplier"] == 0.50

    def test_lockdown_state(self, adapter):
        result = adapter.run([], {"consecutive_losses": 5})
        assert result["mode"] == "LOCKDOWN"
        assert result["risk_multiplier"] == 0.0

    def test_lockdown_via_drawdown(self, adapter):
        result = adapter.run([], {
            "consecutive_losses": 0,
            "total_drawdown_pct": 9.0,
            "config": {"lockdown_total_dd": 8.0},
        })
        assert result["mode"] == "LOCKDOWN"


class TestSignalAdapter:
    @pytest.fixture
    def adapter(self):
        return SignalAdapter()

    def test_missing_data_returns_error(self, adapter):
        result = adapter.run([], {
            "symbol": "NONEXISTENT",
            "data_dir": "/tmp/nonexistent_data",
        })
        assert result["status"] == "error"


HARNESS_SCENARIOS = Path(__file__).resolve().parent.parent / "harness" / "scenarios"


class TestScenarioRunner:
    def test_risk_normal_scenario(self):
        scenarios = load_scenarios(HARNESS_SCENARIOS / "risk_normal.yaml")
        assert len(scenarios) == 1
        runner = ScenarioRunner({"risk_governor": RiskGovernorAdapter()})
        result = runner.run(scenarios[0])
        assert result.status == "passed"

    def test_risk_caution_scenario(self):
        scenarios = load_scenarios(HARNESS_SCENARIOS / "risk_caution.yaml")
        runner = ScenarioRunner({"risk_governor": RiskGovernorAdapter()})
        result = runner.run(scenarios[0])
        assert result.status == "passed"

    def test_risk_defensive_scenario(self):
        scenarios = load_scenarios(HARNESS_SCENARIOS / "risk_defensive.yaml")
        runner = ScenarioRunner({"risk_governor": RiskGovernorAdapter()})
        result = runner.run(scenarios[0])
        assert result.status == "passed"

    def test_risk_lockdown_scenario(self):
        scenarios = load_scenarios(HARNESS_SCENARIOS / "risk_lockdown.yaml")
        runner = ScenarioRunner({"risk_governor": RiskGovernorAdapter()})
        result = runner.run(scenarios[0])
        assert result.status == "passed"

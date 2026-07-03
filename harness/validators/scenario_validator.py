from __future__ import annotations

from harness.contracts import Scenario


def validate_scenario(scenario: Scenario) -> list[str]:
    errors: list[str] = []
    if not scenario.name:
        errors.append("Scenario name is required.")
    if not scenario.module:
        errors.append("Scenario module is required.")
    if not scenario.fixture:
        errors.append("Scenario fixture is required.")
    return errors

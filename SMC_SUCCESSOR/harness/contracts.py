from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ScenarioStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True)
class HarnessEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    module: str
    fixture: str
    expected: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    status: ScenarioStatus
    elapsed_ms: float
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


class ModuleAdapter(Protocol):
    """Boundary every future module must satisfy to be harness-testable."""

    name: str

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        """Run a module in isolation and return structured output."""

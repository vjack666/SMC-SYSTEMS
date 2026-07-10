from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from harness.contracts import Scenario


def load_scenario(path: str | Path) -> Scenario:
    data = _load_yaml(path)
    return Scenario(
        name=data["name"],
        module=data["module"],
        fixture=data["fixture"],
        expected=data.get("expected", {}),
        tags=tuple(data.get("tags", [])),
    )


def load_scenarios(path: str | Path) -> list[Scenario]:
    root = Path(path)
    if root.is_file():
        return [load_scenario(root)]
    return [load_scenario(item) for item in sorted(root.glob("*.yaml"))]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Scenario must be a mapping: {path}")
    return data

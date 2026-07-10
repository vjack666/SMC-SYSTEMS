from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


FIXTURE_ROOT = Path(__file__).resolve().parent


def load_fixture(name_or_path: str | Path) -> dict[str, Any]:
    path = Path(name_or_path)
    if not path.is_absolute():
        path = FIXTURE_ROOT / path
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Fixture must be a mapping: {path}")
    return data

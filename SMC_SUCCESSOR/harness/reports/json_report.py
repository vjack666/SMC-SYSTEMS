from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from harness.contracts import ScenarioResult


def write_json_report(results: list[ScenarioResult], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(result) for result in results]
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

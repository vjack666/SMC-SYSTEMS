from __future__ import annotations

from typing import Any


def collect_run_metrics(output: dict[str, Any]) -> dict[str, Any]:
    emitted_events = output.get("events", [])
    errors = output.get("errors", [])
    return {
        "event_count": len(emitted_events) if isinstance(emitted_events, list) else 0,
        "error_count": len(errors) if isinstance(errors, list) else 0,
    }

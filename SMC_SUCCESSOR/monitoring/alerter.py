from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class Alerter:
    def __init__(self, max_history: int = 100) -> None:
        self._max_history = max_history
        self._alerts: list[dict[str, Any]] = []

    def send(self, level: str, message: str, source: str) -> str:
        alert_id = str(uuid.uuid4())
        self._alerts.append({
            "alert_id": alert_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "source": source,
        })
        if len(self._alerts) > self._max_history:
            self._alerts.pop(0)
        return alert_id

    def get_recent(self, count: int = 10) -> list[dict]:
        return self._alerts[-count:]

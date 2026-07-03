from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from smc_successor.monitoring.config import MonitoringConfig


class Alerter:
    def __init__(self, max_history: int = 100, config: MonitoringConfig | None = None) -> None:
        self._max_history = max_history
        self._config = config or MonitoringConfig()
        self._alerts: list[dict[str, Any]] = []
        self._load()

    def send(self, level: str, message: str, source: str) -> str:
        alert_id = str(uuid.uuid4())
        alert = {
            "alert_id": alert_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "source": source,
        }
        self._alerts.append(alert)
        if len(self._alerts) > self._max_history:
            self._alerts.pop(0)
        self._persist()
        return alert_id

    def get_recent(self, count: int = 10) -> list[dict]:
        return self._alerts[-count:]

    def escalate(self) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self._config.alert_escalation_window_min)
        critical_count = sum(
            1 for a in self._alerts
            if a["level"] == "CRITICAL"
            and datetime.fromisoformat(a["timestamp"]) >= window_start
        )
        if critical_count >= self._config.alert_escalation_critical_count:
            alert_id = str(uuid.uuid4())
            escalation = {
                "alert_id": alert_id,
                "timestamp": now.isoformat(),
                "level": "ESCALATION",
                "message": f"Escalation: {critical_count} CRITICAL alerts in last {self._config.alert_escalation_window_min} min",
                "source": "alerter.escalate",
            }
            self._alerts.append(escalation)
            self._persist()
            return escalation
        return None

    def get_summary(self) -> dict[str, Any]:
        critical_count = sum(1 for a in self._alerts if a["level"] == "CRITICAL")
        warn_count = sum(1 for a in self._alerts if a["level"] == "WARN")
        info_count = sum(1 for a in self._alerts if a["level"] == "INFO")
        last_ts = self._alerts[-1]["timestamp"] if self._alerts else None
        return {
            "total_alerts": len(self._alerts),
            "critical_count": critical_count,
            "warn_count": warn_count,
            "info_count": info_count,
            "last_alert_timestamp": last_ts,
        }

    def _persist(self) -> None:
        path = Path(self._config.alert_persistence_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._alerts, indent=2), encoding="utf-8")

    def _load(self) -> None:
        path = Path(self._config.alert_persistence_file)
        if path.exists():
            try:
                self._alerts = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                self._alerts = []

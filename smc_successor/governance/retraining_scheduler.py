from __future__ import annotations

import json
import os
import time
from typing import Any


class RetrainingScheduler:
    def __init__(
        self,
        check_interval_hours: int = 24,
        min_trades: int = 50,
        degradation_threshold: float = -0.15,
        persistence_file: str = "data/governance/retraining_status.json",
    ) -> None:
        self.check_interval_hours = check_interval_hours
        self.min_trades = min_trades
        self.degradation_threshold = degradation_threshold
        self.persistence_file = persistence_file
        self._last_retraining: dict[str, Any] = {}
        self._trades_since_last: int = 0
        self._load()

    def check(
        self,
        registry: Any,
        performance_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        reason_parts: list[str] = []
        trigger = False

        total_trades = performance_metrics.get("total_trades", 0)
        last_retraining_trades = performance_metrics.get("last_retraining_trades", 0)
        trades_since = total_trades - last_retraining_trades

        if trades_since >= self.min_trades:
            trigger = True
            reason_parts.append(
                f"Trade count threshold reached: {trades_since} >= {self.min_trades}"
            )

        baseline_sharpe = self._last_retraining.get("sharpe_at_retraining")
        current_sharpe = performance_metrics.get("sharpe")
        if baseline_sharpe is not None and current_sharpe is not None:
            change = (current_sharpe - baseline_sharpe) / abs(baseline_sharpe) if baseline_sharpe != 0 else 0.0
            if change <= self.degradation_threshold:
                trigger = True
                reason_parts.append(
                    f"Sharpe degraded {change:.2%} (threshold: {self.degradation_threshold:.0%})"
                )

        reason = "; ".join(reason_parts) if reason_parts else "No action needed"

        return {
            "needs_retraining": trigger,
            "reason": reason,
            "metrics": {
                "trades_since_last_retraining": trades_since,
                "current_sharpe": current_sharpe,
                "baseline_sharpe": baseline_sharpe,
                "degradation": (
                    round(change, 6)
                    if baseline_sharpe is not None and current_sharpe is not None
                    else None
                ),
            },
        }

    def record_retraining(
        self,
        model_id: str,
        timestamp: str | None = None,
    ) -> None:
        self._last_retraining = {
            "model_id": model_id,
            "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._trades_since_last = 0
        self._save()

    def get_status(self) -> dict[str, Any]:
        return {
            "last_retraining": self._last_retraining,
            "trades_since_last_retraining": self._trades_since_last,
            "next_review_hours": self.check_interval_hours,
            "min_trades_threshold": self.min_trades,
            "degradation_threshold": self.degradation_threshold,
        }

    def _load(self) -> None:
        if not os.path.exists(self.persistence_file):
            return
        try:
            with open(self.persistence_file) as f:
                data = json.load(f)
            self._last_retraining = data.get("last_retraining", {})
            self._trades_since_last = data.get("trades_since_last_retraining", 0)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
        with open(self.persistence_file, "w") as f:
            json.dump(
                {
                    "last_retraining": self._last_retraining,
                    "trades_since_last_retraining": self._trades_since_last,
                },
                f,
                indent=2,
            )

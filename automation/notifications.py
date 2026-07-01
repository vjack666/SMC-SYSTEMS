from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger("automation.notifications")


class NotificationManager:
    def __init__(self):
        self._handlers: list[Callable] = []

    def on_notify(self, handler: Callable) -> None:
        self._handlers.append(handler)

    def send(self, message: str, level: str = "info") -> None:
        logger.log(
            logging.INFO if level == "info" else logging.WARNING if level == "warning" else logging.ERROR,
            "Notification [%s]: %s", level, message,
        )
        for handler in self._handlers:
            try:
                handler(message, level)
            except Exception:
                logger.exception("Notification handler error")

    def task_completed(self, task_id: str, description: str, result: str = "") -> None:
        msg = f"Task #{task_id} completed.\n\n{result}" if result else f"Task #{task_id} completed: {description}"
        self.send(msg, "info")

    def task_failed(self, task_id: str, description: str, error: str) -> None:
        self.send(f"Task #{task_id} FAILED: {description}\nError: {error}", "error")

    def tests_failed(self, details: str) -> None:
        self.send(f"Tests FAILED:\n{details}", "error")

    def commit_created(self, commit_hash: str, message: str) -> None:
        self.send(f"Commit created: {commit_hash}\n{message}", "info")

    def exception_occurred(self, location: str, error: str) -> None:
        self.send(f"Exception in {location}:\n{error}", "error")

    def repository_dirty(self, branch: str, changes: list[str]) -> None:
        change_list = "\n".join(changes[:10])
        suffix = f"\n... and {len(changes) - 10} more" if len(changes) > 10 else ""
        self.send(f"Repository dirty on {branch}:\n{change_list}{suffix}", "warning")

    def merge_conflict(self) -> None:
        self.send("Merge conflict detected. Manual resolution required.", "error")

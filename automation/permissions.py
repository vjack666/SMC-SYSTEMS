from __future__ import annotations

import os
import logging
from pathlib import Path

logger = logging.getLogger("automation.permissions")


class PermissionManager:
    def __init__(self, config_path: str | Path | None = None):
        self._authorized_ids: set[int] = set()
        self._load_from_env()

    def _load_from_env(self) -> None:
        raw = os.getenv("TELEGRAM_AUTHORIZED_USERS", "")
        if not raw:
            logger.warning("No TELEGRAM_AUTHORIZED_USERS set in .env")
            return
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                self._authorized_ids.add(int(part))
            except ValueError:
                logger.warning("Invalid user ID in config: %s", part)

    def authorize(self, user_id: int) -> None:
        self._authorized_ids.add(user_id)
        logger.info("Authorized user %s", user_id)

    def revoke(self, user_id: int) -> None:
        self._authorized_ids.discard(user_id)
        logger.info("Revoked user %s", user_id)

    def is_authorized(self, user_id: int) -> bool:
        return user_id in self._authorized_ids

    @property
    def authorized_users(self) -> frozenset[int]:
        return frozenset(self._authorized_ids)

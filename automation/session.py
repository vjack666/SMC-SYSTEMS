from __future__ import annotations

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("automation.session")


@dataclass
class SessionState:
    repository_root: Path = Path.cwd()
    current_branch: str = ""
    last_commit_hash: str = ""
    last_commit_message: str = ""
    is_dirty: bool = False
    pending_changes: list[str] = field(default_factory=list)
    opencode_running: bool = False
    active_tasks: list[str] = field(default_factory=list)


class SessionManager:
    def __init__(self, repository_root: str | Path | None = None):
        root = repository_root or os.getenv("REPOSITORY_PATH", Path.cwd())
        self._state = SessionState(repository_root=Path(root).resolve())

    def refresh(self) -> None:
        self._refresh_git_state()

    def _refresh_git_state(self) -> None:
        root = self._state.repository_root
        git_dir = root / ".git"
        if not git_dir.exists():
            logger.warning("Not a git repository: %s", root)
            return
        try:
            import subprocess
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            self._state.current_branch = result.stdout.strip()
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            parts = result.stdout.strip().split(" ", 1)
            if len(parts) == 2:
                self._state.last_commit_hash = parts[0]
                self._state.last_commit_message = parts[1]
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root, capture_output=True, text=True, timeout=10
            )
            changes = [line for line in result.stdout.splitlines() if line.strip()]
            self._state.is_dirty = len(changes) > 0
            self._state.pending_changes = changes
        except Exception as exc:
            logger.error("Failed to refresh git state: %s", exc)

    @property
    def state(self) -> SessionState:
        return self._state

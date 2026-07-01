from __future__ import annotations

import os
import time
import logging
import subprocess
from pathlib import Path
from typing import Any

from automation.execution_layer import ExecutionResult

logger = logging.getLogger("automation.providers.codex")


class CodexProvider:
    name = "codex"

    def __init__(self, executable: str | None = None, repository_root: Path | None = None):
        self._executable = executable or os.getenv("CODEX_EXECUTABLE", "codex")
        self._repository_root = repository_root or Path(
            os.getenv("REPOSITORY_PATH", Path.cwd())
        ).resolve()

    def execute(self, command: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        started = time.time()
        cwd = context.get("cwd") if context else None
        cwd = Path(cwd) if cwd else self._repository_root
        cmd = [self._executable, command]
        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=600
            )
            duration_ms = (time.time() - started) * 1000
            if result.returncode == 0:
                return ExecutionResult(success=True, output=result.stdout, duration_ms=duration_ms)
            return ExecutionResult(
                success=False, output=result.stdout,
                error=result.stderr or f"Exit code {result.returncode}",
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error="Timeout (600s)", duration_ms=600000)
        except FileNotFoundError:
            return ExecutionResult(success=False, error=f"Executable not found: {self._executable}")
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    def is_available(self) -> bool:
        import shutil
        return shutil.which(self._executable) is not None

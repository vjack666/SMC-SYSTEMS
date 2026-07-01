from __future__ import annotations

import os
import sys
import enum
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("automation.execution_layer")


class ExecutionResult:
    success: bool
    output: str
    error: str | None
    duration_ms: float
    files_modified: list[str]
    metadata: dict[str, Any]

    def __init__(
        self,
        success: bool = False,
        output: str = "",
        error: str | None = None,
        duration_ms: float = 0.0,
        files_modified: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.duration_ms = duration_ms
        self.files_modified = files_modified or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "files_modified": self.files_modified,
            "metadata": self.metadata,
        }


class Provider(Protocol):
    name: str

    def execute(self, command: str, context: dict[str, Any] | None = None) -> ExecutionResult: ...

    def is_available(self) -> bool: ...


class OpenCodeProvider:
    name = "opencode"

    def __init__(self, executable: str | None = None, repository_root: Path | None = None):
        self._executable = executable or os.getenv("OPENCODE_EXECUTABLE", "opencode")
        self._repository_root = repository_root or Path(
            os.getenv("REPOSITORY_PATH", Path.cwd())
        ).resolve()

    def execute(self, command: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        import subprocess
        started = time.time()
        cmd = [self._executable, command]
        if context and context.get("cwd"):
            cwd = Path(context["cwd"])
        else:
            cwd = self._repository_root
        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=600
            )
            duration_ms = (time.time() - started) * 1000
            if result.returncode == 0:
                return ExecutionResult(
                    success=True, output=result.stdout, duration_ms=duration_ms
                )
            return ExecutionResult(
                success=False,
                output=result.stdout,
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


class LocalPythonProvider:
    name = "local_python"

    def __init__(self, repository_root: Path | None = None):
        self._repository_root = repository_root or Path(
            os.getenv("REPOSITORY_PATH", Path.cwd())
        ).resolve()

    def execute(self, command: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        import subprocess
        started = time.time()
        python = os.getenv("PYTHON_EXECUTABLE", sys.executable)
        if not python:
            python = "python"
        script = self._generate_script(command)
        try:
            result = subprocess.run(
                [python, "-c", script],
                cwd=self._repository_root, capture_output=True, text=True, timeout=600
            )
            duration_ms = (time.time() - started) * 1000
            if result.returncode == 0:
                return ExecutionResult(
                    success=True, output=result.stdout, duration_ms=duration_ms
                )
            return ExecutionResult(
                success=False,
                output=result.stdout,
                error=result.stderr or f"Exit code {result.returncode}",
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error="Timeout (600s)", duration_ms=600000)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    def _generate_script(self, command: str) -> str:
        return command

    def is_available(self) -> bool:
        return True


class ExecutionLayer:
    def __init__(self, repository_root: str | Path | None = None):
        self._repository_root = Path(repository_root or os.getenv("REPOSITORY_PATH", Path.cwd())).resolve()
        self._providers: dict[str, Provider] = {
            "opencode": OpenCodeProvider(repository_root=self._repository_root),
            "local_python": LocalPythonProvider(repository_root=self._repository_root),
        }
        self._active_provider: str = os.getenv("ACTIVE_PROVIDER", "local_python")

    @property
    def active_provider(self) -> str:
        return self._active_provider

    @active_provider.setter
    def active_provider(self, name: str) -> None:
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(self._providers.keys())}")
        self._active_provider = name

    def execute(self, command: str, context: dict[str, Any] | None = None) -> ExecutionResult:
        provider = self._providers[self._active_provider]
        logger.info("Executing via %s: %s", provider.name, command[:100])
        return provider.execute(command, context)

    def register_provider(self, name: str, provider: Provider) -> None:
        self._providers[name] = provider
        logger.info("Registered provider: %s", name)

    @property
    def available_providers(self) -> list[str]:
        return [name for name, p in self._providers.items() if p.is_available()]

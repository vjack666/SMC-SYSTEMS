"""Persist desktop crashes for diagnosis."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("results/desktop_crash.log")


def install_crash_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _hook(exc_type, exc, tb):
        LOG_PATH.write_text(
            f"[{datetime.now(timezone.utc).isoformat()}] UNHANDLED\n"
            + "".join(traceback.format_exception(exc_type, exc, tb)),
            encoding="utf-8",
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def log_error(context: str, exc: BaseException) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(
            f"[{datetime.now(timezone.utc).isoformat()}] {context}\n"
            f"{traceback.format_exc()}\n"
        )
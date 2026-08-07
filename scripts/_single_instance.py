"""Instancia unica para scripts de fondo (vigilante, loop).

Evita que dos procesos del mismo script corran a la vez (cerrarian lo mismo
dos veces / ensuciarian logs). Usa un lock file con PID; si el PID sigue vivo,
asume que la instancia previa vive y lanza SystemExit.

Uso:
    from _single_instance import ensure_single_instance
    ensure_single_instance("vigilante_riesgo")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_LOCK_DIR = Path(__file__).resolve().parent / "logs"


def _is_pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # tasklist silencioso: 0 si existe
        r = os.system(f'tasklist /FI "PID eq {pid}" >nul 2>&1')
        return r == 0
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def ensure_single_instance(name: str) -> None:
    """Lanza SystemExit si ya hay una instancia viva de ``name``."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock = _LOCK_DIR / f".{name}.lock"
    if lock.exists():
        try:
            old_pid = int(lock.read_text().strip())
        except Exception:
            old_pid = None
        if old_pid and _is_pid_alive(old_pid):
            print(f"[single_instance] Ya corre {name} (PID {old_pid}). Saliendo.")
            raise SystemExit(0)
    lock.write_text(str(os.getpid()))

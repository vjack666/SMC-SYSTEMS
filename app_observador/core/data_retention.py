"""Retención de datos (regla de Ruben: guarda 3 meses, después borra).

Borra de forma estricta cualquier archivo de black-box / cache con mtime mayor a
RETENTION_DAYS (90). Se ejecuta al arrancar la app y puede correr en un timer
semanal. Es la medida estricta; TimedRotatingFileHandler.backupCount es la red de
seguridad.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from app_observador.config import BLACKBOX_DIR, MAPS_DIR, RETENTION_DAYS
from app_observador.core.blackbox import log_event

# Carpetas sujetas a retención (la app no acumula info vieja)
_RETENTION_DIRS = [BLACKBOX_DIR, MAPS_DIR]


def _older_than(path: Path, days: int) -> bool:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    age_days = (time.time() - mtime) / 86400.0
    return age_days > days


def cleanup_old(days: int = RETENTION_DAYS, dry_run: bool = False) -> dict:
    """Borra archivos con mtime > days en las carpetas de retención.

    Devuelve un resumen {borrados: int, bytes: int, detalle: [...]}.
    Si dry_run=True solo reporta, no borra (útil para tests).
    """
    removed = 0
    freed = 0
    detalle: list[str] = []
    for d in _RETENTION_DIRS:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and _older_than(f, days):
                size = f.stat().st_size
                detalle.append(f"{f.name} ({size} bytes, {days}d+)")
                if not dry_run:
                    try:
                        f.unlink()
                    except OSError:
                        continue
                removed += 1
                freed += size
    return {"borrados": removed, "bytes": freed, "detalle": detalle}


def run_retention() -> dict:
    """Punto de entrada: limpia y registra en la caja negra."""
    res = cleanup_old()
    log_event(
        "data_retention",
        "cleanup_ejecutado",
        level="INFO" if res["borrados"] == 0 else "WARNING",
        data={"borrados": res["borrados"], "bytes": res["bytes"]},
    )
    return res


if __name__ == "__main__":
    # Smoke test real: crea un archivo fake de >90 días y lo borra (no dry_run).
    import tempfile
    from app_observador.config import ensure_dirs
    ensure_dirs()
    fake = BLACKBOX_DIR / "app_2026-01-01.log"
    fake.write_text("old", encoding="utf-8")
    old = fake.stat().st_mtime - (RETENTION_DAYS + 1) * 86400
    import os
    os.utime(fake, (old, old))
    before = fake.exists()
    res = cleanup_old()
    after = fake.exists()
    print(f"ANTES existia={before} | DESPUES existia={after} | borrados={res['borrados']}")
    assert before and not after, "El archivo viejo debio borrarse"
    print("RETENTION OK")

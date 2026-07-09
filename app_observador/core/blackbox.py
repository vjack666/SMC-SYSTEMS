"""Caja negra (black-box) del observador.

Log estructurado en JSON por ciclo de análisis, con rotación diaria y retención de
90 días (regla de Ruben: guarda 3 meses, después borra). Usa solo stdlib
(logging.TimedRotatingFileHandler) — sin dependencias nuevas.

Cada evento se guarda como una línea JSON:
  {"ts": "...", "level": "INFO", "module": "...", "event": "...",
   "symbol": "EURUSD", "tf": "M15", "data": {...}, "error": null}

Esto permite abrir el log y ver QUÉ pasó en cualquier ciclo de los últimos 3 meses
y por qué el semáforo salió como salió.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

from app_observador.config import BLACKBOX_DIR, RETENTION_DAYS


class _JsonFormatter(logging.Formatter):
    """Escribe cada registro como una línea JSON compacta y legible."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": getattr(record, "bb_module", record.name),
            "event": getattr(record, "bb_event", record.getMessage()),
            "symbol": getattr(record, "bb_symbol", ""),
            "tf": getattr(record, "bb_tf", ""),
            "data": getattr(record, "bb_data", None),
            "error": getattr(record, "bb_error", None),
        }
        # Quita claves vacías para no ensuciar el log
        clean = {k: v for k, v in payload.items() if v not in (None, "", {})}
        return json.dumps(clean, ensure_ascii=False, default=str)


def setup_blackbox() -> logging.Logger:
    """Configura y devuelve el logger de la caja negra.

    Retención: backupCount=RETENTION_DAYS en TimedRotatingFileHandler es la red de
    seguridad; data_retention.py borra por mtime como medida estricta.
    """
    BLACKBOX_DIR.mkdir(parents=True, exist_ok=True)
    log_path = BLACKBOX_DIR / "app.log"

    logger = logging.getLogger("app_observador.blackbox")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=RETENTION_DAYS,
        encoding="utf-8",
        utc=True,
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    return logger


# Logger global de la app (se inicializa al importar)
bb = setup_blackbox()


def log_event(
    module: str,
    event: str,
    level: str = "INFO",
    symbol: str = "",
    tf: str = "",
    data: dict | None = None,
    error: str | None = None,
) -> None:
    """Registra un evento en la caja negra. Única API pública recomendada."""
    extra = {
        "bb_module": module,
        "bb_event": event,
        "bb_symbol": symbol,
        "bb_tf": tf,
        "bb_data": data or {},
        "bb_error": error,
    }
    lvl = getattr(logging, level.upper(), logging.INFO)
    bb.log(lvl, event, extra=extra)


def log_error(module: str, event: str, exc: Exception, symbol: str = "", tf: str = "") -> None:
    """Atajo para registrar una excepción con traceback corto."""
    log_event(
        module=module,
        event=event,
        level="ERROR",
        symbol=symbol,
        tf=tf,
        error=f"{type(exc).__name__}: {exc}",
    )


if __name__ == "__main__":
    # Smoke test sin mock: escribe 2 eventos reales y los muestra.
    log_event("blackbox", "smoke_test", level="INFO", data={"ok": True})
    log_event("engine", "ciclo_iniciado", level="INFO", symbol="EURUSD")
    print("BLACKBOX OK:", BLACKBOX_DIR / "app.log")
    sys.exit(0)

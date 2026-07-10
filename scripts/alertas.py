"""
Alertas locales de Windows para la rutina EURUSD.

Popup + sonido sin instalar nada (usa Windows Forms y beep del SO).
Fallbacks: si el popup falla, escribe en logs/alertas.log.

Uso:
  from alertas import alertar
  alertar("VERDE", "EURUSD sesgo LONG, sin roja -> operá")
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ALERT_LOG = BASE / "logs" / "alertas.log"

# En Windows evita que subprocess abra una consola negra al llamar powershell.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _log_only(titulo: str, msg: str) -> None:
    try:
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {titulo}: {msg}\n")
    except Exception:
        pass


def _popup(titulo: str, msg: str) -> bool:
    """Popup de Windows via PowerShell (System.Windows.Forms). Devuelve ok."""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.MessageBox]::Show("
        f"'{msg}', '{titulo}', 'OK', 'Information') | Out-Null"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=30, creationflags=_NO_WINDOW)
        return True
    except Exception:
        return False


def _beep() -> None:
    """Sonido corto via PowerShell."""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[console]::beep(660,300)"],
            capture_output=True, timeout=10, creationflags=_NO_WINDOW)
    except Exception:
        pass


def alertar(titulo: str, msg: str, no_popup: bool = False) -> None:
    """Muestra popup + sonido y registra en log. no_popup -> solo log."""
    _log_only(titulo, msg)
    if no_popup:
        return
    _beep()
    _popup(titulo, msg)


if __name__ == "__main__":
    alertar("PRUEBA ALERTA", "Si ves este popup, las alertas funcionan.")
    print("popup enviado (revisa logs/alertas.log tambien)")

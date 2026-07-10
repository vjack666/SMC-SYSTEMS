"""Garantiza UNA SOLA instancia de un script en Windows (mutex de sesion).

Si ya hay otro proceso con el mismo nombre corriendo, el actual imprime
un aviso y sale con codigo 0 (sin duplicar trabajo ni procesos).

Motivo: el arranque automatico (Programador de tareas / Startup) debe ser
idempotente. Si por cualquier razon se lanza dos veces (login doble,
reinicio de sesion), el segundo se auto-cierra en vez de duplicar loop/
vigilante. Esto mata de raiz el bug de procesos duplicados que antes
obligo a deshabilitar el acceso directo viejo de Inicio.

En no-Windows es no-op (devuelve True) para no romper pruebas locales.
"""
from __future__ import annotations

import ctypes
import sys

# Guardamos el handle vivo para que el mutex de kernel no se libere mientras
# el proceso corre (ctypes no cierra el handle solo, pero lo mantenemos
# referenciado por si acaso).
_HANDLES: list = []


def ensure_single_instance(name: str) -> bool:
    """Devuelve True si somos la unica instancia.

    Si ya corre otro proceso con el mismo `name`, imprime aviso y sale
    del proceso con codigo 0.
    """
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # Mutex de SESION de usuario (prefijo Local\) -> unico por usuario,
        # no cruza entre sesiones de Terminal Services.
        handle = kernel32.CreateMutexW(None, False, f"Local\\SMC_{name}")
        if not handle or handle == 0:
            # No pudimos crear el mutex: mejor dejamos correr que bloquear.
            return True
        # ERROR_ALREADY_EXISTS = 183
        if ctypes.GetLastError() == 183:
            print(f"[single-instance] Ya hay otro '{name}' corriendo. "
                  f"Salida limpia (sin duplicar).")
            sys.exit(0)
        _HANDLES.append(handle)
        return True
    except Exception:
        # Cualquier fallo de API no debe impedir el arranque.
        return True

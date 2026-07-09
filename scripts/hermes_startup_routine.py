"""
Rutina de arranque de Hermes para Ruben.

Lo PRIMERO que hace Hermes al iniciar:
  1) Abre el terminal MT5 FundedNext (si no esta abierto).
  2) Actualiza data/raw con datos EN VIVO (EURUSD D1/H4/M15 por defecto).
  3) Genera la ficha top-down EURUSD (la rutina diaria).

Se ejecuta con el Python del sistema (el que tiene MetaTrader5 real):
  C:\Python314\python.exe scripts/hermes_startup_routine.py

La ventana de PowerShell del Startup ya arranca `hermes`. Para que Hermes
corra ESTO primero, enganchalo desde tu shell de Hermes o dejalo como tarea
previa. Ver notas al final del archivo.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = r"C:\Python314\python.exe"


def run(script: str, *extra: str) -> int:
    cmd = [PY, str(ROOT / script), *extra]
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd)
    return r.returncode


def main() -> int:
    print("=" * 60)
    print("  ARRANQUE HERMES — paso 1: MT5 FundedNext + data en vivo")
    print("=" * 60)

    # 1) Abrir MT5 FundedNext y bajar datos
    rc = run("scripts/update_mt5_data.py", "--symbols", "EURUSD",
             "--tfs", "D1,H4,M15")
    if rc != 0:
        print("[!] La actualizacion fallo (MT5 cerrado o sin login?). "
              "La ficha usara datos cacheados si existen.")

    # 2) Ficha top-down del dia
    print("\n>>> Generando ficha EURUSD...")
    rc2 = run("scripts/rutina_eurusd.py", "--save")
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------------------------------------------------------------------
# NOTA PARA RUBEN (cómo encadenarlo al arranque):
#  - Ya tenes el acceso directo Startup que abre `hermes` solo.
#  - Para que Hermes actualice la data ANTES de que lo uses, hay dos opciones:
#    (a) Manual y simple: vos corres este script cuando abris Hermes
#        (o yo te lo disparo bajo demanda).
#    (b) Automática: reemplazar el Target del acceso directo Startup por un
#        .bat que primero corra este script y luego `hermes`.
#  - El script usa C:\Python314\python.exe porque es el unico con MT5 real.
# ---------------------------------------------------------------------------

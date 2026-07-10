"""
Actualizador de datos EURUSD desde MT5 FundedNext (datos EN VIVO).

Abre el terminal FundedNext si no esta corriendo, se conecta via el paquete
MetaTrader5 real y descarga las velas mas recientes de EURUSD (D1/H4/M15),
guardandolas en data/raw/ como parquet. Lo primero que corre Hermes al iniciar.

Requiere: Python del sistema con MetaTrader5 instalado (NO el venv smc_probe,
que solo tiene un stub). Path por defecto del terminal en _data_legacy.py.

Uso:
  C:\\Python314\\python.exe scripts/update_mt5_data.py
  C:\\Python314\\python.exe scripts/update_mt5_data.py --symbols EURUSD,GBPUSD --tfs D1,H4,M15
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FUNDEDNEXT_TERMINAL = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
DATA_DIR = Path("data/raw")

# En Windows evita que subprocess abra una consola negra al llamar tasklist.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _terminal_running() -> bool:
    """True si terminal64.exe (FundedNext) ya esta en ejecucion."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            capture_output=True, text=True, timeout=15,
            encoding="mbcs", errors="ignore", creationflags=_NO_WINDOW,
        ).stdout.lower()
        return "terminal64.exe" in out
    except Exception:
        return False


def _launch_terminal() -> None:
    if _terminal_running():
        print("[*] Terminal MT5 ya esta abierto.")
        return
    p = Path(FUNDEDNEXT_TERMINAL)
    if not p.exists():
        print(f"[!] No se encontro el terminal en {FUNDEDNEXT_TERMINAL}")
        return
    print(f"[*] Abriendo terminal FundedNext: {FUNDEDNEXT_TERMINAL}")
    subprocess.Popen([FUNDEDNEXT_TERMINAL])
    # dar tiempo a que arranque y loguee la cuenta
    for i in range(30):
        time.sleep(2)
        if _terminal_running():
            print(f"[*] Terminal detectado tras {(i + 1) * 2}s. Esperando login...")
            time.sleep(6)
            return
    print("[!] El terminal no aparecio en 60s; intento conectar igual.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Actualiza data/raw desde MT5 FundedNext")
    ap.add_argument("--symbols", default="EURUSD")
    ap.add_argument("--tfs", default="D1,H4,M15")
    ap.add_argument("--no-launch", action="store_true",
                    help="no abrir el terminal, asumir que ya esta corriendo")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip().upper() for t in args.tfs.split(",") if t.strip()]

    if not args.no_launch:
        _launch_terminal()

    # Import diferido: requiere MetaTrader5 real en este Python.
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("[!] MetaTrader5 no instalado en este Python. Usa C:\\Python314\\python.exe")
        return 2

    if getattr(mt5, "initialize", None) is None or not mt5.initialize(path=FUNDEDNEXT_TERMINAL):
        err = mt5.last_error() if hasattr(mt5, "last_error") else "?"
        print(f"[!] mt5.initialize fallo: {err}. Abre el terminal y loguea la cuenta.")
        return 3

    acc = mt5.account_info()
    if acc is not None:
        print(f"[*] Conectado a cuenta {acc.login} ({acc.server}) balance={acc.balance}")

    from _data_legacy import _download_frame

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, 0
    for sym in symbols:
        for tf in tfs:
            try:
                df = _download_frame(DATA_DIR, sym, tf)
                last = df["time"].iloc[-1]
                print(f"[OK] {sym} {tf}: {len(df)} velas, ultima {last}")
                ok += 1
            except Exception as e:
                print(f"[FAIL] {sym} {tf}: {e}")
                fail += 1

    mt5.shutdown()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n[*] Actualizacion completa {now} — OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

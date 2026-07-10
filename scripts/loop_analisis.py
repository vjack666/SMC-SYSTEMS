"""
Loop de Analisis EURUSD — observador automatico (SIN operar).

Corre dentro de la ventana 8-11 AM Ecuador (13-16 UTC), cada 5 minutos:
  1. Actualiza datos MT5 en vivo (EURUSD D1/H4/M15).
  2. Regenera la ficha tecnica (rutina_eurusd.py).
  3. Regenera el informe combinado (informe_eurusd.py).
  4. Regenera el semaforo (semaforo_fundednext.py) e imprime el veredicto.

NUNCA abre ordenes en MT5. Es un observador para que el trader decida.

Uso:
  C:\\Python314\\python.exe scripts\\loop_analisis.py          # loop continuo
  C:\\Python314\\python.exe scripts\\loop_analisis.py --once    # 1 ciclo y sale
  C:\\Python314\\python.exe scripts\\loop_analisis.py --test-window  # simula ventana abierta

Parada: Ctrl+C (salida limpia).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ecuador = UTC-5, sin DST.
ECUADOR_UTC_OFFSET = -5
TRADE_START_HOUR = 7      # 07:00 Ecuador (arranca temprano, operamos desde las 7)
TRADE_END_HOUR = 20       # 20:00 Ecuador (compu prendida hasta las 8 PM)
CYCLE_SECONDS = 5 * 60    # cada 5 minutos SIEMPRE
ALWAYS_ON = True          # loop nunca duerme: corre 24/7 cada 5 min
PY = r"C:\Python314\python.exe"

# En Windows evita que subprocess abra una consola negra en cada subproceso.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

BASE = Path(__file__).resolve().parent.parent
DIARIO = BASE / "docs" / "diario"


def _now_ecuador() -> datetime:
    """Hora actual en Ecuador (UTC-5)."""
    utc = datetime.now(timezone.utc)
    return utc + timedelta(hours=ECUADOR_UTC_OFFSET)


def _in_window(now_ec: datetime) -> bool:
    return TRADE_START_HOUR <= now_ec.hour < TRADE_END_HOUR


def _fin_de_semana(now_ec: datetime) -> bool:
    """True si el loop debe estar APAGADO:
    - sabado o domingo (cualquier hora)
    - viernes desde las 15:00 Ecuador en adelante
    """
    wd = now_ec.weekday()  # lun=0 ... vie=4, sab=5, dom=6
    if wd == 5 or wd == 6:
        return True
    if wd == 4 and now_ec.hour >= 15:
        return True
    return False


def _run(script: str, *args: str) -> tuple[bool, str]:
    """Ejecuta un script y devuelve (ok, stdout_tail). No lanza."""
    cmd = [PY, str(BASE / "scripts" / script), *args]
    try:
        res = subprocess.run(cmd, cwd=str(BASE), capture_output=True,
                              text=True, timeout=180, creationflags=_NO_WINDOW)
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode == 0, out.strip()[-600:]
    except subprocess.TimeoutExpired:
        return False, f"[timeout] {script}"
    except Exception as e:  # noqa: BLE001
        return False, f"[error] {script}: {e}"


def run_cycle(test: bool = False, no_alert: bool = False) -> dict:
    """Ejecuta un ciclo completo. Devuelve resumen."""
    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    from alertas import alertar

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log = [f"=== CICLO {stamp} ==="]

    # (a) MT5 fresco
    ok, msg = _run("update_mt5_data.py", "--symbols", "EURUSD", "--tfs", "D1,H4,M15")
    if not ok:
        log.append(f"  [AVISO] MT5 no actualizo (uso cache): {msg[:200]}")
    else:
        log.append("  [OK] MT5 actualizado")

    # (b) ficha
    ok, msg = _run("rutina_eurusd.py", "--save")
    log.append(f"  [{'OK' if ok else 'AVISO'}] ficha: {msg[:120]}")

    # (c) informe
    ok, msg = _run("informe_eurusd.py", "--save")
    log.append(f"  [{'OK' if ok else 'AVISO'}] informe: {msg[:120]}")

    # (d) semaforo (imprime veredicto al stdout del loop)
    ok, msg = _run("semaforo_fundednext.py")
    log.append(f"  [{'OK' if ok else 'AVISO'}] semaforo")
    verdict = ""
    red = False
    for line in msg.splitlines():
        if "Veredicto" in line or "SESGO DEL DIA" in line:
            verdict = line.strip()
        if "NOTICIA ROJA" in line and "ninguna" not in line.lower():
            red = True
    if verdict:
        log.append(f"  >>> {verdict}")

    # (e) ALERTAS (popup + sonido)
    if not no_alert:
        if red:
            alertar("NOTICIA ROJA EURUSD",
                    "Evento High USD/EUR en ventana. Regla FundedNext: no operar "
                    "(o 40% profit si cuenta fondeada).")
            log.append("  [ALERTA] NOTICIA ROJA -> popup")
        elif "VERDE" in verdict:
            alertar("VERDE EURUSD", "Semáforo VERDE. Sesgo claro, sin roja. Operá "
                    "con tu plan (riesgo <=1%).")
            log.append("  [ALERTA] VERDE -> popup")
        elif "AMARILLO" in verdict:
            # AMARILLO: solo log, no popup (evita spam)
            log.append("  [info] AMARILLO: sin popup (solo log)")

    # guardar traza del ciclo
    try:
        DIARIO.mkdir(parents=True, exist_ok=True)
        fname = "loop_" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".log"
        with open(DIARIO / fname, "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
    except Exception:
        pass

    print("\n".join(log))
    return {"stamp": stamp, "verdict": verdict, "red": red, "log": log}


def main() -> int:
    ap = argparse.ArgumentParser(description="Loop analisis EURUSD (observador)")
    ap.add_argument("--once", action="store_true", help="1 ciclo y sale")
    ap.add_argument("--test-window", action="store_true",
                    help="fuerza ventana abierta (ignora hora)")
    ap.add_argument("--no-alert", action="store_true",
                    help="desactiva popups de alerta")
    ap.add_argument("--no-weekend-off", action="store_true",
                    help="ignora fin de semana (no se apaga vie 15:00/sab/dom)")
    args = ap.parse_args()

    print(f"[loop] Arrancado. SIEMPRE ACTIVO (cada {CYCLE_SECONDS//60} min, 24/7).")
    print(f"[loop] Ventana trading: {TRADE_START_HOUR:02d}:00-"
          f"{TRADE_END_HOUR:02d}:00 Ecuador | MT5: {PY}")
    print(f"[loop] Fin de semana: se apaga vie 15:00 -> lun (al prender compu).")
    print(f"[loop] sin bot: nunca abre ordenes | alertas: "
          f"{'OFF' if args.no_alert else 'popup+sonido'}")

    try:
        if args.once:
            run_cycle(test=args.test_window, no_alert=args.no_alert)
            return 0

        while True:
            now_ec = _now_ecuador()
            if not args.no_weekend_off and _fin_de_semana(now_ec):
                print(f"[loop] FIN DE SEMANA ({now_ec.strftime('%a %H:%M')} Ecuador). "
                      f"Loop APAGADO. Reanuda al prender la compu el lunes. Salida limpia.")
                break
            in_win = args.test_window or _in_window(now_ec)
            tag = "DENTRO de ventana" if in_win else "fuera de ventana (contexto)"
            print(f"[loop] ciclo {now_ec.strftime('%H:%M')} Ecuador | {tag}")
            run_cycle(test=args.test_window, no_alert=args.no_alert)
            if args.test_window:
                print("[loop] --test-window: 1 ciclo hecho, saliendo.")
                break
            time.sleep(CYCLE_SECONDS)
    except KeyboardInterrupt:
        print("\n[loop] detenido por el usuario (Ctrl+C). Salida limpia.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

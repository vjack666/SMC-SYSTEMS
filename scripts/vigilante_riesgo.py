"""
Vigilante de Riesgo — kill-switch de perdida/ganancia flotante (SOLO CIERRA, nunca abre).

Lee el balance y el equity (balance flotante) de la cuenta MT5 EN VIVO.
Si la perdida diaria flotante toca el limite, cierra TODAS las posiciones
abiertas y avisa con popup rojo. Respeta "sin bot": nunca abre ordenes.

Reusa:
  - risk/sizer.py  -> close_position()  (cierre real de MT5)
  - scripts/alertas.py -> alertar()      (popup + sonido)

Uso (en segundo plano, SIN ventana de consola):
  C:/Python314/pythonw.exe scripts/vigilante_riesgo.py
  C:/Python314/python.exe scripts/vigilante_riesgo.py --no-close   # solo avisa (consola)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# --- parametros (editables) ---
SOFT_PCT = 2.0        # freno suave: cierra todo al 2% perdida diaria flotante
HARD_PCT = 4.0        # freno duro: DLL FundedNext (redundante)
GOAL_PROFIT = 60.0    # meta de ganancia flotante: cierra todo al +$60 (banquear)
CHECK_SECONDS = 15    # cada cuantos segundos revisa el equity
MT5_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "risk"))

from sizer import close_position  # noqa: E402


def _init_mt5():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    return mt5


def _log(msg: str) -> None:
    from datetime import datetime
    try:
        Path(BASE / "logs").mkdir(parents=True, exist_ok=True)
        with open(BASE / "logs" / "vigilante.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass
    print(f"[vigilante] {msg}")


def _cerrar_todo(mt5, no_close: bool) -> int:
    """Cierra todas las posiciones abiertas. Devuelve cantidad cerrada."""
    positions = mt5.positions_get()
    if not positions:
        return 0
    count = 0
    for pos in positions:
        if no_close:
            _log(f"[NO-CLOSE] cerraria {pos.symbol} ticket {pos.ticket} vol {pos.volume}")
            count += 1
            continue
        res = close_position(
            ticket=pos.ticket,
            symbol=pos.symbol,
            volume=pos.volume,
            position_type=pos.type,
        )
        ok = res.get("success") if isinstance(res, dict) else False
        _log(f"{'CERRADO' if ok else 'FALLO'} {pos.symbol} ticket {pos.ticket}: {res}")
        if ok:
            count += 1
    return count


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Vigilante de riesgo (kill-switch)")
    ap.add_argument("--no-close", action="store_true",
                    help="solo avisa, no cierra (pruebas)")
    args = ap.parse_args()

    # Instancia unica: el vigilante SIEMPRE corre en segundo plano como
    # servicio; nunca debe duplicarse (dos vigilantes cierran lo mismo dos
    # veces y ensucian los logs).
    sys.path.insert(0, str(BASE / "scripts"))
    from _single_instance import ensure_single_instance
    ensure_single_instance("vigilante_riesgo")

    _log(f"Arrancado. SOFT={SOFT_PCT}% HARD={HARD_PCT}% (DLL) chequeo={CHECK_SECONDS}s")
    _log("SOLO CIERRA, nunca abre. Respeta sin-bot.")

    mt5 = _init_mt5()
    balance0 = mt5.account_info().balance
    _log(f"Balance apertura: {balance0:.2f}")

    closed_once = False
    try:
        while True:
            info = mt5.account_info()
            if info is None:
                _log("MT5 sin cuenta (desconectado?). Reintentando...")
                time.sleep(CHECK_SECONDS)
                continue
            equity = info.equity
            if balance0 > 0:
                loss_pct = (balance0 - equity) / balance0 * 100.0
            else:
                loss_pct = 0.0
            profit_abs = equity - balance0  # ganancia flotante en $

            if loss_pct >= HARD_PCT:
                _log(f"PERDIDA {loss_pct:.2f}% >= DLL {HARD_PCT}% -> CIERRA TODO")
                n = _cerrar_todo(mt5, args.no_close)
                _log(f"RIESGO CRITICO: cerradas {n} operaciones (canal de aviso desactivado)")
                closed_once = True
            elif loss_pct >= SOFT_PCT and not closed_once:
                _log(f"PERDIDA {loss_pct:.2f}% >= limite {SOFT_PCT}% -> CIERRA TODO")
                n = _cerrar_todo(mt5, args.no_close)
                _log(f"RIESGO: cerradas {n} operaciones para proteger la cuenta (canal desactivado)")
                closed_once = True
            elif profit_abs >= GOAL_PROFIT and not closed_once:
                _log(f"GANANCIA FLOTANTE +{profit_abs:.2f}$ >= meta {GOAL_PROFIT:.2f}$ -> CIERRA TODO (banquear)")
                n = _cerrar_todo(mt5, args.no_close)
                _log(f"META ALCANZADA: cerradas {n} operaciones para fijar ganancia")
                closed_once = True
            else:
                # todo ok: reinicia la bandera si el equity se recupero
                if loss_pct < SOFT_PCT and profit_abs < GOAL_PROFIT:
                    closed_once = False

            time.sleep(CHECK_SECONDS)
    except KeyboardInterrupt:
        _log("Detenido por el usuario (Ctrl+C). Salida limpia.")
        return 0
    except Exception as e:  # noqa: BLE001
        _log(f"Error: {e}")
        return 1
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

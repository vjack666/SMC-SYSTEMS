"""Lectura real de la cuenta MT5 para la app del observador.

Reusa el patron de scripts/vigilante_riesgo.py (_init_mt5 + account_info).
NO inventa numeros: si MT5 no esta conectado, devuelve conectado=False y
los campos en None. Asi la UI nunca muestra un numero falso.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app_observador.core.blackbox import log_event, log_error

MT5_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"

_loaded = {"mt5": None}


def _init_mt5():
    if _loaded["mt5"] is not None:
        return _loaded["mt5"]
    import MetaTrader5 as mt5

    if not mt5.initialize(path=MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    _loaded["mt5"] = mt5
    return mt5


def account_snapshot() -> dict:
    """Devuelve estado real de la cuenta o conectado=False.

    Campos: conectado, login, balance, equity, margin_level, riesgo_dia_pct,
    server, clock_utc.
    """
    try:
        mt5 = _init_mt5()
        info = mt5.account_info()
        if info is None:
            return _desconectado("account_info None")
        # riesgo del dia: perdida flotante respecto al balance
        balance = float(info.balance)
        equity = float(info.equity)
        riesgo = round((balance - equity) / balance * 100, 2) if balance else 0.0
        return {
            "conectado": True,
            "login": info.login,
            "balance": balance,
            "equity": equity,
            "margin_level": float(info.margin_level) if info.margin_level else None,
            "riesgo_dia_pct": riesgo,
            "server": info.server,
            "clock_utc": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        }
    except Exception as e:
        return _desconectado(str(e))


def _desconectado(motivo: str) -> dict:
    log_error("mt5_status", "no_conectado", Exception(motivo))
    return {
        "conectado": False,
        "login": None,
        "balance": None,
        "equity": None,
        "margin_level": None,
        "riesgo_dia_pct": None,
        "server": None,
        "clock_utc": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }


def shutdown() -> None:
    mt5 = _loaded.get("mt5")
    if mt5 is not None:
        try:
            mt5.shutdown()
        except Exception:
            pass
        _loaded["mt5"] = None


if __name__ == "__main__":
    snap = account_snapshot()
    print("MT5:", "CONECTADO" if snap["conectado"] else "DESCONECTADO",
          "| balance:", snap["balance"], "| riesgo_dia_%:", snap["riesgo_dia_pct"])

"""Lectura real de la cuenta MT5 para la app del observador.

Reusa el patron de scripts/vigilante_riesgo.py (_init_mt5 + account_info).
NO inventa numeros: si MT5 no esta conectado, devuelve conectado=False y
los campos en None. Asi la UI nunca muestra un numero falso.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app_observador.core.blackbox import log_event, log_error
from app_observador.core.timezone import operator_clock_str

MT5_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"

_loaded = {"mt5": None}
_snap_cache: dict | None = None
_snap_cache_ts: float = 0.0
_SNAP_TTL_S = 4.0


def _init_mt5():
    if _loaded["mt5"] is not None:
        return _loaded["mt5"]
    import MetaTrader5 as mt5

    if not mt5.initialize(path=MT5_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    _loaded["mt5"] = mt5
    return mt5


def account_snapshot(*, force: bool = False) -> dict:
    """Devuelve estado real de la cuenta o conectado=False.

    Campos: conectado, login, balance, equity, margin_level, riesgo_dia_pct,
    server, clock_utc.

    Cached briefly so UI polls don't hammer MT5 / block the event loop.
    """
    import time

    global _snap_cache, _snap_cache_ts
    now = time.monotonic()
    if (
        not force
        and _snap_cache is not None
        and (now - _snap_cache_ts) < _SNAP_TTL_S
    ):
        return _snap_cache
    try:
        mt5 = _init_mt5()
        info = mt5.account_info()
        if info is None:
            snap = _desconectado("account_info None")
            _snap_cache, _snap_cache_ts = snap, now
            return snap
        # riesgo del dia: perdida flotante respecto al balance
        balance = float(info.balance)
        equity = float(info.equity)
        riesgo = round((balance - equity) / balance * 100, 2) if balance else 0.0
        snap = {
            "conectado": True,
            "login": info.login,
            "balance": balance,
            "equity": equity,
            "margin_level": float(info.margin_level) if info.margin_level else None,
            "riesgo_dia_pct": riesgo,
            "server": info.server,
            "clock_utc": datetime.now(timezone.utc).strftime("%H:%M UTC"),
            "clock_operator": operator_clock_str(),
        }
        _snap_cache, _snap_cache_ts = snap, now
        return snap
    except Exception as e:
        snap = _desconectado(str(e))
        _snap_cache, _snap_cache_ts = snap, now
        return snap


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
        "clock_operator": operator_clock_str(),
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

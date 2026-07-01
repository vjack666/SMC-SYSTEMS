"""Risk Guardian for GRID SCALP — standalone MT5 kill-switch monitor.

Monitors account drawdown in real-time. Cuando el drawdown alcanza el umbral
configurado (default 1%) y hay múltiples posiciones abiertas, cierra todas.

Uso:
    python scripts/grid_risk_guardian.py
    python scripts/grid_risk_guardian.py --dd-threshold 1.5 --interval 5

Ejecutar junto con GRID_SCALP.exe como proceso acompañante.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

import MetaTrader5 as mt5


LOG = logging.getLogger("GridRiskGuardian")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Risk Guardian for GRID SCALP")
    p.add_argument("--dd-threshold", type=float, default=1.0, help="Drawdown %% que activa el cierre (default: 1.0)")
    p.add_argument("--min-positions", type=int, default=2, help="Minimo de posiciones abiertas para activar (default: 2)")
    p.add_argument("--interval", type=int, default=3, help="Intervalo de monitoreo en segundos (default: 3)")
    p.add_argument("--symbol", type=str, default=None, help="Simbolo especifico (default: ninguno = todos)")
    p.add_argument("--exclude", type=str, nargs="*", default=[], help="Simbolos a excluir")
    p.add_argument("--log-file", type=str, default=None, help="Archivo de log (opcional)")
    p.add_argument("--verbose", action="store_true", help="Log detallado")
    return p.parse_args()


def _setup_logging(args: argparse.Namespace) -> None:
    level = logging.DEBUG if args.verbose else logging.INFO
    fmt = "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S", handlers=handlers)


def _mt5_connect(max_retries: int = 3, retry_delay: float = 2.0) -> bool:
    for attempt in range(1, max_retries + 1):
        if mt5.initialize():
            LOG.info("Conectado a MT5")
            return True
        LOG.warning("Intento %d/%d: falló conexión MT5: %s", attempt, max_retries, mt5.last_error())
        if attempt < max_retries:
            time.sleep(retry_delay)
    LOG.error("No se pudo conectar a MT5 después de %d intentos", max_retries)
    return False


def _account_snapshot() -> dict[str, Any]:
    info = mt5.account_info()
    if info is None:
        return {"balance": 0.0, "equity": 0.0, "drawdown_pct": 0.0, "connected": False}
    balance = float(getattr(info, "balance", 0.0) or 0.0)
    equity = float(getattr(info, "equity", 0.0) or 0.0)
    dd_pct = ((balance - equity) / balance * 100.0) if balance > 0 else 0.0
    return {
        "balance": balance,
        "equity": equity,
        "drawdown_pct": round(dd_pct, 4),
        "connected": True,
        "server": str(getattr(info, "server", "") or ""),
        "currency": str(getattr(info, "currency", "") or ""),
    }


def _open_positions(symbol: str | None = None, exclude: list[str] | None = None) -> list[dict[str, Any]]:
    exclude_set = set(exclude or [])
    positions = mt5.positions_get(symbol=symbol) or []
    result: list[dict[str, Any]] = []
    for pos in positions:
        sym = str(getattr(pos, "symbol", "") or "")
        if sym in exclude_set:
            continue
        result.append({
            "ticket": int(getattr(pos, "ticket", 0)),
            "symbol": sym,
            "type": "BUY" if int(getattr(pos, "type", -1)) == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": float(getattr(pos, "volume", 0.0) or 0.0),
            "profit": float(getattr(pos, "profit", 0.0) or 0.0),
            "price_open": float(getattr(pos, "price_open", 0.0) or 0.0),
            "price_current": float(getattr(pos, "price_current", 0.0) or 0.0),
            "sl": float(getattr(pos, "sl", 0.0) or 0.0),
            "tp": float(getattr(pos, "tp", 0.0) or 0.0),
        })
    return result


def _close_all_positions(positions: list[dict[str, Any]]) -> int:
    closed = 0
    for pos in positions:
        ticket = int(pos["ticket"])
        symbol = str(pos["symbol"])
        order_type = mt5.ORDER_TYPE_BUY if str(pos["type"]).upper() == "BUY" else mt5.ORDER_TYPE_SELL
        close_type = mt5.ORDER_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(pos["volume"]),
            "type": close_type,
            "position": ticket,
            "price": mt5.symbol_info_tick(symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask,
            "deviation": 20,
            "magic": 0,
            "comment": "grid_risk_guardian_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
            LOG.info("  Cerrado ticket=%d %s %.2fL profit=%.2f", ticket, symbol, pos["volume"], pos["profit"])
        else:
            err = result.comment if result is not None else "sin respuesta"
            LOG.warning("  Error cerrando ticket=%d: %s", ticket, err)
    return closed


def _print_header() -> None:
    LOG.info("=" * 70)
    LOG.info("GRID RISK GUARDIAN")
    LOG.info("=" * 70)


def _print_status(account: dict[str, Any], positions: list[dict[str, Any]]) -> None:
    LOG.info(
        "Balance=%.2f  Equity=%.2f  DD=%.2f%%  Posiciones=%d",
        account["balance"],
        account["equity"],
        account["drawdown_pct"],
        len(positions),
    )


def main() -> None:
    args = _parse_args()
    _setup_logging(args)
    _print_header()

    LOG.info(
        "Umbral DD=%.1f%%  MinPosiciones=%d  Intervalo=%ds  Symbol=%s  Excluir=%s",
        args.dd_threshold,
        args.min_positions,
        args.interval,
        args.symbol or "TODOS",
        args.exclude,
    )

    if not _mt5_connect():
        sys.exit(1)

    info = mt5.terminal_info()
    if info is not None:
        LOG.info("Terminal: %s | Cuenta: %s", info.trade_allowed, info.path if hasattr(info, "path") else "?")

    LOG.info("Monitoreando... (Ctrl+C para detener)")
    LOG.info("-" * 70)

    try:
        while True:
            account = _account_snapshot()
            if not account["connected"]:
                LOG.warning("Conexión perdida, reconectando...")
                time.sleep(2)
                continue

            positions = _open_positions(symbol=args.symbol, exclude=args.exclude)
            _print_status(account, positions)

            dd_pct: float = account["drawdown_pct"]
            num_positions: int = len(positions)

            if dd_pct >= args.dd_threshold and num_positions >= args.min_positions:
                LOG.warning("=" * 70)
                LOG.warning("¡ACTIVACIÓN! DD=%.2f%% >= %.1f%% con %d posiciones abiertas", dd_pct, args.dd_threshold, num_positions)
                LOG.warning("Cerrando todas las posiciones...")

                closed = _close_all_positions(positions)

                account_post = _account_snapshot()
                LOG.warning(
                    "Cierre completo: %d/%d cerradas | Balance=%.2f  Equity=%.2f  DD=%.2f%%",
                    closed,
                    num_positions,
                    account_post["balance"],
                    account_post["equity"],
                    account_post["drawdown_pct"],
                )
                LOG.warning("=" * 70)

                if closed == num_positions:
                    LOG.info("Todas las posiciones cerradas. Risk Guardian en espera...")
                else:
                    LOG.warning("Quedaron %d posiciones sin cerrar", num_positions - closed)

            time.sleep(max(1, args.interval))

    except KeyboardInterrupt:
        LOG.info("Detenido por el usuario")
    finally:
        mt5.shutdown()
        LOG.info("Desconectado de MT5")


if __name__ == "__main__":
    main()

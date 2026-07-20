"""Fase E1-aplicacion: trade management (BE + parcial + trailing) cableado.

TDD RED->GREEN. La funcion `apply_trade_management` es el CALL-SITE REAL que el
backtest usara para gestionar el trade post-entry: dada la senal (entry/SL/TP/
direction) y la serie de precios POST-entry, simula:
  - salida parcial en tp1 (= entry + 1R para LONG, o -1R para SHORT): cierra
    `partial_pct` del lote y mueve SL a BE (entry +/- buf).
  - trailing stop por steps de `trail_step_r * risk` tras el parcial.
  - cierre final en TP, BE o trailing SL.

Sin datos reales: serie sintetica de M15. NO se corre backtest de PF (bloqueado
hasta Fase G); solo la unidad de la funcion de gestion con precios sinteticos.
"""
import numpy as np
import pandas as pd
import pytest

from ict_backtest.trade_mgmt import apply_trade_management


def _series(prices, base_ts="2026-01-05 10:00", freq="15min"):
    times = pd.date_range(base_ts, periods=len(prices), freq=freq, tz="UTC")
    return pd.DataFrame({"time": times, "close": prices})


def test_parcial_en_1r_y_cierre_en_tp(monkeypatch):
    """LONG: precio sube a 1R (partial+BE), luego a TP (cierre resto)."""
    entry = 1.1000
    sl = 1.0980  # risk 0.0020
    tp = 1.1060   # 3R
    direction = 1
    # close: entra en entry, sube a 1R (1.1020), sigue a TP (1.1060), luego baja.
    prices = [1.1000, 1.1010, 1.1020, 1.1040, 1.1060, 1.1050]
    df = _series(prices)
    res = apply_trade_management(
        entry, sl, tp, direction, df,
        partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0,
    )
    # Debe cerrar parcial en 1R y el resto en TP (no en BE ni trailing).
    assert res["exit_reason"] in ("tp", "partial_tp"), res
    assert res["exit_price"] >= tp - 1e-9, f"esperado cierre >= TP {tp}, vino {res['exit_price']}"
    # El PnL combinado debe ser > 0 (parcial en 1R + resto en 3R).
    assert res["pnl_r"] > 0, f"pnl esperado >0, vino {res['pnl_r']}"


def test_be_protege_si_precio_revierte_despues_de_1r(monkeypatch):
    """LONG: sube a 1R (BE+parcial), luego revierte y toca BE -> sin perdida neta."""
    entry = 1.1000
    sl = 1.0980
    tp = 1.1060
    direction = 1
    # Sube a 1R (1.1020) y cae de vuelta a entry (BE).
    prices = [1.1000, 1.1010, 1.1020, 1.1010, 1.1000, 1.0995]
    df = _series(prices)
    res = apply_trade_management(
        entry, sl, tp, direction, df,
        partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0,
    )
    # Tras el parcial en 1R, el SL va a BE; la caida a entry cierra el resto en BE.
    assert res["exit_reason"] in ("be", "breakeven"), res
    # PnL >= 0: parcial en +1R compensa el resto en 0R.
    assert res["pnl_r"] >= -1e-9, f"pnl esperado >=0, vino {res['pnl_r']}"


def test_sin_parcial_toca_sl_directo(monkeypatch):
    """LONG: precio cae directo al SL sin pasar por 1R -> salida en SL."""
    entry = 1.1000
    sl = 1.0980
    tp = 1.1060
    direction = 1
    prices = [1.1000, 1.0995, 1.0985, 1.0980, 1.0975]
    df = _series(prices)
    res = apply_trade_management(
        entry, sl, tp, direction, df,
        partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0,
    )
    assert res["exit_reason"] == "sl", res
    assert res["pnl_r"] < 0, f"pnl esperado <0, vino {res['pnl_r']}"

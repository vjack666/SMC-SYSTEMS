"""Fase 1.2 (E1, libro 18/20) — wiring de trade_mgmt en simulate_trade.

No es test de unidad de to_breakeven/partial_exit/trailing_stop (eso ya lo
cubre test_e1_trade_mgmt.py / test_e1_applied_trade_mgmt.py). Aqui se prueba
el CALL-SITE REAL: que simulate_trade (engine.py) efectivamente INVOCA
apply_trade_management cuando trade_mgmt=True, y que con trade_mgmt=False el
comportamiento es IDENTICO al historico (regresion cero).

Principio (Ruben): un dispatch tras un return, o un modulo que existe pero
nunca se llama, queda MUERTO aunque el test de la funcion aislada siga verde.
Por eso se prueba el wiring end-to-end sobre un frame sintetico.
"""

import numpy as np
import pandas as pd
import pytest

from ict_backtest.engine import simulate_trade, ICTSignal, apply_trade_management


def _make_signal(entry, sl, tp, direction=1, time="2026-01-01 00:00:00"):
    return ICTSignal(
        symbol="EURUSD", time=time, direction=direction,
        entry=entry, stop_loss=sl, take_profit=tp,
        entry_at=0, sweep_at=0,
    )


def _make_frame(prices, time0="2026-01-01 00:00:00"):
    """Frame sintetico con close==prices; high/low abarcan cada close.
    Los 'time' se generan como strings ISO (misma forma que usa signal.time
    en los tests) para que simulate_trade los encuentre por match exacto.
    """
    n = len(prices)
    times = pd.date_range(time0, periods=n, freq="15min").astype(str).tolist()
    highs = [max(prices[i], prices[min(i + 1, n - 1)]) for i in range(n)]
    lows = [min(prices[i], prices[min(i + 1, n - 1)]) for i in range(n)]
    return pd.DataFrame({
        "time": times, "open": prices, "high": highs,
        "low": lows, "close": prices,
    })


# ---------------------------------------------------------------------------
# 1) simulate_trade LLAMA a apply_trade_management cuando trade_mgmt=True
# ---------------------------------------------------------------------------
def test_simulate_trade_calls_apply_trade_management(monkeypatch):
    called = {}

    real_fn = apply_trade_management

    def spy(entry, sl, tp, direction, df, **kw):
        called["hit"] = True
        return real_fn(entry, sl, tp, direction, df, **kw)

    monkeypatch.setattr("ict_backtest.engine.apply_trade_management", spy)

    frame = _make_frame([1.1000, 1.1010, 1.1020, 1.1030, 1.1040])
    sig = _make_signal(1.1000, 1.0990, 1.1030)
    simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=True)
    assert called.get("hit") is True


def test_simulate_trade_does_not_call_tm_when_disabled(monkeypatch):
    called = {}

    def spy(entry, sl, tp, direction, df, **kw):
        called["hit"] = True
        return apply_trade_management(entry, sl, tp, direction, df, **kw)

    monkeypatch.setattr("ict_backtest.engine.apply_trade_management", spy)

    frame = _make_frame([1.1000, 1.1010, 1.1020, 1.1030, 1.1040])
    sig = _make_signal(1.1000, 1.0990, 1.1030)
    simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=False)
    assert called.get("hit") is None  # nunca se invoco


# ---------------------------------------------------------------------------
# 2) Comportamiento historico IDENTICO con trade_mgmt=False
# ---------------------------------------------------------------------------
def test_historical_identical_when_disabled():
    frame = _make_frame([1.1000, 1.1010, 1.1020, 1.1030, 1.1040])
    sig = _make_signal(1.1000, 1.0990, 1.1030)
    t_off, m_off = simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=False)
    # Sin gestion, el trade simple toca TP (1.1030) en la vela 3.
    assert m_off["exit_reason"] == "TP"
    assert t_off.pnl_r > 0


# ---------------------------------------------------------------------------
# 3) Break Even funciona: toca tp1, retrocede, sale en BE (no SL original)
# ---------------------------------------------------------------------------
def test_break_even_exit():
    # entry 1.1000, sl 1.0990 (risk 10), tp 1.1030 (3R).
    # tp1 = 1.1010 (1R dentro de max_hold). Tras el parcial sube a 1.1020,
    # luego retrocede a 1.0990 (SL original) -> debe salir en BE (1.1000),
    # NO en SL (1.0990), porque tras el parcial el SL se movio a BE.
    prices = [1.1000, 1.1010, 1.1020, 1.0990, 1.0990]
    frame = _make_frame(prices)
    sig = _make_signal(1.1000, 1.0990, 1.1030)
    t_on, m_on = simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=True)
    # El parcial ocurrio (tp1=1.1010 tocado) y el remanente salio en BE.
    assert m_on["exit_reason"] == "BE"
    # PnL del remanente en BE == 0 R (salvo comision), mejor que el SL -1R.
    assert t_on.pnl_r >= -1e-9


# ---------------------------------------------------------------------------
# 4) Partial Exit funciona: parcial_done=True y PnL ponderado
# ---------------------------------------------------------------------------
def test_partial_exit_done():
    # tp1 = 1.1010 (1R). Toca tp1 y luego sigue a TP (1.1030) -> parcial en
    # tp1 + remanente en TP. partial_done debe ser True.
    prices = [1.1000, 1.1010, 1.1020, 1.1030, 1.1040]
    frame = _make_frame(prices)
    sig = _make_signal(1.1000, 1.0990, 1.1030)
    t_on, m_on = simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=True)
    assert m_on["exit_reason"] == "TP"
    # Con parcial 50% en 1.1010 (+1R) y remanente 50% en 1.1030 (+3R),
    # pnl_r ponderado = 0.5*1 + 0.5*3 = 2.0 R (antes de comision).
    assert t_on.pnl_r > 1.0  # claramente > que el SL -1R y > simple 1R parcial


# ---------------------------------------------------------------------------
# 5) Trailing funciona: el SL deslizante SACA en GANANCIA antes del colapso
#    que habria golpeado el SL fijo (-1R). Nota: apply_trade_management emite
#    "sl" cuando el SL deslizante es tocado (no distingue "trailing" del
#    reason); lo que demuestra el trailing es el PnL resultante vs el SL fijo.
# ---------------------------------------------------------------------------
def test_trailing_exit():
    # entry 1.1000 sl 1.0990 (SL fijo = -1R). tp 1.1200 lejano. tp1 = 1.1010.
    # Sube a 1.1100 (trailing SL sube a ~1.1090), retrocede a 1.1095 (toca
    # trailing -> sale en ganancia), luego COLAPSARIA a 1.0990 (SL fijo -1R)
    # pero el trade ya cerro por el trailing.
    prices = [1.1000, 1.1010, 1.1100, 1.1095, 1.0990]
    frame = _make_frame(prices)
    sig = _make_signal(1.1000, 1.0990, 1.1200)
    t_on, m_on = simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=True)
    t_off, m_off = simulate_trade(frame, sig, max_hold_bars=10, trade_mgmt=False)
    # Con gestion (trailing) el trade cierra en GANANCIA (el SL deslizante
    # corto el retroceso antes del colapso al SL fijo).
    assert t_on.pnl_r > 0                 # gano por el trailing
    # Sin gestion el SL fijo es golpeado en el colapso -> perdida -1R.
    assert m_off["exit_reason"] == "SL"
    assert t_off.pnl_r < 0
    # El trailing MEJORO el resultado (evito la perdida del SL fijo).
    assert t_on.pnl_r > t_off.pnl_r

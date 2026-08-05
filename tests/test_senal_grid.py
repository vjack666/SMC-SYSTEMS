"""Tests de la FASE GRID en la pestaña Señal (senal_widget.py).

Verifica la lógica de reglas del grid SIN MT5 real: mockea positions_get
y copy_rates_from_pos. Las reglas son las dictadas por el usuario:
  base 0.50, capa1 0.15 (20p en contra + toque banda), capa2 0.20 (otros 20p).
"""
from __future__ import annotations

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from app_observador.ui.senal_widget import (
    BASE_LOT, GRID_LOT_1, GRID_LOT_2, PIP_STEP,
    _GRID_VALUES, SenalWidget,
)

_app = QApplication.instance() or QApplication([])


def _make_m15(close_prices):
    return pd.DataFrame({
        "close": close_prices,
        "open": close_prices,
        "high": [c + 0.0005 for c in close_prices],
        "low": [c - 0.0005 for c in close_prices],
        "time": list(range(len(close_prices))),
    })


def _inject(widget, n_pos, side, base_price, m15_close):
    """Inyecta un mt5 fake en el widget y fuerza mt5_ready."""
    class FakePos:
        def __init__(self, nn, ss, pp):
            self._nn, self._ss, self._pp = nn, ss, pp
        def positions_get(self, symbol=None):
            if self._nn == 0:
                return ()
            t = 0 if self._ss == "BUY" else 1
            return [type("P", (), {"type": t, "price_open": self._pp})() for _ in range(self._nn)]
        def copy_rates_from_pos(self, symbol, tf, start, count):
            return _make_m15(m15_close).to_dict("records")
        TIMEFRAME_M15 = 15
        def terminal_info(self):
            return object()
        def initialize(self):
            return True
    widget._mt5 = FakePos(n_pos, side, base_price)
    widget._mt5_ready = True


def test_constants_match_user_rules():
    assert BASE_LOT == 0.50
    assert GRID_LOT_1 == 0.15
    assert GRID_LOT_2 == 0.20
    assert PIP_STEP == 20.0
    assert _GRID_VALUES["bb_period"] == 20
    assert _GRID_VALUES["bb_std"] == 2.0


def test_phase_switch_no_position_returns_to_stochastic():
    w = SenalWidget()
    w._mt5_ready = False
    w._mt5 = None
    w._poll_grid()
    assert w._in_grid is False
    assert w._grid_page.isHidden()
    assert not w._setup_page.isHidden()


def test_phase_grid_buy_25pips_down_touch_triggers_capa1():
    w = SenalWidget()
    base = 1.10000
    close = [base - i * 0.0003 for i in range(80)]
    _inject(w, n_pos=1, side="BUY", base_price=base, m15_close=close)
    w._poll_grid()
    assert w._in_grid is True
    assert not w._grid_page.isHidden()
    assert w._lights["r1"]._state is True
    assert w._lights["r2"]._state is True
    assert w._lights["r3"]._state is True


def test_phase_grid_buy_only_5pips_down_not_ready():
    w = SenalWidget()
    base = 1.10000
    # Solo ~5 pips de bajada en la última vela (el resto plano)
    close = [base - 0.0005] * 75 + [base - i * 0.0001 for i in range(5)]
    _inject(w, n_pos=1, side="BUY", base_price=base, m15_close=close)
    w._poll_grid()
    assert w._in_grid is True
    assert w._lights["r1"]._state is False
    assert w._lights["r3"]._state is False


def test_layer_count_from_real_positions():
    w = SenalWidget()
    base = 1.10000
    close = [base - i * 0.0003 for i in range(80)]
    _inject(w, n_pos=3, side="BUY", base_price=base, m15_close=close)
    w._poll_grid()
    assert "3 ops" in w.g_banner.text() or "COMPLETO" in w.g_banner.text()

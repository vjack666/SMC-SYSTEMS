"""TDD E1 — Trade Management (funciones puras, datos sinteticos).

No usa parquet ni datos reales. Objetos fake para tipos ICTSignal/ICTTrade.
"""
from __future__ import annotations

import pytest

from ict_backtest.trade_mgmt import to_breakeven, partial_exit, trailing_stop


# ---------------------------------------------------------------------------
# to_breakeven
# ---------------------------------------------------------------------------
class TestToBreakeven:
    def test_long_no_mueve_si_no_alcanza_trigger(self):
        # risk = 100-90 = 10; trigger 1R => precio >= 110. Aqui 105 < 110.
        assert to_breakeven(entry=100.0, sl=90.0, direction=1,
                            current_price=105.0, be_trigger_r=1.0) is None

    def test_long_mueve_a_be_al_alcanzar_trigger(self):
        sl = to_breakeven(entry=100.0, sl=90.0, direction=1,
                          current_price=110.0, be_trigger_r=1.0)
        assert sl == 100.0

    def test_short_no_mueve_si_no_alcanza(self):
        # risk = 110-100 = 10; trigger 1R => precio <= 90. Aqui 95 > 90.
        assert to_breakeven(entry=100.0, sl=110.0, direction=-1,
                            current_price=95.0, be_trigger_r=1.0) is None

    def test_short_mueve_a_be(self):
        sl = to_breakeven(entry=100.0, sl=110.0, direction=-1,
                          current_price=90.0, be_trigger_r=1.0)
        assert sl == 100.0

    def test_trigger_custom_2r(self):
        assert to_breakeven(entry=100.0, sl=90.0, direction=1,
                            current_price=115.0, be_trigger_r=2.0) is None
        assert to_breakeven(entry=100.0, sl=90.0, direction=1,
                            current_price=120.0, be_trigger_r=2.0) == 100.0

    def test_risk_cero_no_mueve(self):
        assert to_breakeven(entry=100.0, sl=100.0, direction=1,
                            current_price=110.0) is None

    def test_direccion_invalida(self):
        with pytest.raises(ValueError):
            to_breakeven(entry=100.0, sl=90.0, direction=0, current_price=110.0)


# ---------------------------------------------------------------------------
# partial_exit
# ---------------------------------------------------------------------------
class TestPartialExit:
    def test_long_toca_tp1(self):
        assert partial_exit(entry=100.0, tp1=120.0, direction=1,
                            current_price=120.0) is True
        assert partial_exit(entry=100.0, tp1=120.0, direction=1,
                            current_price=125.0) is True

    def test_long_no_toca_tp1(self):
        assert partial_exit(entry=100.0, tp1=120.0, direction=1,
                            current_price=119.9) is False

    def test_short_toca_tp1(self):
        assert partial_exit(entry=100.0, tp1=80.0, direction=-1,
                            current_price=80.0) is True
        assert partial_exit(entry=100.0, tp1=80.0, direction=-1,
                            current_price=75.0) is True

    def test_short_no_toca_tp1(self):
        assert partial_exit(entry=100.0, tp1=80.0, direction=-1,
                            current_price=80.1) is False

    def test_pct_invalido(self):
        with pytest.raises(ValueError):
            partial_exit(entry=100.0, tp1=120.0, direction=1,
                         current_price=120.0, pct=1.5)


# ---------------------------------------------------------------------------
# trailing_stop
# ---------------------------------------------------------------------------
class TestTrailingStop:
    def test_long_no_baja_sl_si_no_avanza(self):
        # risk=10; precio 105 < 1 step => SL queda igual
        assert trailing_stop(entry=100.0, sl=90.0, direction=1,
                             current_price=105.0, step_r=1.0) == 90.0

    def test_long_sube_sl_tras_un_step(self):
        # precio 110 => 1R de favor => SL sube 1 step = 100
        assert trailing_stop(entry=100.0, sl=90.0, direction=1,
                             current_price=110.0, step_r=1.0) == 100.0

    def test_long_sube_sl_tras_dos_steps(self):
        assert trailing_stop(entry=100.0, sl=90.0, direction=1,
                             current_price=120.0, step_r=1.0) == 110.0

    def test_long_nunca_empeora(self):
        # SL ya alto (105); precio solo da 1 step (SL candidato 100) => no baja
        assert trailing_stop(entry=100.0, sl=105.0, direction=1,
                             current_price=110.0, step_r=1.0) == 105.0

    def test_short_baja_sl_tras_un_step(self):
        assert trailing_stop(entry=100.0, sl=110.0, direction=-1,
                             current_price=90.0, step_r=1.0) == 100.0

    def test_short_nunca_empeora(self):
        assert trailing_stop(entry=100.0, sl=95.0, direction=-1,
                             current_price=90.0, step_r=1.0) == 95.0

    def test_direccion_invalida(self):
        with pytest.raises(ValueError):
            trailing_stop(entry=100.0, sl=90.0, direction=0, current_price=110.0)

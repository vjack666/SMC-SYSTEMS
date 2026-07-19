"""RED — Fase 3: emisor M5 (Ejecucion) decide ENTRY_READY.

emit_m5 recibe el setup validado (direction) y la confirmacion de M5.
M5 NO cambia la direccion del plan: solo decide SI entra (confirmacion
de ejecucion). Test FALLA hasta implementar emit_m5.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.plan_fsm import PlanVerdict


def _setup(direction):
    return {"direction": direction}


def _confirm(direction, confirmed):
    return {"direction": direction, "confirmed": confirmed}


def test_emit_m5_entry_ready_cuando_confirmacion_alcista():
    from ict_backtest.plan_emitters import emit_m5

    ev = emit_m5(_setup(1), _confirm(1, True))
    assert ev is not None
    assert ev.layer == "M5"
    assert ev.verdict is PlanVerdict.ENTRY_READY


def test_emit_m5_entry_ready_cuando_confirmacion_bajista():
    from ict_backtest.plan_emitters import emit_m5

    ev = emit_m5(_setup(-1), _confirm(-1, True))
    assert ev.verdict is PlanVerdict.ENTRY_READY


def test_emit_m5_none_cuando_sin_confirmacion():
    from ict_backtest.plan_emitters import emit_m5

    ev = emit_m5(_setup(1), _confirm(1, False))
    assert ev is None


def test_emit_m5_none_cuando_direccion_no_coincide():
    # M5 NO puede invertir la direccion del plan (regla de jerarquia)
    from ict_backtest.plan_emitters import emit_m5

    ev = emit_m5(_setup(1), _confirm(-1, True))
    assert ev is None

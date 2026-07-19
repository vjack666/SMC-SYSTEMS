"""RED — Fase 2: emisor M15 (Setup) envuelve la salida de run_sequence.

emit_m15 recibe la LISTA de senales que devuelve run_sequence (cada una
con phase_log) y emite SETUP_LIVE / STRUCTURE_OK segun la fase alcanzada.
NO corre run_sequence (el loop driver lo hace); el emisor es una funcion
pura sobre la salida. Test FALLA hasta implementar emit_m15.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.plan_fsm import PlanVerdict


def _signal(phase_log):
    return {"phase_log": phase_log}


def test_emit_m15_setup_live_cuando_llega_a_bos():
    from ict_backtest.plan_emitters import emit_m15

    sigs = [_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE"])]
    ev = emit_m15(sigs)
    assert ev is not None
    assert ev.layer == "M15"
    assert ev.verdict is PlanVerdict.SETUP_LIVE


def test_emit_m15_structure_ok_cuando_llega_a_entry():
    from ict_backtest.plan_emitters import emit_m15

    sigs = [_signal(["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"])]
    ev = emit_m15(sigs)
    assert ev.verdict is PlanVerdict.STRUCTURE_OK


def test_emit_m15_none_cuando_sin_senales():
    from ict_backtest.plan_emitters import emit_m15

    ev = emit_m15([])
    assert ev is None


def test_emit_m15_none_cuando_solo_sweep():
    from ict_backtest.plan_emitters import emit_m15

    # sweep sin BOS no es setup valido
    sigs = [_signal(["SWEEP_DONE"])]
    ev = emit_m15(sigs)
    assert ev is None

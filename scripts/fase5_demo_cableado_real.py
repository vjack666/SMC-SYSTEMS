"""Fase 5 demo: CABLEADO REAL del medidor de alineacion (sin contextos reales).

Fase E regla #5: demo sintetica ANTES de tocar datos reales. Valida que
attach_alignment recibe MarketObjects REALES (no dicts planos) y produce
score > 0 cuando hay contexto+setup alineado. No usa data/raw ni run_sequence.

Esto prueba el CONTRATO del loop driver:
  objs_by_tf (MarketObject sellados por TF) -> attach_alignment -> AlignmentReport
sin depender de la forma interna de build_context_stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime, timedelta

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.plan_attach import attach_alignment


def _mk(tf, otype, direction, t, role=None, zone=None):
    return MarketObject(
        type=otype,
        origin_tf=tf,
        direction=direction,
        role=role if role is not None else (
            Role.POI if otype in (ObjectType.FVG, ObjectType.ORDER_BLOCK)
            and tf in ("D1", "H4", "H1") else Role.REFINEMENT),
        state=ObjectState.ACTIVE,
        bar_index=0,
        bar_time=t,
        zone_high=zone[1] if zone else 0.0,
        zone_low=zone[0] if zone else 0.0,
    )


def _scenario_aligned() -> dict:
    """Escenario totalmente alineado: D1/H4 bias + H1 POI + M15 entry + swing."""
    base = datetime(2024, 1, 1, 0, 0)
    objs_by_tf = {
        "D1": [_mk("D1", ObjectType.BOS, 1, base, role=Role.CONTEXT)],
        "H4": [_mk("H4", ObjectType.BOS, 1, base, role=Role.CONTEXT)],
        "H1": [_mk("H1", ObjectType.ORDER_BLOCK, 1, base, role=Role.POI)],
        "M15": [_mk("M15", ObjectType.FVG, 1, base + timedelta(minutes=15),
                    zone=(1.0900, 1.0950))],
        "M5": [_mk("M5", ObjectType.BOS, 1, base + timedelta(minutes=5))],
        "M1": [_mk("M1", ObjectType.CHOCH, 1, base + timedelta(minutes=1))],
    }
    sig = {"direction": 1, "time": base + timedelta(minutes=15), "entry_at": 15}
    swing = (1.1000, 1.0800)  # high, low -> EQ ~1.0900, zona M15 en discount
    return attach_alignment(sig, objs_by_tf, swing=swing)


def _scenario_empty() -> dict:
    """Sin objetos: debe dar score 0, no romper (Regla #4 sin inventar)."""
    sig = {"direction": 1, "time": datetime(2024, 1, 1), "bar_index": 0}
    return attach_alignment(sig, {}, swing=None)


def main() -> None:
    a = _scenario_aligned()
    e = _scenario_empty()
    print("=== DEMO CABLEADO REAL (sintetico) ===")
    print(f"alineado : score={a['alignment']['score']}  "
          f"d1={a['alignment']['d1']} h4={a['alignment']['h4']} "
          f"h1={a['alignment']['h1']} m15={a['alignment']['m15']} "
          f"m5={a['alignment']['m5']} m1={a['alignment']['m1']} "
          f"anchored={a['alignment']['m15_anchored']} "
          f"po3={a['alignment']['po3_complete']}")
    print(f"vacio    : score={e['alignment']['score']}")

    ok = (
        a["alignment"]["score"] >= 5.0
        and a["alignment"]["d1"] and a["alignment"]["h4"]
        and a["alignment"]["h1"] and a["alignment"]["m15"]
        and a["alignment"]["m5"] and a["alignment"]["m1"]
        and a["alignment"]["m15_anchored"]
        and e["alignment"]["score"] == 0.0
    )
    print("RESULTADO:", "PASS" if ok else "FAIL")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

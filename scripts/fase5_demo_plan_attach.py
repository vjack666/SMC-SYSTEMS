"""Fase 5 Brecha A1 — Demo sintetica: attach_alignment califica la senal.

Muestra que por cada senal se adjunta un AlignmentReport multi-TF (D1/H4/H1/
M15/M5/M1) sumando bonus por ancla y zona. NO toca produccion. El bot opera
IGUAL; el reporte solo califica (modo OBSERVE).
Correr: python scripts/fase5_demo_plan_attach.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.plan_attach import attach_alignment


def _o(type, direction, tf, bar_index, role, oid, zh=0.0, zl=0.0):
    return MarketObject(type=type, direction=direction, origin_tf=tf, role=role,
                        state=ObjectState.ACTIVE, bar_index=bar_index, id=oid,
                        zone_high=zh, zone_low=zl)


def main():
    print("=== Demo Brecha A1: attach_alignment (sintetico, modo OBSERVE) ===\n")
    senal = {"direction": 1, "bar_index": 100,
             "phase_log": ["SWEEP_DONE", "DISPLACE_DONE", "BOS_DONE", "ENTRY"]}
    objetos = {
        "D1": [_o(ObjectType.LIQUIDITY, 1, "D1", 10, Role.CONTEXT, "d1")],
        "H4": [_o(ObjectType.BOS, 1, "H4", 20, Role.REFINEMENT, "h4")],
        "H1": [_o(ObjectType.ORDER_BLOCK, 1, "H1", 30, Role.POI, "h1")],
        "M15": [_o(ObjectType.FVG, 1, "M15", 100, Role.REFINEMENT, "fvg",
                   zh=1.1030, zl=1.1020)],
    }
    attached = attach_alignment(senal, objetos, swing=(1.1100, 1.1000))
    rep = attached["alignment"]
    print(f"  score={rep['score']:.1f}")
    print(f"  D1={rep['d1']} H4={rep['h4']} H1={rep['h1']} M15={rep['m15']} "
          f"M5={rep['m5']} M1={rep['m1']}")
    print(f"  POI anclado={rep['m15_anchored']}")
    print("\nEl reporte se adjunta a la senal; el backtest opera IGUAL.")
    print("El score es solo una calificacion para aprender, no un filtro.")


if __name__ == "__main__":
    main()

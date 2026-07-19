"""Fase 5 Brecha B — Demo sintetica: ancla narrativa POI (poi_anchor).

Muestra con datos trucados que un FVG/OB M15 se marca 'anchored' solo si hay
BOS/CHOCH del TF padre (H4/H1) en la misma direccion y ya cerrado. NO toca
produccion. Correr: python scripts/fase5_demo_poi_anchor.py
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
from ict_backtest.poi_anchor import anchor_objects


def _obj(type, direction, tf, bar_index, oid):
    return MarketObject(
        type=type, direction=direction, origin_tf=tf,
        role=Role.POI if tf in ("D1", "H4", "H1") else Role.REFINEMENT,
        state=ObjectState.ACTIVE, bar_index=bar_index, id=oid,
    )


def main():
    print("=== Demo Brecha B: ancla narrativa POI (sintetico) ===\n")

    h4 = [
        _obj(ObjectType.BOS, 1, "H4", 50, "bos_h4"),   # BOS alcista H4 previo
        _obj(ObjectType.CHOCH, -1, "H4", 30, "choch_h4"),  # CHOCH bajista (otra dir)
    ]
    h1 = [
        _obj(ObjectType.BOS, 1, "H1", 80, "bos_h1"),   # BOS alcista H1 previo
    ]
    ltf = [
        _obj(ObjectType.FVG, 1, "M15", 100, "fvg_m15"),
        _obj(ObjectType.FVG, 1, "M15", 200, "fvg_m15_fut"),  # sin padre (caso opuesto)
        _obj(ObjectType.ORDER_BLOCK, -1, "M15", 120, "ob_m15_bear"),
    ]

    anchored = anchor_objects(ltf, {"H4": h4, "H1": h1})

    for o in anchored:
        estado = "ANCLADO" if o.meta.get("anchored") else "suelta"
        padre = o.parent_object or "-"
        print(f"  {o.type.value:12} {o.origin_tf:4} dir={o.direction:+d} "
              f"bar={o.bar_index:>4} -> {estado} (padre={padre})")

    print("\nRegla: FVG/OB M15 cuenta como POI real SOLO si hay BOS/CHOCH HTF")
    print("padre en la misma direccion y ya cerrado. Sin eso = geometria suelta.")
    print("El ancla es BONUS (marca, no borra): el score_plan le da +0.5 si anclado.")


if __name__ == "__main__":
    main()

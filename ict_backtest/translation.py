"""ict_backtest/translation.py — capa de traduccion DataFrame <-> MarketObject.

ESCUDO de compatibilidad (REVISION_ARQUITECTURA_CONVIVENCIA.md):
- objects_to_legacy_df: desde MarketObject reconstruye las columnas sueltas
  que hoy leen sequence/rules/engine/ML/UI. Asi NADIE se entera del cambio.
- df_to_objects (Tarea B.2): desde {tf: df} produce MarketObject con
  origin_tf sellado y role por regla de capa.

El objeto nuevo vive "debajo" como fuente canonica; las columnas son una
VISTA reconstruida, no la verdad.
"""

from __future__ import annotations

import pandas as pd

from ict_backtest.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)


# Capas que cuentan como HTF para la regla de POI/CONTEXT (ontologia).
_HTF_TFS = {"D1", "H4", "H1"}


# Mapeo de estado (objeto -> columna legacy). Ver ontologia §5 y pipeline.
_STATE_TO_STATUS = {
    ObjectState.ACTIVE: "active",
    ObjectState.CREATED: "active",      # aun no mitigado = vigente
    ObjectState.MITIGATED: "active",   # sigue vigente hasta consumo/invalid
    ObjectState.CONSUMED: "active",    # ya operado; pipeline no lo filtra
    ObjectState.INVALIDATED: "none",   # compatible con bos_alive de pipeline
}


def objects_to_legacy_df(objects: list[MarketObject]) -> pd.DataFrame:
    """Reconstruye el dict de columnas sueltas desde MarketObjects.

    Garantiza que sequence.py/rules.py/engine.py/signals/pipeline.py/
    features/engine.py/ml/*/UI sigan leyendo las MISMAS columnas de siempre.
    """
    rows: list[dict] = []
    for o in objects:
        t = o.type.value
        is_bos = t == "BOS"
        is_choch = t == "CHOCH"
        is_fvg = t == "FVG"
        is_ob = t == "ORDER_BLOCK"
        rows.append({
            "type": t,
            "origin_tf": o.origin_tf,
            "role": o.role.value,
            "direction": o.direction,
            "bos_direction": o.direction if is_bos else 0,
            "bos_status": _STATE_TO_STATUS.get(o.state, "none"),
            "choch_dir": o.direction if is_choch else 0,
            "choch_status": _STATE_TO_STATUS.get(o.state, "none") if is_choch else "-",
            "fvg_state": (t if is_fvg else "-"),
            "fvg_bullish": (is_fvg and o.direction == 1),
            "fvg_bearish": (is_fvg and o.direction == -1),
            "ob_direction": (t if is_ob else "-"),
            "ob_bullish": (is_ob and o.direction == 1),
            "ob_bearish": (is_ob and o.direction == -1),
            "ob_status": _STATE_TO_STATUS.get(o.state, "none") if is_ob else "-",
            "macro_direction": (t if (is_bos or is_choch) else "-"),
            "zone_high": o.zone_high,
            "zone_low": o.zone_low,
            "quality_score": o.quality_score,
        })
    return pd.DataFrame(rows)


def df_to_objects(frames: dict[str, pd.DataFrame],
                   symbol: str = "") -> list[MarketObject]:
    """Desde {tf: df con columnas de detectores} produce MarketObjects.

    SELLA la capa (origen) y aplica la regla de rol:
    - HTF (D1/H4/H1): FVG/OB -> POI; BOS/CHOCH -> CONTEXT.
    - LTF (M15/M5/M3/M1): FVG/OB/BOS/CHOCH -> REFINEMENT (nunca POI).

    Reusa las columnas que build_features ya calculo (bos_direction,
    fvg_bullish, etc.). No reescribe los detectores: solo los ENVUELVE en
    objetos con identidad. Es el unico punto de verdad del sello de capa.
    """
    objs: list[MarketObject] = []
    for tf, df in frames.items():
        htf = tf in _HTF_TFS
        for _, row in df.iterrows():
            bd = int(row.get("bos_direction", 0) or 0)
            if bd != 0:
                objs.append(MarketObject(
                    type=ObjectType.BOS, origin_tf=tf,
                    role=Role.CONTEXT if htf else Role.REFINEMENT,
                    direction=bd, symbol=symbol, state=ObjectState.ACTIVE,
                ))
            cd = int(row.get("choch_dir", 0) or 0)
            if cd != 0:
                objs.append(MarketObject(
                    type=ObjectType.CHOCH, origin_tf=tf,
                    role=Role.CONTEXT if htf else Role.REFINEMENT,
                    direction=cd, symbol=symbol, state=ObjectState.ACTIVE,
                ))
            fb = bool(row.get("fvg_bullish", False))
            fbe = bool(row.get("fvg_bearish", False))
            if fb or fbe:
                d = 1 if fb else -1
                objs.append(MarketObject(
                    type=ObjectType.FVG, origin_tf=tf,
                    # POI solo en HTF (regla dura de capa).
                    role=Role.POI if htf else Role.REFINEMENT,
                    direction=d, symbol=symbol, state=ObjectState.ACTIVE,
                ))
            obb = bool(row.get("ob_bullish", False))
            obbe = bool(row.get("ob_bearish", False))
            if obb or obbe:
                d = 1 if obb else -1
                objs.append(MarketObject(
                    type=ObjectType.ORDER_BLOCK, origin_tf=tf,
                    role=Role.POI if htf else Role.REFINEMENT,
                    direction=d, symbol=symbol, state=ObjectState.ACTIVE,
                ))
    return objs

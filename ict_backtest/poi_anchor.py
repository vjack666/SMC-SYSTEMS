"""ict_backtest/poi_anchor.py — Brecha B: ancla narrativa de POI (Fase 5).

El POI real esta ANCLADO a la narrativa: un desplazamiento estructural (BOS/CHOCH)
en el TF padre en la MISMA direccion (libro 21 §4). Sin eso, el FVG/OB es
geometria suelta (auditoria: 100% de las zonas sin ancla hoy).

anchor_objects MARCA cada objeto LTF con meta["anchored"]=True/False segun si
hay BOS/CHOCH en los TF padre (HTF: D1/H4/H1) en la misma direccion y ya cerrado
(bar_index <= al del objeto LTF). NO borra nada: es BONUS (libro 21 §4: POI como
bonus, filtro duro destruye edge).

Funcion PURA: recibe lista de objetos LTF + dict {tf: [objetos HTF]}. No accede a
discos ni a bar_index de df. Anti look-ahead por bar_index.
"""

from __future__ import annotations

from ict_backtest.market_object import MarketObject, ObjectType, Role

# TF que pueden actuar como padre de un POI LTF (ontologia market_object)
_HTF_PARENTS = ("D1", "H4", "H1")


def _is_structural(obj: MarketObject) -> bool:
    return obj.type in (ObjectType.BOS, ObjectType.CHOCH)


def _closed_before(candidate_time, candidate_idx, ltf_time, ltf_idx) -> bool:
    """True si el objeto padre ya cerró ANTES que el LTF (anti look-ahead).

    Dominio real: compara por ``bar_time`` (timestamp), porque HTF y LTF
    tienen índices de barra DISTINTOS (un H4 no comparte bar_index con un
    M15). Fallback a bar_index solo si ambos bar_time son None.
    """
    ct = candidate_time
    lt = ltf_time
    if ct is not None and lt is not None:
        # normaliza a timestamps comparables
        import pandas as pd
        try:
            return pd.to_datetime(ct) <= pd.to_datetime(lt)
        except (TypeError, ValueError):
            pass
    # fallback (sin timestamps): solo si ambos índices presentes
    if candidate_idx is not None and ltf_idx is not None:
        return candidate_idx <= ltf_idx
    return False


def anchor_objects(
    ltf_objects: list[MarketObject],
    htf_objects_by_tf: dict[str, list[MarketObject]],
    window_n: int = 20,
) -> list[MarketObject]:
    """Marca cada objeto LTF con meta['anchored'] segun respaldo HTF padre.

    Para cada objeto LTF (FVG/OB REFINEMENT), busca en los TF padre (D1/H4/H1)
    un BOS/CHOCH en la MISMA direccion ya CERRADO (bar_time <= ltf.bar_time,
    anti look-ahead cross-TF). Solo mira los ultimos ``window_n`` objetos HTF
    previos (ventana, libro 21 §6).
    Devuelve la misma lista (objetos mutados in-place en meta/parent).
    """
    # indice plano de objetos HTF padre por direccion
    parents_by_dir: dict[int, list[MarketObject]] = {1: [], -1: []}
    for tf in _HTF_PARENTS:
        for o in htf_objects_by_tf.get(tf, []) or []:
            if _is_structural(o) and o.direction in parents_by_dir:
                parents_by_dir[o.direction].append(o)

    for obj in ltf_objects:
        obj.meta["anchored"] = False
        obj.parent_object = None
        if obj.direction not in parents_by_dir:
            continue
        candidates = parents_by_dir[obj.direction]
        # solo HTF ya cerrados (bar_time <= LTF) y los ultimos window_n
        prior = [
            p for p in candidates
            if _closed_before(p.bar_time, p.bar_index, obj.bar_time, obj.bar_index)
        ]
        prior = prior[-window_n:] if window_n else prior
        if prior:
            anchor = prior[-1]
            obj.meta["anchored"] = True
            obj.parent_object = anchor.id
            if anchor.id not in obj.related_objects:
                obj.related_objects.append(anchor.id)
    return ltf_objects

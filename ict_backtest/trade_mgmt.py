"""E1 — Trade Management: funciones PURAS de gestion post-entry.

Modulo NUEVO y aislado (no edita canonical/engine/sequence/poi_filter ni datos).
Todas las funciones devuelven SOLO calculo; no mutan estado global.

Tipos ICTSignal/ICTTrade viven en ict_backtest.engine; aqui trabajamos con
primitivos (entry/sl/tp/direction/current_price) para maxima pureza y testeo.

Convencion direccion: +1 long, -1 short (igual que ICTSignal.direction).
"""
from __future__ import annotations


def _check_direction(direction: int) -> None:
    if direction not in (1, -1):
        raise ValueError(f"direction invalida: {direction!r} (use +1 long | -1 short)")


def to_breakeven(
    entry: float,
    sl: float,
    direction: int,
    current_price: float,
    be_trigger_r: float = 1.0,
) -> float | None:
    """Mueve SL a Break-Even (=entry) si el precio avanzo >= be_trigger_r * risk.

    risk = |entry - sl|. Long: avance = current - entry; Short: entry - current.
    Devuelve el nuevo SL (=entry) si se alcanzo el trigger; si no, None (no mover).
    Sin estructura a favor (risk<=0) => None (dejar SL original).
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    if advance >= be_trigger_r * risk:
        return float(entry)
    return None


def partial_exit(
    entry: float,
    tp1: float,
    direction: int,
    current_price: float,
    pct: float = 0.5,
) -> bool:
    """True si el precio toco tp1 (liquidez internal) y corresponde cerrar pct.

    Long: current >= tp1. Short: current <= tp1.
    pct debe estar en (0, 1]. No calcula el cierre; solo señala si corresponde.
    """
    _check_direction(direction)
    if not (0.0 < pct <= 1.0):
        raise ValueError(f"pct fuera de rango (0,1]: {pct!r}")
    if direction == 1:
        return current_price >= tp1
    return current_price <= tp1


def trailing_stop(
    entry: float,
    sl: float,
    direction: int,
    current_price: float,
    step_r: float = 1.0,
) -> float:
    """SL deslizante que solo mejora (sube en long / baja en short), nunca empeora.

    risk = |entry - sl|. Cada step_r de favor arrastra el SL step_r*risk hacia el
    precio. Devuelve max(sl, candidato) en long y min(sl, candidato) en short.
    Si no hay avance suficiente o risk<=0, devuelve el SL original.
    """
    _check_direction(direction)
    risk = abs(entry - sl)
    if risk <= 0:
        return float(sl)
    step = step_r * risk
    advance = (current_price - entry) if direction == 1 else (entry - current_price)
    steps = int(advance // step)  # nro de steps completos de favor
    if steps <= 0:
        return float(sl)
    if direction == 1:
        candidate = entry + (steps - 1) * step
        return float(max(sl, candidate))
    candidate = entry - (steps - 1) * step
    return float(min(sl, candidate))

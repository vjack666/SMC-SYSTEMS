"""ict_backtest/dealing_range.py — Brecha C: dealing range premium/discount (Fase 5).

Tesis (libro 21 §0/§2, libro 08 PO3): un POI valido debe estar en la ZONA
CORRECTA del dealing range. EQ = 50% fib del swing HTF. discount (< EQ) para
long; premium (> EQ) para short; EQ central (~12% del rango) es ambiguo.

classify_zone marca la zona (no borra). zone_ok_for_direction dice si la zona
favorece la direccion del setup. EQ es ambiguo: no cuenta como bonificada pero
NO descarta la senal (BONUS, no filtro duro; libro 21 §4).
"""

from __future__ import annotations

_EQ_BAND = 0.12  # 12% del rango alrededor del EQ se considera ambiguo


def _eq(swing_high: float, swing_low: float) -> float:
    return (swing_high + swing_low) / 2.0


def classify_zone(
    zone_high: float,
    zone_low: float,
    swing_high: float,
    swing_low: float,
) -> str:
    """Clasifica la zona segun el dealing range del swing HTF.

    Usa el midpoint de la zona vs EQ (50% del swing). Devuelve
    'PREMIUM' | 'DISCOUNT' | 'EQ'.
    """
    if swing_high <= swing_low:
        raise ValueError("swing_high debe ser > swing_low")
    eq = _eq(swing_high, swing_low)
    rng = swing_high - swing_low
    band = rng * _EQ_BAND
    mid = (zone_high + zone_low) / 2.0
    if abs(mid - eq) <= band:
        return "EQ"
    return "DISCOUNT" if mid < eq else "PREMIUM"


def zone_ok_for_direction(zone_class: str, direction: int) -> bool:
    """Si la zona favorece la direccion del setup.

    long (1) quiere DISCOUNT; short (-1) quiere PREMIUM. EQ es ambiguo
    (no bonifica, no descarta).
    """
    if zone_class == "DISCOUNT":
        return direction == 1
    if zone_class == "PREMIUM":
        return direction == -1
    return False  # EQ ambiguo

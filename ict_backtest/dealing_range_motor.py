"""ict_backtest/dealing_range_motor.py — Dealing range como input explícito del motor.

Tesis (libro 21 §0/§2, libro 08 PO3): EQ = 50% fib del swing HTF cerrado.
Clasifica la zona del setup en PREMIUM/DISCOUNT/EQ y deja la clase como
metadata en la señal. EQ es ambiguo: NO descarta la señal.

Clave anti look-ahead: usa swing HTF cerrado antes del entry_time.
Solo usa high/low puro, sin ATR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Tuple

from ict_backtest.dealing_range import (_EQ_BAND, _eq, classify_zone,
                                         zone_ok_for_direction)


@dataclass(frozen=True)
class DealingRangeInput:
    symbol: str
    htf_tf: str
    swing_high: float
    swing_low: float
    eq_band: float = _EQ_BAND
    meta: dict = field(default_factory=dict)

    @property
    def eq(self) -> float:
        return _eq(self.swing_high, self.swing_low)

    @property
    def rng(self) -> float:
        return self.swing_high - self.swing_low

    def classify(self, zone_high: float, zone_low: float) -> str:
        return classify_zone(zone_high, zone_low, self.swing_high, self.swing_low)

    def ok_for_direction(self, zone_class: str, direction: int) -> bool:
        return zone_ok_for_direction(zone_class, direction)


def _is_close_to(v: float, target: float, tol: float) -> bool:
    return abs(v - target) <= tol


def compute_zone_class(
    *,
    sig_dir: int,
    swing_high_htf: float | None,
    swing_low_htf: float | None,
    entry: float,
    zone_low: float | None = None,
    zone_high: float | None = None,
) -> str:
    """Devuelve la clase del deal range para la señal actual.

    - Si no hay swing HTF, devuelve ``EQ`` como fallback seguro.
    - Usa la zona FVG/OB del setup cuando está disponible; si no, la usa el entry.
    - PQ = eq, upper = EQ + 12% rango, lower = EQ - 12% rango.
    """
    if swing_high_htf is None or swing_low_htf is None:
        return "EQ"
    if swing_high_htf <= swing_low_htf:
        return "EQ"
    eq = _eq(swing_high_htf, swing_low_htf)
    rng = swing_high_htf - swing_low_htf
    price = entry
    if zone_high is not None and zone_low is not None:
        price = (zone_high + zone_low) / 2.0
    tol = _EQ_BAND * rng
    if _is_close_to(price, eq, tol):
        return "EQ"
    return "DISCOUNT" if price < eq else "PREMIUM"


def resolve_swing_from_ms(
    ms: dict[str, object],
    htf_tf: str,
    at_time: object,
) -> Tuple[float, float] | None:
    """Swing HTF cerrado antes de ``at_time``.

    Anti look-ahead: solo velas con ``time <= at_time``.
    Devuelve ``(high, low)`` o ``None`` cuando no hay datos suficientes.
    """
    df = ms.get(htf_tf)
    if df is None or len(df) == 0:
        return None
    try:
        import pandas as pd

        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        tt = pd.to_datetime(at_time, utc=True, errors="coerce")
        win = df.loc[times <= tt]
    except Exception:
        return None
    if len(win) < 3:
        return None
    return float(win["high"].max()), float(win["low"].min())

"""engine/bias/narrative.py — Implementación de la Narrativa HTF (SPEC §1).

CAPA 1 del motor ICT: lo primero que hace un trader humano tras cargar las
barras — definir el sesgo del día desde los TF mayores.

Contrato (SPEC_TESIS_FORMAL §1 — Narrativa HTF, OBLIGATORIO):
  ENT: velas cerradas D1, H4, H1 (sesgo del día y de la sesión).
  SAL: bias ∈ {BULLISH, BEARISH, NEUTRAL} por TF; alineación D1→H4→H1.
  PRE: velas de TF mayor completamente cerradas (sin look-ahead).
  POST: sesgo disponible como filtro para ITF/exec.
  DEP: ninguna (es la raíz).
  CRIT: bias = dirección del último swing estructural mayor confirmado en TF.
  CASOS LÍMITE: rango (H1 NEUTRAL) → se acepta como contexto, no anula el setup.
  AMBIG: umbral de "estructura mayor" es decisión de ingeniería (ventana de swing).

Reglas de implementación:
  - Sin look-ahead: swings con ventana NO centrada + exposición diferida
    (mismo patrón que el canon ict_backtest/market_structure.py, replicado
    aquí SIN importar el backtest — regla de separación motor ↔ backtest).
  - Confirmación por cuerpo: la dirección sale de la secuencia de swings
    etiquetados (HH/HL → BULLISH, LH/LL → BEARISH), con voto por tramos
    (cambios de dirección) para no confundir rango con tendencia.
  - Sin indicadores: ni ATR ni medias móviles (volatilidad = rango high-low).
  - API pura, sin estado mutable global.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

Bias = str  # "BULLISH" | "BEARISH" | "NEUTRAL"

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class HtfBias:
    """Sesgo por TF y alineación global D1→H4→H1 (SPEC §1 SAL)."""

    d1: Bias
    h4: Bias
    h1: Bias

    @property
    def aligned(self) -> bool:
        """True si los tres TF apuntan a la misma dirección (sin NEUTRAL)."""
        return self.d1 == self.h4 == self.h1 and self.d1 != NEUTRAL

    @property
    def direction(self) -> Bias:
        """Dirección global; NEUTRAL si no hay alineación de los tres TF."""
        return self.d1 if self.aligned else NEUTRAL


def _swing_points(frame: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
    """Swing high/low SIN look-ahead (patrón del canon).

    El swing en la fila i se confirma recién en i+lookback (hay que ver que
    nada lo supere en las siguientes `lookback` velas). Ventana NO centrada
    + shift(lookback).ffill() para exponer el valor solo desde la vela de
    confirmación (hallazgo #1 de la auditoría 2026-07-11).
    """
    window = lookback + 1
    roll_h = frame["high"].rolling(window=window, center=False, min_periods=window)
    roll_l = frame["low"].rolling(window=window, center=False, min_periods=window)
    max_h = roll_h.max()
    min_l = roll_l.min()
    sh_raw = frame["high"].where(
        (frame["high"] == max_h) & (max_h > max_h.shift(1).fillna(max_h))
    )
    sl_raw = frame["low"].where(
        (frame["low"] == min_l) & (min_l < min_l.shift(1).fillna(min_l))
    )
    return sh_raw.shift(lookback).ffill(), sl_raw.shift(lookback).ffill()


def _label_swings(
    swing_high: pd.Series, swing_low: pd.Series
) -> pd.Series:
    """Etiqueta HH/HL/LH/LL por swing confirmado (patrón del canon).

    Un swing cuenta SOLO cuando cambia el nivel expuesto (`!= shift(1)`, el
    ffill repite el mismo swing hasta el próximo). Los primeros swings de cada
    lado (sin referencia previa) quedan NONE: no aportan dirección.
    """
    labels = pd.Series("NONE", index=swing_high.index)
    new_high = swing_high.notna() & (swing_high != swing_high.shift(1))
    new_low = swing_low.notna() & (swing_low != swing_low.shift(1))
    prev_high = swing_high.where(new_high).ffill().shift(1)
    prev_low = swing_low.where(new_low).ffill().shift(1)
    labels[new_high & (swing_high > prev_high)] = "HH"
    labels[new_high & (swing_high < prev_high)] = "LH"
    labels[new_low & (swing_low > prev_low)] = "HL"
    labels[new_low & (swing_low < prev_low)] = "LL"
    return labels.where(new_high | new_low, pd.NA).ffill().fillna("NONE")


def _bias_from_swings(
    swing_high: pd.Series,
    swing_low: pd.Series,
    trend_window: int = 4,
) -> Bias:
    """Dirección del último swing estructural mayor confirmado (SPEC §1 CRIT).

    Voto por TRAMOS (cambios de dirección): agrupa los swings consecutivos de
    la misma polaridad (HH/HL → alcista, LH/LL → bajista) y vota los últimos
    `trend_window` tramos. Un rango alterna tramos → empate → NEUTRAL; una
    tendencia muestra una mayoría clara en una dirección.
    """
    labels = _label_swings(swing_high, swing_low)
    events = labels[labels != "NONE"]
    if len(events) < 2:
        return NEUTRAL
    trends: list[str] = []
    for lab in events.tolist():
        pol = "bull" if lab in ("HH", "HL") else "bear"
        if not trends or trends[-1] != pol:
            trends.append(pol)
    recent = trends[-trend_window:]
    bull = recent.count("bull")
    bear = recent.count("bear")
    if bull > bear:
        return BULLISH
    if bear > bull:
        return BEARISH
    return NEUTRAL


def _bias_for_frame(frame: pd.DataFrame, swing_lookback: int = 5) -> Bias:
    """Sesgo de UN timeframe (SPEC §1): swing_lookback es la AMBIG de ing."""
    sh, sl = _swing_points(frame, swing_lookback)
    return _bias_from_swings(sh, sl)


def compute_htf_bias(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    swing_lookback: int = 5,
) -> HtfBias:
    """Sesgo del día completo: D1 + H4 + H1 + alineación (SPEC §1).

    Args:
        d1/h4/h1: DataFrames de velas con columnas `high`/`low`/`close`,
                  SOLO velas cerradas (sin look-ahead).
        swing_lookback: ventana de swing (AMBIG de ingeniería, default 5).

    Returns:
        HtfBias con el sesgo de cada TF y la alineación global.
    """
    return HtfBias(
        d1=_bias_for_frame(d1, swing_lookback),
        h4=_bias_for_frame(h4, swing_lookback),
        h1=_bias_for_frame(h1, swing_lookback),
    )

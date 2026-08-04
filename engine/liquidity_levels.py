"""engine/liquidity_levels.py — Liquidez BSL/SSL anclada al sesgo HTF (Deuda 4).

Sin indicadores técnicos: SOLO geometría de mercado (high/low/close).
  BSL (Buy Side Liquidity) = máximos previos POR ENCIMA del precio actual.
  SSL (Sell Side Liquidity) = mínimos previos POR DEBAJO del precio actual.

El objetivo del día lo marca el sesgo HTF:
  BULLISH → objetivo BSL (barrer máximos arriba).
  BEARISH → objetivo SSL (barrer mínimos abajo).
  NEUTRAL → NONE.

Regla de oro: engine/ nunca importa ict_backtest/ ni usa ATR/EMA.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _bias_direction(htf_bias) -> str:
    """Extrae la dirección del sesgo; acepta HtfBias o str."""
    if htf_bias is None:
        return NEUTRAL
    if isinstance(htf_bias, str):
        value = htf_bias
    else:
        value = getattr(htf_bias, "direction", NEUTRAL)
    value = (value or NEUTRAL).upper()
    return value if value in (BULLISH, BEARISH) else NEUTRAL


def detect_liquidity_htf(
    frame: pd.DataFrame,
    htf_bias,
    left: int = 3,
    margin_ticks: float = 0.0,
) -> pd.DataFrame:
    """Marca niveles BSL/SSL relevantes por vela, sin look-ahead ni ATR.

    - bsl_level: máximo de las `left` velas previas si está por encima de
      close + margin_ticks; si no, NaN.
    - ssl_level: mínimo de las `left` velas previas si está por debajo de
      close - margin_ticks; si no, NaN.
    - target_liquidity: 'BSL' | 'SSL' | 'NONE' según el sesgo HTF.
    """
    if left < 1:
        raise ValueError("left debe ser >= 1")
    for col in ("high", "low", "close"):
        if col not in frame.columns:
            raise KeyError(f"falta la columna requerida '{col}'")

    out = frame.copy()
    if out.empty:
        out["bsl_level"] = pd.Series(dtype="float64")
        out["ssl_level"] = pd.Series(dtype="float64")
        out["target_liquidity"] = pd.Series(dtype="object")
        return out

    close = out["close"].astype("float64")
    # shift(1): solo velas cerradas previas (sin look-ahead)
    prev_high = out["high"].astype("float64").rolling(left).max().shift(1)
    prev_low = out["low"].astype("float64").rolling(left).min().shift(1)

    margin = float(margin_ticks)
    bsl = prev_high.where(prev_high > close + margin, np.nan)
    ssl = prev_low.where(prev_low < close - margin, np.nan)

    direction = _bias_direction(htf_bias)
    target = {BULLISH: "BSL", BEARISH: "SSL"}.get(direction, "NONE")

    out["bsl_level"] = bsl
    out["ssl_level"] = ssl
    out["target_liquidity"] = target
    return out


def nearest_liquidity_target(
    frame: pd.DataFrame,
    htf_bias,
    left: int = 3,
) -> dict:
    """Devuelve el objetivo de liquidez más cercano al último close.

    {'side': 'BSL'|'SSL'|'NONE', 'level': float|None, 'distance': float}
    """
    empty = {"side": "NONE", "level": None, "distance": float("nan")}
    if frame is None or len(frame) == 0:
        return empty

    marked = detect_liquidity_htf(frame, htf_bias, left=left)
    side = str(marked["target_liquidity"].iloc[-1])
    if side == "NONE":
        return empty

    col = "bsl_level" if side == "BSL" else "ssl_level"
    close = float(marked["close"].astype("float64").iloc[-1])

    # Nivel vigente: el último marcado; si no hay, el extremo previo más cercano
    series = marked[col].dropna()
    if series.empty:
        return {"side": side, "level": None, "distance": float("nan")}

    # de todos los niveles vistos, el más cercano al close en la dirección válida
    values = series.astype("float64").to_numpy()
    if side == "BSL":
        valid = values[values > close]
        level = float(valid.min()) if valid.size else float(values.max())
    else:
        valid = values[values < close]
        level = float(valid.max()) if valid.size else float(values.min())

    return {"side": side, "level": level, "distance": abs(level - close)}


__all__ = ["detect_liquidity_htf", "nearest_liquidity_target"]

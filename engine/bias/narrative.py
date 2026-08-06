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
  - Versión humana de swing: delay mínimo `lookback` velas + confirmación por rotura
    del swing previo en dirección opuesta (docs/tesis/... §1).
  - Confirmación por cuerpo: la dirección sale de la secuencia de swings
    etiquetados (HH/HL → BULLISH, LH/LL → BEARISH), con voto por tramos
    (cambios de dirección) para no confundir rango con tendencia.
  - Sin indicadores: ni ATR ni medias móviles (volatilidad = rango high-low).
  - API pura, sin estado mutable global.

  NOTA (fix T8, 2026-08-06): el criterio de sesgo se calcula por HH+HL / LH+LL
  sobre los ultimos `trend_window` pares de swings confirmados (default 6),
  NO por "tramos" de misma polaridad. El criterio anterior (agrupar swings en
  tramos y votar) dejaba el motor 100% NEUTRAL en H1 real (EURUSD H1 media
  2026-08-06: 100% NEUTRAL antes del fix -> 22.4% despues). En rango (SH/SL
  mixtos) el sesgo sigue NEUTRAL (contexto, no anula el setup).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

Bias = str  # "BULLISH" | "BEARISH" | "NEUTRAL"

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _compose_htf_bias(d1: Bias, h4: Bias, h1: Bias) -> Bias:
    """Composición HTF con D1/H4 como autoridad estructural.
    
    1) D1 y H4 coinciden y son direccionales → ese sentido, H1 no veto.
    2) D1 o H4 ranging → H1 decide (si es direccional).
    3) D1 != H4 y ambos direccionales → H1 desempata por mayoría 2/3.
    """
    d1 = d1 or NEUTRAL
    h4 = h4 or NEUTRAL
    h1 = h1 or NEUTRAL
    
    if d1 in (BULLISH, BEARISH) and d1 == h4:
        return d1
    
    if d1 == NEUTRAL or h4 == NEUTRAL:
        return h1 if h1 in (BULLISH, BEARISH) else NEUTRAL
    
    votes = [d1, h4, h1]
    bull = votes.count(BULLISH)
    bear = votes.count(BEARISH)
    if bull >= 2:
        return BULLISH
    if bear >= 2:
        return BEARISH
    return NEUTRAL


@dataclass(frozen=True)
class HtfBias:
    """Sesgo por TF y alineación global D1→H4→H1 (SPEC §1 SAL)."""

    d1: Bias
    h4: Bias
    h1: Bias

    @property
    def aligned(self) -> bool:
        """True si al menos 2/3 TFs tienen dirección y no hay contradicción."""
        vals = [self.d1, self.h4, self.h1]
        non_neutral = [v for v in vals if v != NEUTRAL]
        if len(non_neutral) < 2:
            return False
        return len(set(non_neutral)) == 1

    @property
    def direction(self) -> Bias:
        """Dirección global; NEUTRAL si contradicción o menos de 2 no NEUTRAL."""
        return _compose_htf_bias(self.d1, self.h4, self.h1)


def _swing_points(frame: pd.DataFrame, lookback: int = 2) -> tuple[pd.Series, pd.Series]:
    """Swing high/low SIN look-ahead, versión humana.

    Confirmación por rotura/retroceso: un extremo solo cuenta como swing
    confirmado cuando el precio rompe el swing previo en la dirección opuesta.
    El primer extremo de cada lado (sin swing previo) se acepta tras el delay
    mínimo de 2 velas.
    """
    n = len(frame)
    high = np.asarray(frame["high"], dtype=float)
    low = np.asarray(frame["low"], dtype=float)

    sh_raw = np.empty(n, dtype=float)
    sl_raw = np.empty(n, dtype=float)
    sh_raw[:] = np.nan
    sl_raw[:] = np.nan

    last_sh = np.nan
    last_sl = np.nan

    for i in range(2, n):
        if low[i] < low[i - 1] and low[i] < low[i - 2]:
            if np.isnan(last_sh) or low[i] < last_sh:
                sl_raw[i] = low[i]
                last_sl = low[i]
        if high[i] > high[i - 1] and high[i] > high[i - 2]:
            if np.isnan(last_sl) or high[i] > last_sl:
                sh_raw[i] = high[i]
                last_sh = high[i]

    delay = 2
    sh_raw_series = pd.Series(sh_raw, index=frame.index)
    sl_raw_series = pd.Series(sl_raw, index=frame.index)
    return (
        sh_raw_series.shift(delay).ffill(),
        sl_raw_series.shift(delay).ffill(),
    )


def _label_swings(
    swing_high: pd.Series, swing_low: pd.Series
) -> pd.Series:
    """Etiqueta HH/HL/LH/LL por swing confirmado (versión humana)."""

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


def _unique_swing_values(swing: pd.Series) -> list[float]:
    """Valores de swing confirmados en orden temporal (sin repetir el mismo nivel)."""
    out: list[float] = []
    prev: float | None = None
    for v in swing.dropna().tolist():
        if prev is None or v != prev:
            out.append(v)
            prev = v
    return out


def _bias_from_swings(
    swing_high: pd.Series,
    swing_low: pd.Series,
    trend_window: int = 6,
) -> Bias:
    """Dirección del último swing estructural mayor confirmado (SPEC §1 CRIT).

    Criterio de TRADER HUMANO (HH+HL / LH+LL), no de micro-oscilación:
      - último swing high (SH) > SH previo  Y  último swing low (SL) > SL previo
        => BULLISH (Higher High + Higher Low).
      - SH < SH previo  Y  SL < SL previo  => BEARISH (Lower High + Lower Low).
      - mixto => NEUTRAL (rango: el humano no opera hasta que rompa).

    Se vota por los últimos `trend_window` pares de swings confirmados para ser
    robusto a oscilaciones menores; la estructura vigente pesa más (pares más
    recientes). Resuelve el bug T8: el criterio anterior agrupaba por "tramos"
    de misma polaridad y, en H1 real (que alterna LL/HH perpetuamente), siempre
    empataba 2/2 → NEUTRAL perpetuo (motor mudo). Con HH+HL/LH+LL el motor
    distingue tendencia de rango: en tendencia vota mayoritariamente bull/bear;
    en rango reconoce mixto y devuelve NEUTRAL (contexto, no anula el setup).
    """
    sh_vals = _unique_swing_values(swing_high)
    sl_vals = _unique_swing_values(swing_low)
    if len(sh_vals) < 2 or len(sl_vals) < 2:
        return NEUTRAL

    n_pairs = min(trend_window, min(len(sh_vals), len(sl_vals)) - 1)
    bull = bear = 0
    for k in range(1, n_pairs + 1):
        sh_up = sh_vals[-k] > sh_vals[-k - 1]
        sl_up = sl_vals[-k] > sl_vals[-k - 1]
        if sh_up and sl_up:
            bull += 1
        elif (not sh_up) and (not sl_up):
            bear += 1
        # mixto => voto range, no cuenta para ninguno

    if bull > bear:
        return BULLISH
    if bear > bull:
        return BEARISH
    return NEUTRAL


def _bias_for_frame(frame: pd.DataFrame, swing_lookback: int = 2) -> Bias:
    """Sesgo de UN timeframe (SPEC §1): swing_lookback es la AMBIG de ing."""
    sh, sl = _swing_points(frame, swing_lookback)
    return _bias_from_swings(sh, sl)


def compute_htf_bias(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    swing_lookback: int = 2,
) -> HtfBias:
    """Sesgo del día completo: D1 + H4 + H1 + alineación (SPEC §1).

    Args:
        d1/h4/h1: DataFrames de velas con columnas `high`/`low`/`close`,
                  SOLO velas cerradas (sin look-ahead).
        swing_lookback: ventana de swing (AMBIG de ingeniería, default 2
                        para versión humana de swing).

    Returns:
        HtfBias con el sesgo de cada TF y la alineación global.
    """
    return HtfBias(
        d1=_bias_for_frame(d1, swing_lookback),
        h4=_bias_for_frame(h4, swing_lookback),
        h1=_bias_for_frame(h1, swing_lookback),
    )


def compute_htf_bias_series(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    m15: pd.DataFrame,
    swing_lookback: int = 2,
) -> pd.DataFrame:
    """Serie temporal de `HtfBias` propagada a H1 y M15.

    Se calcula en cada cierre de H4 y luego se expande por `ffill` sobre la
    línea de tiempo completa de H1 ∪ M15, porque en vivo el operador reutiliza
    el último bias confirmado hasta el próximo cierre H4.
    """
    h4 = h4.sort_index()
    d1_cum = d1
    h4_cum = h4
    h1_cum = h1
    rows: list[dict] = []
    for ts in h4.index:
        if ts in d1.index:
            d1_cum = d1.loc[d1.index <= ts]
        if ts in h1.index:
            h1_cum = h1.loc[h1.index <= ts]
        if ts in h4.index:
            h4_cum = h4.loc[h4.index <= ts]
        if len(d1_cum) < 2 or len(h4_cum) < 2 or len(h1_cum) < 2:
            continue
        bias = compute_htf_bias(d1_cum, h4_cum, h1_cum, swing_lookback=swing_lookback)
        rows.append(
            {
                "timestamp": ts,
                "direction": bias.direction,
                "aligned": bool(bias.aligned),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["timestamp", "direction", "aligned"])
    out = pd.DataFrame(rows).set_index("timestamp").sort_index()

    timeline = pd.DatetimeIndex(sorted(set(h1.index).union(m15.index)))
    out = out.reindex(timeline).ffill().fillna(
        {"direction": NEUTRAL, "aligned": False}
    ).infer_objects(copy=False)
    out.index.name = "timestamp"
    return out


def _suppress_future_no_silent_downcasting() -> None:
    """Opt-in temporal para eliminar el FutureWarning de pandas en ffill/fillna.

    pandas 3.x silenciará el downcasting por defecto; mientras tanto evitamos ruido
    sin tocar tests ni caller.
    """
    try:
        pd.set_option("future.no_silent_downcasting", True)
    except Exception:
        pass


_suppress_future_no_silent_downcasting()

"""Fase C3 — Turtle Soup (sweep PDH/PDL dia previo + reversion).

Implementacion AISLADA: NO edita canonical/engine/sequence. Solo:
  1) is_turtle_soup(...)  -> (bool, meta) puro sobre frames.
  2) flag_turtle_soup(...) -> anota sig.turtle_confirmed / sig.turtle_broke
     dinamicamente en cada ICTSignal (no toca la clase ICTSignal).

CONTRATO (docs/specs/MDS_C3_TURTLE_SOUP.md + libro 18/20):
  Turtle Soup = ir a buscar el BARRIDO del maximo/maximo del DIA
  ANTERIOR (PDH=prev-day-high / PDL=prev-day-low) y revertir: el
  stop-hunt que falla y continua en la direccion del trade.

  - direction == +1 (LONG): el setup busca el PDL del dia previo; el
    sweep debe romper POR DEBAJO el minimo del dia previo, y luego hay
    displacement ALCISTA (reversion al alza).
  - direction == -1 (SHORT): el setup busca el PDH del dia previo; el
    sweep debe romper POR ENCIMA el maximo del dia previo, y luego hay
    displacement BAJISTA.

Principio Brecha D: NO filtra duro por defecto. Solo anota metadato
(turtle_confirmed / turtle_broke). Quien consuma decide.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _coerce_ts(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tz else ts.tz_localize("UTC")


def _prev_day_ohlc(frames: dict[str, pd.DataFrame], ltf: str, sweep_ts: pd.Timestamp) -> dict | None:
    """Devuelve (pdh, pdl) del DIA PREVIO al de sweep_ts, en frames[ltf].

    Calcula el dia del sweep y toma la vela maxima/minima de TODAS las
    velas de frames[ltf] cuyo dia (date) es estrictamente anterior al
    dia del sweep. Si no hay velas previas -> None (sin dia previo).
    """
    if ltf not in frames:
        return None
    series = frames[ltf]
    times = pd.to_datetime(series["time"], utc=True, errors="coerce")
    if len(times) == 0:
        return None
    sweep_day = sweep_ts.normalize()
    mask_prev = times.dt.normalize() < sweep_day
    if not mask_prev.any():
        return None
    prev = series.loc[mask_prev]
    pdh = float(prev["high"].max())
    pdl = float(prev["low"].min())
    return {"pdh": pdh, "pdl": pdl, "n": int(mask_prev.sum())}


def _sweep_broke(sweep_row: pd.Series, meta_pd: dict, direction: int) -> tuple[bool, bool]:
    """¿El sweep rompio PDH (short) / PDL (long) del dia previo?

    Devuelve (broke_pdh, broke_pdl).
    - LONG (dir +1): barre PDL si sweep_row.low < pdl_previo.
    - SHORT (dir -1): barre PDH si sweep_row.high > pdh_previo.
    """
    pdh = meta_pd["pdh"]
    pdl = meta_pd["pdl"]
    low = float(sweep_row.get("low", np.nan))
    high = float(sweep_row.get("high", np.nan))
    broke_pdl = direction == 1 and (not pd.isna(low)) and low < pdl
    broke_pdh = direction == -1 and (not pd.isna(high)) and high > pdh
    return bool(broke_pdh), bool(broke_pdl)


def _has_reversal(df_ltf: pd.DataFrame, sweep_idx: int, direction: int) -> bool:
    """Displacement opuesto AL sweep antes de ~20 velas (reversion).

    Turtle Soup = el barrido falla y el precio REVIERTE en la direccion
    del trade. Medimos un cuerpo (close-open) fuerte en la direccion del
    trade en cualquiera de las ~20 velas posteriores al sweep (ventana
    generosa, sin filtrar duro). El cuerpo debe superar un umbral de
    reversion (>= 0.6 * rango promedio local) para no confundir ruido
    con displacement real.
    """
    n = len(df_ltf)
    if sweep_idx < 0 or sweep_idx >= n:
        return False
    end = min(n, sweep_idx + 21)  # sweep + hasta 20 velas despues
    window = df_ltf.iloc[sweep_idx:end]
    if len(window) == 0:
        return False
    # Rango promedio local (high-low) para umbral de cuerpo significativo.
    rng = (window["high"] - window["low"])
    rng = rng.replace(0, np.nan)
    avg_rng = float(rng.mean(skipna=True)) or 1e-6
    body = (window["close"] - window["open"]).to_numpy(dtype=float)
    if direction == 1:
        # Reversion alcista: cuerpo positivo (close > open) fuerte.
        return bool(np.any(body > 0.6 * avg_rng))
    else:
        # Reversion bajista: cuerpo negativo (close < open) fuerte.
        return bool(np.any(body < -0.6 * avg_rng))


def is_turtle_soup(
    sweep_ts: Any,
    direction: int,
    frames: dict[str, pd.DataFrame],
    ltf: str = "M15",
) -> tuple[bool, dict]:
    """Detecta Turtle Soup (sweep PDH/PDL dia previo + reversion).

    Args:
        sweep_ts: timestamp de la vela de sweep (str/pd.Timestamp).
        direction: +1 LONG (busca PDL) / -1 SHORT (busca PDH).
        frames: dict de DataFrames por TF (debe contener `ltf`).
        ltf: timeframe donde corre el setup (donde se lee el sweep).

    Returns:
        (confirmed: bool, meta: dict)
        meta = {
            "ts_broke_pdh": bool,  # barrio el maximo del dia previo
            "ts_broke_pdl": bool,  # barrio el minimo del dia previo
            "ts_reversal": bool,   # hubo displacement en dir del trade
        }
    """
    meta = {"ts_broke_pdh": False, "ts_broke_pdl": False, "ts_reversal": False}
    ts = _coerce_ts(sweep_ts)
    if ts is None or ltf not in frames:
        return False, meta

    df_ltf = frames[ltf]
    times = pd.to_datetime(df_ltf["time"], utc=True, errors="coerce")
    # Indice de la vela de sweep (time == ts, o la mas cercana <= ts).
    exact = df_ltf.index[times == ts]
    if len(exact):
        sweep_idx = int(exact[0])
    else:
        prior = df_ltf.index[times <= ts]
        if len(prior) == 0:
            return False, meta
        sweep_idx = int(prior[-1])

    prev = _prev_day_ohlc(frames, ltf, ts)
    if prev is None:
        # Sin dia previo: no hay PDH/PDL que barrer -> no es Turtle Soup,
        # pero no filtra duro (solo reporta metadato en falso).
        return False, meta

    sweep_row = df_ltf.iloc[sweep_idx]
    broke_pdh, broke_pdl = _sweep_broke(sweep_row, prev, direction)
    meta["ts_broke_pdh"] = broke_pdh
    meta["ts_broke_pdl"] = broke_pdl

    # Requiere haber roto el extremo del dia previo y luego revertir.
    broke = broke_pdh or broke_pdl
    if broke:
        meta["ts_reversal"] = _has_reversal(df_ltf, sweep_idx, direction)

    confirmed = broke and meta["ts_reversal"]
    return bool(confirmed), meta


def flag_turtle_soup(
    signals: list,
    frames: dict[str, pd.DataFrame],
    ltf: str = "M15",
) -> list:
    """Anota turtle_confirmed / turtle_broke en cada ICTSignal.

    Setea los atributos DINAMICAMENTE (no edita ICTSignal en engine.py).
    Para cada senal usa su timestamp (sig.time) y su direccion.

    Principio Brecha D: NO filtra (no quita senales). Solo anota metadato
    para que el consumidor (scoring/trade-management) decida.

    Returns: la MISMA lista recibida (la muta in-place).
    """
    for sig in signals:
        # El timestamp de referencia es el sweep (sig.sweep_at indice del LTF
        # o sig.time). La senal real de evaluate_signals lleva time=str(timestamp
        # de la vela de entrada), pero aqui necesitamos el instante del sweep.
        # Preferimos sweep_at (indice) resuelto contra frames[ltf]; si no
        # esta, caemos a sig.time.
        direction = int(getattr(sig, "direction", 0) or 0)
        if direction == 0:
            sig.turtle_confirmed = False
            sig.turtle_broke = False
            continue
        ts = None
        sweep_idx = getattr(sig, "sweep_at", None)
        if sweep_idx is not None and ltf in frames and 0 <= int(sweep_idx) < len(frames[ltf]):
            ts = frames[ltf].iloc[int(sweep_idx)]["time"]
        if ts is None:
            ts = getattr(sig, "time", None)
        if ts is None:
            sig.turtle_confirmed = False
            sig.turtle_broke = False
            continue
        ok, meta = is_turtle_soup(ts, direction, frames, ltf)
        sig.turtle_confirmed = bool(ok)
        sig.turtle_broke = bool(meta["ts_broke_pdh"] or meta["ts_broke_pdl"])
    return signals

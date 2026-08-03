"""Efectividad predictiva de BOS/CHOCH.

Mide, para cada evento emitido por el motor:
- BOS alcista: % veces que el maximo de las proximas `k` velas supera el nivel roto
- BOS bajista: % veces que el minimo de las proximas `k` velas perfora el nivel roto
- CHOCH alcista/bajista: % veces que se confirma con un BOS en la nueva direccion
  vs % veces que se invalida antes de esa confirmacion.

Baseline ingenuo: buy-and-hold sobre el mismo tramo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from engine.bos.structure import StructureConfig, detect_market_structure
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet


@dataclass(frozen=True)
class EffectivenessMetrics:
    symbol: str
    timeframe: str
    max_bars: int
    k: int
    total_bars: int
    bos_bullish_events: int = 0
    bos_bullish_hit: int = 0
    bos_bearish_events: int = 0
    bos_bearish_hit: int = 0
    choch_bullish_events: int = 0
    choch_bullish_confirmed: int = 0
    choch_bullish_invalidated: int = 0
    choch_bearish_events: int = 0
    choch_bearish_confirmed: int = 0
    choch_bearish_invalidated: int = 0
    buy_hold_return: float = 0.0


def _resample_to_h4(df: pd.DataFrame) -> pd.DataFrame:
    o = df["open"].resample("4h", label="left", closed="left").first()
    h = df["high"].resample("4h", label="left", closed="left").max()
    l = df["low"].resample("4h", label="left", closed="left").min()
    c = df["close"].resample("4h", label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


def measure_effectiveness(symbol: str = "EURUSD", max_bars: int = 2000, k: int = 5) -> EffectivenessMetrics:
    validated = validate_m15_parquet(symbol)
    m15_df = validated.df.sort_index()
    if max_bars and max_bars > 0:
        m15_df = m15_df.iloc[:max_bars]
    frame = _resample_to_h4(m15_df)
    ms = detect_market_structure(frame, StructureConfig(swing_lookback=5, confirm_bars=2))
    d = ms.frame.copy()

    fh = pd.Series(np.nan, index=d.index)
    fl = pd.Series(np.nan, index=d.index)
    highs = d["high"].values
    lows = d["low"].values
    n = len(d)
    for i in range(n):
        start = i + 1
        end = min(start + k, n)
        if start < n:
            fh.iat[i] = highs[start:end].max()
            fl.iat[i] = lows[start:end].min()

    bos_bullish_events = 0
    bos_bullish_hit = 0
    bos_bearish_events = 0
    bos_bearish_hit = 0
    choch_bullish_events = 0
    choch_bullish_confirmed = 0
    choch_bullish_invalidated = 0
    choch_bearish_events = 0
    choch_bearish_confirmed = 0
    choch_bearish_invalidated = 0

    bull_bos = (d["bos_dir"] == 1).to_numpy().nonzero()[0]
    bear_bos = (d["bos_dir"] == -1).to_numpy().nonzero()[0]
    for idx in bull_bos:
        if idx + k - 1 < n:
            bos_bullish_events += 1
            if fh.iat[idx] > d["high"].iat[idx]:
                bos_bullish_hit += 1
    for idx in bear_bos:
        if idx + k - 1 < n:
            bos_bearish_events += 1
            if fl.iat[idx] < d["low"].iat[idx]:
                bos_bearish_hit += 1

    bull_choch = (d["choch_dir"] == 1).to_numpy().nonzero()[0]
    bear_choch = (d["choch_dir"] == -1).to_numpy().nonzero()[0]
    for idx in bull_choch:
        if idx >= n - 1:
            continue
        choch_bullish_events += 1
        confirmed = False
        invalidated = False
        for j in range(idx + 1, n):
            if d["choch_status"].iat[j] == "invalidated":
                invalidated = True
                break
            if d["bos_dir"].iat[j] == 1:
                confirmed = True
                break
        if confirmed:
            choch_bullish_confirmed += 1
        elif invalidated:
            choch_bullish_invalidated += 1
    for idx in bear_choch:
        if idx >= n - 1:
            continue
        choch_bearish_events += 1
        confirmed = False
        invalidated = False
        for j in range(idx + 1, n):
            if d["choch_status"].iat[j] == "invalidated":
                invalidated = True
                break
            if d["bos_dir"].iat[j] == -1:
                confirmed = True
                break
        if confirmed:
            choch_bearish_confirmed += 1
        elif invalidated:
            choch_bearish_invalidated += 1

    buy_hold = float(np.nan_to_num((frame["close"].iloc[-1] - frame["open"].iloc[0]) / frame["open"].iloc[0], nan=0.0))

    return EffectivenessMetrics(
        symbol=symbol.upper(),
        timeframe="H4",
        max_bars=max_bars,
        k=k,
        total_bars=n,
        bos_bullish_events=bos_bullish_events,
        bos_bullish_hit=bos_bullish_hit,
        bos_bearish_events=bos_bearish_events,
        bos_bearish_hit=bos_bearish_hit,
        choch_bullish_events=choch_bullish_events,
        choch_bullish_confirmed=choch_bullish_confirmed,
        choch_bullish_invalidated=choch_bullish_invalidated,
        choch_bearish_events=choch_bearish_events,
        choch_bearish_confirmed=choch_bearish_confirmed,
        choch_bearish_invalidated=choch_bearish_invalidated,
        buy_hold_return=buy_hold,
    )


def run_effectiveness(symbol: str = "EURUSD", max_bars: int = 2000, k: int = 5) -> dict:
    m = measure_effectiveness(symbol=symbol, max_bars=max_bars, k=k)
    def pct(hit, total):
        return round((hit / total) * 100, 2) if total > 0 else 0.0
    return {
        "symbol": m.symbol,
        "timeframe": m.timeframe,
        "max_bars": m.max_bars,
        "k": m.k,
        "total_bars": m.total_bars,
        "bos_bullish": {"events": m.bos_bullish_events, "hit": m.bos_bullish_hit, "hit_pct": pct(m.bos_bullish_hit, m.bos_bullish_events)},
        "bos_bearish": {"events": m.bos_bearish_events, "hit": m.bos_bearish_hit, "hit_pct": pct(m.bos_bearish_hit, m.bos_bearish_events)},
        "choch_bullish": {"events": m.choch_bullish_events, "confirmed": m.choch_bullish_confirmed, "invalidated": m.choch_bullish_invalidated, "confirmed_pct": pct(m.choch_bullish_confirmed, m.choch_bullish_events)},
        "choch_bearish": {"events": m.choch_bearish_events, "confirmed": m.choch_bearish_confirmed, "invalidated": m.choch_bearish_invalidated, "confirmed_pct": pct(m.choch_bearish_confirmed, m.choch_bearish_events)},
        "baseline_buy_hold_pct": round(m.buy_hold_return * 100, 2),
    }


def main() -> int:
    symbol = os.environ.get("SMCS_EFFECTIVENESS_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_EFFECTIVENESS_MAX_BARS", 2000))
    k = int(os.environ.get("SMCS_EFFECTIVENESS_K", 5))
    report = run_effectiveness(symbol=symbol, max_bars=max_bars, k=k)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

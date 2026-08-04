"""Efectividad predictiva de BOS/CHOCH multi-timeframe.

Mide, para cada evento emitido por el motor en D1/H4/H1/M15:
- Efectividad aligned vs contra el sesgo HTF
- Cantidad de eventos descartados por temporalidad
- Causa explícita de descarte: no_hit_in_k / no_confirmation / invalidated

Baseline ingenuo: buy-and-hold sobre el mismo tramo.
Baseline de ruido: permutación de direcciones para estimar edge real.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from engine.bias.narrative import compute_htf_bias_series
from engine.bos.structure import StructureConfig, detect_market_structure
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet

NEUTRAL = "NEUTRAL"


@dataclass
class TimeframeMetrics:
    timeframe: str
    total_bars: int
    bos_bullish_events: int = 0
    bos_bullish_aligned_hit: int = 0
    bos_bullish_against_hit: int = 0
    bos_bullish_discarded_no_hit: int = 0
    bos_bearish_events: int = 0
    bos_bearish_aligned_hit: int = 0
    bos_bearish_against_hit: int = 0
    bos_bearish_discarded_no_hit: int = 0
    choch_bullish_events: int = 0
    choch_bullish_confirmed_aligned: int = 0
    choch_bullish_confirmed_against: int = 0
    choch_bullish_invalidated: int = 0
    choch_bullish_discarded_no_confirmation: int = 0
    choch_bearish_events: int = 0
    choch_bearish_confirmed_aligned: int = 0
    choch_bearish_confirmed_against: int = 0
    choch_bearish_invalidated: int = 0
    choch_bearish_discarded_no_confirmation: int = 0
    mss_bullish_events: int = 0
    mss_bullish_confirmed_aligned: int = 0
    mss_bullish_confirmed_against: int = 0
    mss_bearish_events: int = 0
    mss_bearish_confirmed_aligned: int = 0
    mss_bearish_confirmed_against: int = 0
    buy_hold_return: float = 0.0


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = df["open"].resample(rule, label="left", closed="left").first()
    h = df["high"].resample(rule, label="left", closed="left").max()
    l = df["low"].resample(rule, label="left", closed="left").min()
    c = df["close"].resample(rule, label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


def _precompute_choch_outcomes(
    d: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Precalcula outcomes de CHOCH para acceso O(1)."""
    n = len(d)
    confirmed = np.full(n, False, dtype=bool)
    invalidated = np.full(n, False, dtype=bool)

    next_bos_bullish = np.full(n, n, dtype=int)
    next_bos_bearish = np.full(n, n, dtype=int)
    next_invalidated = np.full(n, n, dtype=int)

    last_bos_bullish = n
    last_bos_bearish = n
    last_invalidated = n
    for j in range(n - 1, -1, -1):
        if d["bos_dir"].iat[j] == 1:
            last_bos_bullish = j
        if d["bos_dir"].iat[j] == -1:
            last_bos_bearish = j
        if d["choch_status"].iat[j] == "invalidated":
            last_invalidated = j
        next_bos_bullish[j] = last_bos_bullish
        next_bos_bearish[j] = last_bos_bearish
        next_invalidated[j] = last_invalidated

    for i in range(n):
        if d["choch_dir"].iat[i] == 1:
            inv_idx = next_invalidated[i]
            bos_idx = next_bos_bullish[i]
            if inv_idx != n and (bos_idx == n or inv_idx < bos_idx):
                invalidated[i] = True
            elif bos_idx != n:
                confirmed[i] = True
        elif d["choch_dir"].iat[i] == -1:
            inv_idx = next_invalidated[i]
            bos_idx = next_bos_bearish[i]
            if inv_idx != n and bos_idx == n or inv_idx < bos_idx:
                invalidated[i] = True
            elif bos_idx != n:
                confirmed[i] = True

    return confirmed, invalidated


def _measure_timeframe(
    frame: pd.DataFrame,
    bias_index: pd.DataFrame,
    timeframe: str,
    k: int = 5,
    confirm_bars: int = 2,
) -> TimeframeMetrics:
    ms = detect_market_structure(
        frame,
        StructureConfig(swing_lookback=5, confirm_bars=confirm_bars, k=k),
    )
    d = ms.frame
    n = len(d)

    highs = d["high"].values
    lows = d["low"].values
    bos_levels = d["bos_level"].to_numpy()
    fh = np.full(n, np.nan)
    fl = np.full(n, np.nan)
    for i in range(n):
        start = i + 1
        end = min(start + k, n)
        if start < n:
            level = bos_levels[i]
            if np.isfinite(level):
                fh[i] = highs[start:end].max()
                fl[i] = lows[start:end].min()
                if d["bos_dir"].iat[i] == 1:
                    fh[i] = max(fh[i], level)
                elif d["bos_dir"].iat[i] == -1:
                    fl[i] = min(fl[i], level)

    bias_aligned = bias_index.reindex(frame.index).fillna({"aligned": False})["aligned"].to_numpy()
    bias_direction = bias_index.reindex(frame.index).fillna({"direction": NEUTRAL})["direction"].astype(object).to_numpy()

    bos_discard = d["bos_discard_reason"].to_numpy()
    choch_discard = d["choch_discard_reason"].to_numpy()
    choch_status = d["choch_status"].to_numpy()

    m = TimeframeMetrics(timeframe=timeframe, total_bars=n)
    if n > 0:
        m.buy_hold_return = float(
            (d["close"].iloc[-1] - d["open"].iloc[0]) / d["open"].iloc[0]
        )

    for i in range(n):
        is_aligned = bool(bias_aligned[i])
        direction = str(bias_direction[i])

        if d["bos_dir"].iat[i] == 1:
            m.bos_bullish_events += 1
            if pd.isna(bos_discard[i]):
                if is_aligned and direction == "BULLISH":
                    m.bos_bullish_aligned_hit += 1
                else:
                    m.bos_bullish_against_hit += 1
            else:
                m.bos_bullish_discarded_no_hit += 1
        elif d["bos_dir"].iat[i] == -1:
            m.bos_bearish_events += 1
            if pd.isna(bos_discard[i]):
                if is_aligned and direction == "BEARISH":
                    m.bos_bearish_aligned_hit += 1
                else:
                    m.bos_bearish_against_hit += 1
            else:
                m.bos_bearish_discarded_no_hit += 1

        if d["choch_dir"].iat[i] == 1:
            m.choch_bullish_events += 1
            if choch_status[i] in ("active", "invalidated"):
                if is_aligned and direction == "BULLISH":
                    m.choch_bullish_confirmed_aligned += 1
                else:
                    m.choch_bullish_confirmed_against += 1
            elif choch_discard[i] == "INVALIDATED":
                m.choch_bullish_invalidated += 1
            else:
                m.choch_bullish_discarded_no_confirmation += 1
        elif d["choch_dir"].iat[i] == -1:
            m.choch_bearish_events += 1
            if choch_status[i] in ("active", "invalidated"):
                if is_aligned and direction == "BEARISH":
                    m.choch_bearish_confirmed_aligned += 1
                else:
                    m.choch_bearish_confirmed_against += 1
            elif choch_discard[i] == "INVALIDATED":
                m.choch_bearish_invalidated += 1
            else:
                m.choch_bearish_discarded_no_confirmation += 1

        if d["mss_dir"].iat[i] == 1:
            m.mss_bullish_events += 1
            if is_aligned and direction == "BULLISH":
                m.mss_bullish_confirmed_aligned += 1
            else:
                m.mss_bullish_confirmed_against += 1
        elif d["mss_dir"].iat[i] == -1:
            m.mss_bearish_events += 1
            if is_aligned and direction == "BEARISH":
                m.mss_bearish_confirmed_aligned += 1
            else:
                m.mss_bearish_confirmed_against += 1

    return m


def _baseline_permutation(
    frame: pd.DataFrame,
    bias_index: pd.DataFrame,
    k: int = 5,
    confirm_bars: int = 2,
    n_perm: int = 50,
) -> dict:
    """Baseline de ruido por permutación de direcciones."""
    ms = detect_market_structure(
        frame,
        StructureConfig(swing_lookback=5, confirm_bars=confirm_bars),
    )
    d = ms.frame
    real_bos_dir = d["bos_dir"].values.copy()
    real_choch_dir = d["choch_dir"].values.copy()

    bos_bullish_hits = []
    bos_bearish_hits = []
    choch_bullish_confirmed = []
    choch_bearish_confirmed = []

    bos_bullish_aligned_hits = []
    bos_bullish_against_hits = []
    bos_bearish_aligned_hits = []
    bos_bearish_against_hits = []
    choch_bullish_aligned_confirmed = []
    choch_bullish_against_confirmed = []
    choch_bearish_aligned_confirmed = []
    choch_bearish_against_confirmed = []

    highs = d["high"].values
    lows = d["low"].values
    n = len(d)
    fh = np.full(n, np.nan)
    fl = np.full(n, np.nan)
    for i in range(n):
        start = i + 1
        end = min(start + k, n)
        if start < n:
            fh[i] = highs[start:end].max()
            fl[i] = lows[start:end].min()

    bias_aligned = bias_index.reindex(frame.index).fillna({"aligned": False})["aligned"].to_numpy()
    bias_direction = bias_index.reindex(frame.index).fillna({"direction": NEUTRAL})["direction"].astype(object).to_numpy()

    for _ in range(n_perm):
        bos = real_bos_dir.copy()
        choch = real_choch_dir.copy()
        bos_events = np.where(bos != 0)[0]
        if len(bos_events):
            perm = np.random.permutation(bos_events)
            bos[bos_events] = bos[perm]

        choch_events = np.where(choch != 0)[0]
        if len(choch_events):
            perm = np.random.permutation(choch_events)
            choch[choch_events] = choch[perm]

        bb_a_hit = bb_a_cnt = bb_c_hit = bb_c_cnt = 0
        ba_a_hit = ba_a_cnt = ba_c_hit = ba_c_cnt = 0
        ch_bull_a = ch_bull_c = ch_bull_a_cnt = ch_bull_c_cnt = 0
        ch_bear_a = ch_bear_c = ch_bear_a_cnt = ch_bear_c_cnt = 0
        for i in range(n):
            aligned = bool(bias_aligned[i])
            direction = str(bias_direction[i])
            if bos[i] == 1:
                if aligned and direction == "BULLISH":
                    bb_a_cnt += 1
                    if i + k - 1 < n and np.isfinite(fh[i]) and fh[i] > highs[i]:
                        bb_a_hit += 1
                else:
                    bb_c_cnt += 1
                    if i + k - 1 < n and np.isfinite(fh[i]) and fh[i] > highs[i]:
                        bb_c_hit += 1
            elif bos[i] == -1:
                if aligned and direction == "BEARISH":
                    ba_a_cnt += 1
                    if i + k - 1 < n and np.isfinite(fl[i]) and fl[i] < lows[i]:
                        ba_a_hit += 1
                else:
                    ba_c_cnt += 1
                    if i + k - 1 < n and np.isfinite(fl[i]) and fl[i] < lows[i]:
                        ba_c_hit += 1
            if choch[i] == 1:
                if aligned and direction == "BULLISH":
                    ch_bull_a_cnt += 1
                    if i + confirm_bars < n:
                        ch_bull_a += 1
                else:
                    ch_bull_c_cnt += 1
                    if i + confirm_bars < n:
                        ch_bull_c += 1
            elif choch[i] == -1:
                if aligned and direction == "BEARISH":
                    ch_bear_a_cnt += 1
                    if i + confirm_bars < n:
                        ch_bear_a += 1
                else:
                    ch_bear_c_cnt += 1
                    if i + confirm_bars < n:
                        ch_bear_c += 1
        bos_bullish_aligned_hits.append(bb_a_hit / bb_a_cnt if bb_a_cnt else 0.0)
        bos_bullish_against_hits.append(bb_c_hit / bb_c_cnt if bb_c_cnt else 0.0)
        bos_bearish_aligned_hits.append(ba_a_hit / ba_a_cnt if ba_a_cnt else 0.0)
        bos_bearish_against_hits.append(ba_c_hit / ba_c_cnt if ba_c_cnt else 0.0)
        choch_bullish_aligned_confirmed.append(ch_bull_a / ch_bull_a_cnt if ch_bull_a_cnt else 0.0)
        choch_bullish_against_confirmed.append(ch_bull_c / ch_bull_c_cnt if ch_bull_c_cnt else 0.0)
        choch_bearish_aligned_confirmed.append(ch_bear_a / ch_bear_a_cnt if ch_bear_a_cnt else 0.0)
        choch_bearish_against_confirmed.append(ch_bear_c / ch_bear_c_cnt if ch_bear_c_cnt else 0.0)

    return {
        "bos_bullish_hit_baseline_mean": float(np.mean(bos_bullish_hits)),
        "bos_bullish_hit_baseline_std": float(np.std(bos_bullish_hits)),
        "bos_bearish_hit_baseline_mean": float(np.mean(bos_bearish_hits)),
        "bos_bearish_hit_baseline_std": float(np.std(bos_bearish_hits)),
        "choch_bullish_confirmed_baseline_mean": float(np.mean(choch_bullish_confirmed)),
        "choch_bearish_confirmed_baseline_mean": float(np.mean(choch_bearish_confirmed)),
        "bos_bullish_aligned_hit_baseline_mean": float(np.mean(bos_bullish_aligned_hits)),
        "bos_bullish_against_hit_baseline_mean": float(np.mean(bos_bullish_against_hits)),
        "bos_bearish_aligned_hit_baseline_mean": float(np.mean(bos_bearish_aligned_hits)),
        "bos_bearish_against_hit_baseline_mean": float(np.mean(bos_bearish_against_hits)),
        "choch_bullish_aligned_confirmed_baseline_mean": float(np.mean(choch_bullish_aligned_confirmed)),
        "choch_bullish_against_confirmed_baseline_mean": float(np.mean(choch_bullish_against_confirmed)),
        "choch_bearish_aligned_confirmed_baseline_mean": float(np.mean(choch_bearish_aligned_confirmed)),
        "choch_bearish_against_confirmed_baseline_mean": float(np.mean(choch_bearish_against_confirmed)),
    }


def _to_dict(m: TimeframeMetrics, baseline: dict | None = None) -> dict:
    def pct(hit, total):
        return round((hit / total) * 100, 2) if total > 0 else 0.0

    bos_bullish_total = m.bos_bullish_aligned_hit + m.bos_bullish_against_hit + m.bos_bullish_discarded_no_hit
    bos_bearish_total = m.bos_bearish_aligned_hit + m.bos_bearish_against_hit + m.bos_bearish_discarded_no_hit
    choch_bullish_total = (
        m.choch_bullish_confirmed_aligned
        + m.choch_bullish_confirmed_against
        + m.choch_bullish_invalidated
        + m.choch_bullish_discarded_no_confirmation
    )
    choch_bearish_total = (
        m.choch_bearish_confirmed_aligned
        + m.choch_bearish_confirmed_against
        + m.choch_bearish_invalidated
        + m.choch_bearish_discarded_no_confirmation
    )

    out = {
        "timeframe": m.timeframe,
        "total_bars": m.total_bars,
        "bos_bullish": {
            "events": m.bos_bullish_events,
            "aligned_hit": m.bos_bullish_aligned_hit,
            "against_hit": m.bos_bullish_against_hit,
            "aligned_hit_pct": pct(m.bos_bullish_aligned_hit, m.bos_bullish_events),
            "against_hit_pct": pct(m.bos_bullish_against_hit, m.bos_bullish_events),
            "discarded_no_hit": m.bos_bullish_discarded_no_hit,
            "discarded_no_hit_pct": pct(m.bos_bullish_discarded_no_hit, m.bos_bullish_events),
            "hit_pct": pct(bos_bullish_total, m.bos_bullish_events),
        },
        "bos_bearish": {
            "events": m.bos_bearish_events,
            "aligned_hit": m.bos_bearish_aligned_hit,
            "against_hit": m.bos_bearish_against_hit,
            "aligned_hit_pct": pct(m.bos_bearish_aligned_hit, m.bos_bearish_events),
            "against_hit_pct": pct(m.bos_bearish_against_hit, m.bos_bearish_events),
            "discarded_no_hit": m.bos_bearish_discarded_no_hit,
            "discarded_no_hit_pct": pct(m.bos_bearish_discarded_no_hit, m.bos_bearish_events),
            "hit_pct": pct(bos_bearish_total, m.bos_bearish_events),
        },
        "choch_bullish": {
            "events": m.choch_bullish_events,
            "confirmed_aligned": m.choch_bullish_confirmed_aligned,
            "confirmed_against": m.choch_bullish_confirmed_against,
            "invalidated": m.choch_bullish_invalidated,
            "discarded_no_confirmation": m.choch_bullish_discarded_no_confirmation,
            "confirmed_aligned_pct": pct(m.choch_bullish_confirmed_aligned, m.choch_bullish_events),
            "confirmed_against_pct": pct(m.choch_bullish_confirmed_against, m.choch_bullish_events),
            "invalidated_pct": pct(m.choch_bullish_invalidated, m.choch_bullish_events),
            "discarded_no_confirmation_pct": pct(m.choch_bullish_discarded_no_confirmation, m.choch_bullish_events),
            "confirmed_pct": pct(
                m.choch_bullish_confirmed_aligned + m.choch_bullish_confirmed_against,
                m.choch_bullish_events,
            ),
        },
        "choch_bearish": {
            "events": m.choch_bearish_events,
            "confirmed_aligned": m.choch_bearish_confirmed_aligned,
            "confirmed_against": m.choch_bearish_confirmed_against,
            "invalidated": m.choch_bearish_invalidated,
            "discarded_no_confirmation": m.choch_bearish_discarded_no_confirmation,
            "confirmed_aligned_pct": pct(m.choch_bearish_confirmed_aligned, m.choch_bearish_events),
            "confirmed_against_pct": pct(m.choch_bearish_confirmed_against, m.choch_bearish_events),
            "invalidated_pct": pct(m.choch_bearish_invalidated, m.choch_bearish_events),
            "discarded_no_confirmation_pct": pct(m.choch_bearish_discarded_no_confirmation, m.choch_bearish_events),
            "confirmed_pct": pct(
                m.choch_bearish_confirmed_aligned + m.choch_bearish_confirmed_against,
                m.choch_bearish_events,
            ),
        },
        "mss_bullish": {
            "events": m.mss_bullish_events,
            "confirmed_aligned": m.mss_bullish_confirmed_aligned,
            "confirmed_against": m.mss_bullish_confirmed_against,
            "confirmed_aligned_pct": pct(m.mss_bullish_confirmed_aligned, m.mss_bullish_events),
            "confirmed_against_pct": pct(m.mss_bullish_confirmed_against, m.mss_bullish_events),
        },
        "mss_bearish": {
            "events": m.mss_bearish_events,
            "confirmed_aligned": m.mss_bearish_confirmed_aligned,
            "confirmed_against": m.mss_bearish_confirmed_against,
            "confirmed_aligned_pct": pct(m.mss_bearish_confirmed_aligned, m.mss_bearish_events),
            "confirmed_against_pct": pct(m.mss_bearish_confirmed_against, m.mss_bearish_events),
        },
        "baseline_buy_hold_pct": round(m.buy_hold_return * 100, 2),
    }
    if baseline:
        out["baseline"] = baseline
    return out


def run_effectiveness_htf(
    symbol: str = "EURUSD",
    max_bars: int = 2000,
    k: int = 5,
    swing_lookback: int = 5,
    confirm_bars: int = 2,
) -> dict:
    validated = validate_m15_parquet(symbol)
    m15_df = validated.df.sort_index().iloc[:max_bars]

    h4_df = _resample(m15_df, "4h")
    h1_df = _resample(m15_df, "1h")
    d1_df = _resample(m15_df, "1d")

    bias_index = compute_htf_bias_series(
        d1_df, h4_df, h1_df, m15_df, swing_lookback=swing_lookback
    )

    tf_frames = {
        "D1": d1_df,
        "H4": h4_df,
        "H1": h1_df,
        "M15": m15_df,
    }

    results = []
    for tf, frame in tf_frames.items():
        metrics = _measure_timeframe(
            frame=frame,
            bias_index=bias_index,
            timeframe=tf,
            k=k,
            confirm_bars=confirm_bars,
        )
        baseline = _baseline_permutation(frame, bias_index, k=k, confirm_bars=confirm_bars)
        results.append(_to_dict(metrics, baseline=baseline))

    return {
        "symbol": symbol.upper(),
        "max_bars": max_bars,
        "k": k,
        "swing_lookback": swing_lookback,
        "confirm_bars": confirm_bars,
        "bias_coverage": {
            str(tf): float((bias_index["direction"].ne("NEUTRAL") | bias_index["aligned"]).mean())
            for tf, _ in tf_frames.items()
        },
        "timeframes": results,
    }


def main() -> int:
    symbol = os.environ.get("SMCS_EFFECTIVENESS_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_EFFECTIVENESS_MAX_BARS", 2000))
    k = int(os.environ.get("SMCS_EFFECTIVENESS_K", 5))
    swing_lookback = int(os.environ.get("SMCS_EFFECTIVENESS_SWING_LOOKBACK", 5))
    confirm_bars = int(os.environ.get("SMCS_EFFECTIVENESS_CONFIRM_BARS", 2))
    report = run_effectiveness_htf(
        symbol=symbol,
        max_bars=max_bars,
        k=k,
        swing_lookback=swing_lookback,
        confirm_bars=confirm_bars,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from engine.bias.narrative import BULLISH, BEARISH, NEUTRAL, HtfBias, compute_htf_bias_series
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.htf_narrative import build_htf_narrative, narrative_ready_for_trade
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = df["open"].resample(rule, label="left", closed="left").first()
    h = df["high"].resample(rule, label="left", closed="left").max()
    l = df["low"].resample(rule, label="left", closed="left").min()
    c = df["close"].resample(rule, label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


@dataclass
class TimeframeMetrics:
    timeframe: str = ""
    total_bars: int = 0
    buy_hold_return: float = 0.0
    bos_bullish_events: int = 0
    bos_bullish_aligned_hit: int = 0
    bos_bullish_against_hit: int = 0
    bos_bullish_discarded_fakeout: int = 0
    bos_bullish_discarded_no_hit: int = 0
    bos_bearish_events: int = 0
    bos_bearish_aligned_hit: int = 0
    bos_bearish_against_hit: int = 0
    bos_bearish_discarded_fakeout: int = 0
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
    baseline_buy_hold_pct: float = 0.0
    baseline: dict | None = None
    htf_ready_bars: int = 0
    htf_ready_pct: float = 0.0
    htf_checked_bars: int = 0


def _serialize(obj: Any) -> Any:
    if isinstance(obj, TimeframeMetrics):
        data = dataclasses.asdict(obj)
        baseline = data.pop("baseline", {})
        data["baseline_buy_hold_pct"] = data.get("buy_hold_return", 0.0) * 100
        data["baseline"] = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in baseline.items()}
        return data
    if isinstance(obj, float) and np.isnan(obj):
        return None
    raise TypeError(f"Not serializable: {type(obj)}")


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
    bos_real = d["bos_real"].to_numpy() if "bos_real" in d.columns else np.ones(n, dtype=bool)

    # --- Cobertura honesta del HTF
    # se construye SOBRE velas ya cerradas (hasta i-1). build_htf_narrative recibe
    # ese sub-frame y resuelve bias/zona/liquidez/POI con geometría pura.
    narr_window = 200
    narr_step = 50
    htf_ready = 0
    htf_checked = 0
    for i in range(narr_window, n, narr_step):
        sub = frame.iloc[:i]
        if len(sub) < narr_window:
            continue
        sub = sub.iloc[-narr_window:]
        bdir = str(bias_direction[i - 1]) if (i - 1) < n else NEUTRAL
        baligned = bool(bias_aligned[i - 1]) if (i - 1) < n else False
        hbias = HtfBias(
            d1=bdir if bdir in (BULLISH, BEARISH) else NEUTRAL,
            h4=bdir if bdir in (BULLISH, BEARISH) else NEUTRAL,
            h1=bdir if bdir in (BULLISH, BEARISH) else NEUTRAL,
        )
        try:
            narr = build_htf_narrative(sub, lookback=10, htf_bias=hbias)
            htf_checked += 1
            if narrative_ready_for_trade(narr):
                htf_ready += 1
        except Exception:
            pass

    m = TimeframeMetrics(timeframe=timeframe, total_bars=n)
    if n > 0:
        m.buy_hold_return = float(
            (d["close"].iloc[-1] - d["open"].iloc[0]) / d["open"].iloc[0]
        )
    if htf_checked > 0:
        m.htf_ready_bars = htf_ready
        m.htf_checked_bars = htf_checked
        m.htf_ready_pct = htf_ready / htf_checked

    for i in range(n):
        is_aligned = bool(bias_aligned[i])
        direction = str(bias_direction[i])
        real = bool(bos_real[i])

        if d["bos_dir"].iat[i] == 1:
            m.bos_bullish_events += 1
            if pd.isna(bos_discard[i]):
                if real:
                    if is_aligned and direction == "BULLISH":
                        m.bos_bullish_aligned_hit += 1
                    else:
                        m.bos_bullish_against_hit += 1
                else:
                    m.bos_bullish_discarded_fakeout += 1
            else:
                m.bos_bullish_discarded_no_hit += 1
        elif d["bos_dir"].iat[i] == -1:
            m.bos_bearish_events += 1
            if pd.isna(bos_discard[i]):
                if real:
                    if is_aligned and direction == "BEARISH":
                        m.bos_bearish_aligned_hit += 1
                    else:
                        m.bos_bearish_against_hit += 1
                else:
                    m.bos_bearish_discarded_fakeout += 1
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
) -> dict[str, Any]:
    ms = detect_market_structure(
        frame,
        StructureConfig(swing_lookback=5, confirm_bars=confirm_bars, k=k),
    )
    d = ms.frame
    real_bos_dir = d["bos_dir"].values.copy()
    real_choch_dir = d["choch_dir"].values.copy()

    bos_bullish_aligned_hits: list[float] = []
    bos_bullish_against_hits: list[float] = []
    bos_bearish_aligned_hits: list[float] = []
    bos_bearish_against_hits: list[float] = []
    choch_bullish_aligned_confirmed: list[float] = []
    choch_bullish_against_confirmed: list[float] = []
    choch_bearish_aligned_confirmed: list[float] = []
    choch_bearish_against_confirmed: list[float] = []

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
            bos[bos_events] = bos[np.random.permutation(bos_events)]

        choch_events = np.where(choch != 0)[0]
        if len(choch_events):
            choch[choch_events] = choch[np.random.permutation(choch_events)]

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
                    ch_bull_a += 1
                else:
                    ch_bull_c_cnt += 1
                    ch_bull_c += 1
            elif choch[i] == -1:
                if aligned and direction == "BEARISH":
                    ch_bear_a_cnt += 1
                    ch_bear_a += 1
                else:
                    ch_bear_c_cnt += 1
                    ch_bear_c += 1

        if bb_a_cnt:
            bos_bullish_aligned_hits.append(bb_a_hit / bb_a_cnt)
        if bb_c_cnt:
            bos_bullish_against_hits.append(bb_c_hit / bb_c_cnt)
        if ba_a_cnt:
            bos_bearish_aligned_hits.append(ba_a_hit / ba_a_cnt)
        if ba_c_cnt:
            bos_bearish_against_hits.append(ba_c_hit / ba_c_cnt)
        if ch_bull_a_cnt:
            choch_bullish_aligned_confirmed.append(ch_bull_a / ch_bull_a_cnt)
        if ch_bull_c_cnt:
            choch_bullish_against_confirmed.append(ch_bull_c / ch_bull_c_cnt)
        if ch_bear_a_cnt:
            choch_bearish_aligned_confirmed.append(ch_bear_a / ch_bear_a_cnt)
        if ch_bear_c_cnt:
            choch_bearish_against_confirmed.append(ch_bear_c / ch_bear_c_cnt)

    def _mean_std(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return float("nan"), float("nan")
        return float(np.mean(vals)), float(np.std(vals, ddof=0))

    return {
        "bos_bullish_aligned_hit_baseline_mean": _mean_std(bos_bullish_aligned_hits)[0],
        "bos_bullish_aligned_hit_baseline_std": _mean_std(bos_bullish_aligned_hits)[1],
        "bos_bullish_against_hit_baseline_mean": _mean_std(bos_bullish_against_hits)[0],
        "bos_bullish_against_hit_baseline_std": _mean_std(bos_bullish_against_hits)[1],
        "bos_bearish_aligned_hit_baseline_mean": _mean_std(bos_bearish_aligned_hits)[0],
        "bos_bearish_aligned_hit_baseline_std": _mean_std(bos_bearish_aligned_hits)[1],
        "bos_bearish_against_hit_baseline_mean": _mean_std(bos_bearish_against_hits)[0],
        "bos_bearish_against_hit_baseline_std": _mean_std(bos_bearish_against_hits)[1],
        "choch_bullish_aligned_confirmed_baseline_mean": _mean_std(choch_bullish_aligned_confirmed)[0],
        "choch_bullish_aligned_confirmed_baseline_std": _mean_std(choch_bullish_aligned_confirmed)[1],
        "choch_bullish_against_confirmed_baseline_mean": _mean_std(choch_bullish_against_confirmed)[0],
        "choch_bullish_against_confirmed_baseline_std": _mean_std(choch_bullish_against_confirmed)[1],
        "choch_bearish_aligned_confirmed_baseline_mean": _mean_std(choch_bearish_aligned_confirmed)[0],
        "choch_bearish_aligned_confirmed_baseline_std": _mean_std(choch_bearish_aligned_confirmed)[1],
        "choch_bearish_against_confirmed_baseline_mean": _mean_std(choch_bearish_against_confirmed)[0],
        "choch_bearish_against_confirmed_baseline_std": _mean_std(choch_bearish_against_confirmed)[1],
    }


def run_effectiveness_htf(
    symbol: str = "EURUSD",
    max_bars: int = 30000,
    k: int = 5,
    swing_lookback: int = 5,
    confirm_bars: int = 2,
) -> dict[str, Any]:
    validated = validate_m15_parquet(symbol)
    m15_df = validated.df.sort_index().iloc[:max_bars]
    h4_df = _resample(m15_df, "4h")
    h1_df = _resample(m15_df, "1h")
    d1_df = _resample(m15_df, "1d")

    bias_index = compute_htf_bias_series(d1_df, h4_df, h1_df, m15_df, swing_lookback=swing_lookback)

    timeframes = {
        "D1": d1_df,
        "H4": h4_df,
        "H1": h1_df,
        "M15": m15_df,
    }

    bias_coverage = {}
    timeframes_metrics = []
    for tf, frame in timeframes.items():
        series = bias_index.reindex(frame.index)
        bias_coverage[tf] = float(series["aligned"].mean())
        m = _measure_timeframe(frame, bias_index, tf, k=k, confirm_bars=confirm_bars)
        m.baseline = _baseline_permutation(frame, bias_index, k=k, confirm_bars=confirm_bars)
        timeframes_metrics.append(dataclasses.asdict(m))

    return {
        "symbol": symbol,
        "max_bars": max_bars,
        "k": k,
        "swing_lookback": swing_lookback,
        "confirm_bars": confirm_bars,
        "bias_coverage": bias_coverage,
        "timeframes": timeframes_metrics,
    }


def main() -> int:
    symbol = os.environ.get("SMCS_EFFECTIVENESS_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_EFFECTIVENESS_MAX_BARS", 30000))
    k = int(os.environ.get("SMCS_EFFECTIVENESS_K", 5))
    swing_lookback = int(os.environ.get("SMCS_EFFECTIVENESS_SWING_LOOKBACK", 5))
    confirm_bars = int(os.environ.get("SMCS_EFFECTIVENESS_CONFIRM_BARS", 2))
    print(json.dumps(run_effectiveness_htf(symbol, max_bars, k, swing_lookback, confirm_bars), ensure_ascii=False, indent=2, default=_serialize))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

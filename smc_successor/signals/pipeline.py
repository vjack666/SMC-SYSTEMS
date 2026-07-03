from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from smc_successor.agents.orchestrator import AgentOrchestrator
from smc_successor.data import load_frame
from smc_successor.detectors import (
    CHOCH_BEARISH,
    CHOCH_BULLISH,
    BosConfig,
    compute_zones,
    detect_bos,
    detect_choch,
    detect_displacement,
    detect_fvg,
    detect_order_blocks,
    ZoneConfig,
)
from smc_successor.indicators import add_atr, add_ema, add_rsi
from smc_successor.trend_context import build_trend_context_frame


@dataclass(frozen=True)
class ScalpingSignal:
    symbol: str
    time: str
    direction: int
    confidence: float
    entry: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class ScalpingConfig:
    trend_confidence_threshold: float = 0.45
    require_d1_h4_agreement: bool = False
    ob_fvg_proximity_atr: float = 1.5
    allow_xau_asia_session: bool = False
    relaxed_bos: bool = False
    use_confluence_mode: bool = True
    min_confluence_score: int = 2
    min_atr_ratio: float = 1.0


def _session_filter(times: pd.Series, symbol: str, allow_xau_asia: bool) -> pd.Series:
    hours = pd.to_datetime(times, utc=True).dt.hour
    london = (hours >= 7) & (hours <= 11)
    new_york = (hours >= 13) & (hours <= 17)
    asia = (hours >= 0) & (hours <= 5)
    if allow_xau_asia and symbol == "XAUUSD":
        return london | new_york | asia
    return london | new_york


def _last_anchor(series: pd.Series, condition: pd.Series) -> pd.Series:
    marker = pd.Series(np.nan, index=series.index, dtype=float)
    marker.loc[condition] = series.loc[condition].astype(float)
    return marker.ffill()


def build_scalping_context(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    config: ScalpingConfig | None = None,
    orchestrator: AgentOrchestrator | None = None,
) -> pd.DataFrame:
    if config is None:
        config = ScalpingConfig()

    data = load_frame(data_dir, symbol, timeframe)

    data = detect_bos(data, BosConfig(followthrough_bars=18))
    data = detect_choch(data)
    data = detect_fvg(data)
    data = detect_order_blocks(data)
    data = detect_displacement(data)
    data = compute_zones(data, ZoneConfig(swing_lookback=20))

    data["atr"] = add_atr(data, 14)
    data["ema_fast"] = add_ema(data, 20)
    data["ema_slow"] = add_ema(data, 50)
    data["rsi"] = add_rsi(data, 14)
    data["atr_ratio"] = data["atr"] / data["atr"].rolling(20).mean().replace(0.0, np.nan)

    macro = build_trend_context_frame(symbol=symbol, ltf_frame=data, data_dir=data_dir)
    data = pd.merge_asof(data.sort_values("time"), macro.sort_values("time"), on="time", direction="backward")

    macro_direction = np.where(
        data["trend_score"] >= 30.0,
        "BULLISH",
        np.where(data["trend_score"] <= -30.0, "BEARISH", "RANGING"),
    )
    data["macro_direction"] = macro_direction
    data["d1_direction"] = np.where(data["d1_trend"].isin(["BULLISH", "BEARISH"]), data["d1_trend"], "RANGING")
    data["macro_trend"] = data["macro_direction"]

    regime_pass = ~data["regime_state"].isin(["LOW_VOL", "CHAOTIC"])
    trend_filter = (
        data["macro_direction"].isin(["BULLISH", "BEARISH"])
        & (data["trend_confidence"] >= float(config.trend_confidence_threshold))
        & regime_pass
    )

    session_filter = _session_filter(data["time"], symbol, config.allow_xau_asia_session)
    atr_filter = data["atr_ratio"].fillna(0.0) > config.min_atr_ratio

    if config.relaxed_bos:
        bos_up = data["bos_direction"].rolling(2, min_periods=1).max() > 0
        bos_down = data["bos_direction"].rolling(2, min_periods=1).min() < 0
    else:
        bos_up = data["bos_direction"] > 0
        bos_down = data["bos_direction"] < 0

    bos_filter = (
        ((data["macro_direction"] == "BULLISH") & bos_up)
        | ((data["macro_direction"] == "BEARISH") & bos_down)
    )

    volume_filter = data["tick_volume"] >= (data["tick_volume"].rolling(20).mean().fillna(0.0) * 0.90)

    bullish_anchor = _last_anchor(
        data["close"],
        data["fvg_bullish"] | data["ob_bullish"],
    )
    bearish_anchor = _last_anchor(
        data["close"],
        data["fvg_bearish"] | data["ob_bearish"],
    )
    bull_near = ((data["close"] - bullish_anchor).abs() / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= (
        config.ob_fvg_proximity_atr
    )
    bear_near = ((data["close"] - bearish_anchor).abs() / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= (
        config.ob_fvg_proximity_atr
    )
    ob_fvg_filter = (
        ((data["macro_direction"] == "BULLISH") & bull_near)
        | ((data["macro_direction"] == "BEARISH") & bear_near)
    )

    recent_bearish_choch = (data["choch_signal"] == CHOCH_BEARISH).rolling(10, min_periods=1).max().astype(bool)
    recent_bullish_choch = (data["choch_signal"] == CHOCH_BULLISH).rolling(10, min_periods=1).max().astype(bool)
    choch_filter = (
        ((data["macro_direction"] == "BULLISH") & (~recent_bearish_choch))
        | ((data["macro_direction"] == "BEARISH") & (~recent_bullish_choch))
    )

    swing_high_ref = data["high"].rolling(20, min_periods=5).max().shift(1)
    swing_low_ref = data["low"].rolling(20, min_periods=5).min().shift(1)
    swing_dist = np.minimum((data["close"] - swing_high_ref).abs(), (data["close"] - swing_low_ref).abs())
    swing_filter = (swing_dist / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= 1.5

    trend_up = data["ema_fast"] > data["ema_slow"]
    trend_down = data["ema_fast"] < data["ema_slow"]
    micro_filter = (
        ((data["macro_direction"] == "BULLISH") & trend_up & data["rsi"].between(40, 74))
        | ((data["macro_direction"] == "BEARISH") & trend_down & data["rsi"].between(26, 60))
    )

    data["filter_trend"] = trend_filter
    data["filter_session"] = session_filter
    data["filter_atr"] = atr_filter
    data["filter_ob_fvg"] = ob_fvg_filter
    data["filter_bos"] = bos_filter
    data["filter_volume"] = volume_filter
    data["filter_micro"] = micro_filter
    data["filter_choch"] = choch_filter
    data["filter_swing"] = swing_filter

    if orchestrator is not None:
        data = orchestrator.analyze_context(data)
        decision_conf = data["agent_decision_confidence"].fillna(0.0)
        decision_bias = data["agent_decision_bias"].fillna("NEUTRAL")
        data["filter_agents"] = (
            (decision_conf >= 0.50)
            & ((decision_bias == "BULLISH") | (decision_bias == "BEARISH"))
        )
    else:
        data["filter_agents"] = True

    max_confluence = 6.0 if orchestrator is not None else 5.0
    confluence_score = (
        data["filter_trend"].astype(int)
        + data["filter_bos"].astype(int)
        + data["filter_ob_fvg"].astype(int)
        + data["filter_choch"].astype(int)
        + data["filter_swing"].astype(int)
        + (data["filter_agents"].astype(int) if orchestrator is not None else 0)
    )
    data["confluence_score"] = confluence_score

    data["signal_confidence"] = (0.40 + (confluence_score / max_confluence) * 0.55).clip(lower=0.40, upper=0.95)

    mandatory_pass = data["filter_session"] & data["filter_atr"]
    signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score)

    data["signal_direction"] = 0
    data.loc[signal_pass & (data["macro_direction"] == "BULLISH"), "signal_direction"] = 1
    data.loc[signal_pass & (data["macro_direction"] == "BEARISH"), "signal_direction"] = -1

    swing_low_20 = data["last_swing_low"].ffill().rolling(20, min_periods=1).apply(
        lambda s: s.dropna().iloc[-1] if not s.dropna().empty else float("nan"), raw=False
    )
    swing_high_20 = data["last_swing_high"].ffill().rolling(20, min_periods=1).apply(
        lambda s: s.dropna().iloc[-1] if not s.dropna().empty else float("nan"), raw=False
    )
    data["structural_sl"] = float("nan")
    long_mask = data["signal_direction"] == 1
    short_mask = data["signal_direction"] == -1
    data.loc[long_mask, "structural_sl"] = swing_low_20
    data.loc[short_mask, "structural_sl"] = swing_high_20

    has_swing = data["structural_sl"].notna()
    data.loc[long_mask & ~has_swing, "structural_sl"] = data.loc[long_mask & ~has_swing, "close"] - data.loc[long_mask & ~has_swing, "atr"]
    data.loc[short_mask & ~has_swing, "structural_sl"] = data.loc[short_mask & ~has_swing, "close"] + data.loc[short_mask & ~has_swing, "atr"]

    data["passed_all_filters"] = mandatory_pass & (data["confluence_score"] == max_confluence)
    return data


def summarize_filter_diagnosis(context: pd.DataFrame) -> dict[str, int]:
    total = int(len(context))
    return {
        "total_bars": total,
        "rejected_by_trend_filter": int((~context["filter_trend"]).sum()),
        "rejected_by_session_filter": int((~context["filter_session"]).sum()),
        "rejected_by_atr_filter": int((~context["filter_atr"]).sum()),
        "rejected_by_ob_fvg_filter": int((~context["filter_ob_fvg"]).sum()),
        "rejected_by_bos_filter": int((~context["filter_bos"]).sum()),
        "rejected_by_volume_filter": int((~context["filter_volume"]).sum()),
        "passed_all_filters": int(context["passed_all_filters"].sum()),
    }


def build_scalping_signals(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    min_confidence: float = 0.65,
    config: ScalpingConfig | None = None,
) -> list[ScalpingSignal]:
    context = build_scalping_context(symbol=symbol, timeframe=timeframe, data_dir=data_dir, config=config)
    valid = context[(context["signal_direction"] != 0) & (context["signal_confidence"] >= min_confidence)]

    results: list[ScalpingSignal] = []
    for _, row in valid.iterrows():
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0.0:
            continue

        entry = float(row["close"])
        direction = int(row["signal_direction"])
        sl = entry - atr if direction == 1 else entry + atr
        tp = entry + (2.0 * atr) if direction == 1 else entry - (2.0 * atr)

        results.append(
            ScalpingSignal(
                symbol=symbol,
                time=str(row["time"]),
                direction=direction,
                confidence=float(row["signal_confidence"]),
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
            )
        )

    return results

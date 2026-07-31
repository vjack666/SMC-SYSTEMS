from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast

import numpy as np
import pandas as pd

from agents.orchestrator import AgentOrchestrator
from data import load_frame
from detectors import (
    compute_zones,
    detect_displacement,
    detect_fvg,
    detect_order_blocks,
    ZoneConfig,
)
from indicators import add_atr, add_ema, add_rsi, add_stochastic
from trend_context import build_trend_context_frame
from ict_backtest.market_structure import StructureConfig, detect_market_structure


@dataclass(frozen=True)
class ScalpingSignal:
    symbol: str
    time: str
    direction: int
    confidence: float
    entry: float
    stop_loss: float
    take_profit: float
    meta: dict[str, Any] | None = None


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
    use_ml_quality_filter: bool = False
    ml_model_path: str = "ml/models/quality_filter.pkl"
    confluence_weights: dict[str, float] = field(default_factory=lambda: {
        "trend": 3.0,
        "choch": 3.0,
        "ob": 2.0,
        "fvg": 2.0,
        "displacement": 2.0,
        "bos": 1.0,
        "swing": 1.0,
        "agents": 2.0,
        "sweep": 2.0,
        "ote": 1.0,
        "choch_bos_confirm": 2.0,
    })
    enable_sweep_filter: bool = True
    enable_ote_filter: bool = True
    sweep_lookback: int = 8
    sequence_bos_gap: int = 10
    mandatory_choch_bos_confirm: bool = False
    enable_detector_invalidation: bool = False
    use_mtf_structure_align: bool = False
    tf_level_score_weights: dict[str, float] = field(default_factory=lambda: {
        "HTF": 0.20,
        "ITF": 0.10,
        "LTF": 0.00,
    })


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
    progress_cb: Callable[[str, int, int, str], None] | None = None,
) -> pd.DataFrame:
    if config is None:
        config = ScalpingConfig()

    steps = [
        "load_frame", "market_structure", "detect_fvg",
        "detect_order_blocks", "detect_displacement", "compute_zones",
        "indicators", "trend_context", "filters", "sweep_ote",
        "confluence", "done",
    ]
    total_steps = len(steps)

    def _step(idx: int, msg: str) -> None:
        if progress_cb:
            progress_cb("context", idx, total_steps, f"{symbol} {msg}")

    _step(0, "loading data...")
    data = load_frame(data_dir, symbol, timeframe)

    _step(1, "detecting market structure (canonical BOS/CHOCH)...")
    ms = detect_market_structure(data, StructureConfig(swing_lookback=5, confirm_bars=2))
    data["bos_dir"] = ms["bos_dir"].astype(int).values
    data["choch_dir"] = ms["choch_dir"].astype(int).values
    data["bos_status"] = ms["bos_status"].astype(str).values
    data["choch_status"] = ms["choch_status"].astype(str).values
    data["bos_level"] = ms["bos_level"].values
    data["choch_level"] = ms["choch_level"].values

    _step(2, "detecting FVG...")
    fvg = detect_fvg(data)
    data["fvg_bullish"] = fvg["fvg_bullish"].astype(bool).values
    data["fvg_bearish"] = fvg["fvg_bearish"].astype(bool).values

    _step(3, "detecting order blocks...")
    ob = detect_order_blocks(data)
    data["ob_bullish"] = ob["ob_bullish"].astype(bool).values
    data["ob_bearish"] = ob["ob_bearish"].astype(bool).values
    data["ob_status"] = ob["ob_status"].astype(str).values

    _step(4, "detecting displacement...")
    disp = detect_displacement(data)
    data["displacement_bullish"] = disp["displacement_bullish"].astype(bool).values
    data["displacement_bearish"] = disp["displacement_bearish"].astype(bool).values

    _step(5, "computing zones...")
    zones = compute_zones(data)
    data["ob_zone_bullish"] = zones["ob_zone_bullish"].astype(bool).values
    data["ob_zone_bearish"] = zones["ob_zone_bearish"].astype(bool).values
    data["fvg_zone_bullish"] = zones["fvg_zone_bullish"].astype(bool).values
    data["fvg_zone_bearish"] = zones["fvg_zone_bearish"].astype(bool).values

    _step(6, "computing indicators...")
    data = add_atr(data, period=14)
    data = add_ema(data, span=20)
    data = add_ema(data, span=50)
    data = add_rsi(data, period=14)
    data = add_stochastic(data, k_period=14, d_period=3)

    _step(7, "building trend context...")
    tc = build_trend_context_frame(data, data_dir=data_dir, symbol=symbol, timeframe=timeframe)
    if tc is not None and not tc.empty:
        data["d1_bias"] = "NEUTRAL"
        data["h4_bias"] = "NEUTRAL"
        if "bias" in tc.columns:
            data["d1_bias"] = tc["bias"].reindex(data.index).fillna("NEUTRAL").values
        if "h4_bias" in tc.columns:
            data["h4_bias"] = tc["h4_bias"].reindex(data.index).fillna("NEUTRAL").values

    _step(8, "building filters...")
    atr = data["atr"].replace(0.0, np.nan)
    atr_valid = data["atr"].fillna(0.0) > 0.0

    trend_filter = data.get("d1_bias", pd.Series("NEUTRAL", index=data.index)) == data.get("h4_bias", pd.Series("NEUTRAL", index=data.index))
    if config.relaxed_bos:
        trend_filter = pd.Series(True, index=data.index)

    session_filter = _session_filter(data["time"], symbol, config.allow_xau_asia_session)
    atr_filter = (data["atr"].fillna(0.0) >= 0.0) if config.min_atr_ratio <= 0 else (data["atr"].fillna(0.0) >= float(data["atr"].rolling(20).min()))

    ob_cond = (data["ob_status"].isin(["active", "none"]) if (config.enable_detector_invalidation and "ob_status" in data.columns) else True)
    bullish_anchor = _last_anchor(
        data["close"],
        (data["fvg_bullish"] | data["ob_bullish"]) & ob_cond,
    )
    bearish_anchor = _last_anchor(
        data["close"],
        (data["fvg_bearish"] | data["ob_bearish"]) & ob_cond,
    )
    def _near(anchor):
        return ((data["close"] - anchor).abs() / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= config.ob_fvg_proximity_atr

    bull_near = _near(bullish_anchor)
    bear_near = _near(bearish_anchor)
    ob_fvg_filter = (
        ((data["macro_direction"] == "BULLISH") & bull_near)
        | ((data["macro_direction"] == "BEARISH") & bear_near)
    )

    recent_bearish_choch = (data["choch_signal"] == "CHOCH_BEARISH").rolling(10, min_periods=1).max().astype(bool)
    recent_bullish_choch = (data["choch_signal"] == "CHOCH_BULLISH").rolling(10, min_periods=1).max().astype(bool)

    if config.enable_detector_invalidation and "choch_status" in data.columns:
        choch_alive = data["choch_status"].isin(["active", "none"])
    else:
        choch_alive = pd.Series(True, index=data.index)

    choch_filter = (
        ((data["macro_direction"] == "BULLISH") & (~recent_bearish_choch) & choch_alive)
        | ((data["macro_direction"] == "BEARISH") & (~recent_bullish_choch) & choch_alive)
    )

    swing_high_ref = data["high"].rolling(20, min_periods=5).max().shift(1)
    swing_low_ref = data["low"].rolling(20, min_periods=5).min().shift(1)
    swing_dist = np.minimum((data["close"] - swing_high_ref).abs(), (data["close"] - swing_low_ref).abs())
    swing_filter = (swing_dist / data["atr"].replace(0.0, np.nan)).fillna(99.0) <= 1.5

    recent_bullish_displacement = data["displacement_bullish"].rolling(10, min_periods=1).max().astype(bool)
    recent_bearish_displacement = data["displacement_bearish"].rolling(10, min_periods=1).max().astype(bool)
    data["filter_displacement"] = (
        ((data["macro_direction"] == "BULLISH") & recent_bullish_displacement)
        | ((data["macro_direction"] == "BEARISH") & recent_bearish_displacement)
    ).to_numpy()

    trend_up = data["ema_fast"] > data["ema_slow"]
    trend_down = data["ema_fast"] < data["ema_slow"]
    micro_filter = (
        ((data["macro_direction"] == "BULLISH") & trend_up & data["rsi"].between(40, 74))
        | ((data["macro_direction"] == "BEARISH") & trend_down & data["rsi"].between(26, 60))
    )

    _step(10, "sweep + OTE filters...")

    data["filter_trend"] = trend_filter
    data["filter_session"] = session_filter
    data["filter_atr"] = atr_filter
    data["filter_ob_fvg"] = ob_fvg_filter
    data["filter_bos"] = choch_filter
    data["filter_volume"] = data["tick_volume"] >= (data["tick_volume"].rolling(20).mean().fillna(0.0) * 0.90)
    data["filter_micro"] = micro_filter
    data["filter_choch"] = choch_filter
    data["filter_swing"] = swing_filter

    recent_bos_bull = data["bos_dir"].rolling(config.sequence_bos_gap, min_periods=1).max() > 0
    recent_bos_bear = data["bos_dir"].rolling(config.sequence_bos_gap, min_periods=1).min() < 0
    choch_bos_confirm = (
        ((data["macro_direction"] == "BULLISH") & recent_bearish_choch & recent_bos_bull & choch_alive)
        | ((data["macro_direction"] == "BEARISH") & recent_bullish_choch & recent_bos_bear & choch_alive)
    )
    data["filter_choch_bos_confirm"] = choch_bos_confirm

    if config.enable_sweep_filter:
        data["filter_sweep"] = data["recent_liquidity_sweep"] if "recent_liquidity_sweep" in data.columns else True
    else:
        data["filter_sweep"] = True
    if not config.enable_ote_filter:
        data["filter_ote"] = True

    active = {
        k: data[f"filter_{k}"]
        for k in ["trend", "choch", "ob", "fvg", "displacement", "bos", "swing", "agents", "sweep", "ote", "choch_bos_confirm"]
        if f"filter_{k}" in data.columns
    }
    weights = config.confluence_weights
    confluence_score = sum(active[k].astype(int) * weights.get(k, 1.0) for k in active)
    max_confluence = sum(weights.get(k, 1.0) for k in active)
    data["confluence_score"] = confluence_score

    data["signal_confidence"] = (0.40 + (confluence_score / max_confluence) * 0.55).clip(lower=0.40, upper=0.95)

    mandatory_pass = data["filter_session"] & data["filter_atr"]

    reversal_setup = recent_bearish_choch | recent_bullish_choch
    choch_bos_gate = (~reversal_setup) | data["filter_choch_bos_confirm"].astype(bool)
    if config.mandatory_choch_bos_confirm:
        signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score) & choch_bos_gate
    else:
        signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score)

    data["signal_direction"] = 0
    data.loc[signal_pass & (data["macro_direction"] == "BULLISH"), "signal_direction"] = 1
    data.loc[signal_pass & (data["macro_direction"] == "BEARISH"), "signal_direction"] = -1

    swing_low_20 = data["swing_low"].ffill().rolling(20, min_periods=1).apply(
        lambda s: s.dropna().iloc[-1] if not s.dropna().empty else float("nan"), raw=False
    )
    swing_high_20 = data["swing_high"].ffill().rolling(20, min_periods=1).apply(
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
    _step(12, f"context ready ({len(data)} bars)")
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


def _align_signals_tf_level(context: pd.DataFrame, symbol: str, ltf: str = "M5") -> pd.Series:
    if "time" not in context.columns:
        return pd.Series([""] * len(context), index=context.index, dtype=object)
    try:
        from pathlib import Path
        from ict_backtest.structure_mtf_align import AlignConfig, align_structure_mtf
        ms_by_tf: dict[str, pd.DataFrame] = {}
        for tf_name in [ltf, "H1", "H4", "D1"]:
            tf_path = Path(f"data/raw/{symbol}_{tf_name}.parquet")
            if tf_path.exists():
                tf_frame = pd.read_parquet(tf_path)
                tf_frame = tf_frame.dropna(subset=["open", "high", "low", "close"]).sort_values("time").reset_index(drop=True)
                if tf_name == ltf:
                    tf_frame = tf_frame.tail(50000).reset_index(drop=True)
                ms_by_tf[tf_name] = detect_market_structure(tf_frame, StructureConfig(swing_lookback=5, confirm_bars=2))
        if not ms_by_tf:
            return pd.Series([""] * len(context), index=context.index, dtype=object)

        # Usa la config calibrada del audit: soft match + ventanas lead/lag
        align_report = align_structure_mtf(ms_by_tf, AlignConfig(ltf=ltf))

        # Map robusto: normaliza tz y fallback LTF
        onset_map: dict[tuple[pd.Timestamp, str, int], str] = {}
        for onset in align_report.get("onsets", []):
            raw = pd.Timestamp(onset.time)
            norm = raw.tz_convert(None) if getattr(raw, "tz", None) is not None else raw
            onset_map[(norm, onset.event, int(onset.direction))] = onset.tf_level or "LTF"

        tf_level_series = pd.Series([""] * len(context), index=context.index, dtype=object)
        for i, row in context.iterrows():
            if pd.isna(row.get("time")):
                continue
            raw_time = pd.Timestamp(row["time"])
            row_time = raw_time.tz_convert(None) if getattr(raw_time, "tz", None) is not None else raw_time

            dir_val = 0
            ev = ""
            if int(row.get("bos_dir", 0) or 0) != 0:
                dir_val = int(row["bos_dir"])
                ev = "bos"
            elif int(row.get("choch_dir", 0) or 0) != 0:
                dir_val = int(row["choch_dir"])
                ev = "choch"

            if ev:
                tf_level_series.at[i] = onset_map.get((row_time, ev, dir_val), "LTF")
        return tf_level_series
    except Exception:
        return pd.Series([""] * len(context), index=context.index, dtype=object)


def build_scalping_signals(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    min_confidence: float = 0.65,
    config: ScalpingConfig | None = None,
) -> list[ScalpingSignal]:
    context = build_scalping_context(symbol=symbol, timeframe=timeframe, data_dir=data_dir, config=config)
    tf_level_series = pd.Series([""] * len(context), index=context.index, dtype=object)
    if config and config.use_mtf_structure_align:
        tf_level_series = _align_signals_tf_level(context, symbol, ltf=timeframe)
        if config.tf_level_score_weights:
            tf_level_bonus = tf_level_series.map(config.tf_level_score_weights).fillna(0.0).to_numpy()
            context["signal_confidence"] = (context["signal_confidence"] + tf_level_bonus).clip(lower=0.40, upper=0.95)
    context["tf_level_aligned"] = tf_level_series

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

        meta: dict[str, Any] = {}
        if config and config.use_mtf_structure_align:
            tf_level = str(row.get("tf_level_aligned", ""))
            if tf_level in {"HTF", "ITF", "LTF"}:
                meta["tf_level"] = tf_level
                if int(row.get("bos_dir", 0) or 0) != 0:
                    meta["structure_event"] = "BOS"
                elif int(row.get("choch_dir", 0) or 0) != 0:
                    meta["structure_event"] = "CHOCH"
                elif direction == 1:
                    meta["structure_event"] = "BOS"
                elif direction == -1:
                    meta["structure_event"] = "CHOCH"

        results.append(
            ScalpingSignal(
                symbol=symbol,
                time=str(row["time"]),
                direction=direction,
                confidence=float(row["signal_confidence"]),
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
                meta=meta or None,
            )
        )

    return results

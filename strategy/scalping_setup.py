from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from modules.bos.detector import BosConfig, detect_bos
from modules.choch.detector import CHOCH_BEARISH, CHOCH_BULLISH, detect_choch
from modules.fvg.detector import detect_fvg
from modules.indicators import add_atr, add_ema, add_rsi
from modules.ob.detector import detect_order_blocks
from modules.stochastic_exhaustion.config import StochasticExhaustionConfig
from modules.stochastic_exhaustion.detector import detect_exhaustion
from modules.structural_sl.detector import calculate_structural_stop
from modules.trend.context_engine import build_trend_context_frame
from modules.wyckoff.config import WyckoffConfig
from modules.wyckoff.detector import detect_wyckoff
from ml.regime_detector import detect_regimes
from pac_sequence.state_machine import StateMachineConfig, run_state_machine
from strategy.confluence_scorer import calculate_confluence_score, ConfluenceWeights, REGIME_BOOSTS


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
    use_pac: bool = True
    use_structural_sl: bool = True
    pac_ttl_bars: int = 64
    pac_mitigation_method: str = "wick"
    structural_sl_lookback: int = 20
    use_stochastic_exhaustion: bool = True
    use_wyckoff: bool = True


def _load_frame(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


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


def _build_exhaustion_series(data: pd.DataFrame, config: ScalpingConfig) -> pd.Series:
    series = pd.Series(False, index=data.index)
    if config.use_stochastic_exhaustion and "exhaustion_bullish" in data.columns and "exhaustion_bearish" in data.columns:
        series = series | data["exhaustion_bullish"] | data["exhaustion_bearish"]
    if config.use_wyckoff and "wyckoff_accumulation" in data.columns:
        series = series | data["wyckoff_accumulation"]
    return series


def _apply_pac_to_context(
    data: pd.DataFrame,
    config: ScalpingConfig,
) -> pd.DataFrame:
    pac_config = StateMachineConfig(
        ttl_bars=config.pac_ttl_bars,
        mitigation_method=config.pac_mitigation_method,
    )
    data["pac_entry_ready"] = False
    data["pac_mitigation_idx"] = -1
    data["pac_entry_idx"] = -1
    data["pac_invalidation"] = ""
    data["pac_exhaustion_confirmed"] = False

    exhaustion_series = _build_exhaustion_series(data, config) if (config.use_stochastic_exhaustion or config.use_wyckoff) else None

    fvg_indices = data.index[data["fvg_bullish"] | data["fvg_bearish"]].tolist()

    for create_idx in fvg_indices:
        row = data.iloc[create_idx]
        direction = int(row["fvg_direction"])
        if direction == 0:
            continue
        zone_low = float(row["fvg_zone_low"])
        zone_high = float(row["fvg_zone_high"])
        if not np.isfinite(zone_low) or not np.isfinite(zone_high):
            continue

        result = run_state_machine(
            scored=data,
            create_idx=create_idx,
            direction=direction,
            zone_low=zone_low,
            zone_high=zone_high,
            config=pac_config,
            setup_id=f"pac_{create_idx}",
            exhaustion_series=exhaustion_series,
        )

        entry_idx = result.get("entry_idx")
        invalidation = result.get("invalidation")

        if entry_idx is not None and invalidation is None:
            data.at[data.index[entry_idx], "pac_entry_ready"] = True
            data.at[data.index[entry_idx], "pac_mitigation_idx"] = result.get("mitigation_idx", -1)
            data.at[data.index[entry_idx], "pac_entry_idx"] = entry_idx
            data.at[data.index[entry_idx], "pac_exhaustion_confirmed"] = result.get("exhaustion_confirmed", False)
        elif invalidation is not None:
            last_idx = min(create_idx + config.pac_ttl_bars, len(data) - 1)
            data.at[data.index[last_idx], "pac_invalidation"] = invalidation

    return data


def _apply_structural_sl_to_context(
    data: pd.DataFrame,
    config: ScalpingConfig,
) -> pd.DataFrame:
    data["structural_stop_price"] = np.nan
    data["structural_stop_distance"] = np.nan
    data["structural_stop_atr"] = np.nan

    signal_indices = data.index[data["signal_direction"] != 0].tolist()
    for idx in signal_indices:
        direction = int(data.at[idx, "signal_direction"])
        stop = calculate_structural_stop(
            df=data,
            entry_idx=idx,
            direction=direction,
            lookback_origin=config.structural_sl_lookback,
            atr_col="atr",
        )
        if stop is not None:
            data.at[idx, "structural_stop_price"] = stop.structural_stop_price
            data.at[idx, "structural_stop_distance"] = stop.stop_distance_pips
            data.at[idx, "structural_stop_atr"] = stop.stop_distance_atr

    return data


def build_scalping_context(
    symbol: str,
    timeframe: str = "M15",
    data_dir: Path = Path("data/mt5"),
    config: ScalpingConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = ScalpingConfig()

    data = _load_frame(data_dir, symbol, timeframe)

    data = detect_bos(data, BosConfig(followthrough_bars=18))
    data = detect_choch(data)
    data = detect_fvg(data)
    data = detect_order_blocks(data)
    data["atr"] = add_atr(data, 14)

    if config.use_stochastic_exhaustion:
        ex_config = StochasticExhaustionConfig()
        data = detect_exhaustion(data, ex_config)

    if config.use_wyckoff:
        wyc_config = WyckoffConfig()
        data = detect_wyckoff(data, wyc_config)

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

    data = detect_regimes(data)

    regime_pass = ~data["market_regime"].isin(["LOW_VOL", "CHAOTIC"])
    trend_filter = (
        data["macro_direction"].isin(["BULLISH", "BEARISH"])
        & (data["trend_confidence"] >= float(config.trend_confidence_threshold))
        & regime_pass
    )

    session_filter = _session_filter(data["time"], symbol, config.allow_xau_asia_session)
    # Mandatory market-activity gate: ATR must be above its 20-period average.
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

    exhaustion_ok = pd.Series(True, index=data.index)
    if config.use_stochastic_exhaustion and "exhaustion_bullish" in data.columns:
        exhaustion_ok = exhaustion_ok & (
            (data["exhaustion_bullish"] & (data["macro_direction"] == "BEARISH"))
            | (data["exhaustion_bearish"] & (data["macro_direction"] == "BULLISH"))
        )
    data["filter_exhaustion"] = exhaustion_ok

    wyckoff_ok = pd.Series(True, index=data.index)
    if config.use_wyckoff and "wyckoff_accumulation" in data.columns:
        wyckoff_ok = wyckoff_ok & data["wyckoff_accumulation"]
    data["filter_wyckoff"] = wyckoff_ok

    data["exhaustion_compression_ratio"] = np.where(
        data["atr"].replace(0.0, np.nan) > 0,
        (data["high"] - data["low"]) / data["atr"].replace(0.0, np.nan),
        0.0,
    )
    wyckoff_events = (
        data["wyckoff_sc"].astype(int)
        + data["wyckoff_ar"].astype(int)
        + data["wyckoff_st"].astype(int)
        + data["wyckoff_spring"].astype(int)
        + data["wyckoff_sos"].astype(int)
        + data["wyckoff_lps"].astype(int)
    ) if "wyckoff_sc" in data.columns else 0
    data["wyckoff_event_score"] = np.minimum(wyckoff_events, 5) if isinstance(wyckoff_events, pd.Series) else 0
    data["distance_to_fvg_zone"] = np.nan
    data["distance_to_swing_high"] = np.nan
    data["distance_to_swing_low"] = np.nan
    if "fvg_zone_low" in data.columns and "fvg_zone_high" in data.columns:
        data["distance_to_fvg_zone"] = np.where(
            data["fvg_zone_low"].notna() & data["fvg_zone_high"].notna(),
            np.minimum(
                (data["close"] - data["fvg_zone_low"]).abs(),
                (data["close"] - data["fvg_zone_high"]).abs(),
            ) / data["atr"].replace(0.0, np.nan),
            np.nan,
        )
    if "swing_high" in data.columns:
        data["distance_to_swing_high"] = (data["swing_high"].ffill() - data["close"]).abs() / data["atr"].replace(0.0, np.nan)
    if "swing_low" in data.columns:
        data["distance_to_swing_low"] = (data["close"] - data["swing_low"].ffill()).abs() / data["atr"].replace(0.0, np.nan)
    data["temporal_alignment_score"] = np.where(
        data["macro_direction"].isin(["BULLISH", "BEARISH"]),
        np.where(data["d1_direction"] == data["macro_direction"], 1.0, 0.5),
        0.0,
    )
    pac_ready_count = data["pac_entry_ready"].rolling(100, min_periods=1).sum() if "pac_entry_ready" in data.columns else 0
    total_fvg = (data["fvg_bullish"] | data["fvg_bearish"]).rolling(100, min_periods=1).sum().replace(0, 1)
    data["pac_completion_rate"] = (pac_ready_count / total_fvg) if isinstance(pac_ready_count, pd.Series) else 0.0
    exhaustion_total = (data["exhaustion_bullish"] | data["exhaustion_bearish"]).astype(int) if "exhaustion_bullish" in data.columns else 0
    total_bars = data.index / max(len(data), 1)
    data["exhaustion_confluence_ratio"] = (exhaustion_total.rolling(50).sum() / 50.0) if isinstance(exhaustion_total, pd.Series) else 0.0

    max_confluence = 7
    raw_score = (
        data["filter_trend"].astype(int)
        + data["filter_bos"].astype(int)
        + data["filter_ob_fvg"].astype(int)
        + data["filter_choch"].astype(int)
        + data["filter_swing"].astype(int)
        + data["filter_exhaustion"].astype(int)
        + data["filter_wyckoff"].astype(int)
    )
    data["confluence_score"] = raw_score
    data["passed_all_filters"] = data["filter_session"] & data["filter_atr"] & (raw_score == max_confluence)

    if config.use_pac:
        data = _apply_pac_to_context(data, config)

    if "ml_probability" not in data.columns:
        data["ml_probability"] = 0.50
    weights = ConfluenceWeights()
    confidences = []
    for i in range(len(data)):
        row = data.iloc[i]
        regime = str(row.get("market_regime", "RANGING"))
        conf = calculate_confluence_score(row, weights=weights, regime=regime)
        confidences.append(conf)
    data["signal_confidence"] = np.clip(confidences, 0.30, 0.95)

    mandatory_pass = data["filter_session"] & data["filter_atr"]
    min_conf = 0.35
    signal_pass = mandatory_pass & (data["signal_confidence"] >= min_conf)

    data["signal_direction"] = 0
    data.loc[signal_pass & (data["macro_direction"] == "BULLISH"), "signal_direction"] = 1
    data.loc[signal_pass & (data["macro_direction"] == "BEARISH"), "signal_direction"] = -1

    data["signal_direction"] = data["signal_direction"] * data["pac_entry_ready"].astype(int)

    if config.use_structural_sl:
        data = _apply_structural_sl_to_context(data, config)

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

        use_structural = config.use_structural_sl and np.isfinite(row.get("structural_stop_price", np.nan))
        if use_structural:
            sl = float(row["structural_stop_price"])
            risk = abs(entry - sl)
            if risk <= 0.0:
                sl = entry - atr if direction == 1 else entry + atr
                risk = abs(entry - sl)
            tp = entry + (2.0 * risk) if direction == 1 else entry - (2.0 * risk)
        else:
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

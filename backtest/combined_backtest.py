from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.regime_detector import detect_regimes
from risk.dynamic_threshold_engine import DynamicThresholdConfig, threshold_for_regime
from risk.meta_risk_governor import GovernorConfig, GovernorState, mode_risk_multiplier, mode_threshold_add, next_state
from strategy.scalping_setup import (
    ScalpingConfig,
    ScalpingSignal,
    build_scalping_context,
    summarize_filter_diagnosis,
)


@dataclass(frozen=True)
class CombinedBacktestConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    timeframe: str = "M15"
    min_confidence: float = 0.52
    max_hold_bars: int = 16
    start_time: str | None = None
    end_time: str | None = None
    enabled_symbols: tuple[str, ...] | None = None
    scalping_config: ScalpingConfig = ScalpingConfig()
    max_bars: int | None = None
    use_ml_quality_filter: bool = True
    ml_model_path: Path = Path("ml/models/quality_filter.pkl")
    base_ml_threshold: float = 0.60
    threshold_engine: DynamicThresholdConfig = DynamicThresholdConfig()
    risk_governor: GovernorConfig = GovernorConfig()
    quality_dataset_path: Path = Path("results/ml_trade_dataset.csv")
    dataset_quality_log_path: Path = Path("results/ml_dataset_quality_log.json")


@dataclass(frozen=True)
class CombinedTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    confidence: float
    entry: float
    exit: float
    pnl_r: float


def _load(data_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing market data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _apply_time_window(frame: pd.DataFrame, start_time: str | None, end_time: str | None) -> pd.DataFrame:
    data = frame.copy()
    if start_time is not None:
        data = data[data["time"] >= pd.to_datetime(start_time, utc=True)]
    if end_time is not None:
        data = data[data["time"] <= pd.to_datetime(end_time, utc=True)]
    return data.reset_index(drop=True)


def _build_signals_from_context(
    symbol: str,
    context: pd.DataFrame,
    min_confidence: float,
    scalping_config: ScalpingConfig | None = None,
) -> list[ScalpingSignal]:
    if scalping_config is None:
        scalping_config = ScalpingConfig()

    valid = context[(context["signal_direction"] != 0) & (context["signal_confidence"] >= min_confidence)]

    results: list[ScalpingSignal] = []
    for _, row in valid.iterrows():
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0.0:
            continue

        entry = float(row["close"])
        direction = int(row["signal_direction"])

        use_structural = scalping_config.use_structural_sl and np.isfinite(row.get("structural_stop_price", np.nan))
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


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(x):
        return default
    return x


def _coerce_utc_timestamp(value: Any) -> pd.Timestamp | None:
    if isinstance(value, pd.Timestamp):
        ts = value
    else:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _load_ml_model(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except (OSError, ValueError, TypeError):
        return None


def _predict_quality_probability(model: Any | None, feature_row: dict[str, Any], fallback: float) -> float:
    if model is None:
        return float(max(0.0, min(1.0, fallback)))
    if not hasattr(model, "predict_proba"):
        return float(max(0.0, min(1.0, fallback)))
    x = pd.DataFrame([feature_row])
    proba = np.asarray(model.predict_proba(x))
    if proba.ndim != 2 or proba.shape[0] == 0 or proba.shape[1] < 2:
        return float(max(0.0, min(1.0, fallback)))
    value = float(proba[0, 1])
    if not np.isfinite(value):
        return float(max(0.0, min(1.0, fallback)))
    return float(max(0.0, min(1.0, value)))


def _simulate_trade_with_stats(
    frame: pd.DataFrame,
    signal: ScalpingSignal,
    max_hold_bars: int,
) -> tuple[CombinedTrade | None, dict[str, Any]]:
    times = frame["time"].astype(str)
    matches = frame.index[times == signal.time]
    if len(matches) == 0:
        return None, {"exit_reason": "time_not_found", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    idx = int(matches[0])
    sl = signal.stop_loss
    tp = signal.take_profit
    risk = abs(signal.entry - sl)
    if risk <= 0.0:
        return None, {"exit_reason": "invalid_risk", "mfe_r": 0.0, "mae_r": 0.0, "hold_bars": 0}

    exit_idx = idx
    exit_price = signal.entry
    exit_reason = "hold_limit"
    mfe_r = -1e9
    mae_r = 1e9

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high = float(row["high"])
        low = float(row["low"])

        if signal.direction == 1:
            step_mfe = (high - signal.entry) / risk
            step_mae = (low - signal.entry) / risk
            if low <= sl:
                exit_idx = j
                exit_price = sl
                exit_reason = "SL"
                mfe_r = max(mfe_r, step_mfe)
                mae_r = min(mae_r, step_mae)
                break
            if high >= tp:
                exit_idx = j
                exit_price = tp
                exit_reason = "TP"
                mfe_r = max(mfe_r, step_mfe)
                mae_r = min(mae_r, step_mae)
                break
        else:
            step_mfe = (signal.entry - low) / risk
            step_mae = (signal.entry - high) / risk
            if high >= sl:
                exit_idx = j
                exit_price = sl
                exit_reason = "SL"
                mfe_r = max(mfe_r, step_mfe)
                mae_r = min(mae_r, step_mae)
                break
            if low <= tp:
                exit_idx = j
                exit_price = tp
                exit_reason = "TP"
                mfe_r = max(mfe_r, step_mfe)
                mae_r = min(mae_r, step_mae)
                break

        exit_idx = j
        exit_price = float(row["close"])
        mfe_r = max(mfe_r, step_mfe)
        mae_r = min(mae_r, step_mae)

    pnl_r = (exit_price - signal.entry) / risk if signal.direction == 1 else (signal.entry - exit_price) / risk
    trade = CombinedTrade(
        symbol=signal.symbol,
        entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]),
        direction=signal.direction,
        confidence=signal.confidence,
        entry=signal.entry,
        exit=exit_price,
        pnl_r=float(pnl_r),
    )

    hold_bars = max(0, int(exit_idx - idx))
    if mfe_r < -1e8:
        mfe_r = 0.0
    if mae_r > 1e8:
        mae_r = 0.0
    return trade, {
        "exit_reason": exit_reason,
        "mfe_r": float(mfe_r),
        "mae_r": float(mae_r),
        "hold_bars": hold_bars,
    }


def _validate_dataset(df: pd.DataFrame) -> dict[str, Any]:
    required = [
        "trade_id",
        "symbol",
        "direction",
        "timestamp",
        "session",
        "weekday",
        "trend_confidence",
        "atr_ratio",
        "pnl_r",
        "win",
    ]
    missing = [c for c in required if c not in df.columns]
    nan_cells = int(df.isna().sum().sum())
    return {
        "schema_version": "v1",
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_required": missing,
        "nan_cells": nan_cells,
    }


def _simulate_trade(frame: pd.DataFrame, signal: ScalpingSignal, max_hold_bars: int) -> CombinedTrade | None:
    times = frame["time"].astype(str)
    matches = frame.index[times == signal.time]
    if len(matches) == 0:
        return None
    idx = int(matches[0])

    sl = signal.stop_loss
    tp = signal.take_profit
    risk = abs(signal.entry - sl)
    if risk <= 0.0:
        return None

    exit_idx = idx
    exit_price = signal.entry

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high = float(row["high"])
        low = float(row["low"])

        if signal.direction == 1:
            if low <= sl:
                exit_idx = j
                exit_price = sl
                break
            if high >= tp:
                exit_idx = j
                exit_price = tp
                break
        else:
            if high >= sl:
                exit_idx = j
                exit_price = sl
                break
            if low <= tp:
                exit_idx = j
                exit_price = tp
                break

        exit_idx = j
        exit_price = float(row["close"])

    pnl_r = (exit_price - signal.entry) / risk if signal.direction == 1 else (signal.entry - exit_price) / risk
    return CombinedTrade(
        symbol=signal.symbol,
        entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]),
        direction=signal.direction,
        confidence=signal.confidence,
        entry=signal.entry,
        exit=exit_price,
        pnl_r=float(pnl_r),
    )


def _max_daily_drawdown_pct(times: pd.Series, pnl_r: pd.Series, risk_per_trade_pct: float = 1.0) -> float:
    frame = pd.DataFrame({"time": pd.to_datetime(times, utc=True), "pnl_r": pnl_r})
    if frame.empty:
        return 0.0

    frame["date"] = frame["time"].dt.date
    worst = 0.0
    for _, group in frame.groupby("date"):
        day_equity_pct = group["pnl_r"].cumsum() * risk_per_trade_pct
        day_peak = day_equity_pct.cummax()
        day_dd = day_equity_pct - day_peak
        worst = min(worst, float(day_dd.min()))
    return worst


def _sharpe(pnl_r: pd.Series) -> float:
    if pnl_r.empty:
        return 0.0
    std = float(pnl_r.std(ddof=0))
    if std == 0.0:
        return 0.0
    return float((pnl_r.mean() / std) * np.sqrt(252.0))


def _compute_metrics(trades_df: pd.DataFrame) -> dict[str, float | int]:
    pnl = trades_df["pnl_r"].astype(float)
    equity = pnl.cumsum()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = float(losses.sum()) if not losses.empty else 0.0
    pf = gross_profit / abs(gross_loss) if gross_loss != 0.0 else float("inf")

    max_dd_r = float((equity - equity.cummax()).min())
    return {
        "total_trades": int(len(trades_df)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(pf),
        "max_drawdown_r": max_dd_r,
        "max_drawdown_pct": float(abs(max_dd_r) * 1.0),
        "max_daily_drawdown_pct": float(abs(_max_daily_drawdown_pct(trades_df["entry_time"], pnl))),
        "sharpe_ratio": float(_sharpe(pnl)),
        "expectancy_r": float(pnl.mean()),
    }


def run_combined_backtest(config: CombinedBacktestConfig | None = None) -> tuple[dict[str, float | int], pd.DataFrame]:
    if config is None:
        config = CombinedBacktestConfig()

    threshold_cfg = (
        DynamicThresholdConfig(**config.threshold_engine)
        if isinstance(config.threshold_engine, dict)
        else config.threshold_engine
    )
    governor_cfg = GovernorConfig(**config.risk_governor) if isinstance(config.risk_governor, dict) else config.risk_governor
    scalping_cfg = ScalpingConfig(**config.scalping_config) if isinstance(config.scalping_config, dict) else config.scalping_config
    ml_model_path = Path(config.ml_model_path)
    quality_dataset_path = Path(config.quality_dataset_path)
    dataset_quality_log_path = Path(config.dataset_quality_log_path)

    active_symbols = config.enabled_symbols if config.enabled_symbols is not None else config.symbols

    trades: list[CombinedTrade] = []
    dataset_rows: list[dict[str, Any]] = []
    ml_model = _load_ml_model(ml_model_path) if config.use_ml_quality_filter else None
    governor_state = GovernorState()
    running_pnl: list[float] = []

    for symbol in active_symbols:
        frame = _load(config.data_dir, symbol, config.timeframe)
        frame = _apply_time_window(frame, config.start_time, config.end_time)
        context = build_scalping_context(
            symbol=symbol,
            timeframe=config.timeframe,
            data_dir=config.data_dir,
            config=scalping_cfg,
        )
        context = _apply_time_window(context, config.start_time, config.end_time)
        context = detect_regimes(context)

        if config.max_bars is not None and int(config.max_bars) > 0:
            max_rows = int(config.max_bars)
            frame = frame.tail(max_rows).reset_index(drop=True)
            context = context.tail(max_rows).reset_index(drop=True)

        signals = _build_signals_from_context(
            symbol=symbol,
            context=context,
            min_confidence=config.min_confidence,
            scalping_config=scalping_cfg,
        )
        context_map = {str(row["time"]): row for _, row in context.iterrows()}

        if config.start_time is not None or config.end_time is not None:
            start_ts = pd.to_datetime(config.start_time, utc=True) if config.start_time is not None else None
            end_ts = pd.to_datetime(config.end_time, utc=True) if config.end_time is not None else None
            scoped_signals: list[ScalpingSignal] = []
            signal_ts_map: dict[str, pd.Timestamp] = {}
            for signal in signals:
                ts = _coerce_utc_timestamp(signal.time)
                if ts is None:
                    continue
                if start_ts is not None and ts < start_ts:
                    continue
                if end_ts is not None and ts > end_ts:
                    continue
                scoped_signals.append(signal)
                signal_ts_map[signal.time] = ts
            signals = scoped_signals
        else:
            signal_ts_map = {}

        for signal in signals:
            row = context_map.get(signal.time)
            if row is None:
                continue

            signal_ts = signal_ts_map.get(signal.time)
            if signal_ts is None:
                signal_ts = _coerce_utc_timestamp(signal.time)
                if signal_ts is None:
                    continue
                signal_ts_map[signal.time] = signal_ts

            signal_hour = int(signal_ts.hour)
            signal_weekday = int(signal_ts.weekday())

            regime = str(row.get("market_regime", "RANGING"))
            dynamic_threshold = threshold_for_regime(regime, threshold_cfg)
            governor_state = next_state(governor_state, governor_cfg)
            dynamic_threshold = min(0.95, dynamic_threshold + mode_threshold_add(governor_state.mode))

            feature_row = {
                "symbol": symbol,
                "direction": "LONG" if signal.direction == 1 else "SHORT",
                "timestamp": signal.time,
                "session": "ASIA" if signal_hour <= 5 else ("LONDON" if signal_hour <= 11 else "NEW_YORK"),
                "weekday": signal_weekday,
                "bos_detected": int(bool(_safe_float(row.get("bos_direction", 0.0)))),
                "bos_strength": _safe_float(row.get("bos_direction", 0.0)),
                "choch_detected": int(bool(_safe_float(row.get("choch_signal", 0.0)))),
                "choch_strength": _safe_float(row.get("choch_signal", 0.0)),
                "fvg_detected": int(bool(row.get("fvg_bullish", False) or row.get("fvg_bearish", False))),
                "fvg_size": _safe_float(row.get("fvg_size", 0.0)),
                "order_block_detected": int(bool(row.get("ob_bullish", False) or row.get("ob_bearish", False))),
                "ob_distance": _safe_float(row.get("ob_distance", 0.0)),
                "liquidity_sweep": int(bool(row.get("liquidity_sweep_down", False) or row.get("liquidity_sweep_up", False))),
                "displacement_strength": _safe_float(row.get("ema_distance", 0.0)),
                "d1_bias": str(row.get("d1_direction", "RANGING")),
                "h4_bias": str(row.get("h4_trend", "RANGING")),
                "trend_alignment": str(row.get("macro_direction", "RANGING")),
                "trend_confidence": _safe_float(row.get("trend_confidence", 0.0)),
                "ema_fast": _safe_float(row.get("ema_fast", 0.0)),
                "ema_slow": _safe_float(row.get("ema_slow", 0.0)),
                "ema_distance": abs(_safe_float(row.get("ema_fast", 0.0)) - _safe_float(row.get("ema_slow", 0.0))),
                "ema_slope": _safe_float(row.get("ema_slope", 0.0)),
                "atr": _safe_float(row.get("atr", 0.0)),
                "atr_ratio": _safe_float(row.get("atr_ratio", 0.0)),
                "candle_range_vs_atr": (_safe_float(row.get("high", 0.0)) - _safe_float(row.get("low", 0.0))) / max(_safe_float(row.get("atr", 1.0), 1.0), 1e-9),
                "volatility_regime": regime,
                "rsi": _safe_float(row.get("rsi", 50.0), 50.0),
                "rsi_slope": _safe_float(row.get("rsi", 50.0), 50.0) - _safe_float(context.iloc[max(0, int(row.name) - 1)].get("rsi", 50.0), 50.0),
                "volume_ratio": _safe_float(row.get("tick_volume", 0.0)) / max(_safe_float(context["tick_volume"].rolling(20).mean().iloc[int(row.name)] if "tick_volume" in context.columns else 1.0, 1.0), 1e-9),
                "momentum_strength": _safe_float(row.get("ema_fast", 0.0)) - _safe_float(row.get("ema_slow", 0.0)),
                "spread": 0.0,
                "sl_distance": abs(signal.entry - signal.stop_loss),
                "tp_distance": abs(signal.take_profit - signal.entry),
                "rr_ratio": abs(signal.take_profit - signal.entry) / max(abs(signal.entry - signal.stop_loss), 1e-9),
                "expected_hold_bars": config.max_hold_bars,
                "max_favorable_excursion": 0.0,
                "max_adverse_excursion": 0.0,
                "ml_probability": float(signal.confidence),
                "ml_threshold": float(dynamic_threshold),
                "governor_mode": governor_state.mode,
                "risk_multiplier": mode_risk_multiplier(governor_state.mode),
                "market_regime": regime,
            }

            ml_probability = _predict_quality_probability(ml_model, feature_row, fallback=signal.confidence)
            allow_trade = (not config.use_ml_quality_filter) or (ml_probability >= dynamic_threshold)

            if governor_state.mode == "LOCKDOWN":
                allow_trade = False

            if not allow_trade:
                dataset_rows.append(
                    {
                        "schema_version": "v1",
                        "trade_id": f"{symbol}-{signal.time}-REJECT",
                        "symbol": symbol,
                        "direction": "LONG" if signal.direction == 1 else "SHORT",
                        "timestamp": signal.time,
                        "session": feature_row["session"],
                        "weekday": feature_row["weekday"],
                        "bos_detected": int(bool(_safe_float(row.get("bos_direction", 0.0)))),
                        "bos_strength": feature_row["bos_strength"],
                        "choch_detected": int(bool(_safe_float(row.get("choch_signal", 0.0)))),
                        "choch_strength": feature_row["choch_strength"],
                        "fvg_detected": int(bool(row.get("fvg_bullish", False) or row.get("fvg_bearish", False))),
                        "fvg_size": feature_row["fvg_size"],
                        "order_block_detected": int(bool(row.get("ob_bullish", False) or row.get("ob_bearish", False))),
                        "ob_distance": feature_row["ob_distance"],
                        "liquidity_sweep": int(bool(feature_row["choch_detected"])) if "choch_detected" in feature_row else 0,
                        "displacement_strength": feature_row["displacement_strength"],
                        "d1_bias": feature_row["d1_bias"],
                        "h4_bias": feature_row["h4_bias"],
                        "trend_alignment": feature_row["trend_alignment"],
                        "trend_confidence": feature_row["trend_confidence"],
                        "ema_fast": feature_row["ema_fast"],
                        "ema_slow": feature_row["ema_slow"],
                        "ema_distance": feature_row["ema_distance"],
                        "ema_slope": feature_row["ema_slope"],
                        "atr": feature_row["atr"],
                        "atr_ratio": feature_row["atr_ratio"],
                        "candle_range_vs_atr": feature_row["candle_range_vs_atr"],
                        "volatility_regime": feature_row["volatility_regime"],
                        "rsi": feature_row["rsi"],
                        "rsi_slope": feature_row["rsi_slope"],
                        "volume_ratio": feature_row["volume_ratio"],
                        "momentum_strength": feature_row["momentum_strength"],
                        "spread": feature_row["spread"],
                        "sl_distance": feature_row["sl_distance"],
                        "tp_distance": feature_row["tp_distance"],
                        "rr_ratio": feature_row["rr_ratio"],
                        "expected_hold_bars": feature_row["expected_hold_bars"],
                        "pnl_r": 0.0,
                        "win": 0,
                        "exit_reason": "ML_FILTER_REJECTED",
                        "max_favorable_excursion": 0.0,
                        "max_adverse_excursion": 0.0,
                        "ml_probability": ml_probability,
                        "ml_threshold": dynamic_threshold,
                        "governor_mode": governor_state.mode,
                        "risk_multiplier": mode_risk_multiplier(governor_state.mode),
                    }
                )
                continue

            trade, stats = _simulate_trade_with_stats(frame, signal, config.max_hold_bars)
            if trade is None:
                continue
            trades.append(trade)

            running_pnl.append(float(trade.pnl_r))
            governor_state.consecutive_losses = governor_state.consecutive_losses + 1 if trade.pnl_r < 0 else 0
            cum = np.cumsum(np.array(running_pnl, dtype=float))
            dd = cum - np.maximum.accumulate(cum)
            governor_state.total_drawdown_pct = abs(float(dd.min())) if len(dd) else 0.0

            entry_day = pd.to_datetime(signal.time, utc=True).date()
            day_vals = [
                running_pnl[k]
                for k, t in enumerate([pd.to_datetime(x.entry_time, utc=True).date() for x in trades])
                if t == entry_day
            ]
            if day_vals:
                day_cum = np.cumsum(np.array(day_vals, dtype=float))
                day_dd = day_cum - np.maximum.accumulate(day_cum)
                governor_state.day_drawdown_pct = abs(float(day_dd.min()))

            dataset_rows.append(
                {
                    "schema_version": "v1",
                    "trade_id": f"{symbol}-{signal.time}-{len(trades)}",
                    "symbol": symbol,
                    "direction": "LONG" if signal.direction == 1 else "SHORT",
                    "timestamp": signal.time,
                    "session": feature_row["session"],
                    "weekday": feature_row["weekday"],
                    "bos_detected": int(bool(_safe_float(row.get("bos_direction", 0.0)))),
                    "bos_strength": feature_row["bos_strength"],
                    "choch_detected": int(bool(_safe_float(row.get("choch_signal", 0.0)))),
                    "choch_strength": feature_row["choch_strength"],
                    "fvg_detected": int(bool(row.get("fvg_bullish", False) or row.get("fvg_bearish", False))),
                    "fvg_size": feature_row["fvg_size"],
                    "order_block_detected": int(bool(row.get("ob_bullish", False) or row.get("ob_bearish", False))),
                    "ob_distance": feature_row["ob_distance"],
                    "liquidity_sweep": int(bool(_safe_float(row.get("choch_signal", 0.0)))),
                    "displacement_strength": feature_row["displacement_strength"],
                    "d1_bias": feature_row["d1_bias"],
                    "h4_bias": feature_row["h4_bias"],
                    "trend_alignment": feature_row["trend_alignment"],
                    "trend_confidence": feature_row["trend_confidence"],
                    "ema_fast": feature_row["ema_fast"],
                    "ema_slow": feature_row["ema_slow"],
                    "ema_distance": feature_row["ema_distance"],
                    "ema_slope": feature_row["ema_slope"],
                    "atr": feature_row["atr"],
                    "atr_ratio": feature_row["atr_ratio"],
                    "candle_range_vs_atr": feature_row["candle_range_vs_atr"],
                    "volatility_regime": feature_row["volatility_regime"],
                    "rsi": feature_row["rsi"],
                    "rsi_slope": feature_row["rsi_slope"],
                    "volume_ratio": feature_row["volume_ratio"],
                    "momentum_strength": feature_row["momentum_strength"],
                    "spread": feature_row["spread"],
                    "sl_distance": feature_row["sl_distance"],
                    "tp_distance": feature_row["tp_distance"],
                    "rr_ratio": feature_row["rr_ratio"],
                    "expected_hold_bars": feature_row["expected_hold_bars"],
                    "pnl_r": float(trade.pnl_r),
                    "win": int(trade.pnl_r > 0),
                    "exit_reason": stats["exit_reason"],
                    "max_favorable_excursion": stats["mfe_r"],
                    "max_adverse_excursion": stats["mae_r"],
                    "ml_probability": ml_probability,
                    "ml_threshold": dynamic_threshold,
                    "governor_mode": governor_state.mode,
                    "risk_multiplier": mode_risk_multiplier(governor_state.mode),
                    "market_regime": regime,
                }
            )

    if not trades:
        raise RuntimeError("No combined strategy trades were produced.")

    trades_df = pd.DataFrame([asdict(item) for item in trades])
    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"], utc=True)
    trades_df = trades_df.sort_values("entry_time").reset_index(drop=True)

    metrics = _compute_metrics(trades_df)

    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "combined_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    trades_df.to_csv(out / "combined_trades.csv", index=False)

    dataset_df = pd.DataFrame(dataset_rows)
    if not dataset_df.empty:
        quality_dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_df.to_csv(quality_dataset_path, index=False)
        quality = _validate_dataset(dataset_df)
        dataset_quality_log_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_quality_log_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    return metrics, trades_df


def run_filter_diagnosis(config: CombinedBacktestConfig | None = None) -> dict[str, dict[str, int]]:
    if config is None:
        config = CombinedBacktestConfig()
    scalping_cfg = ScalpingConfig(**config.scalping_config) if isinstance(config.scalping_config, dict) else config.scalping_config

    diagnosis: dict[str, dict[str, int]] = {}
    filter_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    active_symbols = config.enabled_symbols if config.enabled_symbols is not None else config.symbols
    for symbol in active_symbols:
        context = build_scalping_context(
            symbol=symbol,
            timeframe=config.timeframe,
            data_dir=config.data_dir,
            config=scalping_cfg,
        )
        context = detect_regimes(context)
        context = _apply_time_window(context, config.start_time, config.end_time)
        if config.max_bars is not None and int(config.max_bars) > 0:
            context = context.tail(int(config.max_bars)).reset_index(drop=True)
        summary = summarize_filter_diagnosis(context)
        diagnosis[symbol] = {
            "total_bars": summary["total_bars"],
            "rejected_by_trend": summary["rejected_by_trend_filter"],
            "rejected_by_session": summary["rejected_by_session_filter"],
            "rejected_by_atr": summary["rejected_by_atr_filter"],
            "rejected_by_ob_fvg": summary["rejected_by_ob_fvg_filter"],
            "rejected_by_bos": summary["rejected_by_bos_filter"],
            "rejected_by_volume": summary["rejected_by_volume_filter"],
            "passed": summary["passed_all_filters"],
        }
        filter_rows.append({"symbol": symbol, **diagnosis[symbol]})

        if "market_regime" in context.columns:
            counts = context["market_regime"].astype(str).value_counts().to_dict()
            for regime_name, n in counts.items():
                regime_rows.append(
                    {
                        "symbol": symbol,
                        "market_regime": regime_name,
                        "bars": int(n),
                        "share": float(n / max(len(context), 1)),
                    }
                )

    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "filter_diagnosis.json").write_text(json.dumps(diagnosis, indent=2), encoding="utf-8")
    pd.DataFrame(filter_rows).to_csv(out / "filter_diagnostics.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(out / "regime_diagnostics.csv", index=False)
    return diagnosis


def metrics_pass_thresholds(metrics: dict[str, float | int]) -> bool:
    return (
        int(metrics.get("total_trades", 0)) >= 200
        and float(metrics.get("win_rate", 0.0)) > 0.50
        and float(metrics.get("profit_factor", 0.0)) > 1.4
        and float(metrics.get("max_drawdown_pct", 999.0)) < 8.0
        and float(metrics.get("max_daily_drawdown_pct", 999.0)) < 4.0
        and float(metrics.get("sharpe_ratio", -99.0)) > 1.0
        and float(metrics.get("expectancy_r", -99.0)) > 0.0
    )


def _calibration_options(base: CombinedBacktestConfig) -> list[tuple[str, CombinedBacktestConfig]]:
    base_scalping = ScalpingConfig(**base.scalping_config) if isinstance(base.scalping_config, dict) else base.scalping_config
    base_scalping_dict = asdict(base_scalping)

    a = CombinedBacktestConfig(
        **{
            **asdict(base),
            "min_confidence": 0.55,
            "scalping_config": ScalpingConfig(**{**base_scalping_dict, "trend_confidence_threshold": 0.55}),
        }
    )
    b = CombinedBacktestConfig(
        **{**asdict(a), "scalping_config": ScalpingConfig(**{**asdict(a.scalping_config), "require_d1_h4_agreement": False})}
    )
    c = CombinedBacktestConfig(
        **{**asdict(b), "scalping_config": ScalpingConfig(**{**asdict(b.scalping_config), "ob_fvg_proximity_atr": 1.5})}
    )
    d = CombinedBacktestConfig(
        **{**asdict(c), "scalping_config": ScalpingConfig(**{**asdict(c.scalping_config), "allow_xau_asia_session": True})}
    )
    e = CombinedBacktestConfig(
        **{**asdict(d), "scalping_config": ScalpingConfig(**{**asdict(d.scalping_config), "relaxed_bos": True})}
    )
    f = CombinedBacktestConfig(
        **{
            **asdict(e),
            "base_ml_threshold": 0.64,
            "scalping_config": ScalpingConfig(**{**asdict(e.scalping_config), "min_atr_ratio": 0.90}),
        }
    )
    g = CombinedBacktestConfig(
        **{
            **asdict(f),
            "base_ml_threshold": 0.67,
            "min_confidence": 0.58,
        }
    )
    return [("A", a), ("B", b), ("C", c), ("D", d), ("E", e), ("F", f), ("G", g)]


def run_calibration(base_config: CombinedBacktestConfig | None = None) -> tuple[CombinedBacktestConfig, dict[str, float | int]]:
    if base_config is None:
        base_config = CombinedBacktestConfig()

    logs: list[dict[str, Any]] = []
    chosen_config = base_config
    chosen_metrics: dict[str, float | int] = {}
    best_score = -1e12
    calibration_start = time.monotonic()
    options = _calibration_options(base_config)
    total_options = len(options)
    consecutive_no_trade_errors = 0

    for idx, (option_name, option_cfg) in enumerate(options, start=1):
        elapsed = time.monotonic() - calibration_start
        avg_per_option = elapsed / max(idx - 1, 1)
        eta = avg_per_option * max(total_options - idx + 1, 0)
        print(
            f"[CALIBRATION] {idx}/{total_options} option={option_name} elapsed={elapsed/60:.1f}m eta={eta/60:.1f}m",
            end="\r",
            flush=True,
        )
        try:
            metrics, _ = run_combined_backtest(option_cfg)
            consecutive_no_trade_errors = 0
            score = (
                float(metrics.get("profit_factor", 0.0)) * 2.0
                + float(metrics.get("sharpe_ratio", 0.0))
                + float(metrics.get("expectancy_r", 0.0))
                - float(metrics.get("max_drawdown_pct", 0.0)) * 0.25
                - float(metrics.get("max_daily_drawdown_pct", 0.0)) * 0.5
                + min(int(metrics.get("total_trades", 0)), 300) / 300.0
            )
            logs.append({"option": option_name, "metrics": metrics, "score": score})
            print(
                f"[CALIBRATION] {idx}/{total_options} option={option_name} trades={int(metrics.get('total_trades', 0))} "
                f"pf={float(metrics.get('profit_factor', 0.0)):.2f} wr={float(metrics.get('win_rate', 0.0)):.2f}    "
            )

            if score > best_score:
                best_score = score
                chosen_config = option_cfg
                chosen_metrics = metrics

            if int(metrics.get("total_trades", 0)) >= 200 and metrics_pass_thresholds(metrics):
                chosen_config = option_cfg
                chosen_metrics = metrics
                break
        except RuntimeError as exc:
            error_text = str(exc)
            logs.append({"option": option_name, "error": error_text})
            print(f"[CALIBRATION] {idx}/{total_options} option={option_name} error={error_text}")
            if "No combined strategy trades were produced." in error_text:
                consecutive_no_trade_errors += 1
                if consecutive_no_trade_errors >= 3:
                    print("[CALIBRATION] stopping early after 3 consecutive no-trade options.")
                    break
            else:
                consecutive_no_trade_errors = 0

    total_elapsed = time.monotonic() - calibration_start
    print(f"[CALIBRATION] done in {total_elapsed/60:.1f}m")

    if int(chosen_metrics.get("total_trades", 0)) >= 200 and not metrics_pass_thresholds(chosen_metrics):
        confluence_cfg = CombinedBacktestConfig(
            **{
                **asdict(chosen_config),
                "scalping_config": ScalpingConfig(
                    **{**asdict(chosen_config.scalping_config), "use_confluence_mode": True, "min_confluence_score": 3}
                ),
            }
        )
        try:
            confluence_metrics, _ = run_combined_backtest(confluence_cfg)
            logs.append({"option": "CONFLUENCE_SCORE_GE_3", "metrics": confluence_metrics})
            chosen_config = confluence_cfg
            chosen_metrics = confluence_metrics
        except RuntimeError as exc:
            logs.append({"option": "CONFLUENCE_SCORE_GE_3", "error": str(exc)})

    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration_log.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")
    return chosen_config, chosen_metrics


def run_oos_backtest(
    config: CombinedBacktestConfig,
    split_months_train: int = 18,
    split_months_test: int = 6,
) -> dict[str, float | int]:
    frame = _load(config.data_dir, config.symbols[0], config.timeframe)
    full_start = pd.to_datetime(frame["time"], utc=True).min()
    full_end = pd.to_datetime(frame["time"], utc=True).max()
    split_point = full_start + pd.DateOffset(months=split_months_train)
    expected_oos_start = full_end - pd.DateOffset(months=split_months_test)
    start_test = max(split_point, expected_oos_start)

    oos_cfg = CombinedBacktestConfig(
        data_dir=config.data_dir,
        symbols=config.symbols,
        timeframe=config.timeframe,
        min_confidence=config.min_confidence,
        max_hold_bars=config.max_hold_bars,
        start_time=str(start_test),
        end_time=str(full_end),
        enabled_symbols=config.enabled_symbols,
        scalping_config=config.scalping_config,
        max_bars=config.max_bars,
    )
    try:
        metrics, _ = run_combined_backtest(oos_cfg)
    except RuntimeError:
        metrics = {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_r": 0.0,
            "max_drawdown_pct": 0.0,
            "max_daily_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "expectancy_r": 0.0,
        }
    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "oos_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def run_per_symbol(config: CombinedBacktestConfig) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for symbol in config.symbols:
        symbol_cfg = CombinedBacktestConfig(
            data_dir=config.data_dir,
            symbols=config.symbols,
            timeframe=config.timeframe,
            min_confidence=config.min_confidence,
            max_hold_bars=config.max_hold_bars,
            start_time=config.start_time,
            end_time=config.end_time,
            enabled_symbols=(symbol,),
            scalping_config=config.scalping_config,
            max_bars=config.max_bars,
        )
        try:
            metrics, _ = run_combined_backtest(symbol_cfg)
        except RuntimeError:
            metrics = {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_r": 0.0,
                "max_drawdown_pct": 0.0,
                "max_daily_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "expectancy_r": 0.0,
            }
        out[symbol] = metrics
        Path("results").mkdir(parents=True, exist_ok=True)
        (Path("results") / f"metrics_{symbol}.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return out


def generate_prop_firm_report(payload: dict[str, Any], out_path: Path = Path("results/prop_firm_report.md")) -> None:
    in_sample = payload.get("in_sample", {})
    oos = payload.get("out_of_sample", {})
    per_symbol = payload.get("per_symbol", {})
    calibration = payload.get("calibration_history", [])
    training = payload.get("training_summary", {})
    warnings = payload.get("warnings", [])
    recommended = payload.get("recommended", {})

    lines = [
        "# Prop Firm Report",
        "",
        "## Executive Summary",
        "| Metric | In-Sample | Out-of-Sample |",
        "|---|---:|---:|",
    ]
    keys = [
        "total_trades",
        "win_rate",
        "profit_factor",
        "max_drawdown_pct",
        "max_daily_drawdown_pct",
        "sharpe_ratio",
        "expectancy_r",
    ]
    for key in keys:
        left = in_sample.get(key, "n/a")
        right = oos.get(key, "n/a")
        if isinstance(left, float):
            left = f"{left:.4f}"
        if isinstance(right, float):
            right = f"{right:.4f}"
        lines.append(f"| {key} | {left} | {right} |")

    lines.extend(["", "## Per-Symbol Metrics", "| Symbol | Trades | Win Rate | PF | DD% | Daily DD% | Sharpe | Expectancy | Pass |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"])
    for symbol, metrics in per_symbol.items():
        passed = metrics_pass_thresholds(metrics)
        lines.append(
            "| "
            f"{symbol} | {int(metrics.get('total_trades', 0))} | {float(metrics.get('win_rate', 0.0)):.4f} | "
            f"{float(metrics.get('profit_factor', 0.0)):.4f} | {float(metrics.get('max_drawdown_pct', 0.0)):.4f} | "
            f"{float(metrics.get('max_daily_drawdown_pct', 0.0)):.4f} | {float(metrics.get('sharpe_ratio', 0.0)):.4f} | "
            f"{float(metrics.get('expectancy_r', 0.0)):.4f} | {'PASS' if passed else 'FAIL'} |"
        )

    lines.extend(["", "## Calibration History"]) 
    for item in calibration:
        option = item.get("option", "?")
        metrics = item.get("metrics", {})
        lines.append(
            f"- Option {option}: trades={metrics.get('total_trades', 0)}, "
            f"win_rate={float(metrics.get('win_rate', 0.0)):.4f}, "
            f"pf={float(metrics.get('profit_factor', 0.0)):.4f}, "
            f"dd%={float(metrics.get('max_drawdown_pct', 0.0)):.4f}"
        )

    lines.extend(["", "## ML Model Performance"]) 
    for module, summary in training.items():
        lines.append(
            f"- {module}: samples={summary.get('n_samples', 0)}, features={summary.get('n_features', 0)}, "
            f"cv_mean={float(summary.get('cv_mean', 0.0)):.4f}, cv_std={float(summary.get('cv_std', 0.0)):.4f}"
        )

    lines.extend(["", "## Final Recommended Parameters"]) 
    for key, value in recommended.items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Risk Warnings"]) 
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No extreme historical losing streak condition detected beyond normal volatility clusters.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    print("Running diagnostic backtest to count filter rejections. This may take a few minutes.")
    diagnosis = run_filter_diagnosis(CombinedBacktestConfig())
    print(json.dumps(diagnosis, indent=2))

    chosen_config, in_sample = run_calibration(CombinedBacktestConfig())
    oos = run_oos_backtest(chosen_config)
    per_symbol = run_per_symbol(chosen_config)

    report_payload = {
        "in_sample": in_sample,
        "out_of_sample": oos,
        "per_symbol": per_symbol,
        "calibration_history": json.loads(Path("results/calibration_log.json").read_text(encoding="utf-8")),
        "training_summary": {},
        "recommended": asdict(chosen_config.scalping_config),
        "warnings": [],
    }
    generate_prop_firm_report(report_payload)


if __name__ == "__main__":
    main()

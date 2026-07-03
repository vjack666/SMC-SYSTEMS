from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

ProgressCB = Callable[[str, int, int, str], None] | None

import numpy as np
import pandas as pd

from smc_successor.agents.orchestrator import AGENT_COLUMNS, AgentOrchestrator
from smc_successor.data import apply_time_window, load_frame
from smc_successor.features import FeatureEngine
from smc_successor.regime import detect_regimes
from smc_successor.risk import (
    DynamicThresholdConfig,
    GovernorConfig,
    GovernorPool,
    GovernorState,
    mode_risk_multiplier,
    mode_threshold_add,
    next_state,
    threshold_for_regime,
)
from smc_successor.signals import ScalpingConfig, ScalpingSignal, build_scalping_context, summarize_filter_diagnosis


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


def _build_signals_from_context(
    symbol: str,
    context: pd.DataFrame,
    min_confidence: float,
) -> list[ScalpingSignal]:
    valid = context[(context["signal_direction"] != 0) & (context["signal_confidence"] >= min_confidence)]

    results: list[ScalpingSignal] = []
    for _, row in valid.iterrows():
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0.0:
            continue

        entry = float(row["close"])
        direction = int(row["signal_direction"])

        structural_sl = row.get("structural_sl")
        if structural_sl is not None and np.isfinite(float(structural_sl)):
            sl = float(structural_sl)
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
        from smc_successor.ml.trainer import load_model as _lm
        model, _metadata = _lm(path)
        return model
    except Exception:
        try:
            import joblib
            return joblib.load(path)
        except (OSError, ValueError, TypeError):
            return None


def _predict_quality_probability(model: Any | None, feature_row: dict[str, Any], fallback: float) -> float:
    try:
        from smc_successor.ml.trainer import predict_proba as _pp
        x = pd.DataFrame([feature_row])
        return _pp(model, x, fallback=fallback)
    except Exception:
        return float(max(0.0, min(1.0, fallback)))


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
        "trade_id", "symbol", "direction", "timestamp", "session",
        "weekday", "trend_confidence", "atr_ratio", "pnl_r", "win",
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


def run_combined_backtest(
    config: CombinedBacktestConfig | None = None,
    progress_cb: ProgressCB = None,
) -> tuple[dict[str, float | int], pd.DataFrame]:
    if config is None:
        config = CombinedBacktestConfig()

    threshold_cfg = (
        DynamicThresholdConfig(**config.threshold_engine)
        if isinstance(config.threshold_engine, dict)
        else config.threshold_engine
    )
    governor_cfg = GovernorConfig(**config.risk_governor) if isinstance(config.risk_governor, dict) else config.risk_governor
    scalping_cfg = ScalpingConfig(**config.scalping_config) if isinstance(config.scalping_config, dict) else config.scalping_config

    active_symbols = config.enabled_symbols if config.enabled_symbols is not None else config.symbols

    trades: list[CombinedTrade] = []
    dataset_rows: list[dict[str, Any]] = []
    ml_model = _load_ml_model(config.ml_model_path) if config.use_ml_quality_filter else None
    governor_pool = GovernorPool(governor_cfg)
    running_pnl: list[float] = []

    feature_engine = FeatureEngine()

    for sym_idx, symbol in enumerate(active_symbols):
        if progress_cb:
            progress_cb("symbol", sym_idx, len(active_symbols), symbol)
        frame = load_frame(config.data_dir, symbol, config.timeframe)
        frame = apply_time_window(frame, config.start_time, config.end_time)
        if progress_cb:
            progress_cb("context", 0, 1, f"{symbol} building scalping context...")
        orchestrator = AgentOrchestrator() if config.use_ml_quality_filter else None
        context = build_scalping_context(
            symbol=symbol,
            timeframe=config.timeframe,
            data_dir=config.data_dir,
            config=scalping_cfg,
            orchestrator=orchestrator,
        )
        context = apply_time_window(context, config.start_time, config.end_time)
        context = detect_regimes(context)
        if progress_cb:
            progress_cb("context", 1, 1, f"{symbol} context ready ({len(context)} bars)")

        if config.max_bars is not None and int(config.max_bars) > 0:
            max_rows = int(config.max_bars)
            frame = frame.tail(max_rows).reset_index(drop=True)
            context = context.tail(max_rows).reset_index(drop=True)

        signals = _build_signals_from_context(
            symbol=symbol,
            context=context,
            min_confidence=config.min_confidence,
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

        total_signals = len(signals)
        for signal_idx, signal in enumerate(signals):
            if progress_cb:
                progress_cb("signals", signal_idx, total_signals, f"{symbol} | trades={len(trades)}")

            row = context_map.get(signal.time)
            if row is None:
                continue

            signal_ts = signal_ts_map.get(signal.time)
            if signal_ts is None:
                signal_ts = _coerce_utc_timestamp(signal.time)
                if signal_ts is None:
                    continue
                signal_ts_map[signal.time] = signal_ts

            regime = str(row.get("market_regime", "RANGING"))
            dynamic_threshold = threshold_for_regime(regime, threshold_cfg)
            current_gov_state = governor_pool.get_state(symbol)
            current_gov_state = governor_pool.next(symbol, current_gov_state)
            dynamic_threshold = min(0.95, dynamic_threshold + mode_threshold_add(current_gov_state.mode))

            core_features = feature_engine.extract_features(context, int(row.name))
            feature_row: dict[str, Any] = {
                **core_features,
                "timestamp": signal.time,
                "sl_distance": abs(signal.entry - signal.stop_loss),
                "tp_distance": abs(signal.take_profit - signal.entry),
                "rr_ratio": abs(signal.take_profit - signal.entry) / max(abs(signal.entry - signal.stop_loss), 1e-9),
                "expected_hold_bars": config.max_hold_bars,
                "ml_probability": float(signal.confidence),
                "ml_threshold": float(dynamic_threshold),
                "governor_mode": current_gov_state.mode,
                "risk_multiplier": mode_risk_multiplier(current_gov_state.mode),
            }
            for agent_col in AGENT_COLUMNS:
                feature_row[agent_col] = row.get(agent_col, None)

            ml_probability = _predict_quality_probability(ml_model, feature_row, fallback=signal.confidence)
            allow_trade = (not config.use_ml_quality_filter) or (ml_probability >= dynamic_threshold)

            if current_gov_state.mode == "LOCKDOWN":
                allow_trade = False

            def _build_dataset_row(
                trade_id: str,
                pnl_r_val: float,
                win_val: int,
                exit_reason_val: str,
                mfe_r_val: float,
                mae_r_val: float,
            ) -> dict[str, Any]:
                row_out: dict[str, Any] = {
                    "schema_version": "v3",
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "timestamp": signal.time,
                }
                for k, v in feature_row.items():
                    if k not in row_out and k != "timestamp":
                        row_out[k] = v
                row_out.update({
                    "pnl_r": pnl_r_val,
                    "win": win_val,
                    "exit_reason": exit_reason_val,
                    "max_favorable_excursion": mfe_r_val,
                    "max_adverse_excursion": mae_r_val,
                    "ml_probability": ml_probability,
                    "ml_threshold": dynamic_threshold,
                    "governor_mode": current_gov_state.mode,
                    "risk_multiplier": mode_risk_multiplier(current_gov_state.mode),
                    "market_regime": regime,
                })
                return row_out

            if not allow_trade:
                dataset_rows.append(_build_dataset_row(
                    trade_id=f"{symbol}-{signal.time}-REJECT",
                    pnl_r_val=0.0,
                    win_val=0,
                    exit_reason_val="ML_FILTER_REJECTED",
                    mfe_r_val=0.0,
                    mae_r_val=0.0,
                ))
                continue

            trade, stats = _simulate_trade_with_stats(frame, signal, config.max_hold_bars)
            if trade is None:
                continue
            trades.append(trade)

            running_pnl.append(float(trade.pnl_r))
            current_gov_state = governor_pool.update_from_trade(symbol, float(trade.pnl_r))

            dataset_rows.append(_build_dataset_row(
                trade_id=f"{symbol}-{signal.time}-{len(trades)}",
                pnl_r_val=float(trade.pnl_r),
                win_val=int(trade.pnl_r > 0),
                exit_reason_val=stats["exit_reason"],
                mfe_r_val=stats["mfe_r"],
                mae_r_val=stats["mae_r"],
            ))

    if not trades:
        raise RuntimeError("No combined strategy trades were produced.")

    trades_df = pd.DataFrame([asdict(item) for item in trades])
    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"], utc=True)
    trades_df = trades_df.sort_values("entry_time").reset_index(drop=True)

    metrics = _compute_metrics(trades_df)

    if dataset_rows:
        dataset_df = pd.DataFrame(dataset_rows)
        dataset_df.to_csv(config.quality_dataset_path, index=False)
        quality_log = {
            "total_rows": len(dataset_df),
            "accepted_trades": int(dataset_df["exit_reason"].ne("ML_FILTER_REJECTED").sum()),
            "rejected_by_ml": int((dataset_df["exit_reason"] == "ML_FILTER_REJECTED").sum()),
            "win_rate_weighted": float(dataset_df["win"].mean()) if "win" in dataset_df.columns else 0.0,
        }
        config.dataset_quality_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config.dataset_quality_log_path, "w") as f:
            json.dump(quality_log, f, indent=2)

    return metrics, trades_df


def run_filter_diagnosis(config: CombinedBacktestConfig | None = None) -> dict[str, dict[str, int]]:
    if config is None:
        config = CombinedBacktestConfig()
    scalping_cfg = ScalpingConfig(**config.scalping_config) if isinstance(config.scalping_config, dict) else config.scalping_config

    diagnosis: dict[str, dict[str, int]] = {}
    active_symbols = config.enabled_symbols if config.enabled_symbols is not None else config.symbols
    for symbol in active_symbols:
        context = build_scalping_context(
            symbol=symbol,
            timeframe=config.timeframe,
            data_dir=config.data_dir,
            config=scalping_cfg,
        )
        context = detect_regimes(context)
        context = apply_time_window(context, config.start_time, config.end_time)
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

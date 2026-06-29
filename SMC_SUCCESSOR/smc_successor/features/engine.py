from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_FEATURES: tuple[str, ...] = (
    "symbol",
    "direction",
    "session",
    "weekday",
    "bos_detected",
    "bos_strength",
    "choch_detected",
    "choch_strength",
    "fvg_detected",
    "fvg_size",
    "fvg_fill_status",
    "fvg_direction",
    "ob_detected",
    "ob_distance",
    "liquidity_sweep",
    "displacement_magnitude",
    "displacement_bullish",
    "displacement_bearish",
    "premium_discount_zone",
    "premium_distance",
    "ote_long_min",
    "ote_short_min",
    "d1_bias",
    "h4_bias",
    "trend_alignment",
    "trend_confidence",
    "ema_fast",
    "ema_slow",
    "ema_distance",
    "ema_slope",
    "atr",
    "atr_ratio",
    "candle_range_vs_atr",
    "volatility_regime",
    "rsi",
    "rsi_slope",
    "volume_ratio",
    "momentum_strength",
    "spread",
    "market_regime",
    "directional_efficiency",
    "range_compression",
)

LABEL_COLS: tuple[str, ...] = (
    "future_return",
    "win",
    "pnl_r",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "exit_reason",
)

LEAKAGE_COLS: tuple[str, ...] = (
    "pnl_r",
    "win",
    "exit_reason",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "future_return",
)


@dataclass
class FeatureConfig:
    features: tuple[str, ...] = DEFAULT_FEATURES
    label_horizon: int = 8
    one_hot_encode: tuple[str, ...] = ("session", "market_regime", "volatility_regime", "d1_bias", "h4_bias", "trend_alignment", "fvg_fill_status", "fvg_direction", "premium_discount_zone")
    drop_leakage: bool = True


def _safe_num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(x):
        return default
    return x


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


class FeatureEngine:
    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config or FeatureConfig()

    def extract_features(self, context: pd.DataFrame, index: int) -> dict[str, Any]:
        if index < 0 or index >= len(context):
            raise IndexError(f"Index {index} out of bounds for context of length {len(context)}")
        row = context.iloc[index]
        feats: dict[str, Any] = {}

        for key in self.config.features:
            val = self._resolve_feature(key, row, context, index)
            feats[key] = val

        return feats

    def _resolve_feature(self, key: str, row: pd.Series, context: pd.DataFrame, index: int) -> Any:
        if key == "symbol":
            return str(row.get("symbol", "UNKNOWN"))
        if key == "direction":
            direction = row.get("signal_direction", 0)
            return "LONG" if _safe_num(direction) == 1 else "SHORT"
        if key == "session":
            hour = self._resolve_hour(row, context, index)
            if hour <= 5:
                return "ASIA"
            if hour <= 11:
                return "LONDON"
            return "NEW_YORK"
        if key == "weekday":
            return self._resolve_weekday(row, context, index)
        if key == "bos_detected":
            return int(_coerce_bool(row.get("bos_direction", 0)))
        if key == "bos_strength":
            return _safe_num(row.get("bos_direction", 0.0))
        if key == "choch_detected":
            return int(_coerce_bool(row.get("choch_signal", 0)))
        if key == "choch_strength":
            return _safe_num(row.get("choch_signal", 0.0))
        if key == "fvg_detected":
            return int(_coerce_bool(row.get("fvg_bullish", False)) or _coerce_bool(row.get("fvg_bearish", False)))
        if key == "fvg_size":
            return _safe_num(row.get("fvg_size", 0.0))
        if key == "ob_detected":
            return int(_coerce_bool(row.get("ob_bullish", False)) or _coerce_bool(row.get("ob_bearish", False)))
        if key == "ob_distance":
            return _safe_num(row.get("ob_distance", 0.0))
        if key == "liquidity_sweep":
            return int(_coerce_bool(row.get("liquidity_sweep_down", False)) or _coerce_bool(row.get("liquidity_sweep_up", False)))
        if key == "displacement_magnitude":
            return _safe_num(row.get("displacement_magnitude", 0.0))
        if key == "displacement_bullish":
            return int(_coerce_bool(row.get("displacement_bullish", False)))
        if key == "displacement_bearish":
            return int(_coerce_bool(row.get("displacement_bearish", False)))
        if key == "fvg_fill_status":
            return str(row.get("fvg_fill_status", "none"))
        if key == "fvg_direction":
            bull = _coerce_bool(row.get("fvg_bullish", False))
            bear = _coerce_bool(row.get("fvg_bearish", False))
            return "BULLISH" if bull else ("BEARISH" if bear else "NONE")
        if key == "premium_discount_zone":
            return str(row.get("premium_discount_zone", "OTE_NONE"))
        if key == "premium_distance":
            return _safe_num(row.get("premium_distance", 0.0))
        if key == "ote_long_min":
            return _safe_num(row.get("ote_long_min", 0.0))
        if key == "ote_short_min":
            return _safe_num(row.get("ote_short_min", 0.0))
        if key == "d1_bias":
            return str(row.get("d1_direction", "RANGING"))
        if key == "h4_bias":
            return str(row.get("h4_trend", "RANGING"))
        if key == "trend_alignment":
            return str(row.get("macro_direction", "RANGING"))
        if key == "trend_confidence":
            return _safe_num(row.get("trend_confidence", 0.0))
        if key == "ema_fast":
            return _safe_num(row.get("ema_fast", 0.0))
        if key == "ema_slow":
            return _safe_num(row.get("ema_slow", 0.0))
        if key == "ema_distance":
            fast = _safe_num(row.get("ema_fast", 0.0))
            slow = _safe_num(row.get("ema_slow", 0.0))
            return abs(fast - slow)
        if key == "ema_slope":
            return _safe_num(row.get("ema_slope", 0.0))
        if key == "atr":
            return _safe_num(row.get("atr", 0.0))
        if key == "atr_ratio":
            return _safe_num(row.get("atr_ratio", 0.0))
        if key == "candle_range_vs_atr":
            high = _safe_num(row.get("high", 0.0))
            low = _safe_num(row.get("low", 0.0))
            atr = max(_safe_num(row.get("atr", 1.0)), 1e-9)
            return (high - low) / atr
        if key == "volatility_regime":
            return str(row.get("market_regime", "RANGING"))
        if key == "rsi":
            return _safe_num(row.get("rsi", 50.0), 50.0)
        if key == "rsi_slope":
            current_rsi = _safe_num(row.get("rsi", 50.0), 50.0)
            if index > 0:
                prev_rsi = _safe_num(context.iloc[index - 1].get("rsi", 50.0), 50.0)
            else:
                prev_rsi = current_rsi
            return current_rsi - prev_rsi
        if key == "volume_ratio":
            tick_vol = _safe_num(row.get("tick_volume", 0.0))
            if "tick_volume" in context.columns:
                avg_vol = _safe_num(context["tick_volume"].rolling(20, min_periods=1).mean().iloc[index])
            else:
                avg_vol = 1.0
            if avg_vol < 1e-9:
                avg_vol = 1.0
            return tick_vol / avg_vol
        if key == "momentum_strength":
            fast = _safe_num(row.get("ema_fast", 0.0))
            slow = _safe_num(row.get("ema_slow", 0.0))
            return fast - slow
        if key == "spread":
            return _safe_num(row.get("spread", 0.0))
        if key == "market_regime":
            return str(row.get("market_regime", "RANGING"))
        if key == "directional_efficiency":
            return _safe_num(row.get("directional_efficiency", 0.0))
        if key == "range_compression":
            return _safe_num(row.get("range_compression", 1.0))
        return _safe_num(row.get(key, 0.0))

    def _resolve_hour(self, row: pd.Series, context: pd.DataFrame, index: int) -> int:
        ts = row.get("time", None)
        if ts is not None:
            try:
                return int(pd.to_datetime(ts, utc=True).hour)
            except (ValueError, TypeError):
                pass
        return 0

    def _resolve_weekday(self, row: pd.Series, context: pd.DataFrame, index: int) -> int:
        ts = row.get("time", None)
        if ts is not None:
            try:
                return int(pd.to_datetime(ts, utc=True).weekday())
            except (ValueError, TypeError):
                pass
        return 0

    def build_training_dataset(self, context: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        n = len(context)
        for i in range(n):
            feats = self.extract_features(context, i)
            future_idx = min(i + self.config.label_horizon, n - 1)
            entry_close = _safe_num(context.iloc[i].get(close_col, 0.0))
            future_close = _safe_num(context.iloc[future_idx].get(close_col, 0.0))
            if entry_close > 1e-9:
                future_return = (future_close - entry_close) / entry_close
            else:
                future_return = 0.0
            feats["future_return"] = future_return
            feats["win"] = int(future_return > 0.0)
            feats["pnl_r"] = _safe_num(context.iloc[i].get("pnl_r", 0.0))
            feats["max_favorable_excursion"] = _safe_num(context.iloc[i].get("max_favorable_excursion", 0.0))
            feats["max_adverse_excursion"] = _safe_num(context.iloc[i].get("max_adverse_excursion", 0.0))
            feats["exit_reason"] = str(context.iloc[i].get("exit_reason", "UNKNOWN"))
            rows.append(feats)

        df = pd.DataFrame(rows)

        for col in self.config.one_hot_encode:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df.drop(columns=[col]), dummies], axis=1)

        if self.config.drop_leakage:
            cols_to_drop = [c for c in LEAKAGE_COLS if c in df.columns]
            df = df.drop(columns=cols_to_drop)

        df = df.fillna(0.0)
        return df

    def build_feature_matrix(self, context: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        n = len(context)
        for i in range(n):
            feats = self.extract_features(context, i)
            rows.append(feats)

        df = pd.DataFrame(rows)

        for col in self.config.one_hot_encode:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df.drop(columns=[col]), dummies], axis=1)

        df = df.fillna(0.0)
        return df

"""Shared ML quality-filter inference for backtest and live/paper trading."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from agents.orchestrator import AGENT_COLUMNS
from features import FeatureEngine
from risk import DynamicThresholdConfig, mode_threshold_add, threshold_for_regime


@dataclass
class QualityFilterConfig:
    enabled: bool = True
    model_path: Path = Path("ml/models/quality_filter.pkl")
    threshold_config: DynamicThresholdConfig | None = None
    max_hold_bars: int = 16
    fallback_probability: float = 0.5


class QualityFilter:
    def __init__(self, config: QualityFilterConfig | None = None) -> None:
        self.config = config or QualityFilterConfig()
        self._model: Any | None = None
        self._feature_engine = FeatureEngine()
        self._threshold_cfg = self.config.threshold_config or DynamicThresholdConfig()
        if self.config.enabled:
            self._model = self._load_model(self.config.model_path)

    @property
    def is_active(self) -> bool:
        return self.config.enabled and self._model is not None

    @classmethod
    def load(cls, model_path: Path | str = Path("ml/models/quality_filter.pkl")) -> QualityFilter:
        return cls(QualityFilterConfig(enabled=True, model_path=Path(model_path)))

    def _load_model(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            from ml.trainer import load_model

            model, _metadata = load_model(path)
            return model
        except Exception:
            try:
                import joblib

                return joblib.load(path)
            except (OSError, ValueError, TypeError):
                return None

    def build_feature_row(
        self,
        context: pd.DataFrame,
        bar_idx: int,
        *,
        timestamp: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        signal_confidence: float,
        governor_mode: str = "NORMAL",
    ) -> dict[str, Any]:
        row = context.iloc[bar_idx]
        core_features = self._feature_engine.extract_features(context, bar_idx)
        regime = str(row.get("market_regime", "RANGING"))
        dynamic_threshold = threshold_for_regime(regime, self._threshold_cfg)
        dynamic_threshold = min(0.95, dynamic_threshold + mode_threshold_add(governor_mode))

        feature_row: dict[str, Any] = {
            **core_features,
            "timestamp": timestamp,
            "sl_distance": abs(entry - stop_loss),
            "tp_distance": abs(take_profit - entry),
            "rr_ratio": abs(take_profit - entry) / max(abs(entry - stop_loss), 1e-9),
            "expected_hold_bars": self.config.max_hold_bars,
            "ml_probability": float(signal_confidence),
            "ml_threshold": float(dynamic_threshold),
            "governor_mode": governor_mode,
        }
        for agent_col in AGENT_COLUMNS:
            feature_row[agent_col] = row.get(agent_col, None)
        return feature_row

    def predict_probability(self, feature_row: dict[str, Any], fallback: float) -> float:
        if self._model is None:
            return float(fallback)
        try:
            from ml.trainer import predict_proba

            x = pd.DataFrame([feature_row])
            return predict_proba(self._model, x, fallback=fallback)
        except Exception:
            return float(max(0.0, min(1.0, fallback)))

    def evaluate_signal(
        self,
        context: pd.DataFrame,
        bar_idx: int,
        *,
        timestamp: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        signal_confidence: float,
        governor_mode: str = "NORMAL",
    ) -> tuple[bool, float, float]:
        if not self.is_active:
            return True, signal_confidence, 0.0

        feature_row = self.build_feature_row(
            context,
            bar_idx,
            timestamp=timestamp,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_confidence=signal_confidence,
            governor_mode=governor_mode,
        )
        threshold = float(feature_row["ml_threshold"])
        probability = self.predict_probability(feature_row, fallback=signal_confidence)
        return probability >= threshold, probability, threshold
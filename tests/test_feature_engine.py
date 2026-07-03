from __future__ import annotations

import pandas as pd
import pytest

from smc_successor.features import DEFAULT_FEATURES, LABEL_COLS, LEAKAGE_COLS, FeatureEngine
from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv as synthetic_ohlcv


@pytest.fixture
def sample_context() -> pd.DataFrame:
    df = synthetic_ohlcv(n_bars=50)
    df["time"] = pd.date_range("2025-01-01", periods=50, freq="15min", tz="UTC")
    df["symbol"] = "EURUSD"
    df["signal_direction"] = 1
    df["bos_direction"] = 0.0
    df["choch_signal"] = 0.0
    df["fvg_bullish"] = False
    df["fvg_bearish"] = False
    df["fvg_size"] = 0.0
    df["ob_bullish"] = False
    df["ob_bearish"] = False
    df["ob_distance"] = 0.0
    df["liquidity_sweep_up"] = False
    df["liquidity_sweep_down"] = False
    df["ema_fast"] = df["close"].ewm(span=8).mean()
    df["ema_slow"] = df["close"].ewm(span=20).mean()
    df["ema_slope"] = df["ema_fast"].diff(5).fillna(0.0)
    df["atr"] = df["close"].rolling(14).std()
    df["atr_ratio"] = df["atr"] / df["close"]
    df["rsi"] = 50.0
    df["d1_direction"] = "BULLISH"
    df["h4_trend"] = "BULLISH"
    df["macro_direction"] = "BULLISH"
    df["trend_confidence"] = 0.8
    df["tick_volume"] = 100
    df["market_regime"] = "RANGING"
    df["directional_efficiency"] = 0.5
    df["range_compression"] = 0.8
    df["spread"] = 0.0001
    return df


class TestFeatureEngine:
    def test_extract_features_returns_all_default_fields(self, sample_context):
        engine = FeatureEngine()
        feats = engine.extract_features(sample_context, 10)
        for key in DEFAULT_FEATURES:
            assert key in feats, f"Missing feature: {key}"
        assert len(feats) >= len(DEFAULT_FEATURES)

    def test_extract_features_correct_values(self, sample_context):
        engine = FeatureEngine()
        feats = engine.extract_features(sample_context, 10)
        assert feats["symbol"] == "EURUSD"
        assert feats["direction"] == "LONG"
        assert feats["bos_detected"] == 0
        assert feats["choch_detected"] == 0
        assert feats["fvg_detected"] == 0
        assert feats["ob_detected"] == 0
        assert feats["d1_bias"] == "BULLISH"
        assert feats["h4_bias"] == "BULLISH"
        assert feats["trend_alignment"] == "BULLISH"
        assert feats["trend_confidence"] == 0.8
        assert feats["spread"] == 0.0001

    def test_extract_features_detected_flags(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "bos_direction"] = 1.5
        ctx.loc[10, "fvg_bullish"] = True
        ctx.loc[10, "ob_bearish"] = True
        engine = FeatureEngine()
        feats = engine.extract_features(ctx, 10)
        assert feats["bos_detected"] == 1
        assert feats["bos_strength"] == 1.5
        assert feats["fvg_detected"] == 1
        assert feats["ob_detected"] == 1

    def test_extract_features_session_detection(self, sample_context):
        engine = FeatureEngine()
        ctx = sample_context.copy()
        asia = pd.Timestamp("2025-01-01 03:00", tz="UTC")
        london = pd.Timestamp("2025-01-01 08:00", tz="UTC")
        ny = pd.Timestamp("2025-01-01 14:00", tz="UTC")
        ctx.loc[0, "time"] = asia
        ctx.loc[1, "time"] = london
        ctx.loc[2, "time"] = ny
        assert engine.extract_features(ctx, 0)["session"] == "ASIA"
        assert engine.extract_features(ctx, 1)["session"] == "LONDON"
        assert engine.extract_features(ctx, 2)["session"] == "NEW_YORK"

    def test_extract_features_short_direction(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "signal_direction"] = -1
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["direction"] == "SHORT"

    def test_extract_features_rsi_slope(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "rsi"] = 60.0
        ctx.loc[9, "rsi"] = 50.0
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["rsi_slope"] == 10.0

    def test_extract_features_rsi_slope_at_boundary(self, sample_context):
        feats = FeatureEngine().extract_features(sample_context, 0)
        assert feats["rsi_slope"] == 0.0

    def test_extract_features_ema_distance(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "ema_fast"] = 1.1050
        ctx.loc[10, "ema_slow"] = 1.1000
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["ema_distance"] == pytest.approx(0.005)

    def test_extract_features_momentum_strength(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "ema_fast"] = 1.1050
        ctx.loc[10, "ema_slow"] = 1.1000
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["momentum_strength"] == pytest.approx(0.005)

    def test_extract_features_volume_ratio(self, sample_context):
        ctx = sample_context.copy()
        ctx["tick_volume"] = 100
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["volume_ratio"] == pytest.approx(1.0)

    def test_extract_features_candle_range_vs_atr(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "high"] = 1.1100
        ctx.loc[10, "low"] = 1.1000
        ctx.loc[10, "atr"] = 0.005
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["candle_range_vs_atr"] == pytest.approx(2.0)

    def test_extract_features_missing_columns_defaults(self, sample_context):
        minimal = pd.DataFrame({"close": [1.0, 1.1, 1.2], "time": pd.date_range("2025-01-01", periods=3, freq="15min", tz="UTC")})
        feats = FeatureEngine().extract_features(minimal, 1)
        for key in DEFAULT_FEATURES:
            assert key in feats, f"Missing feature: {key}"
        assert feats["bos_detected"] == 0
        assert feats["trend_confidence"] == 0.0
        assert feats["volume_ratio"] == 0.0

    def test_extract_features_out_of_bounds_raises(self, sample_context):
        engine = FeatureEngine()
        with pytest.raises(IndexError):
            engine.extract_features(sample_context, 999)

    def test_build_training_dataset_returns_dataframe(self, sample_context):
        engine = FeatureEngine()
        df = engine.build_training_dataset(sample_context)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(sample_context)

    def test_build_training_dataset_leakage_removed(self, sample_context):
        engine = FeatureEngine()
        df = engine.build_training_dataset(sample_context)
        for col in LEAKAGE_COLS:
            assert col not in df.columns, f"Leakage column found: {col}"

    def test_build_training_dataset_has_labels(self, sample_context):
        engine = FeatureEngine(config=None)
        df = engine.build_training_dataset(sample_context)
        assert "future_return" not in df.columns
        assert "win" not in df.columns

    def test_build_training_dataset_one_hot_encoding(self, sample_context):
        engine = FeatureEngine()
        df = engine.build_training_dataset(sample_context)
        oh_cols = [c for c in df.columns if c.startswith("session_") or c.startswith("market_regime_")]
        assert len(oh_cols) >= 1
        assert "session_ASIA" in df.columns or "session_LONDON" in df.columns

    def test_build_feature_matrix_no_labels(self, sample_context):
        engine = FeatureEngine()
        df = engine.build_feature_matrix(sample_context)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(sample_context)
        for col in LEAKAGE_COLS:
            assert col not in df.columns

    def test_build_feature_matrix_one_hot(self, sample_context):
        engine = FeatureEngine()
        df = engine.build_feature_matrix(sample_context)
        assert "session_ASIA" in df.columns or "session_LONDON" in df.columns

    def test_build_feature_matrix_symbol_not_in_context(self, sample_context):
        ctx = sample_context.drop(columns=["symbol"], errors="ignore")
        engine = FeatureEngine()
        feats = engine.extract_features(ctx, 10)
        assert feats["symbol"] == "UNKNOWN"

    def test_config_custom_features(self, sample_context):
        from smc_successor.features.engine import FeatureConfig
        cfg = FeatureConfig(features=("rsi", "atr", "symbol"))
        engine = FeatureEngine(cfg)
        feats = engine.extract_features(sample_context, 10)
        assert set(feats.keys()) == {"rsi", "atr", "symbol"}

    def test_config_disable_one_hot(self, sample_context):
        from smc_successor.features.engine import FeatureConfig
        cfg = FeatureConfig(one_hot_encode=())
        engine = FeatureEngine(cfg)
        df = engine.build_training_dataset(sample_context)
        assert "session" in df.columns
        oh_cols = [c for c in df.columns if c.startswith("session_")]
        assert len(oh_cols) == 0

    def test_extract_features_liquidity_sweep(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "liquidity_sweep_up"] = True
        ctx.loc[10, "liquidity_sweep_down"] = False
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["liquidity_sweep"] == 1

    def test_extract_features_volatility_regime(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "market_regime"] = "HIGH_VOL"
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["volatility_regime"] == "HIGH_VOL"

    def test_extract_features_displacement_magnitude(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "displacement_magnitude"] = 1.75
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["displacement_magnitude"] == pytest.approx(1.75)

    def test_extract_features_displacement_bullish(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "displacement_bullish"] = True
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["displacement_bullish"] == 1

    def test_extract_features_displacement_bearish(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "displacement_bearish"] = True
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["displacement_bearish"] == 1

    def test_extract_features_fvg_fill_status(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "fvg_fill_status"] = "bullish_unfilled"
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["fvg_fill_status"] == "bullish_unfilled"

    def test_extract_features_fvg_direction(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "fvg_bullish"] = True
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["fvg_direction"] == "BULLISH"
        ctx.loc[10, "fvg_bullish"] = False
        ctx.loc[10, "fvg_bearish"] = True
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["fvg_direction"] == "BEARISH"

    def test_extract_features_premium_discount_zone(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "premium_discount_zone"] = "OTE_LONG"
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["premium_discount_zone"] == "OTE_LONG"

    def test_extract_features_premium_distance(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "premium_distance"] = 0.35
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["premium_distance"] == pytest.approx(0.35)

    def test_extract_features_ote_long_min(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "ote_long_min"] = 1.0800
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["ote_long_min"] == pytest.approx(1.0800)

    def test_extract_features_ote_short_min(self, sample_context):
        ctx = sample_context.copy()
        ctx.loc[10, "ote_short_min"] = 1.0900
        feats = FeatureEngine().extract_features(ctx, 10)
        assert feats["ote_short_min"] == pytest.approx(1.0900)

    def test_build_training_dataset_label_horizon(self, sample_context):
        from smc_successor.features.engine import FeatureConfig
        cfg = FeatureConfig(label_horizon=3)
        engine = FeatureEngine(cfg)
        df = engine.build_training_dataset(sample_context)
        assert isinstance(df, pd.DataFrame)

    def test_extract_features_directional_efficiency(self, sample_context):
        ctx = sample_context.copy()
        ctx["directional_efficiency"] = 0.75
        feats = FeatureEngine().extract_features(ctx, 5)
        assert feats["directional_efficiency"] == 0.75

    def test_extract_features_range_compression(self, sample_context):
        ctx = sample_context.copy()
        ctx["range_compression"] = 0.42
        feats = FeatureEngine().extract_features(ctx, 5)
        assert feats["range_compression"] == 0.42

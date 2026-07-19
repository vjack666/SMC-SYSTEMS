"""Legacy detector tests (BOS/CHOCH via detectors.bos/choch).

MOVIDO desde tests/test_signal_pipeline.py el 2026-07-19: tras unificar
BOS/CHOCH en ict_backtest/market_structure (canonico), los detectores
legacy detectors/bos.py + detectors/choch.py fueron eliminados. Estos
tests validaban el contrato del detector legacy y ya no aplican.
"""
import pytest

from detectors import BosConfig, CHOCH_BEARISH, CHOCH_BULLISH, detect_bos, detect_choch, detect_fvg, detect_order_blocks
from fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
from indicators import add_atr, add_ema, add_rsi


class TestDetectors:
    def test_bos_detector_adds_columns(self, synth_frame):
        result = detect_bos(synth_frame)
        assert "bos_direction" in result.columns
        assert "bos_level" in result.columns
        assert "liquidity_sweep_down" in result.columns
        assert "liquidity_sweep_up" in result.columns

    def test_bos_detector_with_config(self, synth_frame):
        cfg = BosConfig(swing_lookback=3, followthrough_bars=5)
        result = detect_bos(synth_frame, cfg)
        assert "bos_direction" in result.columns

    def test_choch_detector_adds_columns(self, synth_frame):
        result = detect_choch(synth_frame)
        assert "choch_signal" in result.columns
        assert set(result["choch_signal"].unique()).issubset({"NONE", CHOCH_BULLISH, CHOCH_BEARISH})

    def test_fvg_detector_adds_columns(self, synth_frame):
        result = detect_fvg(synth_frame)
        assert "fvg_bullish" in result.columns
        assert "fvg_bearish" in result.columns

    def test_ob_detector_adds_columns(self, synth_frame):
        result = detect_order_blocks(synth_frame)
        assert "ob_bullish" in result.columns
        assert "ob_bearish" in result.columns

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import pytest

from paper_trading.models import PaperPosition, PositionSide, PositionStatus, TradeMode
from paper_trading.runner import PaperTradingRunner
from signals.pipeline import ScalpingConfig

CANONICAL_DTYPE = np.dtype([
    ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
    ("close", "f8"), ("tick_volume", "i8"), ("spread", "i8"), ("real_volume", "i8"),
])


def _rates(completed_time: int, high: float = 1.105, low: float = 1.095,
           close: float = 1.100) -> np.ndarray:
    return np.array(
        [(completed_time - 60, 1.100, 1.102, 1.098, 1.101, 100, 0, 0),
         (completed_time, 1.099, high, low, close, 200, 0, 0)],
        dtype=CANONICAL_DTYPE,
    )


@pytest.fixture
def runner(tmp_path):
    return PaperTradingRunner(
        symbols=["EURUSD"],
        state_dir=tmp_path,
        data_dir=tmp_path,
        kill_switch_path=tmp_path / "KILL_SWITCH",
        max_hold_bars=3,
        scalping_config=ScalpingConfig(use_ml_quality_filter=False),
    )


class TestDetectNewCandle:
    def test_first_call_returns_true(self, runner):
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)):
            assert runner._detect_new_candle("EURUSD") is True

    def test_same_candle_returns_false(self, runner):
        runner.last_completed["EURUSD"] = 200
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)):
            assert runner._detect_new_candle("EURUSD") is False

    def test_new_time_returns_true(self, runner):
        runner.last_completed["EURUSD"] = 100
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(300)):
            assert runner._detect_new_candle("EURUSD") is True
            assert runner.last_completed["EURUSD"] == 300

    def test_none_rates_returns_false(self, runner):
        with patch.object(mt5, "copy_rates_from_pos", return_value=None):
            assert runner._detect_new_candle("EURUSD") is False

    def test_fewer_than_two_rates_returns_false(self, runner):
        single = np.array(
            [(200, 1.1, 1.11, 1.09, 1.105, 100, 0, 0)],
            dtype=CANONICAL_DTYPE,
        )
        with patch.object(mt5, "copy_rates_from_pos", return_value=single):
            assert runner._detect_new_candle("EURUSD") is False


class TestCheckPosition:
    def add_long(self, runner, entry=1.1000, sl=1.0950, tp=1.1100):
        pos = PaperPosition(
            symbol="EURUSD", side=PositionSide.LONG, entry_price=entry,
            stop_loss=sl, take_profit=tp, volume=0.1,
            open_time=datetime.now(timezone.utc), signal_confidence=0.8,
        )
        runner.positions["EURUSD"] = pos
        return pos

    def add_short(self, runner, entry=1.1000, sl=1.1050, tp=1.0950):
        pos = PaperPosition(
            symbol="EURUSD", side=PositionSide.SHORT, entry_price=entry,
            stop_loss=sl, take_profit=tp, volume=0.1,
            open_time=datetime.now(timezone.utc), signal_confidence=0.8,
        )
        runner.positions["EURUSD"] = pos
        return pos

    def test_no_position_returns_early(self, runner):
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)):
            runner._check_position("EURUSD")
        assert "EURUSD" not in runner.positions

    def test_long_sl_hit(self, runner):
        pos = self.add_long(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.105, 1.094, 1.100)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_SL
        assert pos.close_price == 1.0950
        assert pos.reason == "SL hit"

    def test_long_tp_hit(self, runner):
        pos = self.add_long(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.111, 1.099, 1.1105)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_TP
        assert pos.close_price == 1.1100
        assert pos.reason == "TP hit"

    def test_long_expiry(self, runner):
        pos = self.add_long(runner)
        pos.open_bar_index = 3
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.104, 1.099, 1.103)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_EXPIRY
        assert pos.close_price == 1.103
        assert pos.reason == "max hold expired"

    def test_long_no_hit_keeps_open(self, runner):
        pos = self.add_long(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.108, 1.096, 1.107)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.OPEN
        assert pos.open_bar_index == 1

    def test_short_sl_hit(self, runner):
        pos = self.add_short(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.106, 1.099, 1.105)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_SL
        assert pos.close_price == 1.1050
        assert pos.reason == "SL hit"

    def test_short_tp_hit(self, runner):
        pos = self.add_short(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.103, 1.094, 1.100)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_TP
        assert pos.close_price == 1.0950
        assert pos.reason == "TP hit"

    def test_short_expiry(self, runner):
        pos = self.add_short(runner)
        pos.open_bar_index = 3
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.102, 1.098, 1.101)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_EXPIRY
        assert pos.close_price == 1.101
        assert pos.reason == "max hold expired"

    def test_short_no_hit_keeps_open(self, runner):
        pos = self.add_short(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.103, 1.096, 1.102)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.OPEN
        assert pos.open_bar_index == 1

    def test_position_not_open_returns_early(self, runner):
        pos = self.add_long(runner)
        pos.status = PositionStatus.CLOSED_SL
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)):
            runner._check_position("EURUSD")
        assert pos.status == PositionStatus.CLOSED_SL

    def test_position_removed_after_close(self, runner):
        self.add_long(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.105, 1.094, 1.100)):
            runner._check_position("EURUSD")
        assert "EURUSD" not in runner.positions

    def test_check_position_pnl_correct(self, runner):
        pos = self.add_long(runner, entry=1.1000, sl=1.0950, tp=1.1100)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.105, 1.094, 1.100)):
            runner._check_position("EURUSD")
        assert pos.pips == pytest.approx(-0.005)
        assert pos.pnl == pytest.approx(-50.0)

    @patch("paper_trading.runner.next_state")
    def test_governor_updated_on_close(self, mock_next, runner):
        mock_next.return_value = runner.governor
        self.add_long(runner)
        with patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200, 1.105, 1.094, 1.100)):
            runner._check_position("EURUSD")
        mock_next.assert_called_once()


class TestProcessSymbol:
    def test_no_new_candle_checks_position(self, runner):
        runner.last_completed["EURUSD"] = 200
        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed") as mock_recon,
            patch.object(runner, "_check_position") as mock_check,
            patch.object(runner, "_refresh_data") as mock_refresh,
        ):
            runner._process_symbol("EURUSD")
            mock_recon.assert_called_once()
            mock_check.assert_called_once_with("EURUSD")
            mock_refresh.assert_not_called()

    def test_governor_lockdown_skips_pipeline(self, runner):
        runner.governor.mode = "LOCKDOWN"
        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed"),
            patch.object(runner, "_check_position") as mock_check,
            patch.object(runner, "_refresh_data") as mock_refresh,
            patch.object(runner, "_open_position") as mock_open,
        ):
            runner._process_symbol("EURUSD")
            mock_refresh.assert_not_called()
            mock_open.assert_not_called()
            mock_check.assert_called_once()

    def test_signal_opens_position(self, runner):
        context = pd.DataFrame([{
            "signal_direction": 1, "signal_confidence": 0.85, "close": 1.1050, "atr": 0.005,
            "open": 1.1040, "high": 1.1060, "low": 1.1030, "volume": 100,
        }])

        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed"),
            patch.object(runner, "_refresh_data"),
            patch("paper_trading.runner.build_scalping_context", return_value=context),
            patch.object(runner, "_open_position") as mock_open,
            patch.object(runner, "_check_position") as mock_check,
        ):
            runner._process_symbol("EURUSD")
            mock_open.assert_called_once()
            mock_check.assert_called_once()

    def test_no_signal_does_not_open(self, runner):
        context = pd.DataFrame([{
            "signal_direction": 0, "signal_confidence": 0.85, "close": 1.1050, "atr": 0.005,
            "open": 1.1040, "high": 1.1060, "low": 1.1030, "volume": 100,
        }])

        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed"),
            patch.object(runner, "_refresh_data"),
            patch("paper_trading.runner.build_scalping_context", return_value=context),
            patch.object(runner, "_open_position") as mock_open,
            patch.object(runner, "_check_position") as mock_check,
        ):
            runner._process_symbol("EURUSD")
            mock_open.assert_not_called()
            mock_check.assert_called_once()

    def test_live_mode_calls_sync_live_position(self, runner):
        runner.mode = TradeMode.LIVE
        runner.last_completed["EURUSD"] = 200
        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed"),
            patch.object(runner, "_sync_live_position") as mock_sync,
            patch.object(runner, "_check_position"),
        ):
            runner._process_symbol("EURUSD")
            mock_sync.assert_called_once_with("EURUSD")

    def test_pipeline_error_still_checks_position(self, runner):
        with (
            patch.object(mt5, "copy_rates_from_pos", return_value=_rates(200)),
            patch.object(runner, "_reconnect_if_needed"),
            patch.object(runner, "_refresh_data"),
            patch("paper_trading.runner.build_scalping_context", side_effect=RuntimeError("boom")),
            patch.object(runner, "_check_position") as mock_check,
        ):
            runner._process_symbol("EURUSD")
            mock_check.assert_called_once()

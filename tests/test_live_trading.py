from __future__ import annotations

from pathlib import Path

import pytest

from paper_trading.models import PaperPosition, PositionSide, PositionStatus, TradeMode


class TestTradeMode:
    def test_paper_value(self):
        assert TradeMode.PAPER.value == "PAPER"

    def test_live_value(self):
        assert TradeMode.LIVE.value == "LIVE"

    def test_enum_members(self):
        assert len(TradeMode) == 2


class TestPaperPositionTicket:
    def test_ticket_defaults_to_none(self):
        pos = PaperPosition(
            symbol="EURUSD",
            side=PositionSide.LONG,
            entry_price=1.10000,
            stop_loss=1.09500,
            take_profit=1.11000,
            volume=0.10,
            open_time=__import__("datetime").datetime.now(),
        )
        assert pos.ticket is None

    def test_ticket_can_be_set(self):
        pos = PaperPosition(
            symbol="EURUSD",
            side=PositionSide.LONG,
            entry_price=1.10000,
            stop_loss=1.09500,
            take_profit=1.11000,
            volume=0.10,
            open_time=__import__("datetime").datetime.now(),
            ticket=123456,
        )
        assert pos.ticket == 123456


class TestConstructorMode:
    def test_default_mode_is_paper(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"])
        assert runner.mode == TradeMode.PAPER

    def test_live_mode_from_init(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"], mode=TradeMode.LIVE)
        assert runner.mode == TradeMode.LIVE

    def test_magic_default(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"])
        assert runner.magic == 20260701

    def test_custom_magic(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"], magic=12345)
        assert runner.magic == 12345

    def test_deviation_default(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"])
        assert runner.deviation == 10

    def test_kill_switch_path_default(self):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"])
        assert runner.kill_switch_path == Path("data/KILL_SWITCH")


class TestKillSwitch:
    def test_kill_switch_not_present(self, tmp_path):
        from paper_trading.runner import PaperTradingRunner

        runner = PaperTradingRunner(symbols=["EURUSD"], kill_switch_path=tmp_path / "KILL_SWITCH")
        assert not runner._check_kill_switch()
        assert runner.running is False

    def test_kill_switch_detected(self, tmp_path):
        from paper_trading.runner import PaperTradingRunner

        ks_path = tmp_path / "KILL_SWITCH"
        ks_path.write_text("")
        runner = PaperTradingRunner(symbols=["EURUSD"], kill_switch_path=ks_path)
        runner.running = True
        assert runner._check_kill_switch()
        assert runner.running is False
        assert not ks_path.exists()

    def test_kill_switch_removes_file(self, tmp_path):
        from paper_trading.runner import PaperTradingRunner

        ks_path = tmp_path / "KILL_SWITCH"
        ks_path.write_text("STOP")
        runner = PaperTradingRunner(symbols=["EURUSD"], kill_switch_path=ks_path)
        runner.running = True
        runner._check_kill_switch()
        assert not ks_path.exists()


class TestGovernorPersistence:
    def test_save_and_load_governor_state(self, tmp_path):
        from paper_trading.persistence import load_governor_state, save_governor_state
        from risk.governor import GovernorState

        state = GovernorState(mode="CAUTION", consecutive_losses=2, day_drawdown_pct=1.5, total_drawdown_pct=2.0)
        path = tmp_path / "governor.json"
        save_governor_state(state, path)
        assert path.exists()

        loaded = load_governor_state(path)
        assert loaded is not None
        assert loaded.mode == "CAUTION"
        assert loaded.consecutive_losses == 2
        assert loaded.day_drawdown_pct == 1.5
        assert loaded.total_drawdown_pct == 2.0

    def test_load_governor_state_nonexistent(self, tmp_path):
        from paper_trading.persistence import load_governor_state

        result = load_governor_state(tmp_path / "nonexistent.json")
        assert result is None

    def test_save_and_load_default_governor(self, tmp_path):
        from paper_trading.persistence import load_governor_state, save_governor_state
        from risk.governor import GovernorState

        state = GovernorState()
        path = tmp_path / "governor.json"
        save_governor_state(state, path)

        loaded = load_governor_state(path)
        assert loaded is not None
        assert loaded.mode == "NORMAL"
        assert loaded.consecutive_losses == 0
        assert loaded.day_drawdown_pct == 0.0
        assert loaded.total_drawdown_pct == 0.0

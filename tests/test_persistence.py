from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from paper_trading.models import PaperPosition, PositionSide, PositionStatus
from paper_trading.persistence import (
    decode_position,
    encode_position,
    load_governor_state,
    load_positions,
    save_governor_state,
    save_positions,
    save_trade_log,
)
from risk.governor import GovernorState


@pytest.fixture
def tmp_path(tmpdir: Path) -> Path:  # type: ignore[no-any-unimported]
    return Path(tmpdir)


def test_encode_position_full():
    pos = PaperPosition(
        symbol="EURUSD",
        side=PositionSide.LONG,
        entry_price=1.10000,
        stop_loss=1.09500,
        take_profit=1.11000,
        volume=0.10,
        open_time=datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc),
        open_bar_index=42,
        close_price=1.10500,
        close_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        status=PositionStatus.CLOSED_TP,
        pnl=50.0,
        pips=50.0,
        reason="take_profit_hit",
        signal_confidence=0.75,
        ticket=1001,
    )
    result = encode_position(pos)
    assert result["symbol"] == "EURUSD"
    assert result["side"] == "LONG"
    assert result["entry_price"] == 1.10000
    assert result["close_price"] == 1.10500
    assert result["status"] == "CLOSED_TP"
    assert result["pnl"] == 50.0
    assert result["ticket"] == 1001
    assert result["close_time"] is not None


def test_encode_position_open():
    pos = PaperPosition(
        symbol="GBPUSD",
        side=PositionSide.SHORT,
        entry_price=1.25000,
        stop_loss=1.25500,
        take_profit=1.24000,
        volume=0.05,
        open_time=datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc),
    )
    result = encode_position(pos)
    assert result["close_price"] is None
    assert result["close_time"] is None
    assert result["status"] == "OPEN"


def test_decode_position():
    data = {
        "symbol": "EURUSD",
        "side": "LONG",
        "entry_price": 1.10000,
        "stop_loss": 1.09500,
        "take_profit": 1.11000,
        "volume": 0.10,
        "open_time": "2024-01-15T08:30:00+00:00",
        "open_bar_index": 42,
        "close_price": 1.10500,
        "close_time": "2024-01-15T12:00:00+00:00",
        "status": "CLOSED_TP",
        "pnl": 50.0,
        "pips": 50.0,
        "reason": "take_profit_hit",
        "signal_confidence": 0.75,
        "ticket": 1001,
    }
    pos = decode_position(data)
    assert pos.symbol == "EURUSD"
    assert pos.side == PositionSide.LONG
    assert pos.entry_price == 1.10000
    assert pos.close_price == 1.10500
    assert pos.status == PositionStatus.CLOSED_TP
    assert pos.ticket == 1001


def test_roundtrip_position():
    pos = PaperPosition(
        symbol="USDJPY",
        side=PositionSide.SHORT,
        entry_price=150.500,
        stop_loss=151.000,
        take_profit=149.500,
        volume=0.20,
        open_time=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
        open_bar_index=10,
        status=PositionStatus.OPEN,
    )
    encoded = encode_position(pos)
    decoded = decode_position(encoded)
    assert decoded.symbol == pos.symbol
    assert decoded.side == pos.side
    assert decoded.entry_price == pos.entry_price
    assert decoded.stop_loss == pos.stop_loss
    assert decoded.take_profit == pos.take_profit
    assert decoded.volume == pos.volume
    assert decoded.open_time == pos.open_time
    assert decoded.open_bar_index == pos.open_bar_index
    assert decoded.status == pos.status


def test_save_and_load_positions(tmp_path: Path):
    path = tmp_path / "positions.json"
    positions = {
        "EURUSD": PaperPosition(
            symbol="EURUSD",
            side=PositionSide.LONG,
            entry_price=1.10000,
            stop_loss=1.09500,
            take_profit=1.11000,
            volume=0.10,
            open_time=datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc),
        ),
    }
    save_positions(positions, path)
    assert path.exists()
    loaded = load_positions(path)
    assert "EURUSD" in loaded
    assert loaded["EURUSD"].symbol == "EURUSD"
    assert loaded["EURUSD"].entry_price == 1.10000


def test_load_positions_missing(tmp_path: Path):
    path = tmp_path / "nonexistent.json"
    result = load_positions(path)
    assert result == {}


def test_save_and_load_empty_positions(tmp_path: Path):
    path = tmp_path / "empty.json"
    save_positions({}, path)
    loaded = load_positions(path)
    assert loaded == {}


def test_save_trade_log(tmp_path: Path):
    path = tmp_path / "trade_log.json"
    trades = [
        {"symbol": "EURUSD", "pnl": 50.0, "time": "2024-01-15T12:00:00"},
        {"symbol": "GBPUSD", "pnl": -20.0, "time": "2024-01-15T14:00:00"},
    ]
    save_trade_log(trades, path)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert len(loaded) == 2
    assert loaded[0]["symbol"] == "EURUSD"


def test_save_trade_log_empty(tmp_path: Path):
    path = tmp_path / "empty_log.json"
    save_trade_log([], path)
    assert not path.exists()


def test_save_and_load_governor_state(tmp_path: Path):
    path = tmp_path / "governor.json"
    state = GovernorState(mode="CAUTION", consecutive_losses=3, day_drawdown_pct=2.5, total_drawdown_pct=5.0)
    save_governor_state(state, path)
    assert path.exists()
    loaded = load_governor_state(path)
    assert loaded is not None
    assert loaded.mode == "CAUTION"
    assert loaded.consecutive_losses == 3
    assert loaded.day_drawdown_pct == 2.5


def test_load_governor_state_missing(tmp_path: Path):
    path = tmp_path / "nonexistent.json"
    result = load_governor_state(path)
    assert result is None


def test_load_governor_state_defaults(tmp_path: Path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({}), encoding="utf-8")
    state = load_governor_state(path)
    assert state is not None
    assert state.mode == "NORMAL"
    assert state.consecutive_losses == 0

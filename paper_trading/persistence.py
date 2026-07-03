from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from paper_trading.models import PaperPosition, PositionSide, PositionStatus


def encode_position(pos: PaperPosition) -> dict[str, Any]:
    return {
        "symbol": pos.symbol,
        "side": pos.side.value,
        "entry_price": pos.entry_price,
        "stop_loss": pos.stop_loss,
        "take_profit": pos.take_profit,
        "volume": pos.volume,
        "open_time": pos.open_time.isoformat(),
        "open_bar_index": pos.open_bar_index,
        "close_price": pos.close_price,
        "close_time": pos.close_time.isoformat() if pos.close_time else None,
        "status": pos.status.value,
        "pnl": pos.pnl,
        "pips": pos.pips,
        "reason": pos.reason,
        "signal_confidence": pos.signal_confidence,
    }


def decode_position(data: dict[str, Any]) -> PaperPosition:
    return PaperPosition(
        symbol=data["symbol"],
        side=PositionSide(data["side"]),
        entry_price=data["entry_price"],
        stop_loss=data["stop_loss"],
        take_profit=data["take_profit"],
        volume=data["volume"],
        open_time=datetime.fromisoformat(data["open_time"]),
        open_bar_index=data.get("open_bar_index", 0),
        close_price=data.get("close_price"),
        close_time=datetime.fromisoformat(data["close_time"]) if data.get("close_time") else None,
        status=PositionStatus(data["status"]),
        pnl=data.get("pnl", 0.0),
        pips=data.get("pips", 0.0),
        reason=data.get("reason", ""),
        signal_confidence=data.get("signal_confidence", 0.0),
    )


def save_positions(positions: dict[str, PaperPosition], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {symbol: encode_position(pos) for symbol, pos in positions.items()}
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_positions(path: Path) -> dict[str, PaperPosition]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {symbol: decode_position(pos) for symbol, pos in data.items()}


def save_trade_log(trades: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not trades:
        return
    path.write_text(json.dumps(trades, indent=2, default=str), encoding="utf-8")

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TradeMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED_TP = "CLOSED_TP"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_EXPIRY = "CLOSED_EXPIRY"
    CLOSED_MANUAL = "CLOSED_MANUAL"


@dataclass
class PaperPosition:
    symbol: str
    side: PositionSide
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    open_time: datetime
    open_bar_index: int = 0
    close_price: Optional[float] = None
    close_time: Optional[datetime] = None
    status: PositionStatus = PositionStatus.OPEN
    pnl: float = 0.0
    pips: float = 0.0
    reason: str = ""
    signal_confidence: float = 0.0
    ticket: Optional[int] = None


@dataclass
class TradeRecord:
    symbol: str
    side: PositionSide
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    volume: float
    open_time: datetime
    close_time: datetime
    status: PositionStatus
    pnl: float
    pips: float
    signal_confidence: float
    reason: str = ""
    exit_bar: int = 0

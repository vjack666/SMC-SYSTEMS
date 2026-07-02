from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Signal — from Python → MT5
# ---------------------------------------------------------------------------


class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE_BUY = "CLOSE_BUY"
    CLOSE_SELL = "CLOSE_SELL"
    MODIFY_SLTP = "MODIFY_SLTP"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class SignalMessage:
    """Trading signal sent from the Python engine to the MT5 EA."""

    signal_id: str
    symbol: str
    action: SignalAction
    order_type: OrderType = OrderType.MARKET
    volume: float | None = None
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""
    magic_number: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "volume": self.volume,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "comment": self.comment,
            "magic_number": self.magic_number,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


# ---------------------------------------------------------------------------
# Trade Result — from MT5 → Python
# ---------------------------------------------------------------------------


class TradeResultCode(Enum):
    OK = 0
    REJECTED = 1
    TIMEOUT = 2
    ERROR = 3
    INSUFFICIENT_MARGIN = 4
    INVALID_SIGNAL = 5
    MARKET_CLOSED = 6


@dataclass
class TradeResult:
    """Result of executing a signal on MT5."""

    signal_id: str
    ticket: int | None
    code: TradeResultCode = TradeResultCode.OK
    message: str = ""
    filled_volume: float | None = None
    fill_price: float | None = None
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        return self.code == TradeResultCode.OK and self.ticket is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "ticket": self.ticket,
            "code": self.code.value,
            "message": self.message,
            "filled_volume": self.filled_volume,
            "fill_price": self.fill_price,
            "commission": self.commission,
            "swap": self.swap,
            "profit": self.profit,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Account Status — from MT5 → Python (periodic)
# ---------------------------------------------------------------------------


@dataclass
class AccountStatus:
    """Snapshot of MT5 account state."""

    account_id: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float | None
    floating_pnl: float | None
    open_positions: int = 0
    server_time: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "margin_free": self.margin_free,
            "margin_level": self.margin_level,
            "floating_pnl": self.floating_pnl,
            "open_positions": self.open_positions,
            "server_time": self.server_time,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Heartbeat — bidirectional health check
# ---------------------------------------------------------------------------


@dataclass
class Heartbeat:
    """Periodic health-check message between Python and MT5."""

    source: str  # "python" | "mt5"
    status: str  # "ALIVE", "DEGRADED", "DOWN"
    uptime_sec: float = 0.0
    last_signal_ms: float | None = None
    last_result_ms: float | None = None
    errors_last_window: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "uptime_sec": self.uptime_sec,
            "last_signal_ms": self.last_signal_ms,
            "last_result_ms": self.last_result_ms,
            "errors_last_window": self.errors_last_window,
            "timestamp": self.timestamp.isoformat(),
        }

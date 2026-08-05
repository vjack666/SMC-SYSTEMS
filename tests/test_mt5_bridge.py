from __future__ import annotations

from integration.mt5_bridge.config import MT5BridgeConfig
from integration.mt5_bridge.orchestrator import MT5BridgeAdapter
from integration.mt5_bridge.schema import (
    OrderType,
    SignalAction,
    SignalMessage,
    TradeResult,
    TradeResultCode,
)


def test_signal_message_to_dict_roundtrip():
    msg = SignalMessage(
        signal_id="abc123",
        symbol="EURUSD",
        action=SignalAction.BUY,
        order_type=OrderType.MARKET,
        volume=0.1,
        stop_loss=1.09,
        take_profit=1.12,
    )
    data = msg.to_dict()
    assert data["signal_id"] == "abc123"
    assert data["symbol"] == "EURUSD"
    assert data["action"] == "BUY"
    assert data["volume"] == 0.1


def test_trade_result_success_property():
    ok = TradeResult(signal_id="s1", ticket=1001, code=TradeResultCode.OK)
    bad = TradeResult(signal_id="s2", ticket=None, code=TradeResultCode.REJECTED)
    assert ok.success is True
    assert bad.success is False


def test_bridge_heartbeat_alive_when_started(tmp_path):
    cfg = MT5BridgeConfig(base_dir=tmp_path, signal_log_dir="signals")
    bridge = MT5BridgeAdapter(cfg)
    assert bridge.heartbeat().status == "DOWN"
    bridge.start()
    try:
        assert bridge.heartbeat().status == "ALIVE"
    finally:
        bridge.stop()
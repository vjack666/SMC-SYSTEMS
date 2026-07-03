from __future__ import annotations

from typing import Any

from harness.contracts import HarnessEvent
from smc_successor.integration.mt5_bridge.orchestrator import MT5BridgeAdapter as Bridge
from smc_successor.integration.mt5_bridge.schema import SignalAction, SignalMessage

BRIDGE = Bridge()
_BRIDGE_STARTED = False


def _ensure_bridge():
    global _BRIDGE_STARTED
    if not _BRIDGE_STARTED:
        BRIDGE.start()
        _BRIDGE_STARTED = True


class MT5BridgeHarnessAdapter:
    """Minimal harness adapter for the MT5 Bridge Module (F5)."""

    name = "mt5_bridge"

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        _ensure_bridge()
        symbol = str(parameters.get("symbol", "EURUSD"))
        action_str = str(parameters.get("action", "BUY"))
        volume = float(parameters.get("volume", 0.01))
        sl = parameters.get("stop_loss")
        tp = parameters.get("take_profit")

        try:
            action = SignalAction(action_str)
        except ValueError:
            return {
                "module": self.name,
                "status": "error",
                "error": f"Invalid action: {action_str}",
            }

        signal = SignalMessage(
            signal_id="harness_test",
            symbol=symbol,
            action=action,
            volume=volume,
            stop_loss=float(sl) if sl is not None else None,
            take_profit=float(tp) if tp is not None else None,
            comment="harness smoke test",
        )

        result = BRIDGE.send_signal(signal)
        hb = BRIDGE.heartbeat()

        return {
            "module": self.name,
            "status": "ok",
            "symbol": symbol,
            "action": action_str,
            "volume": volume,
            "signal_sent": signal.signal_id,
            "trade_result_code": result.code.value,
            "trade_result_message": result.message,
            "heartbeat_status": hb.status,
        }

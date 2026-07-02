from __future__ import annotations

from typing import Any

from backtest.mt5_validation.mt5_backtest_runner import MT5BacktestRunner, SlippageConfig
from harness.contracts import HarnessEvent
from integration.mt5_bridge.schema import SignalAction, SignalMessage, OrderType


class MQL5EAHarnessAdapter:
    """Simulates the MQL5 EA within the harness using the backtest runner.

    Uses file-mode protocol (same as the real EA) to process signals
    and return trade results. Validates the round-trip:
    Python signal → EA parse → execution → result.
    """

    name = "mt5_ea"

    def __init__(self) -> None:
        self._runner = MT5BacktestRunner(SlippageConfig(mode="fixed", fixed_pips=0.5))

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
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
            signal_id="harness_ea_test",
            symbol=symbol,
            action=action,
            order_type=OrderType.MARKET,
            volume=volume,
            stop_loss=float(sl) if sl is not None else None,
            take_profit=float(tp) if tp is not None else None,
            comment="harness ea test",
        )

        results = self._runner.run([signal])
        trade = results[0] if results else None

        if trade is None:
            return {
                "module": self.name,
                "status": "error",
                "error": "No trade result produced",
            }

        return {
            "module": self.name,
            "status": "ok",
            "symbol": trade.symbol,
            "action": trade.action.value,
            "volume": trade.volume,
            "signal_id": trade.signal_id,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "gross_profit": trade.gross_profit,
            "net_profit": trade.net_profit,
            "pips": trade.pips,
            "exit_reason": trade.exit_reason,
            "slippage": trade.slippage,
        }

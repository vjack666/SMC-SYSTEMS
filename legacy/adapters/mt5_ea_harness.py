from __future__ import annotations

from typing import Any

try:
    from legacy.backtest.validation.mt5_backtest_runner import MT5BacktestRunner, SlippageConfig
    from legacy.harness.contracts import HarnessEvent
except ModuleNotFoundError:
    from backtest.validation.mt5_backtest_runner import MT5BacktestRunner, SlippageConfig
    from harness.contracts import HarnessEvent

# Canal de envío a MT5 (integration.mt5_bridge) eliminado: se empieza de 0.
# El adaptador queda desactivado.


class MQL5EAHarnessAdapter:
    """Simula el EA MQL5 dentro del harness. Canal MT5 desactivado."""

    name = "mt5_ea"

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "module": self.name,
            "status": "disabled",
            "error": "canal de envio a MT5 eliminado (empezar de 0)",
        }

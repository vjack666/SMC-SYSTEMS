from __future__ import annotations

from typing import Any

from harness.contracts import HarnessEvent

# Canal de envío a MT5 (integration.mt5_bridge) eliminado: se empieza de 0.
# Este adaptador queda desactivado para no romper el harness por import faltante.


class MT5BridgeHarnessAdapter:
    """Adaptador del canal MT5 (F5) desactivado."""

    name = "mt5_bridge"

    def run(self, events: list[HarnessEvent], parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "module": self.name,
            "status": "disabled",
            "error": "canal de envio a MT5 eliminado (empezar de 0)",
        }

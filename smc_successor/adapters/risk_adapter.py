from __future__ import annotations

from typing import Any

from smc_successor.risk import GovernorConfig, GovernorState, mode_risk_multiplier, mode_threshold_add, next_state


class RiskGovernorAdapter:
    name = "risk_governor"

    def run(self, events: list[Any], parameters: dict[str, Any]) -> dict[str, Any]:
        losses = int(parameters.get("consecutive_losses", 0))
        day_dd = float(parameters.get("day_drawdown_pct", 0.0))
        total_dd = float(parameters.get("total_drawdown_pct", 0.0))

        cfg_dict = parameters.get("config", {})
        cfg = GovernorConfig(**cfg_dict) if cfg_dict else None

        state = GovernorState(
            consecutive_losses=losses,
            day_drawdown_pct=day_dd,
            total_drawdown_pct=total_dd,
        )

        new_state = next_state(state, cfg)
        return {
            "module": self.name,
            "event_names": [],
            "status": "ok",
            "mode": new_state.mode,
            "consecutive_losses": new_state.consecutive_losses,
            "day_drawdown_pct": new_state.day_drawdown_pct,
            "total_drawdown_pct": new_state.total_drawdown_pct,
            "threshold_add": mode_threshold_add(new_state.mode),
            "risk_multiplier": mode_risk_multiplier(new_state.mode),
        }

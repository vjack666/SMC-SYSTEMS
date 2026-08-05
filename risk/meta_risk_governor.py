from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GovernorState:
    mode: str = "NORMAL"
    consecutive_losses: int = 0
    day_drawdown_pct: float = 0.0
    total_drawdown_pct: float = 0.0


@dataclass(frozen=True)
class GovernorConfig:
    caution_after_losses: int = 2
    defensive_after_losses: int = 3
    lockdown_after_losses: int = 5
    caution_day_dd: float = 2.0
    defensive_day_dd: float = 3.0
    lockdown_day_dd: float = 4.0
    caution_total_dd: float = 5.0
    defensive_total_dd: float = 7.0
    lockdown_total_dd: float = 8.0


def next_state(current: GovernorState, cfg: GovernorConfig | None = None) -> GovernorState:
    if cfg is None:
        cfg = GovernorConfig()

    losses = int(current.consecutive_losses)
    day_dd = float(current.day_drawdown_pct)
    total_dd = float(current.total_drawdown_pct)

    mode = "NORMAL"
    if (
        losses >= cfg.lockdown_after_losses
        or day_dd >= cfg.lockdown_day_dd
        or total_dd >= cfg.lockdown_total_dd
    ):
        mode = "LOCKDOWN"
    elif (
        losses >= cfg.defensive_after_losses
        or day_dd >= cfg.defensive_day_dd
        or total_dd >= cfg.defensive_total_dd
    ):
        mode = "DEFENSIVE"
    elif (
        losses >= cfg.caution_after_losses
        or day_dd >= cfg.caution_day_dd
        or total_dd >= cfg.caution_total_dd
    ):
        mode = "CAUTION"

    return GovernorState(
        mode=mode,
        consecutive_losses=losses,
        day_drawdown_pct=day_dd,
        total_drawdown_pct=total_dd,
    )


def mode_threshold_add(mode: str) -> float:
    m = str(mode or "NORMAL").upper()
    if m == "CAUTION":
        return 0.03
    if m == "DEFENSIVE":
        return 0.08
    if m == "LOCKDOWN":
        return 1.00
    return 0.0


def mode_risk_multiplier(mode: str) -> float:
    m = str(mode or "NORMAL").upper()
    if m == "CAUTION":
        return 0.75
    if m == "DEFENSIVE":
        return 0.50
    if m == "LOCKDOWN":
        return 0.0
    return 1.0

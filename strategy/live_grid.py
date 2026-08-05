"""3-layer Bollinger averaging grid for the paper_trading runner.

Replicates the semantics of the verified simulator in signals/paper_sim.py:
- Layers: L1 at signal entry (l1_lot); L2 at entry -/+ step (l2_lot);
  L3 at entry -/+ 2*step (l2_lot). BUY averages down, SELL averages up.
- step = grid_step_pips * PIP (0.0001) by default; optionally a multiple of
  the Bollinger band width (use_band_step).
- Floating PnL sign convention matches paper_sim._layers_pnl:
  BUY: (price - entry) * lot * 100000; SELL: (entry - price) * lot * 100000.
- The whole grid closes when floating pnl >= +profit_limit_usd or
  <= -loss_limit_usd (limits live in risk.governor.GovernorConfig).

Flag-gated: GridConfig.enabled defaults to False, so runner behavior is
unchanged unless explicitly enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

PIP = 0.0001
CONTRACT = 100000.0
MAX_LAYERS = 3


@dataclass
class GridConfig:
    """Configuration of the live grid (defaults = winning 2-year sweep)."""

    enabled: bool = False
    l1_lot: float = 0.30
    l2_lot: float = 0.20
    grid_step_pips: int = 10
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    use_band_step: bool = False
    band_step_mult: float = 1.0


def compute_bollinger(
    closes, period: int = 20, std: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (mid, upper, lower) Bollinger bands as numpy arrays.

    Uses a simple rolling mean/std (ddof=0); the first period-1 values are NaN.
    """
    c = np.asarray(closes, dtype=float)
    n = len(c)
    mid = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = c[i - period + 1 : i + 1]
        m = window.mean()
        s = window.std(ddof=0)
        mid[i] = m
        upper[i] = m + std * s
        lower[i] = m - std * s
    return mid, upper, lower


@dataclass
class GridLayer:
    """One layer of the grid: target price, lot size and opened state."""

    price: float
    lot: float
    opened: bool = False
    ticket: int | None = None


class GridBook:
    """Tracks up to 3 same-direction layers for one symbol.

    side: "BUY" or "SELL". L1 is opened immediately at the signal entry;
    L2/L3 open when a candle range touches their grid level (call
    check_pending each candle with the candle high/low).
    """

    def __init__(self, symbol: str, side: str, entry: float, cfg: GridConfig,
                 step: float | None = None) -> None:
        self.symbol = symbol
        self.side = side
        self.entry = float(entry)
        self.cfg = cfg
        self.step = float(step) if step is not None else cfg.grid_step_pips * PIP
        sign = -1.0 if side == "BUY" else 1.0
        self.layers: list[GridLayer] = [
            GridLayer(price=self.entry, lot=cfg.l1_lot, opened=True),
            GridLayer(price=self.entry + sign * self.step, lot=cfg.l2_lot),
            GridLayer(price=self.entry + sign * 2.0 * self.step, lot=cfg.l2_lot),
        ]
        self.open_bar_index = 0
        self.closed = False
        # Fallback/bookkeeping fields set by the runner.
        self.stop_loss: float = 0.0
        self.take_profit: float = 0.0
        self.confidence: float = 0.0
        self.open_time: datetime | None = None

    @property
    def opened_layers(self) -> list[GridLayer]:
        return [l for l in self.layers if l.opened]

    def check_pending(self, low: float, high: float) -> list[GridLayer]:
        """Open pending layers whose target price falls inside [low, high].

        Returns the layers newly opened this candle (for LIVE order placement).
        Layers must fill in order (L2 before L3), like the reference sim.
        """
        newly: list[GridLayer] = []
        for layer in self.layers:
            if layer.opened:
                continue
            if low <= layer.price <= high:
                layer.opened = True
                newly.append(layer)
            else:
                break
        return newly

    def floating_pnl(self, price: float) -> float:
        """Floating USD PnL over opened layers (matches paper_sim._layers_pnl)."""
        total = 0.0
        for layer in self.opened_layers:
            if self.side == "BUY":
                total += (price - layer.price) * layer.lot * CONTRACT
            else:
                total += (layer.price - price) * layer.lot * CONTRACT
        return total

    def should_close(
        self, price: float, profit_limit_usd: float, loss_limit_usd: float
    ) -> str | None:
        """Return "PROFIT_LIMIT"/"LOSS_LIMIT" if floating pnl hit a limit.

        Limits <= 0.0 disable the corresponding side (governor default 0.0
        = feature off, existing behavior unchanged).
        """
        pnl = self.floating_pnl(price)
        if profit_limit_usd > 0.0 and pnl >= profit_limit_usd:
            return "PROFIT_LIMIT"
        if loss_limit_usd > 0.0 and pnl <= -loss_limit_usd:
            return "LOSS_LIMIT"
        return None

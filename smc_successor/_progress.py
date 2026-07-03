from __future__ import annotations

import time
from typing import Any


class ProgressTracker:
    """Lightweight progress reporter — works with or without tqdm."""

    def __init__(self, total: int, desc: str = "", unit: str = "it", ascii: bool = True) -> None:
        self.total = total
        self.desc = desc
        self.unit = unit
        self.n = 0
        self._start = time.time()
        self._last_print = 0.0
        self._ascii = ascii

    def update(self, n: int = 1) -> None:
        self.n += n
        now = time.time()
        if now - self._last_print < 0.125:
            return
        self._last_print = now
        self._render()

    def set_postfix(self, **kwargs: Any) -> None:
        self._postfix = kwargs

    def close(self) -> None:
        self._render()
        print()

    def _render(self) -> None:
        pct = self.n / self.total if self.total > 0 else 0
        bar_w = 30
        filled = int(bar_w * pct)
        if self._ascii:
            bar = "#" * filled + "." * (bar_w - filled)
        else:
            bar = "█" * filled + "░" * (bar_w - filled)
        elapsed = time.time() - self._start
        rate = self.n / elapsed if elapsed > 0 else 0
        extra = getattr(self, "_postfix", {})
        extra_str = " | " + " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        print(
            f"\r  {self.desc}: |{bar}| {self.n}/{self.total} "
            f"({pct*100:.0f}%) [{elapsed:.0f}s {rate:.0f}{self.unit}/s]{extra_str}",
            end="",
        )

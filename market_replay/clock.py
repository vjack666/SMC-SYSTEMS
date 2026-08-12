"""market_replay/clock.py — Reloj temporal del replay.

ReplayClock expone la secuencia real de instantes: itera las velas del LTF
en orden cronológico y, para cada cierre, dice qué TF superiores ya están
disponibles (closed-only). Es la única autoridad de DISPONIBILIDAD temporal;
no decide nada de trading.

market_replay -> engine (solo TemporalAvailability)
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

import pandas as pd

from market_replay.availability import TemporalAvailability, TF_CHAIN


class ReplayClock:
    """Itera (i, t, htf_snapshot) en orden temporal."""

    def __init__(self, avail: TemporalAvailability):
        self.avail = avail
        self.ltf = avail.ltf
        self._ltf_df = avail.frames.get(self.ltf)
        if self._ltf_df is None or len(self._ltf_df) == 0:
            self._times = []
        else:
            self._times = list(pd.to_datetime(self._ltf_df["time"], utc=True))

    def __iter__(self):
        for i, t in enumerate(self._times):
            yield i, t, self.avail.snapshot(t, include_ltf=False)

    def __len__(self) -> int:
        return len(self._times)

    def available_tfs_at(self, t) -> list[str]:
        """TFs cuya vela ya cerró en t (incluido el LTF)."""
        snap = self.avail.snapshot(t, include_ltf=True)
        return [tf for tf, row in snap.items() if row is not None]

    def assert_no_future_leak(self, t, requested_tf: str) -> None:
        """Garantía anti look-ahead: un TF no puede estar disponible antes de cerrar.

        Levanta AssertionError si se pidiera una vela de ``requested_tf`` que aún
        no cerró respecto a t. Útil en la prueba de destrucción / auditoría.
        """
        if not self.avail.is_available(requested_tf, t):
            raise AssertionError(
                f"look-ahead: {requested_tf} no disponible en {t} (aún no cerró)"
            )

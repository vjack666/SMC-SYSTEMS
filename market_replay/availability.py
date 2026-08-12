"""market_replay/availability.py — Disponibilidad temporal del mercado.

Responsabilidad UNICA de esta capa: decir, para un instante ``t`` dado,
qué velas de cada timeframe YA CERRARON y por tanto son conocidas por el
motor. Nada de lógica SMC: ni BOS, ni sweep, ni POI, ni entradas.

La regla es HTF CLOSED-ONLY (anti look-ahead cross-timeframe): una vela de
un TF superior no está disponible hasta que su barra cerró respecto a ``t``
(time + duration <= t). Esto se delega a ``engine._util.closed_row_at_time``,
que ya vive en el motor y es la fuente canónica de la sincronización temporal.

market_replay -> engine  (dependencia correcta)
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

import pandas as pd

from engine._util import closed_row_at_time

# Duraciones canónicas de la cadena ICT (deben coincidir con los datos en disco).
TF_DURATION = {
    "D1": "1d",
    "H4": "4h",
    "H1": "1h",
    "M15": "15m",
    "M5": "5m",
    "M1": "1m",
}
TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")


def tf_duration(tf: str) -> str:
    """Duración pandas de un timeframe (p.ej. '4h')."""
    return TF_DURATION.get(tf, f"{_minutes_of(tf)}m")


def _minutes_of(tf: str) -> int:
    digits = "".join(ch for ch in tf if ch.isdigit())
    unit = tf[-1:].upper() if tf else "M"
    base = int(digits or 1)
    mult = {"M": 1, "H": 60, "D": 1440}.get(unit, 1)
    return base * mult


class TemporalAvailability:
    """Responde si, al instante ``t`` (cierre de una vela LTF), cada TF superior
    tiene una vela ya cerrada disponible.

    El reloj de replay solo consulta esto; no decide nada de trading.
    """

    def __init__(self, frames: dict[str, pd.DataFrame], ltf: str = "M15"):
        # Solo nos interesan los TF que existan en los datos.
        self.frames = {tf: df for tf, df in frames.items() if tf in TF_DURATION}
        self.ltf = ltf if ltf in self.frames else (next(iter(self.frames)) if self.frames else ltf)

    def available_row(self, tf: str, t) -> pd.Series | None:
        """Fila de ``tf`` ya cerrada al tiempo ``t`` (o None si no hay)."""
        df = self.frames.get(tf)
        if df is None or len(df) == 0:
            return None
        dur = tf_duration(tf)
        try:
            return closed_row_at_time(df, t, dur)
        except TypeError:
            # duration no resoluble: caer a la versión sin duration (cierre simple).
            from engine.plan import _closed_row_at_time

            return _closed_row_at_time(df, t)

    def is_available(self, tf: str, t) -> bool:
        return self.available_row(tf, t) is not None

    def snapshot(self, t, include_ltf: bool = True) -> dict[str, pd.Series | None]:
        """Snapshot closed-only de toda la cadena en ``t``.

        El LTF se incluye tal cual (su propia vela acaba de cerrar en ``t``).
        Los HTF superiores solo si ya cerraron.
        """
        out: dict[str, pd.Series | None] = {}
        for tf in TF_CHAIN:
            if tf not in self.frames:
                continue
            if tf == self.ltf and not include_ltf:
                continue
            out[tf] = self.available_row(tf, t)
        return out

"""market_replay/feed.py — Ingestión incremental de OHLC crudo.

MarketFeed recibe velas UNA a la vez (o en bloque) por timeframe y mantiene,
para cada TF, la ventana de velas ya conocidas. NO contiene lógica de mercado:
solo acumula lo que el reloj le entrega y lo expone como DataFrame.

El motor (engine) es ignorante de este feed: MarketReplay le pasa, en cada
paso, el DataFrame de ventana ya recortado a lo disponible en ``t``.

market_replay -> engine  (ninguna import aquí salvo tipos)
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Columnas canónicas de un OHLC crudo.
OHLC_COLS = ("time", "open", "high", "low", "close")


@dataclass
class FeedCandle:
    """Vela cruda de un TF. Unidad mínima que el reloj empuja al feed."""

    tf: str
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float

    def as_row(self) -> dict:
        return {
            "time": self.time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }


class MarketFeed:
    """Acumulador incremental de velas por TF.

    Uso típico (replay histórico):
        feed = MarketFeed()
        for tf, df in frames.items():
            feed.ingest(tf, df)          # precarga (o se empuja vela a vela)
        # el reloj luego pide window(tf, t)
    """

    def __init__(self, tfs: tuple[str, ...] | None = None):
        self._windows: dict[str, pd.DataFrame] = {}
        self._tfs = list(tfs) if tfs else []

    # ----- ingesta -----------------------------------------------------
    def ingest(self, tf: str, df: pd.DataFrame) -> None:
        """Añade (o reemplaza) el DataFrame completo de un TF."""
        if tf not in self._tfs:
            self._tfs.append(tf)
        df = df.copy()
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
            df = df.sort_values("time").reset_index(drop=True)
        self._windows[tf] = df

    def push(self, candle: FeedCandle) -> None:
        """Empuja UNA vela al feed (modo streaming real)."""
        if candle.tf not in self._tfs:
            self._tfs.append(candle.tf)
        df = self._windows.get(candle.tf, pd.DataFrame(columns=list(OHLC_COLS)))
        df = pd.concat([df, pd.DataFrame([candle.as_row()])], ignore_index=True)
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        df = df.sort_values("time").reset_index(drop=True)
        self._windows[candle.tf] = df

    # ----- consulta ----------------------------------------------------
    def window(self, tf: str, t=None) -> pd.DataFrame:
        """Ventana de ``tf`` conocida hasta ``t`` (inclusive).

        Si ``t`` es None, devuelve todo lo acumulado.
        """
        df = self._windows.get(tf)
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=list(OHLC_COLS))
        if t is None:
            return df.copy()
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        return df.loc[times <= tt].reset_index(drop=True)

    def available_tfs(self) -> list[str]:
        return list(self._tfs)

    def empty(self) -> bool:
        return all(len(df) == 0 for df in self._windows.values())

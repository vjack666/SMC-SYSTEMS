"""market_replay — infraestructura de lectura viva del motor.

Capa permanente que reproduce la DISPONIBILIDAD del mercado en el tiempo y
alimenta DIRECTAMENTE al engine (engine.sequence), registrando la lectura
causal en un EventJournal.

No contiene lógica SMC (BOS/sweep/POI/entradas/scoring/WR/PF/edge). Su único
trabajo es reproducir el flujo temporal del mercado.

Dependencias:
    market_replay -> engine          (consumidor del motor)
    market_replay -> ict_backtest    PROHIBIDO
    engine         -> market_replay  PROHIBIDO (motor ignora el alimentador)
"""

from market_replay.feed import MarketFeed, FeedCandle
from market_replay.availability import TemporalAvailability, TF_CHAIN, tf_duration
from market_replay.clock import ReplayClock
from market_replay.journal import EventJournal, JournalEntry
from market_replay.replay import MarketReplay, ReplayResult
from market_replay.readout import ReadoutFormatter, Readout, KnownFrame, ReadEvent

__all__ = [
    "MarketFeed",
    "FeedCandle",
    "TemporalAvailability",
    "TF_CHAIN",
    "tf_duration",
    "ReplayClock",
    "EventJournal",
    "JournalEntry",
    "MarketReplay",
    "ReplayResult",
    "ReadoutFormatter",
    "Readout",
    "KnownFrame",
    "ReadEvent",
]

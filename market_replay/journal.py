"""market_replay/journal.py — Registro causal vela-a-vela.

EventJournal es la memoria observable de lo que el motor "sabe" en cada
instante. NO calcula nada: solo guarda, en orden temporal, cada evento que
el motor emite (LIQUIDITY -> SWEEP -> DISPLACE -> BOS -> POI -> REFINEMENT ->
RETURN -> CONTRACT) con su parent (anti look-ahead: el parent ya existía).

Responde a: "¿qué sabía el motor en este instante?" consultando por
timestamp / candle / event_id / parent.

market_replay -> engine  (tipos/SequenceState solo para lectura)
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class JournalEntry:
    """Un evento de lectura del motor en un instante concreto."""

    timestamp: str = ""          # cierre de la vela que originó el evento
    timeframe: str = ""          # TF de la vela que se procesó
    candle_index: int = -1       # índice de esa vela en su TF
    event_id: str = ""           # id del evento (sweep_id, bos_id, ...)
    parent_event_id: str = ""    # id del evento padre ya confirmado
    event_type: str = ""         # LIQUIDITY/SWEEP/DISPLACE/BOS/POI/REFINEMENT/RETURN/CONTRACT
    direction: int = 0           # +1/-1/0
    level: float = float("nan")  # nivel relevante (si aplica)
    state: str = ""              # fase de la secuencia en ese instante
    state_snapshot: dict = field(default_factory=dict)  # SequenceState.to_snapshot() en ese instante
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = None if (self.level != self.level) else self.level
        return d


class EventJournal:
    """Append-only, serializable a JSONL. El replay lo llena vela a vela."""

    def __init__(self, path: str | Path | None = None):
        self._entries: list[JournalEntry] = []
        self._path = Path(path) if path else None

    def record(self, entry: JournalEntry) -> None:
        self._entries.append(entry)
        if self._path:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict(), default=str) + "\n")

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def by_timestamp(self, t) -> list[JournalEntry]:
        ts = str(t)
        return [e for e in self._entries if e.timestamp == ts]

    def by_event_id(self, eid: str) -> JournalEntry | None:
        for e in self._entries:
            if e.event_id == eid:
                return e
        return None

    def children_of(self, parent_eid: str) -> list[JournalEntry]:
        return [e for e in self._entries if e.parent_event_id == parent_eid]

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._entries]

    def save(self, path: str | Path) -> None:
        p = Path(path)
        with p.open("w", encoding="utf-8") as fh:
            for e in self._entries:
                fh.write(json.dumps(e.to_dict(), default=str) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "EventJournal":
        j = cls()
        p = Path(path)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    j._entries.append(JournalEntry(**json.loads(line)))
        return j

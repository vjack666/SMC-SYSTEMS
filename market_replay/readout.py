"""market_replay/readout.py — Formateador de LECTURA del motor (sin decisión).

Consumidor puro de `engine.sequence.SequenceState` + snapshot HTF. Su único
trabajo es VOLCAR, en lenguaje legible, qué vio el motor en un instante dado:

    CONOCIDO  -> velas HTF ya cerradas hasta t (disponibilidad temporal)
    LECTURA   -> cadena causal LIQUIDITY -> SWEEP -> DISPLACEMENT -> BOS ->
                 POI -> REFINEMENT -> RETURN -> CONTRACT, resuelta desde
                 state.event_objs (MarketObject[])

NO calcula WR/PF/edge/expectancy. NO evalúa si la señal "ganó". Solo reporta
la lectura causal. Esto es la puerta 6 del roadmap (auditoría de lectura contra
datos reales), no un backtest 2.0.

market_replay -> engine.sequence / engine.market_object  (lectura)
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.market_object import MarketObject


# Orden causal canónico de la formación ICT (igual que replay._STATE_EVENT_FIELDS).
_READOUT_CHAIN = (
    ("liquidity_id", "LIQUIDITY"),
    ("sweep_id", "SWEEP"),
    ("displace_id", "DISPLACEMENT"),
    ("bos_id", "BOS"),
    ("poi_id", "POI"),
    ("refinement_id", "REFINEMENT"),
    ("entry_id", "RETURN"),
    ("contract_id", "CONTRACT"),
)


@dataclass
class KnownFrame:
    """Lo que el motor CONOCÍA en t (snapshot HTF closed-only)."""

    tf: str
    time: str
    high: float
    low: float
    close: float


@dataclass
class ReadEvent:
    """Un eslabón de la LECTURA (un MarketObject resuelto)."""

    order: int
    event_type: str
    object_id: str
    origin_tf: str
    role: str
    direction: int
    zone_high: float
    zone_low: float
    parent_object: str | None
    state: str


@dataclass
class Readout:
    timestamp: str
    ltf: str
    candle_index: int
    known: list = field(default_factory=list)   # KnownFrame[]
    events: list = field(default_factory=list)  # ReadEvent[]
    htf_aligned: bool = True
    htf_reason: str = "ok"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "ltf": self.ltf,
            "candle_index": self.candle_index,
            "known": [vars(k) for k in self.known],
            "events": [vars(e) for e in self.events],
            "htf_aligned": self.htf_aligned,
            "htf_reason": self.htf_reason,
        }


class ReadoutFormatter:
    """Resuelve el estado del motor a un Readout legible (CONOCIDO + LECTURA)."""

    def __init__(self, state_has_objects: bool = True):
        self._use_objs = state_has_objects

    def format(
        self,
        state,
        timestamp: str,
        ltf: str,
        candle_index: int,
        htf_snapshot: dict | None = None,
    ) -> Readout:
        """Construye el Readout desde `state` (SequenceState) y el snapshot HTF.

        `htf_snapshot`: dict tf -> pd.Series (fila ya cerrada) o None.
        """
        known = self._known(state, htf_snapshot)
        events = self._events(state)
        return Readout(
            timestamp=timestamp,
            ltf=ltf,
            candle_index=candle_index,
            known=known,
            events=events,
            htf_aligned=bool(getattr(state, "htf_aligned", True)),
            htf_reason=str(getattr(state, "htf_reason", "ok")),
        )

    # ------------------------------------------------------------------
    def _known(self, state, htf_snapshot) -> list:
        out = []
        if not htf_snapshot:
            return out
        for tf, row in htf_snapshot.items():
            if row is None:
                continue
            out.append(
                KnownFrame(
                    tf=tf,
                    time=str(row.get("time", "")),
                    high=float(row.get("high", float("nan")) or float("nan")),
                    low=float(row.get("low", float("nan")) or float("nan")),
                    close=float(row.get("close", float("nan")) or float("nan")),
                )
            )
        return out

    def _events(self, state) -> list:
        objs = getattr(state, "event_objs", {}) or {}
        events = []
        order = 0
        for fid_field, etype in _READOUT_CHAIN:
            oid = getattr(state, fid_field, "") or ""
            if not oid:
                continue
            mo = objs.get(oid)
            order += 1
            if isinstance(mo, MarketObject):
                events.append(
                    ReadEvent(
                        order=order,
                        event_type=etype,
                        object_id=mo.id,
                        origin_tf=mo.origin_tf,
                        role=str(mo.role.value if hasattr(mo.role, "value") else mo.role),
                        direction=int(mo.direction),
                        zone_high=float(mo.zone_high or float("nan")),
                        zone_low=float(mo.zone_low or float("nan")),
                        parent_object=mo.parent_object,
                        state=str(mo.state.value if hasattr(mo.state, "value") else mo.state),
                    )
                )
            else:
                # Sin MarketObject resuelto: al menos registramos el id.
                events.append(
                    ReadEvent(
                        order=order,
                        event_type=etype,
                        object_id=oid,
                        origin_tf="",
                        role="",
                        direction=int(getattr(state, "direction", 0) or 0),
                        zone_high=float("nan"),
                        zone_low=float("nan"),
                        parent_object="",
                        state="",
                    )
                )
        return events

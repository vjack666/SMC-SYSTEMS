"""market_replay/replay.py — Alimentador de mercado hacia el motor.

MarketReplay NO contiene lógica SMC. Su único trabajo es:
  1. recortar, para cada instante t (cierre de vela LTF), la ventana de OHLC
     conocida (feed + disponibilidad HTF closed-only);
  2. empujar esa ventana al motor (engine.sequence.run_sequence_traced) con
     el estado previo y start_i = última vela ya procesada;
  3. volcar al EventJournal los eventos que el motor decidió en ESTE instante.

El motor recibe SOLO lo disponible en t => lectura causal real (no batch fingido).

market_replay -> engine.sequence    (consumidor)
market_replay -> ict_backtest       PROHIBIDO
engine -> market_replay             PROHIBIDO (motor ignora el alimentador)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from engine.sequence import SequenceConfig, run_sequence_traced, SequenceState
from market_replay.availability import TemporalAvailability, TF_CHAIN
from market_replay.feed import MarketFeed
from market_replay.journal import EventJournal, JournalEntry


# Mapa de campos del SequenceState -> tipo de evento del journal.
_STATE_EVENT_FIELDS = (
    ("liquidity_id", "LIQUIDITY"),
    ("sweep_id", "SWEEP"),
    ("displace_id", "DISPLACE"),
    ("bos_id", "BOS"),
    ("poi_id", "POI"),
    ("refinement_id", "REFINEMENT"),
    ("entry_id", "RETURN"),
    ("contract_id", "CONTRACT"),
)


@dataclass
class ReplayResult:
    journal: EventJournal
    signals: list = field(default_factory=list)
    final_state: SequenceState | None = None
    steps: int = 0


class MarketReplay:
    """Reproduce el mercado como un flujo temporal y alimenta al motor."""

    def __init__(
        self,
        feed: MarketFeed,
        ltf: str = "M15",
        cfg: SequenceConfig | None = None,
        journal_path: str | None = None,
    ):
        self.feed = feed
        self.ltf = ltf
        self.cfg = cfg or SequenceConfig()
        self.avail = TemporalAvailability({tf: feed.window(tf) for tf in feed.available_tfs()}, ltf)
        self.journal = EventJournal(journal_path)

    # ------------------------------------------------------------------
    def _htf_ctx_fn(self, t):
        """Contexto HTF closed-only en t, delegado a la disponibilidad.

        Devuelve un dict plano mínimo (igual contrato que el est_htf_fn del
        backtest): solo exponer las filas ya cerradas. El motor lo consume
        para su lectura top-down; aquí NO decidimos nada.
        """
        snap = self.avail.snapshot(t, include_ltf=False)
        out: dict = {}
        for tf, row in snap.items():
            if row is None:
                continue
            out[tf] = {
                "trend": str(row.get("trend", "RANGING")),
                "high": float(row.get("high", float("nan"))),
                "low": float(row.get("low", float("nan"))),
                "close": float(row.get("close", float("nan"))),
            }
        return out

    # ------------------------------------------------------------------
    def run(self) -> ReplayResult:
        """Corre vela a vela sobre el LTF.

        En cada paso i (cierre de la vela LTF i):
          - recorta la ventana LTF a [0..i] (solo velas cerradas <= t);
          - snapshot HTF closed-only en t;
          - llama al motor con start_i=i-1 y el estado previo => procesa SOLO i;
          - registra en el journal los eventos nuevos del state.
        """
        ltf_df_full = self.feed.window(self.ltf)
        if len(ltf_df_full) == 0:
            return ReplayResult(journal=self.journal, final_state=None, steps=0)

        state = SequenceState()
        prev_ids: set[str] = set()
        all_signals: list = []
        steps = 0

        for i in range(1, len(ltf_df_full)):
            t = ltf_df_full.iloc[i]["time"]
            # Ventana disponible EN ESTE instante (anti look-ahead).
            win = ltf_df_full.iloc[: i + 1].reset_index(drop=True)

            signals, _phase, _exp, state = run_sequence_traced(
                win,
                self._htf_ctx_fn,
                self.cfg,
                ltf_tf=self.ltf,
                initial_state=state,
                start_i=i - 1,
            )
            all_signals.extend(signals)
            self._record_events(state, t, self.ltf, i, prev_ids)
            prev_ids = {fid for fid, _ in _state_event_pairs(state)}
            steps += 1

        return ReplayResult(journal=self.journal, signals=all_signals, final_state=state, steps=steps)

    # ------------------------------------------------------------------
    def _record_events(self, state: SequenceState, t, tf: str, i: int, prev_ids: set[str]) -> None:
        """Registra en el journal los event_ids que el motor fijó EN este paso."""
        for fid, etype in _state_event_pairs(state):
            if not fid or fid in prev_ids:
                continue
            parent = _parent_of(state, fid)
            self.journal.record(
                JournalEntry(
                    timestamp=str(pd.to_datetime(t, utc=True)),
                    timeframe=tf,
                    candle_index=i,
                    event_id=fid,
                    parent_event_id=parent,
                    event_type=etype,
                    direction=int(getattr(state, "direction", 0) or 0),
                    level=float(getattr(state, "bos_level", float("nan")) or float("nan")),
                    state=str(getattr(state, "phase", "")),
                )
            )


def _state_event_pairs(state: SequenceState):
    pairs = []
    for field_name, etype in _STATE_EVENT_FIELDS:
        val = getattr(state, field_name, "")
        if val:
            pairs.append((str(val), etype))
    return pairs


def _parent_of(state: SequenceState, eid: str) -> str:
    """Devuelve el id del evento padre en la cadena causal.

    Orden causal: LIQUIDITY <- SWEEP <- DISPLACE <- BOS <- POI <-
    REFINEMENT <- RETURN <- CONTRACT. El parent es el evento inmediatamente
    anterior que ya esté presente en el state.
    """
    order = [f for f, _ in _STATE_EVENT_FIELDS]
    present = {getattr(state, f, ""): True for f in order}
    target = None
    for f in order:
        val = getattr(state, f, "")
        if val == eid:
            break
        if val:
            target = str(val)
    return target or ""

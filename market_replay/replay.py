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

from engine.sequence import SequenceConfig, run_sequence_traced, SequenceState, _candle_objects
# FIX frontera (2026-08-13, Consejo autorizado): MarketReplay REUTILIZA las
# autoridades de contexto del engine en lugar de entregar un dict plano
# degradado. NO se implementa logica SMC aqui (prohibido por SDD_SEPARACION).
from engine.multitf_context import build_multitf_context
from engine.poi_anchor import make_htf_poi_fn
from engine.htf_pd_index import HtfPdIndex
from engine.market_structure import detect_market_structure
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
        *,
        htf: str | None = None,
    ):
        self.feed = feed
        self.ltf = ltf
        self.htf = htf
        self.cfg = cfg or SequenceConfig()
        self.avail = TemporalAvailability({tf: feed.window(tf) for tf in feed.available_tfs()}, ltf)
        self.journal = EventJournal(journal_path)

    # ------------------------------------------------------------------
    def _htf_ctx_fn(self, i: int):
        """Contexto HTF closed-only en t, REUTILIZANDO las autoridades del engine.

        FIX frontera (2026-08-13, Consejo autorizado): en lugar de entregar un
        dict plano degradado {trend,h,low,close} con trend=RANGING forzado,
        delegamos en build_multitf_context del engine, que calcula el bias
        top-down real (D1->H4->H1) y pd_zones via build_context_stack. El motor
        recibe el MISMO contrato que via backtest canonico (canonical.est_htf_ctx_fn).
        NO se implementa logica SMC aqui: solo se orquesta la autoridad existente.
        """
        ltf_df = getattr(self, "_ltf_df", None)
        t = ltf_df.iloc[i]["time"] if ltf_df is not None else None
        if t is None:
            return {}
        # ms con detect_market_structure ya aplicado (autoridad del engine,
        # igual que el backtest canonico en canonical.py:187). Construido
        # UNA vez en run(), no por vela.
        ms = getattr(self, "_ms_struct", None)
        if ms is None:
            return {}
        # anchored_pd_zones lo aporta el engine; pasamos None para no duplicar
        # logica de replay (la autoridad vive en engine.poi_anchor).
        return build_multitf_context(ms, t, tfs=tuple(ms.keys()), anchored_pd_zones=None)

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
        self._ltf_df = ltf_df_full  # expuesto para _htf_ctx_fn (lee t por indice)
        if len(ltf_df_full) == 0:
            return ReplayResult(journal=self.journal, final_state=None, steps=0)

        # FIX frontera (2026-08-13, Consejo autorizado): REUTILIZAR las autoridades
        # de contexto del engine en lugar de entregar un contexto degradado.
        # detect_market_structure / build_multitf_context / make_htf_poi_fn /
        # HtfPdIndex ya viven en engine/; MarketReplay solo los ORQUESTA (no los
        # reimplementa). El backtest canonico hace exactamente esto (canonical.py
        # :187-208). Cero logica SMC nueva en replay.
        # ms con estructura calculada UNA vez (fuera del loop, igual que backtest).
        self._ms_struct = {
            tf: detect_market_structure(df) for tf, df in self.avail.frames.items()
        }
        # La secuencia necesita saber qué capa del MultiTFContext representa
        # el sesgo HTF. El backtest EURUSD usa H4; en feeds reducidos sin H4
        # conservamos el camino legacy sin capa HTF seleccionable.
        replay_htf = self.htf
        if replay_htf is None and "H4" in self._ms_struct:
            replay_htf = "H4"
        if replay_htf is None:
            replay_htf = next(
                (tf for tf in ("D1", "H1") if tf in self._ms_struct),
                None,
            )
        _htf_frames = {tf: self._ms_struct[tf] for tf in ("D1", "H4", "H1") if tf in self._ms_struct}
        htf_poi_fn = make_htf_poi_fn(ltf_df_full, _htf_frames) if _htf_frames else None
        htf_pd_index = None
        if _htf_frames:
            htf_pd_index = HtfPdIndex(_htf_frames).build_ltf_map(ltf_df_full)

        # M2-bis (2026-08-12): preconvertir la lista de objetos LTF UNA sola vez.
        # Antes, cada paso recortaba el DataFrame y el motor reconstruia los
        # MarketObject desde cero (O(n) por vela => O(n^2) total). Ahora pasamos
        # una sublista por referencia (slice O(1)) y copy_objs=False en el motor,
        # que SOLO LEE objs por indice <= i (FASE 0: sin mutacion). Equivalencia
        # estructural vela-a-vela demostrada en tests/test_sequence_copy_equivalence.py.
        # El motor de secuencia consume campos estructurales del LTF
        # (bos_dir/choch_dir, entre otros) desde MarketObject.meta. El feed
        # conserva OHLC crudo, pero `_ms_struct` ya contiene la estructura
        # calculada por la autoridad del engine. Si envolvemos el OHLC crudo,
        # `_has_bos` no ve los eventos LTF y el replay queda en 0 setups aunque
        # el contexto HTF sea correcto.
        ltf_struct_full = self._ms_struct.get(self.ltf, ltf_df_full)
        objs_full = _candle_objects(ltf_struct_full, self.ltf)

        state = SequenceState()
        prev_ids: set[str] = set()
        all_signals: list = []
        steps = 0

        for i in range(1, len(ltf_df_full)):
            t = ltf_df_full.iloc[i]["time"]
            # Ventana disponible EN ESTE instante (anti look-ahead): sublista por
            # referencia, O(1), sin reconversion ni copia.
            win = objs_full[: i + 1]

            signals, _phase, _exp, state = run_sequence_traced(
                win,
                None,  # est_htf_fn legacy: no usamos el path plano
                self.cfg,
                ltf_tf=self.ltf,
                initial_state=state,
                start_i=i - 1,
                copy_objs=False,
                est_htf_ctx_fn=self._htf_ctx_fn,
                htf_poi_fn=htf_poi_fn,
                htf_pd_index=htf_pd_index,
                htf=replay_htf,
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
                    state_snapshot=state.to_snapshot(),
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

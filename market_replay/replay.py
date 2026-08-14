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
from engine.multitf_context import build_multitf_context, extract_htf_layer, MultiTFContext
from engine.poi_anchor import make_htf_poi_fn
from engine.htf_pd_index import HtfPdIndex
from engine.market_structure import detect_market_structure
from engine._util import tf_duration
from market_replay.availability import TemporalAvailability, TF_CHAIN
from market_replay.feed import MarketFeed
from market_replay.journal import EventJournal, JournalEntry

import time as _time
import psutil as _psutil

# Log de avances: cada N velas se imprime estado del replay (observabilidad).
LOG_EVERY = 50


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
        """Contexto HTF closed-only en t[i], O(1) via array precomputado.

        SOLUCION A (rendimiento, 2026-08-14): el contexto HTF ya NO se
        recomputa por vela (era O(n^2): build_multitf_context es O(n) por
        llamada y se invocaba n veces dentro del loop de run_sequence_traced).
        En run() precomputamos, UNA sola vez y de forma incremental, el indice
        de la vela HTF cerrada <= t[i] para cada TF (O(n) total). Aqui solo
        hacemos lookup O(1) y reconstruimos el MultiTFContext hasta i,
        preservando causalidad (closed-only, sin mirar futuro).
        """
        arr = getattr(self, "_htf_closed_idx", None)
        if arr is None:
            return {}
        ctx = {}
        for tf, idx_by_i in arr.items():
            ji = idx_by_i[i]
            if ji is None:
                continue
            ctx[tf] = self._ms_struct[tf].iloc[ji].to_dict()
        return extract_htf_layer(MultiTFContext(ctx), self.htf) if self.htf else ctx

    # ------------------------------------------------------------------
    def _precompute_htf_index(self, ltf_df_full: pd.DataFrame) -> None:
        """Precomputa, O(n) total, el indice HTF cerrado <= t[i] por vela LTF.

        Barrido a dos punteros (no usa closed_row_at_time, que es O(n) ciego):
        como t[i] crece monotonicamente, el indice HTF valido solo avanza.
        Costo total O(n_ltf + n_htf), O(1) amortizado por vela. Esto elimina
        el O(n^2) que existia al recomputar build_multitf_context por vela.
        """
        self._htf_closed_idx = {}
        for tf in ("D1", "H4", "H1"):
            if tf not in self._ms_struct:
                continue
            htf_df = self._ms_struct[tf]
            dur = tf_duration(tf)
            htimes = pd.to_datetime(htf_df["time"], utc=True, errors="coerce")
            ltimes = pd.to_datetime(ltf_df_full["time"], utc=True, errors="coerce")
            n_ltf = len(ltf_df_full)
            n_htf = len(htf_df)
            idx_by_i: list = [None] * n_ltf
            ji = -1
            for i in range(n_ltf):
                t = ltimes.iloc[i]
                if pd.isna(t):
                    continue
                cutoff = t - pd.Timedelta(dur)
                # Avanza el puntero HTF mientras la vela ji+1 haya CERRADO (<= cutoff).
                while ji + 1 < n_htf and not pd.isna(htimes.iloc[ji + 1]) and htimes.iloc[ji + 1] <= cutoff:
                    ji += 1
                idx_by_i[i] = ji if ji >= 0 else None
            self._htf_closed_idx[tf] = idx_by_i

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

        # SOLUCION A (rendimiento, 2026-08-14): precomputar indices HTF cerrados
        # UNA vez (O(n) total) antes del loop, para que _htf_ctx_fn sea O(1).
        self._precompute_htf_index(ltf_df_full)

        state = SequenceState()
        prev_ids: set[str] = set()
        all_signals: list = []
        steps = 0
        _t0 = _time.time()
        _proc = _psutil.Process()

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

            # LOG DE AVANCES (observabilidad): cada LOG_EVERY velas.
            if i % LOG_EVERY == 0:
                _bias = "?"
                _arr = getattr(self, "_htf_closed_idx", {})
                if "H4" in _arr and _arr["H4"][i] is not None:
                    _row = self._ms_struct["H4"].iloc[_arr["H4"][i]]
                    _bias = str(_row.get("trend", "?")).replace("RANGING", "R")
                _mem = _proc.memory_info().rss / (1024 * 1024)
                _cpu = _proc.cpu_percent()
                _el = _time.time() - _t0
                print(
                    f"[REPLAY {self.ltf}] vela {i}/{len(ltf_df_full)-1} "
                    f"biasH4={_bias} fase={getattr(state,'phase','?')} "
                    f"setups={len(all_signals)} "
                    f"{_el:.1f}s mem={_mem:.0f}MB cpu={_cpu:.0f}%",
                    flush=True,
                )

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

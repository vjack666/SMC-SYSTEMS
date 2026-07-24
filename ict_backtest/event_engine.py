"""ict_backtest/event_engine.py — Fase E (R10.C): motor canonico semantico.

Reemplaza el recorrido por timer de `run_sequence`. Las decisiones NACEN del
significado del mercado (eventos + estados + grafo + narrativa), NUNCA de
ventanas temporales ni de `i - idx > N`.

Flujo (DISENO_R10C_R11.md §5):
    detectors (objetos ya estructurales)
      -> EventEngine emite eventos
      -> StateMachine aplica transiciones (Fase A)
      -> Invalidators (Fase B) invalidan por contexto/grafo
      -> ObjectGraph (Fase C) navega relaciones
      -> MarketNarrative (Fase D) agrupa la historia
      -> senal SOLO si el objeto esta ACTIVE/MITIGATED en narrativa VIGENTE

NUNCA importa confirmation_window / bos_gap. max_hold es el UNICO tope de
seguridad (exposicion), no una ventana de confirmacion.
"""
from __future__ import annotations

from typing import Any, Callable

from ict_backtest.market_narrative import MarketNarrative
from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)
from ict_backtest.object_graph import ObjectGraph
from ict_backtest.state_machine import MarketEvent, StateMachine

# Tipos de objeto que pueden originar una senal (no el CANDLE observado).
_SIGNAL_TYPES = (ObjectType.BOS, ObjectType.CHOCH, ObjectType.FVG, ObjectType.ORDER_BLOCK)
# Tipos que funcionan como raiz de una narrativa (la historia arranca en el barrido).
_ROOT_TYPES = (ObjectType.SWEEP,)

# Mapeo objeto -> tipo de evento semantico (strings planos, ver state_machine).
_EVENT_BY_TYPE = {
    ObjectType.SWEEP: "LiquidityTaken",
    ObjectType.BOS: "StructureBroken",
    ObjectType.CHOCH: "StructureBroken",
    ObjectType.FVG: "LiquidityTaken",
    ObjectType.ORDER_BLOCK: "LiquidityTaken",
}

LAST_META: dict = {}


def _find_return_bar(ltf_df: Any, zone_high: float, zone_low: float,
                     after_bar: int) -> int | None:
    """Find the first bar AFTER ``after_bar`` where price touches [zone_low, zone_high].

    Returns the bar_index (DataFrame integer position) of the return bar, or
    ``None`` if price never returns to the zone within the available data.
    This is the semantic equivalent of ``_touches_zone`` in ``run_sequence``.
    """
    if ltf_df is None or not len(ltf_df):
        return None
    if zone_high <= zone_low or zone_high <= 0:
        return None
    n = len(ltf_df)
    start = int(after_bar) + 1
    if start >= n:
        return None
    for i in range(start, n):
        row = ltf_df.iloc[i]
        low = float(row.get("low", 0))
        high = float(row.get("high", 0))
        if low <= zone_high and high >= zone_low:
            return i
    return None


def _to_objs(ltf_df_or_objs: Any, ltf_tf: str) -> list[MarketObject]:
    if isinstance(ltf_df_or_objs, list):
        return ltf_df_or_objs
    # DataFrame: reutiliza el path de detectors (data_feed.build_objects).
    from ict_backtest.data_feed import build_objects

    return build_objects({ltf_tf: ltf_df_or_objs})


class EventEngine:
    """Cola de eventos discretos desde los objetos ya detectados.

    Un evento por objeto estructural relevante, ordenado por su bar_index
    (metadato del objeto, NO un reloj de decision). No recorre velas.
    """

    def emit(self, objs: list[MarketObject]) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        for o in objs:
            etype = _EVENT_BY_TYPE.get(o.type)
            if etype is None:
                continue
            events.append(MarketEvent(type=etype, target=o, context=None))
        events.sort(key=lambda e: e.target.bar_index or 0)
        return events


def run_semantic(
    ltf_df_or_objs: Any,
    est_htf_fn: Callable[..., Any],
    cfg: Any,
    htf_poi_fn: Callable[..., Any] | None = None,
    ltf_tf: str = "M15",
    max_hold: int = 200,
    *,
    ltf_df: Any | None = None,
    est_htf_ctx_fn: Callable[..., Any] | None = None,
    exec_df: Any | None = None,
    exec_tf: str | None = None,
) -> list[dict]:
    """Motor canonico semantico. Emite senales SOLO desde objetos vivos.

    Sin reloj: la caducidad es por Invalidators (evento), no por N velas.
    max_hold es el unico tope de seguridad (exposicion), reportado en meta.

    ``ltf_df`` (opcional): DataFrame LTF para calcular ``entry_at`` (barra
    donde el precio retorna a la zona).  Si se omite, ``entry_at`` coincide
    con ``bar_index`` (compatibilidad con tests existentes).
    """
    # Resolve ltf_df for entry_at computation.
    _ltf_df = ltf_df
    if _ltf_df is None and hasattr(ltf_df_or_objs, "iloc"):
        _ltf_df = ltf_df_or_objs

    objs = _to_objs(ltf_df_or_objs, ltf_tf)
    g = ObjectGraph()
    for o in objs:
        g.add(o)
    for o in objs:
        if o.parent_object is not None:
            parent = g.get(o.parent_object)
            if parent is not None:
                g.link(parent, o)

    # Enlace CAUSAL (no temporal): cada BOS busca el SWEEP MAS CERCANO ANTERIOR
    # de su MISMA direccion de setup cuya ZONA CRUZA la del BOS (el precio salio
    # de la zona de liquidez y rompio estructura relevante). Ese sweep es la
    # causa del BOS (displacement -> BOS confirmado). Un sweep consume la
    # liquidez una sola vez (meta["consumed"]): si ya fue tomado por un BOS
    # previo, no alimenta a otro. Sin numero fijo de velas: la causalidad es por
    # ZONA (precio), no reloj. Relacion demostrada: Legacy ⊆ Semantic.
    bos_by_dir: dict[int, list[MarketObject]] = {}
    sweeps_by_dir: dict[int, list[MarketObject]] = {}
    for o in objs:
        if o.type == ObjectType.BOS:
            bos_by_dir.setdefault(o.direction, []).append(o)
        elif o.type == ObjectType.SWEEP:
            sweeps_by_dir.setdefault(o.direction, []).append(o)
    for d, bs in bos_by_dir.items():
        bs.sort(key=lambda b: b.bar_index or 0)
    for d, sw in sweeps_by_dir.items():
        sw.sort(key=lambda s: s.bar_index or 0)
    for d, bss in bos_by_dir.items():
        for bos in bss:
            for sw in sweeps_by_dir.get(d, []):
                if (sw.bar_index or 0) >= (bos.bar_index or 0):
                    break
                zh, zl = sw.zone_high, sw.zone_low
                if zh > 0 and zl > 0 and bos.zone_high >= zl and bos.zone_low <= zh \
                        and not sw.meta.get("consumed", False):
                    g.link(sw, bos)
                    sw.meta["consumed"] = True
                    sw.meta["linked_bos"] = bos.id
                    break

    sm = StateMachine()
    for ev in EventEngine().emit(objs):
        sm.apply(ev)

    roots = [o for o in objs if o.type in _ROOT_TYPES]
    narratives = [MarketNarrative.from_root(g, r) for r in roots if g.parents(r) == []]

    signals: list[dict] = []
    used_max_hold = 0
    for narr in narratives:
        if not narr.is_active():
            continue
        # Invalidador B2 (Fase B2) DENTRO de la narrativa: si hay un BOS de
        # direccion opuesta en ESTA historia, la estructura se invalida
        # (conflicto de direcciones = ruido). Semantico, no global, sin reloj.
        sig = narr.signal_objects()
        if any(o.type == ObjectType.BOS and o.direction != b.direction
               for b in sig if b.type == ObjectType.BOS
               for o in sig):
            continue
        for o in sig:
            if o.type not in _SIGNAL_TYPES:
                continue
            # Cadena minima (ambiguedad A3): debe colgar de un SWEEP (la misma
            # precondicion que exige run_sequence). Sin esto, run_semantic
            # podria ser mas permisivo que el legacy y romper el SUBSET.
            parents = g.parents(o)
            root = next((p for p in parents if p.type in _ROOT_TYPES), None)
            if root is None:
                continue
            if o.state not in (ObjectState.ACTIVE, ObjectState.MITIGATED):
                continue
            if not (o.zone_high > 0 or o.zone_low > 0):
                continue
            # Tope de seguridad (exposicion), NO ventana de confirmacion.
            if max_hold is not None and o.bar_index > max_hold:
                used_max_hold += 1
            # entry_at = barra donde el precio RETORNA a la zona (si ltf_df
            # esta disponible). Sin ltf_df, entry_at = bar_index (compat
            # con tests existentes). El entry en canonical.py lee el precio
            # de entry_at (open de la vela siguiente), asi que debe apuntar
            # a la vela de retorno, no a la de creacion del objeto.
            entry_bar = o.bar_index
            if _ltf_df is not None and o.zone_high > 0 and o.zone_low > 0:
                ret = _find_return_bar(
                    _ltf_df, o.zone_high, o.zone_low,
                    int(o.bar_index),
                )
                if ret is not None:
                    entry_bar = ret
            signals.append({
                "id": o.id,
                "root_id": root.id,
                "type": o.type.value,
                "direction": o.direction,
                "bar_index": o.bar_index,
                "entry_at": entry_bar,
                "time": str(_ltf_df.iloc[entry_bar]["time"]) if _ltf_df is not None and entry_bar < len(_ltf_df) else "",
                "zone_high": o.zone_high,
                "zone_low": o.zone_low,
                "narrative_active": True,
                "state": o.state.value,
            })

    # Meta de seguridad (sin reloj de decision).
    LAST_META.clear()
    LAST_META["max_hold_used"] = used_max_hold
    LAST_META["signal_count"] = len(signals)
    LAST_META["objects"] = objs  # para el adaptador: mismos objetos usados internamente

    # --- HTF gate: filter signals that oppose D1/H4/H1 trend ---
    # Uses top_down_allows_trade from the multi-TF context (same gate
    # used by run_sequence in the legacy path).  When est_htf_ctx_fn is
    # not available, signals pass unfiltered (backward compatible).
    if est_htf_ctx_fn is not None and signals:
        from ict_backtest.v2.context_mtf import top_down_allows_trade
        filtered: list[dict] = []
        gate_reasons: dict[str, int] = {}
        for sig in signals:
            entry_bar = sig.get("entry_at", sig.get("bar_index", 0))
            if _ltf_df is not None and entry_bar < len(_ltf_df):
                ctx = est_htf_ctx_fn(entry_bar)
                ok, reason = top_down_allows_trade(
                    ctx, sig["direction"], counter_trend=False,
                    require_pd=False,  # PD is bonus, not gate (Fase E audit)
                )
                if ok:
                    filtered.append(sig)
                else:
                    gate_reasons[reason] = gate_reasons.get(reason, 0) + 1
            else:
                filtered.append(sig)  # no time data, pass through
        signals = filtered
        LAST_META["gate_reasons"] = gate_reasons
        LAST_META["pre_gate_count"] = len(gate_reasons) + len(filtered)

    # --- Pass 2 (exec TF): detect trigger objects on M5/M1 and match to LTF zones ---
    # The ICT thesis requires exec TF to independently confirm entry via
    # SWEEP/FVG/BOS within the LTF zone.  This is the "Two-pass" architecture:
    #   Pass 1 (above): LTF (M15) detects zones (BOS, FVG, OB, SWEEP)
    #   Pass 2 (below): exec TF (M5/M1) detects trigger objects within those zones
    if exec_df is not None and exec_tf is not None and signals:
        from ict_backtest.data_feed import build_objects as _build_objects
        exec_objs = _build_objects({exec_tf: exec_df})
        # Build exec objects indexed by bar_index for fast lookup
        exec_by_bar: dict[int, MarketObject] = {}
        for eo in exec_objs:
            if eo.bar_index is not None:
                exec_by_bar[int(eo.bar_index)] = eo

        matched_signals: list[dict] = []
        for sig in signals:
            sig_dir = sig["direction"]
            ltf_bos_bar = sig.get("bar_index", 0)
            ltf_zh = sig.get("zone_high", 0)
            ltf_zl = sig.get("zone_low", 0)
            if ltf_zh <= 0 or ltf_zl <= 0:
                matched_signals.append(sig)
                continue

            # Find exec SWEEP that overlaps LTF zone and occurs AFTER LTF BOS
            exec_sweep = None
            exec_entry_bar = None
            for eo in exec_objs:
                if eo.type != ObjectType.SWEEP:
                    continue
                if eo.direction != sig_dir:
                    continue
                eo_bar = int(eo.bar_index) if eo.bar_index is not None else 0
                if eo_bar <= ltf_bos_bar:
                    continue
                # Price overlap: exec zone must touch LTF zone
                if eo.zone_high >= ltf_zl and eo.zone_low <= ltf_zh:
                    exec_sweep = eo
                    break

            if exec_sweep is not None:
                # Find exec entry bar: first exec bar after sweep that returns to zone
                sweep_bar = int(exec_sweep.bar_index)
                exec_entry_bar = _find_return_bar(
                    exec_df, ltf_zh, ltf_zl, sweep_bar,
                )
                sig["exec_sweep_at"] = sweep_bar
                sig["exec_sweep_high"] = exec_sweep.zone_high
                sig["exec_sweep_low"] = exec_sweep.zone_low
                sig["exec_entry_at"] = exec_entry_bar if exec_entry_bar is not None else sweep_bar + 1
                sig["exec_tf"] = exec_tf
                matched_signals.append(sig)
            # If no exec SWEEP matches, signal is dropped (no exec confirmation)

        signals = matched_signals
        LAST_META["exec_objects_count"] = len(exec_objs)
        LAST_META["exec_matched_count"] = len(signals)

    return signals

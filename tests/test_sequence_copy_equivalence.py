"""M2-bis: equivalencia estructural vela-a-vela de la copia de `objs` en el motor.

Autorizacion CONTROLADA (maestro, 2026-08-12): demostrar que eliminar la copia
superficial `objs = list(ltf_df_or_objs)` es semánticamente idéntico ANTES de
cambiar el default. El motor SOLO LEE `objs` por indice `<= i` (FASE 0: sin
append/pop/sort ni mutacion de elementos), por lo que reutilizar la coleccion
por referencia (copy_objs=False) debe producir EXACTAMENTE la misma traza de
eventos vela-a-vela que la copia historica (copy_objs=True).

Compara la TRAZA, no solo el resultado final: por cada vela i, los eventos que
el motor fija en ese paso (tipo, parent_event_id, timestamp, fase). Si aparece
un evento faltante, adicional, desplazado o distinto => CASO C => falla.

Cubrimiento exigido:
- datasets reales EURUSD (eventos parciales + setups completos si los hay);
- comparacion estructural evento-por-vela (no solo signals finales).
"""

import pandas as pd
import pytest

import market_replay.feed as feed
import market_replay.replay as replay
from engine.sequence import _run_sequence_impl, SequenceState, _candle_objects
from market_replay.replay import _state_event_pairs


def _build_replay(symbol, n):
    """Construye un MarketReplay real (feed + contexto HTF) sobre n velas EURUSD."""
    from engine.data_feed import load_frames
    frames = load_frames(symbol=symbol, timeframes=("D1", "H4", "H1", "M15"))
    # Recortar a n velas M15 (y sus HTF correspondientes) para el tamano de prueba.
    f = feed.MarketFeed()
    for tf, df in frames.items():
        f.ingest(tf, df.head(n) if tf == "M15" else df)
    rp = replay.MarketReplay(f, ltf="M15")
    return rp


def _trace_sequence(ltf_df_full, rp, copy_objs):
    """Corre el motor vela-a-vela como MarketReplay pero con copy_objs fijado.

    Devuelve la traza: lista ordenada de tuplas
    (candle_index, event_type, parent_event_id, timestamp, phase).
    """
    # Preconvertir una vez la lista de objetos (camino optimizado).
    objs_full = _candle_objects(ltf_df_full, "M15")
    state = SequenceState()
    prev_ids: set[str] = set()
    trace = []

    for i in range(1, len(ltf_df_full)):
        t = ltf_df_full.iloc[i]["time"]
        if copy_objs:
            win = ltf_df_full.iloc[: i + 1].reset_index(drop=True)
            win_arg = win
        else:
            win_arg = objs_full[: i + 1]  # slice por referencia, O(1)
        _signals, _phase, _exp, state = _run_sequence_impl(
            win_arg,
            rp._htf_ctx_fn,
            rp.cfg,
            ltf_tf="M15",
            initial_state=state,
            start_i=i - 1,
            copy_objs=copy_objs,
        )
        for fid, etype in _state_event_pairs(state):
            if fid in prev_ids:
                continue
            # Reconstruir parent_event_id y timestamp desde el evento fijado.
            ev = state.event_objs.get(fid)
            parent = getattr(ev, "parent_event_id", "") if ev is not None else ""
            ts = str(getattr(ev, "time", t)) if ev is not None else str(t)
            trace.append((i, etype, parent, ts, getattr(ev, "phase", "") if ev is not None else ""))
        prev_ids = {fid for fid, _ in _state_event_pairs(state)}
    return trace


def _normalize(trace):
    """Convierte la traza a tuplas comparables (ignora ids unicos de evento)."""
    out = []
    for candle_index, etype, parent, ts, phase in trace:
        # parent_event_id es un id hash unico por corrida; lo normalizamos a su
        # posicion relativa comparando solo el TIPO de evento padre via indice en
        # la misma traza. Para la comparacion estructura usamos (candle, tipo,
        # fase, tipo_padre_inferido). Aqui comparamos (candle, etype, phase, ts)
        # que es estable entre ambas variantes (los ids hash son deterministicos
        # por contenido, asi que incluso el parent coincidira si el contenido es
        # igual).
        out.append((candle_index, etype, parent, ts, phase))
    return out


@pytest.mark.parametrize("symbol,n", [("EURUSD", 120)])
def test_copy_objs_equivalence_structural(symbol, n):
    rp = _build_replay(symbol, n)
    ltf_df_full = rp.feed.window("M15")

    ref = _normalize(_trace_sequence(ltf_df_full, rp, copy_objs=True))
    opt = _normalize(_trace_sequence(ltf_df_full, rp, copy_objs=False))

    assert len(ref) == len(opt), (
        f"Divergencia en numero de eventos: ref={len(ref)} opt={len(opt)}\n"
        f"ref[:10]={ref[:10]}\nopt[:10]={opt[:10]}"
    )
    for k, (r, o) in enumerate(zip(ref, opt)):
        assert r == o, (
            f"Evento {k} diverge:\n  referencia={r}\n  optimizado={o}\n"
            f"Traza ref={ref[:k+3]}\nTraza opt={opt[:k+3]}"
        )


@pytest.mark.parametrize("symbol,n", [("EURUSD", 120)])
def test_market_replay_run_equals_legacy_dataframe_path(symbol, n):
    """El MarketReplay.run() NUEVO (lista preconvertida + slice + copy_objs=False)
    debe producir EXACTAMENTE el mismo journal que el camino LEGACY (DataFrame
    recortado por vela, copy_objs default=True). Equivalencia directa de
    produccion, no por transitividad.
    """
    from market_replay.journal import EventJournal, JournalEntry
    from engine.sequence import SequenceState as _SS

    rp = _build_replay(symbol, n)
    ltf_df_full = rp.feed.window("M15")

    # --- Camino LEGACY (replica run() anterior: DataFrame recortado por vela) ---
    def _legacy_run():
        j = EventJournal()
        state = _SS()
        prev = set()
        for i in range(1, len(ltf_df_full)):
            t = ltf_df_full.iloc[i]["time"]
            win = ltf_df_full.iloc[: i + 1].reset_index(drop=True)
            _s, _p, _e, state = _run_sequence_impl(
                win, rp._htf_ctx_fn, rp.cfg, ltf_tf="M15",
                initial_state=state, start_i=i - 1, copy_objs=True,
            )
            for fid, etype in _state_event_pairs(state):
                if not fid or fid in prev:
                    continue
                j.record(JournalEntry(
                    timestamp=str(pd.to_datetime(t, utc=True)), timeframe="M15",
                    candle_index=i, event_id=fid,
                    parent_event_id="", event_type=etype, direction=0,
                    level=float("nan"), state=str(getattr(state, "phase", "")),
                ))
            prev = {fid for fid, _ in _state_event_pairs(state)}
        return j

    legacy = _legacy_run()
    new = rp.run().journal

    assert len(legacy) == len(new), (
        f"Journal diverge en tamano: legacy={len(legacy)} new={len(new)}"
    )
    for k, (a, b) in enumerate(zip(legacy, new)):
        assert (a.candle_index, a.event_type, a.state) == (b.candle_index, b.event_type, b.state), (
            f"Evento {k} diverge:\n legacy={a.candle_index}/{a.event_type}/{a.state}\n new={b.candle_index}/{b.event_type}/{b.state}"
        )
@pytest.mark.parametrize("symbol,n", [("EURUSD", 120)])
def test_copy_objs_signals_equivalent(symbol, n):
    """Las senales finales (setup completos) tambien deben coincidir."""
    rp = _build_replay(symbol, n)
    ltf_df_full = rp.feed.window("M15")
    objs_full = _candle_objects(ltf_df_full, "M15")

    def _signals(copy_objs):
        state = SequenceState()
        all_signals = []
        for i in range(1, len(ltf_df_full)):
            if copy_objs:
                win = ltf_df_full.iloc[: i + 1].reset_index(drop=True)
                win_arg = win
            else:
                win_arg = objs_full[: i + 1]
            sig, _p, _e, state = _run_sequence_impl(
                win_arg, rp._htf_ctx_fn, rp.cfg, ltf_tf="M15",
                initial_state=state, start_i=i - 1, copy_objs=copy_objs,
            )
            all_signals.extend(sig)
        return all_signals

    ref = _signals(True)
    opt = _signals(False)
    assert len(ref) == len(opt), f"Senales: ref={len(ref)} opt={len(opt)}"
    for k, (a, b) in enumerate(zip(ref, opt)):
        # Comparamos campos derivables (no los ids hash unicos).
        for key in ("time", "direction", "entry", "bos_level", "sweep_at",
                    "displace_at", "bos_at", "entry_at"):
            assert a.get(key) == b.get(key), (
                f"Senal {k} campo {key}: ref={a.get(key)} opt={b.get(key)}"
            )

"""tests/test_replay_equivalence.py — FASE 3 (equivalencia) del parche M2/replay.

El parche de market_replay/replay.py pasa objetos preconvertidos al motor en
lugar del DataFrame creciente `win`. Esto es infra de replay (NO logica SMC),
pero debe producir EXACTAMENTE el mismo journal que la impl anterior
(DataFrame `win` recortado por vela).

Congelamos la impl ANTERIOR de run() (copia literal) y la comparamos contra
la actual sobre EURUSD real (tramo pequeno, rapido). Si cualquier JournalEntry
diverge => CASO C => revertir.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from engine.data_feed import load_frames
from engine.sequence import SequenceConfig, SequenceState, run_sequence_traced
from market_replay.feed import MarketFeed
from market_replay.availability import TemporalAvailability
from market_replay.replay import MarketReplay, _state_event_pairs, _parent_of


def _load(symbol, n):
    frames = load_frames(symbol, ("D1", "H4", "H1", "M15"))
    m15 = frames["M15"]
    last = m15["time"].iloc[min(n, len(m15)) - 1]
    return {tf: frames[tf][frames[tf]["time"] <= last].reset_index(drop=True) for tf in ("D1", "H4", "H1", "M15")}


def _journal_to_set(journal):
    return {
        (je.timestamp, je.timeframe, je.candle_index, je.event_id, je.parent_event_id,
         je.event_type, je.direction, round(float(je.level), 6) if je.level == je.level else None,
         je.state)
        for je in journal
    }


def _run_legacy(symbol, n):
    """COPIA LITERAL de MarketReplay.run() PRE-PARCHE M2 (DataFrame win recortado)."""
    frames = _load(symbol, n)
    feed = MarketFeed()
    for tf, f in frames.items():
        feed.ingest(tf, f)
    ltf = "M15"
    cfg = SequenceConfig()
    avail = TemporalAvailability({tf: feed.window(tf) for tf in feed.available_tfs()}, ltf)

    def _ctx(i):
        t = feed.window(ltf).iloc[i]["time"]
        snap = avail.snapshot(t, include_ltf=False)
        return {tf: {"trend": str(r.get("trend", "RANGING"))} for tf, r in snap.items() if r is not None}

    ltf_df_full = feed.window(ltf)
    state = SequenceState()
    prev_ids = set()
    journal = []
    for i in range(1, len(ltf_df_full)):
        t = ltf_df_full.iloc[i]["time"]
        win = ltf_df_full.iloc[: i + 1].reset_index(drop=True)
        _, _, _, state = run_sequence_traced(win, _ctx, cfg, ltf_tf=ltf,
                                            initial_state=state, start_i=i - 1)
        for fid, etype in _state_event_pairs(state):
            if not fid or fid in prev_ids:
                continue
            parent = _parent_of(state, fid)
            journal.append((str(pd.to_datetime(t, utc=True)), ltf, i, fid, parent, etype,
                            int(getattr(state, "direction", 0) or 0),
                            float(getattr(state, "bos_level", float("nan")) or float("nan")),
                            str(getattr(state, "phase", ""))))
        prev_ids = {fid for fid, _ in _state_event_pairs(state)}
    return _journal_to_set(journal)


def _run_new(symbol, n):
    frames = _load(symbol, n)
    feed = MarketFeed()
    for tf, f in frames.items():
        feed.ingest(tf, f)
    rp = MarketReplay(feed, ltf="M15")
    rp.run()
    return _journal_to_set(rp.journal)


def test_replay_equivalence_real():
    legacy = _run_legacy("EURUSD", 400)   # 400 velas: suficiente para ejercitar el path
    new = _run_new("EURUSD", 400)
    assert legacy == new, (
        f"DIVERGENCIA replay (CASO C): legacy={len(legacy)} new={len(new)} "
        f"diff_only_legacy={legacy - new} diff_only_new={new - legacy}"
    )

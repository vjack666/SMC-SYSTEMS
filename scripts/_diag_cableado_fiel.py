"""Verifica la hipotesis del Director: el replay NO esta cableado igual a FASE A.

Llama run_sequence_traced con la llamada EXACTA de FASE A (df completo, sin
htf_poi_fn/htf_pd_index) + est_htf_ctx_fn con cache O(n). Si esto da setups y
el replay (sublista + filtros) da 0, la hipotesis se confirma: el replay esta
mal cableado.
"""

import sys, os, time, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context, MultiTFContext
from engine.poi_anchor import build_htf_structure_index
from engine._util import tf_duration
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay

SYMBOL = "EURUSD"
TFS = ("D1", "H4", "H1", "M15")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def load_frames(n_m15):
    frames = {}
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    for tf in TFS:
        fp = os.path.join(base, f"{SYMBOL}_{tf}.parquet")
        if os.path.exists(fp):
            df = pd.read_parquet(fp)
            frames[tf] = df.iloc[:n_m15] if tf == "M15" else df
    return frames


def cached_ctx_factory(ms, htf_frames):
    ltf_df = ms["M15"]
    n = len(ltf_df)
    htf_data = {tf: htf_frames[tf] for tf in htf_frames}
    htimes = {tf: list(pd.to_datetime(htf_data[tf]["time"], utc=True, errors="coerce")) for tf in htf_data}
    idx_by_i = {tf: [None] * n for tf in htf_data}
    for tf in htf_data:
        ht = htimes[tf]
        dur = tf_duration(tf)
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] + pd.Timedelta(dur) <= t:
                ji += 1
            idx_by_i[tf][i] = ji if ji >= 0 else None
    _ev = build_htf_structure_index(htf_frames) if htf_frames else []
    def fn(i):
        anchored = None
        if _ev:
            ltf_t = pd.to_datetime(ms["M15"].iloc[i]["time"], utc=True, errors="coerce")
            prior = [e for e in _ev if e.time is not None and e.time <= ltf_t]
            anchored = {}
            for e in prior:
                anchored.setdefault(e.tf, []).append(e)
        ctx = {}
        for tf in htf_data:
            j = idx_by_i[tf][i]
            if j is not None:
                ctx[tf] = htf_data[tf].iloc[j].to_dict()
        return MultiTFContext(ctx)
    return fn


def main():
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    htf_frames = {tf: df for tf, df in frames.items() if tf != "M15"}
    ltf = ms["M15"]
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)
    ctx_fn = cached_ctx_factory(ms, htf_frames)

    # === LLAMADA EXACTA FASE A: df completo, sin htf_poi_fn/htf_pd_index, est_htf_ctx_fn=cache ===
    print(f"[VERIF] Llamada FASE A fiel sobre {N} velas M15 (df completo, sin filtros)...")
    t0 = time.time()
    sigs, phase, _, _ = run_sequence_traced(
        ltf, None, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    ta = time.time() - t0
    print(f"    setups={len(sigs)} funnel={dict(phase)} tiempo={ta:.1f}s")

    # === REPLAY TAL CUAL (sublista + filtros) ===
    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=cfg)
    t0 = time.time()
    res = rp.run()
    tb = time.time() - t0
    print(f"[REPLAY] sublista+filtros: setups={len(res.signals)} tiempo={tb:.1f}s")

    print("\n=== Veredicto ===")
    if len(sigs) > 0 and len(res.signals) == 0:
        print(">>> HIPOTESIS CONFIRMADA: el replay esta mal cableado (sublista+filtros => 0).")
    elif len(sigs) == 0 and len(res.signals) == 0:
        print(">>> AMBOS 0: la diferencia de cableado no es la causa (problema mas profundo).")
    else:
        print(f">>> Inesperado: FASE-A={len(sigs)} REPLAY={len(res.signals)}")


if __name__ == "__main__":
    main()

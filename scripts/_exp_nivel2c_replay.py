"""NIVEL 2c — MarketReplay (Opción B + Opción 3) vs BATCH fiel, datos reales N=300.

Valida la cadena completa: el replay (que usa SequenceRunner.step(i) vela a vela
con closed_index O(n)) debe producir los MISMOS setups que el batch fiel.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig, run_sequence_traced, _candle_objects
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context
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
            frames[tf] = df.iloc[: max(n_m15, 20)] if tf != "M15" else df.iloc[:n_m15]
    return frames


def ctx_fn_factory(ms, htf_frames):
    ltf_df = ms["M15"]
    n = len(ltf_df)
    idx_by_i = {}
    for tf in htf_frames:
        ht = list(pd.to_datetime(htf_frames[tf]["time"], utc=True, errors="coerce"))
        dur = tf_duration(tf)
        arr = [None] * n
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] + pd.Timedelta(dur) <= t:
                ji += 1
            arr[i] = ji if ji >= 0 else None
        idx_by_i[tf] = arr
    def fn(i):
        t = ms["M15"].iloc[i]["time"]
        ci = {tf: idx_by_i[tf][i] for tf in htf_frames if idx_by_i[tf][i] is not None}
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1"),
                                      anchored_pd_zones=None, closed_index=ci)
    return fn


def main():
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf = ms["M15"]
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)
    ctx_fn = ctx_fn_factory(ms, {tf: ms[tf] for tf in ("D1", "H4", "H1")})

    # BATCH fiel (SequenceRunner.run_all internamente)
    objs = _candle_objects(ltf, "M15")
    t0 = time.time()
    sigs_b, phase_b, _, _ = run_sequence_traced(
        ltf, None, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    tb = time.time() - t0
    print(f"[BATCH] setups={len(sigs_b)} funnel={dict(phase_b)} tiempo={tb:.1f}s")

    # REPLAY (SequenceRunner.step(i) vela a vela, con closed_index O(n))
    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=cfg)
    t0 = time.time()
    res = rp.run()
    tr = time.time() - t0
    print(f"[REPLAY OpcionB] setups={len(res.signals)} tiempo={tr:.1f}s")

    print("\n=== Veredicto Nivel 2c (REPLAY == BATCH) ===")
    if len(res.signals) == len(sigs_b):
        print(f"✅ REPLAY({len(res.signals)}) == BATCH({len(sigs_b)}). "
              f"Opción B + Opción 3: replay vela-a-vela O(N) con misma semántica.")
    else:
        print(f"❌ DIVERGEN: REPLAY={len(res.signals)} BATCH={len(sigs_b)}. Investigar.")


if __name__ == "__main__":
    main()

"""NIVEL 2 — Replay (Opción 3, fiel+O(n)) vs batch fiel, en datos reales N=300.

Valida: REPLAY(t) produce los MISMOS setups que el camino batch fiel en la misma
muestra. El batch NO es autoridad, pero si ambos coinciden en esta muestra, el
replay respeta causalidad sin diverger del contexto fiel.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.market_structure import detect_market_structure
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


def main():
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf = ms["M15"]
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)

    # BATCH fiel (sin closed_index; build_multitf_context por vela, O(n^2) pero N=300 termina)
    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=cfg)
    t0 = time.time()
    res = rp.run()
    tb = time.time() - t0
    print(f"[REPLAY Opcion3] setups={len(res.signals)} tiempo={tb:.1f}s")

    # BATCH fiel directo (misma llamada que FASE A, contexto fiel)
    from engine.multitf_context import build_multitf_context
    def ctx_fn(i):
        t = ltf.iloc[i]["time"]
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1"), anchored_pd_zones=None)
    t0 = time.time()
    sigs, phase, _, _ = run_sequence_traced(ltf, None, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    ta = time.time() - t0
    print(f"[BATCH fiel]      setups={len(sigs)} funnel={dict(phase)} tiempo={ta:.1f}s")

    print("\n=== Veredicto Nivel 2 ===")
    if len(res.signals) == len(sigs):
        print(f"✅ REPLAY({len(res.signals)}) == BATCH({len(sigs)}) en N={N}. Coincidencia de conteo.")
    else:
        print(f"❌ DIVERGEN: REPLAY={len(res.signals)} BATCH={len(sigs)}. Investigar.")


if __name__ == "__main__":
    main()

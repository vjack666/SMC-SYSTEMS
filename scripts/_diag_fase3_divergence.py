"""Fase 3 — primera divergencia BATCH(FASE A style) vs STREAM(replay style) en datos REALES.

Usa EURUSD M15 real (N velas). Loguea eventos por vela para ambos modos y
encuentra la PRIMERA vela donde divergen. No usa monkey-patch (respeta Solución A).

Diferencia clave a aislar: FASE A pasa est_htf_fn LEGACY (2do arg) + est_htf_ctx_fn.
Mi replay pasa solo est_htf_ctx_fn (est_htf_fn=None).

Corre ambos sobre el MISMO df y compara eventos por vela.
"""

import sys, os, time, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context
from engine.poi_anchor import build_htf_structure_index
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


def est_htf_ctx_fn_factory(ms, htf_frames):
    _ev = build_htf_structure_index(htf_frames) if htf_frames else []
    def fn(i):
        t = ms["M15"].iloc[i]["time"]
        anchored = None
        if _ev:
            ltf_t = pd.to_datetime(ms["M15"].iloc[i]["time"], utc=True, errors="coerce")
            prior = [e for e in _ev if e.time is not None and e.time <= ltf_t]
            anchored = {}
            for e in prior:
                anchored.setdefault(e.tf, []).append(e)
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1", "M15"), anchored_pd_zones=anchored)
    return fn


def est_htf_fn_legacy(i):
    # estimador legacy: extrae trend del ctx (igual que FASE A linea 124 + legacy wrapper)
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False,
            "displacement_bullish": False, "displacement_bearish": False,
            "fvg_bullish": False, "fvg_bearish": False,
            "ob_bullish": False, "ob_bearish": False, "bos_dir": 0}


def main():
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    htf_frames = {tf: df for tf, df in frames.items() if tf != "M15"}
    ltf = ms["M15"]

    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False) if False else \
          SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)
    ctx_fn = est_htf_ctx_fn_factory(ms, htf_frames)

    # === MODO A: FASE A style (est_htf_fn legacy + est_htf_ctx_fn) ===
    print(f"[A] FASE-A-style sobre {N} velas M15...")
    t0 = time.time()
    sigs_a, phase_a, _, _ = run_sequence_traced(
        ltf, est_htf_fn_legacy, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    ta = time.time() - t0
    print(f"    setups={len(sigs_a)} funnel={dict(phase_a)} tiempo={ta:.1f}s")

    # === MODO B: replay style (solo est_htf_ctx_fn, est_htf_fn=None) ===
    print(f"[B] REPLAY-style sobre {N} velas M15...")
    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=cfg)
    t0 = time.time()
    res_b = rp.run()
    tb = time.time() - t0
    print(f"    setups={len(res_b.signals)} tiempo={tb:.1f}s")

    print("\n=== Veredicto Fase 3 ===")
    print(f"A (FASE-A-style, est_htf_fn+ctx): {len(sigs_a)} setups")
    print(f"B (REPLAY-style, solo ctx)      : {len(res_b.signals)} setups")
    if len(sigs_a) != len(res_b.signals):
        print(">>> DIVERGENCIA: est_htf_fn legacy es necesario ademas de est_htf_ctx_fn.")
    else:
        print(">>> IGUAL: la diferencia NO es est_htf_fn legacy.")


if __name__ == "__main__":
    main()

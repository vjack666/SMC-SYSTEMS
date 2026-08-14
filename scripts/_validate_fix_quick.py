"""Validacion rapida del FIX de cableado MarketReplay (tramo corto ~1 semana).

NO es el backtest completo. Solo orquesta MarketReplay (consumidor puro) sobre
N_M15 velas M15 + HTF completos, y comprueba las 4 pruebas del Consejo:
  1. setups > 0
  2. linaje (event_objects)
  3. trend real (!= RANGING)
  4. POI anclado > 0
"""

import sys, os, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import glob

from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay
from engine.sequence import SequenceConfig
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context

SYMBOL = "EURUSD"
TFS = ("D1", "H4", "H1", "M15")
N_M15 = int(sys.argv[1]) if len(sys.argv) > 1 else 800


def main():
    frames = {}
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    for tf in TFS:
        fp = os.path.join(base, f"{SYMBOL}_{tf}.parquet")
        if os.path.exists(fp):
            df = pd.read_parquet(fp)
            frames[tf] = df.iloc[:N_M15] if tf == "M15" else df
    print(f"[cargado] M15={len(frames.get('M15', []))} velas")

    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)

    # FIX de cableado (Codex, commit 1651bdf): el replay construye el LTF
    # estructurado internamente y acepta htf explicito. Lo ejercitamos igual.
    t0 = time.time()
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=SequenceConfig(bos_gap=10))
    res = rp.run()
    el = time.time() - t0

    n_sig = len(res.signals)
    wl = sum(1 for s in res.signals if isinstance(s, dict) and s.get("event_objects"))
    poi = sum(1 for e in res.journal if getattr(e, "state_snapshot", {}).get("poi_present"))
    from collections import Counter
    c = Counter(e.event_type for e in res.journal)

    # trend real por muestreo
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    mid = min(len(frames["M15"]) - 1, N_M15 // 2)
    t = frames["M15"].iloc[mid]["time"]
    ctx = build_multitf_context(ms, t, tfs=tuple(ms.keys()), anchored_pd_zones=None)
    trends = [ctx.get(tf, {}).get("trend") for tf in ("D1", "H4", "H1")]

    print(f"[tiempo] {el:.1f}s  steps={res.steps}")
    print(f"[setups] {n_sig}  linaje={wl}")
    print(f"[eventos] {dict(c)}")
    print(f"[POI] poi_present True = {poi}")
    print(f"[trend] D1/H4/H1 = {trends}")

    ok = (n_sig > 0) and (wl == n_sig) and any(tr not in (None, "RANGING") for tr in trends) and (poi > 0)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)

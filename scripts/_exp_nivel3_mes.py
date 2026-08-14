"""NIVEL 3 — Un mes de datos M15 (~2113 velas) en modo INCREMENTAL (replay causal).

Config EXACTA de FASE A:
- require_displacement=True, displace_gap=6, bos_gap=10, counter_trend=False,
  tp_mode='fixed2r', invalidate_on_opposite_swing=False
- anchored_pd_zones=True (htf_poi_fn de FASE A)
- Modo incremental: MarketReplay usa SequenceRunner.step(i) vela a vela.

Mide:
1. Estructura LTF disponible (FVG/OB en M15, CHOCH en H4) tras detect_market_structure.
2. Setups del replay (causal). Si 0 => el motor no opera bajo info causal (no es
   la estrategia ni la muestra: es falla del motor en regimen causal).

Criterio del Director: si en un mes real de datos el replay causal da 0 setups,
algo NO funciona y no es la estrategia.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import SequenceConfig
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context
from engine._util import tf_duration
from engine.poi_anchor import make_htf_poi_fn
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay

SYMBOL = "EURUSD"
TFS = ("D1", "H4", "H1", "M15")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2113


def load_frames(n_m15):
    frames = {}
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    for tf in TFS:
        fp = os.path.join(base, f"{SYMBOL}_{tf}.parquet")
        if os.path.exists(fp):
            df = pd.read_parquet(fp)
            frames[tf] = df.iloc[: max(n_m15, 20)] if tf != "M15" else df.iloc[:n_m15]
    return frames


def main():
    t_start = time.time()
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf = ms["M15"]
    n = len(ltf)

    # Estructura LTF disponible
    n_fvg = int((ltf.get("fvg_state", pd.Series(["NONE"] * n)) != "NONE").sum())
    n_ob = int((ltf.get("ob_direction", pd.Series(["-"] * n)) != "-").sum())
    n_h4_choch = int((ms["H4"].get("choch_signal", pd.Series([""] * len(ms["H4"]))) != "").sum())
    n_h4_bos = int((ms["H4"].get("bos_dir", pd.Series([0] * len(ms["H4"]))) != 0).sum())
    print(f"[DATOS] M15 velas={n} | FVG={n_fvg} | OB={n_ob}")
    print(f"[DATOS] H4 BOS={n_h4_bos} | CHOCH={n_h4_choch}")
    print(f"[TIEMPO] load+detect: {time.time()-t_start:.1f}s")

    # Config EXACTA FASE A
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)

    # anchored_pd_zones (FASE A usa htf_poi_fn)
    htf_frames = {tf: ms[tf] for tf in ("D1", "H4", "H1")}
    htf_poi_fn = make_htf_poi_fn(ltf, htf_frames)

    # est_htf_ctx_fn con Opción 3 (closed_index O(n))
    idx_by_i = {}
    for tf in htf_frames:
        ht = list(pd.to_datetime(htf_frames[tf]["time"], utc=True, errors="coerce"))
        dur = tf_duration(tf)
        arr = [None] * n
        ji = -1
        for i in range(n):
            t = pd.to_datetime(ltf.iloc[i]["time"], utc=True, errors="coerce")
            while ji + 1 < len(ht) and ht[ji + 1] + pd.Timedelta(dur) <= t:
                ji += 1
            arr[i] = ji if ji >= 0 else None
        idx_by_i[tf] = arr
    def ctx_fn(i):
        t = ltf.iloc[i]["time"]
        ci = {tf: idx_by_i[tf][i] for tf in htf_frames if idx_by_i[tf][i] is not None}
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1"),
                                      anchored_pd_zones=None, closed_index=ci)

    # Replay incremental (SequenceRunner.step(i)). El replay arma htf_poi_fn
    # internamente (FASE A: anchored_pd_zones via make_htf_poi_fn).
    feed = MarketFeed()
    for tf, df in frames.items():
        feed.ingest(tf, df)
    rp = MarketReplay(feed=feed, ltf="M15", htf="H4", cfg=cfg)
    t0 = time.time()
    res = rp.run()
    tr = time.time() - t0

    print(f"\n=== NIVEL 3 (un mes, {n} velas M15, replay causal) ===")
    print(f"REPLAY setups = {len(res.signals)}  | tiempo = {tr:.1f}s")
    if res.signals:
        print("Primeros setups:")
        for s in res.signals[:5]:
            print(f"  dir={s.get('direction')} entry={s.get('entry')} "
                  f"sweep_at={s.get('sweep_at')} bos_at={s.get('bos_at')} entry_at={s.get('entry_at')}")
    else:
        print("⚠️ 0 setups en un mes de datos bajo info causal.")
        print("   Si FASE A reportó 18 en batch sobre esta ventana, entonces:")
        print("   el motor NO opera bajo regimen causal => falla del motor (no estrategia).")
        print(f"   Estructura disponible: FVG={n_fvg} OB={n_ob} CHOCH_H4={n_h4_choch} BOS_H4={n_h4_bos}")
        if n_fvg == 0 and n_ob == 0:
            print("   CAUSA: detect_market_structure no marca FVG/OB en M15 => no hay cuadro de entrada.")
        elif n_h4_choch == 0:
            print("   CAUSA: CHOCH H4=0 => falta confirmacion de reversal en HTF.")


if __name__ == "__main__":
    main()

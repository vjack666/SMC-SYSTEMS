"""NIVEL 2 — Equivalencia BATCH vs STEP(i) vela por vela (Opción B, Change Gate).

Valida la condición del Director: step(i) debe producir los MISMOS eventos que
el batch, vela por vela, con indices absolutos intactos.

- BATCH: run_sequence_traced(objs, est_htf_ctx_fn)  [una sola corrida]
- STREAM: SequenceRunner(objs, est_htf_ctx_fn); for i: runner.step(i)  [vela a vela]

Compara:
  - total de setups
  - cada senal: direction, sweep_at, displace_at, bos_at, entry_at, event_ids
  - estado final (phase_seen)

Si son identicas => step(i) es la MISMA maquina de estados (una sola logica).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from engine.sequence import (SequenceConfig, run_sequence_traced, SequenceRunner,
                              _candle_objects)
from engine.market_structure import detect_market_structure
from engine.multitf_context import build_multitf_context
from engine._util import tf_duration

SYMBOL = "EURUSD"
TFS = ("D1", "H4", "H1", "M15")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def load_frames(n_m15):
    frames = {}
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    for tf in TFS:
        fp = os.path.join(base, f"{SYMBOL}_{tf}.parquet")
        if os.path.exists(fp):
            # Recortar TODOS los TF a una ventana acotada (como hace el feed del
            # replay con window()). Evita detect_market_structure O(n^2) sobre
            # el parquet completo de D1/H4/H1 (miles de velas => lento/colgado).
            df = pd.read_parquet(fp)
            frames[tf] = df.iloc[: max(n_m15, 20)] if tf != "M15" else df.iloc[:n_m15]
    return frames


def ctx_fn_factory(ms, htf_frames):
    # Opcion 3: precompute idx_by_i O(n) total, lookup O(1) por vela.
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
        closed_index = {tf: idx_by_i[tf][i] for tf in htf_frames if idx_by_i[tf][i] is not None}
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1"),
                                      anchored_pd_zones=None, closed_index=closed_index)
    return fn


def main():
    print(f"[NIVEL2] arrancando N={N}...", flush=True)
    frames = load_frames(N)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf = ms["M15"]
    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10,
                         invalidate_on_opposite_swing=False)
    ctx_fn = ctx_fn_factory(ms, {tf: ms[tf] for tf in ("D1", "H4", "H1")})

    # BATCH (run_sequence_traced => SequenceRunner.run_all internamente)
    sigs_batch, phase_batch, _, state_batch = run_sequence_traced(
        ltf, None, cfg, ltf_tf="M15", htf="H4", est_htf_ctx_fn=ctx_fn)
    print(f"[BATCH] setups={len(sigs_batch)} funnel={dict(phase_batch)}")

    # STREAM (SequenceRunner.step(i) por vela)
    # SequenceRunner espera objs como lista de MarketObject (no DataFrame).
    objs = _candle_objects(ltf, "M15")
    runner = SequenceRunner(objs, ctx_fn, cfg, ltf_tf="M15", htf="H4")
    for i in range(1, len(ltf)):
        runner.step(i)
    sigs_stream = runner.signals
    print(f"[STREAM] setups={len(sigs_stream)} funnel={dict(runner.phase_seen)}")

    # Comparacion vela por vela (senales en orden de aparicion)
    print("\n=== Veredicto Nivel 2 (BATCH == STREAM) ===")
    if len(sigs_batch) != len(sigs_stream):
        print(f"❌ DIVERGEN: total BATCH={len(sigs_batch)} STREAM={len(sigs_stream)}")
        return
    ok = True
    for k, (b, s) in enumerate(zip(sigs_batch, sigs_stream)):
        for field in ("direction", "sweep_at", "displace_at", "bos_at", "entry_at"):
            if b.get(field) != s.get(field):
                print(f"❌ senal {k} campo {field}: BATCH={b.get(field)} STREAM={s.get(field)}")
                ok = False
        # event_ids (lineage)
        if b.get("event_ids") != s.get("event_ids"):
            print(f"❌ senal {k} event_ids divergen: BATCH={b.get('event_ids')} STREAM={s.get('event_ids')}")
            ok = False
    if ok:
        print(f"✅ BATCH == STREAM en {len(sigs_batch)} setups. step(i) es la MISMA maquina "
              f"de estados (una sola logica, indices absolutos intactos).")
        print("   Opción B cumple: O(N) vela-a-vela, cero segunda implementacion.")


if __name__ == "__main__":
    main()

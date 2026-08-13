"""scripts/profile_replay_scaling.py — FASE 1: de donde vienen los ~3s/vela.

Mide el tiempo total de MarketReplay.run() sobre ventanas crecientes de
EURUSD M15 real y reporta si el costo por vela crece con el historico
(adaptador recalculando) o es plano (motor O(1) incremental).

No modifica engine. Solo temporiza.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from engine.data_feed import load_frames
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay


def _scaling(symbol, sizes, data_dir=None) -> dict:
    import sys
    tc = time.perf_counter()
    frames = load_frames(symbol, ("D1", "H4", "H1", "M15"),
                         **({"data_dir": data_dir} if data_dir else {}))
    print(f"[profile] load_frames: {time.perf_counter()-tc:.2f}s (M15={len(frames['M15'])})", flush=True)
    m15 = frames["M15"]
    rows = []
    for n in sizes:
        e = min(n, len(m15))
        last = m15["time"].iloc[e - 1]
        fwd = {tf: frames[tf][frames[tf]["time"] <= last].reset_index(drop=True) for tf in ("D1", "H4", "H1", "M15")}
        feed = MarketFeed()
        for tf, f in fwd.items():
            feed.ingest(tf, f)
        t0 = time.perf_counter()
        rp = MarketReplay(feed, ltf="M15")
        rp.run()
        dt = time.perf_counter() - t0
        rows.append({"n_velas": e, "total_s": round(dt, 3), "seg_por_vela": round(dt / max(1, e), 4)})
        print(f"[profile] n={e} run={dt:.2f}s ({dt/max(1,e):.4f}s/vela)", flush=True)
    # deducir orden: comparar ratio de tiempo vs ratio de tamaño entre extremos.
    a, b = rows[0], rows[-1]
    r_n = b["n_velas"] / a["n_velas"]
    r_t = b["total_s"] / max(1e-9, a["total_s"])
    exponent = round(__import__("math").log(r_t) / __import__("math").log(r_n), 2)
    return {
        "rows": rows,
        "radio_tamano": round(r_n, 2),
        "radio_tiempo": round(r_t, 2),
        "exponente_aprox": exponent,  # ~1 lineal, ~2 cuadratico (recalculo historico)
        "veredicto": (
            "O(n^2): el adaptador/motor recalcula historico por vela"
            if exponent >= 1.5
            else "O(n) aproximado: costo por vela estable"
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--sizes", default="100,200,400,800,1600")
    p.add_argument("--data-dir", default=None)
    args = p.parse_args(argv)
    sizes = [int(x) for x in args.sizes.split(",")]
    out = _scaling(args.symbol, sizes, Path(args.data_dir) if args.data_dir else None)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

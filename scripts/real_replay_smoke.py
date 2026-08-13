"""scripts/real_replay_smoke.py — FASE 7 (M2): replay REAL de N velas EURUSD.

No construye nada. Solo corre MarketReplay.run() sobre un tramo real recortado
y reporta: velas, segundos, seg/vela, n_setup_detectados (senales con phase
ENTRY), y muestra los primeros setups reales (si los hay).

Uso:
  python scripts/real_replay_smoke.py --symbol EURUSD --n 1600
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from engine.data_feed import load_frames
from market_replay.feed import MarketFeed
from market_replay.replay import MarketReplay
from engine.sequence import SequenceState


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--n", type=int, default=1600)
    p.add_argument("--data-dir", default=None)
    args = p.parse_args(argv)

    t0 = time.perf_counter()
    frames = load_frames(args.symbol, ("D1", "H4", "H1", "M15"),
                         **({"data_dir": Path(args.data_dir)} if args.data_dir else {}))
    print(f"[load] {time.perf_counter()-t0:.2f}s M15={len(frames['M15'])}", flush=True)

    m15 = frames["M15"]
    n = min(args.n, len(m15))
    last = m15["time"].iloc[n - 1]
    fwd = {tf: frames[tf][frames[tf]["time"] <= last].reset_index(drop=True)
           for tf in ("D1", "H4", "H1", "M15")}
    feed = MarketFeed()
    for tf, f in fwd.items():
        feed.ingest(tf, f)

    rp = MarketReplay(feed, ltf="M15")
    t1 = time.perf_counter()
    res = rp.run()
    dt = time.perf_counter() - t1
    print(f"[run] {dt:.2f}s ({dt/max(1,n):.4f}s/vela) velas={n}", flush=True)

    # Las senales reales (setups completos) viven en res.signals (lista de dicts).
    # Un setup real tiene direction != 0 y entry presente.
    signals = res.signals or []
    setups = [s for s in signals if s.get("direction") not in (0, None) and s.get("entry") is not None]

    # Eventos del journal (cadena causal) para contexto.
    try:
        n_journal = len(list(res.journal))
    except Exception:
        n_journal = -1

    muestra = []
    for s in setups[:10]:
        muestra.append({
            "time": str(s.get("time")),
            "direction": s.get("direction"),
            "entry": s.get("entry"),
            "bos_level": s.get("bos_level"),
            "sweep_at": s.get("sweep_at"),
            "bos_at": s.get("bos_at"),
            "entry_at": s.get("entry_at"),
        })

    out = {
        "symbol": args.symbol,
        "n_velas": n,
        "run_s": round(dt, 3),
        "seg_por_vela": round(dt / max(1, n), 4),
        "n_senales_total": len(signals),
        "n_setups_reales": len(setups),
        "n_eventos_journal": n_journal,
        "setups_muestra": muestra,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

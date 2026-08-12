"""market_replay/inspect_real.py — Auditoría de LECTURA contra datos reales.

REAL-MARKET-REPLAY / AUDITORÍA DE LECTURA (puerta 6 del roadmap).

Carga EURUSD real desde data/raw, reproduce el mercado vela-a-vela con
market_replay (UNA pasada incremental) y, POR CADA SETUP que el motor forma,
emite un Readout restaurado desde el journal (que ya guarda el snapshot de
estado del motor por paso):

    CONOCIDO  (velas HTF ya cerradas hasta ese instante)
    LECTURA   (cadena causal LIQUIDITY->...->CONTRACT con MarketObjects)

REGLA DE ORO: el auditor NO evalúa si la señal ganó. Nada de WR/PF/expectancy/
edge/profit. Solo reporta "qué vio el motor" y "qué hizo con lo que vio"
(eventos), sin mirar ninguna vela posterior (cerrado por closed-only + la
auditoría temporal/MTF ya superada).

market_replay -> engine.data_feed / engine.sequence / engine.market_object
market_replay -> ict_backtest  PROHIBIDO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.sequence import SequenceState
from engine.data_feed import load_frames
from market_replay.feed import MarketFeed
from market_replay.availability import TemporalAvailability
from market_replay.replay import MarketReplay
from market_replay.readout import ReadoutFormatter, KnownFrame

TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")
# Para la auditoría de LECTURA de formación usamos la cadena de 4 TFs
# (D1/H4/H1/M15): M5/M1 son refinamiento LTF y encarecen el motor sin cambiar
# la formación ICT. Esto acelera el barrido sobre datos reales.
_READ_CHAIN = ("D1", "H4", "H1", "M15")
_SETUP_EVENT_FIELDS = (
    "sweep_id",
    "bos_id",
    "poi_id",
    "refinement_id",
    "entry_id",
    "contract_id",
)


def _available_tf_chain(ltf: str) -> tuple[str, ...]:
    idx = _READ_CHAIN.index(ltf) if ltf in _READ_CHAIN else len(_READ_CHAIN) - 1
    return _READ_CHAIN[: idx + 1] or _READ_CHAIN


def run_real_audit(
    symbol: str = "EURUSD",
    ltf: str = "M15",
    limit: int = 0,
    max_setups: int = 0,
    data_dir=None,
    chunk_size: int = 1200,
    max_chunks: int = 60,
) -> list[dict]:
    """Corre la auditoría y devuelve la lista de readouts (dicts).

    Estrategia anti-timeout: en lugar de procesar todo el dataset de una vez
    (lento sobre 114k velas), barre en CHUNKS pequeños de `chunk_size` velas
    hasta acumular `max_setups` setups o agotar `max_chunks`. Cada chunk es
    incremental y rapido. Asi la auditoria de LECTURA encuentra los primeros
    setups reales del motor sobre EURUSD historico sin colgarse.
    """
    tfs = _available_tf_chain(ltf)
    frames_all = load_frames(symbol, tfs, **({"data_dir": data_dir} if data_dir else {}))
    if ltf not in frames_all or len(frames_all[ltf]) == 0:
        raise RuntimeError(f"{symbol} {ltf} no disponible en data/raw")
    m15 = frames_all[ltf]
    total = len(m15)
    if limit:
        total = min(total, limit)

    readouts: list[dict] = []
    setups = 0
    chunks_done = 0
    start = 0

    while start < total and chunks_done < max_chunks and setups < (max_setups or 10**9):
        end = min(start + chunk_size, total)
        last = m15["time"].iloc[end - 1]
        frames = {tf: frames_all[tf][frames_all[tf]["time"] <= last].reset_index(drop=True) for tf in tfs}
        # Recorta cada TF al chunk relevante (el motor lee ventana creciente).
        feed = MarketFeed()
        for tf, f in frames.items():
            feed.ingest(tf, f)
        rp = MarketReplay(feed, ltf=ltf)
        res = rp.run()
        avail = TemporalAvailability({tf: feed.window(tf) for tf in feed.available_tfs()}, ltf)
        fmt = ReadoutFormatter()
        prev_ids: set[str] = set()
        for je in res.journal:
            sd = getattr(je, "state_snapshot", None) or {}
            st = SequenceState.from_snapshot(sd) if sd else None
            if st is None:
                continue
            cur = {getattr(st, f, "") for f in _SETUP_EVENT_FIELDS if getattr(st, f, "")}
            if cur - prev_ids:
                known = _known_at(avail, je.timestamp)
                ro = fmt.format(st, je.timestamp, je.timeframe, je.candle_index, htf_snapshot=known)
                readouts.append(ro.to_dict())
                setups += 1
                if max_setups and setups >= max_setups:
                    break
            prev_ids = cur
        chunks_done += 1
        start = end

    return readouts


def _known_at(avail: TemporalAvailability, t) -> dict:
    try:
        snap = avail.snapshot(t, include_ltf=False)
    except Exception:
        return {}
    return snap


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="inspect_real", description="Auditoría de lectura vs datos reales")
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--ltf", default="M15")
    p.add_argument("--limit", type=int, default=20000)
    p.add_argument("--max-setups", type=int, default=20)
    p.add_argument("--chunk-size", type=int, default=1200)
    p.add_argument("--max-chunks", type=int, default=60)
    p.add_argument("--data-dir", default=None)
    p.add_argument("--json", action="store_true", help="emitir JSON en vez de reporte legible")
    args = p.parse_args(argv)

    try:
        readouts = run_real_audit(
            args.symbol, args.ltf, args.limit,
            max_setups=args.max_setups,
            data_dir=Path(args.data_dir) if args.data_dir else None,
            chunk_size=args.chunk_size,
            max_chunks=args.max_chunks,
        )
    except RuntimeError as e:
        print(f"[inspect_real] {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(readouts, default=str))
    else:
        for ro in readouts:
            _print_readout(ro)
    return 0


def _print_readout(ro: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"{ro['timestamp']}  [{ro['ltf']} #{ro['candle_index']}]")
    print("CONOCIDO:")
    for k in ro.get("known", []):
        print(f"  {k['tf']:>3}  H={k['high']} L={k['low']} C={k['close']}")
    print("LECTURA:")
    for e in ro["events"]:
        lvl = e["zone_low"] if e["zone_low"] == e["zone_low"] else float("nan")
        hlv = e["zone_high"] if e["zone_high"] == e["zone_high"] else float("nan")
        print(
            f"  {e['order']}. {e['event_type']:<11} {e['origin_tf']:<2} "
            f"{e['role']:<11} dir={e['direction']:+d} "
            f"[{hlv},{lvl}] parent={e['parent_object']}"
        )
    print(f"HTF aligned={ro['htf_aligned']} ({ro['htf_reason']})")


if __name__ == "__main__":
    raise SystemExit(main())

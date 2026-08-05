"""Pre-cachea el context de build_scalping_context por simbolo a disco (pickle).
Evita reconstruir 22-40s por cada reintento del driver (el launcher mata a ~55s).
Uso: python _precache.py --symbol EURUSD   (o sin --symbol para los 8)

Instrumentacion: escribe results/edge_diagnosis/precache_progress.json tras cada
simbolo (mismo patron que run.py / edge_diagnosis progress.json).
"""
import sys
import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent  # SMC-SYSTEMS
sys.path.insert(0, str(ROOT))
import data as _d
_orig = _d.load_frame
_d.load_frame = lambda dd, sym, tf, auto_download=True, max_stale_hours=None: _orig(dd, sym, tf, auto_download=False)

from signals import build_scalping_context, ScalpingConfig
import pickle

DATA_DIR = ROOT / "data" / "raw"

SYMBOLS_FULL = ["EURUSD", "AUDUSD", "NZDUSD", "USDCAD", "XAUUSD"]
SYMBOLS_SHORT = ["GBPUSD", "USDCHF", "USDJPY"]
ALL = SYMBOLS_FULL + SYMBOLS_SHORT
TIMEFRAME = "M15"

PROGRESS_PATH = ROOT / "results" / "edge_diagnosis" / "precache_progress.json"
HANG_STALE_SECONDS = 300


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _write_progress(payload: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def emit(done: int, total: int, *, status: str, current: str | None,
         started_at: str, t_start: float, errors: list[dict]) -> None:
    elapsed = time.time() - t_start
    avg = (elapsed / done) if done > 0 else None
    remaining = total - done
    eta_left = (avg * remaining) if avg is not None else None
    eta_at = None
    if eta_left is not None:
        eta_at = (datetime.now().astimezone().replace(microsecond=0)
                  + timedelta(seconds=eta_left)).isoformat()
    payload = {
        "task": "precache",
        "status": status,
        "total_units": total,
        "done_units": done,
        "percent": round(done / total * 100, 1) if total else 0.0,
        "current_symbol": current,
        "current_variant": None,
        "started_at": started_at,
        "updated_at": _iso_now(),
        "elapsed_seconds": round(elapsed, 1),
        "avg_seconds_per_unit": round(avg, 2) if avg is not None else None,
        "eta_seconds_remaining": round(eta_left, 1) if eta_left is not None else None,
        "eta_at": eta_at,
        "hang_stale_seconds": HANG_STALE_SECONDS,
        "errors": errors,
    }
    if status == "done":
        payload["current_symbol"] = None
        payload["percent"] = 100.0
        payload["eta_seconds_remaining"] = 0
        payload["eta_at"] = _iso_now()
    try:
        _write_progress(payload)
    except Exception as wexc:
        print(f"[WARN precache progress] {wexc}", flush=True)


def precache(symbol: str):
    cache_dir = ROOT / "results" / "edge_diagnosis" / "_ctx"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = cache_dir / f"{symbol}.pkl"
    if cpath.exists():
        print(f"[precache] {symbol} ya cacheado, skip", flush=True)
        return
    print(f"[precache] construyendo {symbol}...", flush=True)
    ctx = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR,
                                 config=ScalpingConfig(), orchestrator=None)
    with open(cpath, "wb") as f:
        pickle.dump(ctx, f)
    print(f"[precache] {symbol} guardado: {len(ctx)} bars", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", nargs="*", default=None,
                    help="uno o varios simbolos; omitir para los 8")
    args = ap.parse_args()
    syms = args.symbol if args.symbol else ALL
    total = len(syms)
    started_at = _iso_now()
    t_start = time.time()
    errors: list[dict] = []
    done = 0
    emit(done, total, status="running", current=syms[0] if syms else None,
         started_at=started_at, t_start=t_start, errors=errors)
    for s in syms:
        try:
            precache(s)
        except Exception as exc:
            import traceback as _tb
            print(f"[precache][ERROR] {s}: {exc}", flush=True)
            print(_tb.format_exc(), flush=True)
            errors.append({"symbol": s, "variant": None, "error": str(exc)})
        done += 1
        emit(done, total, status="running", current=(syms[done] if done < total else None),
             started_at=started_at, t_start=t_start, errors=errors)
    emit(done, total, status="done", current=None,
         started_at=started_at, t_start=t_start, errors=errors)
    print("[precache] FIN", flush=True)

"""Pre-cachea contextos de variantes DETECTOR_AFFECTING (prox_1/2/3, mc_1/3/4, w0_sweep, w0_ote)
por simbolo a disco. El build de estas variantes tarda 22-70s (prox_3 ~70s), asi que se
cachean una vez y el driver las lee en <1s. Con checkpoint: si el launcher mata el proceso,
al relanzar continúa desde donde quedó.

Uso:
  python _precache_variants.py            # todas las variantes x simbolos (con checkpoint)
  python _precache_variants.py --symbol EURUSD   # solo un simbolo
"""
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import data as _d
_orig = _d.load_frame
_d.load_frame = lambda dd, sym, tf, auto_download=True, max_stale_hours=None: _orig(dd, sym, tf, auto_download=False)

from signals import build_scalping_context, ScalpingConfig
DATA_DIR = ROOT / "data" / "raw"
import pickle

SYMBOLS_FULL = ["EURUSD", "AUDUSD", "NZDUSD", "USDCAD", "XAUUSD"]
SYMBOLS_SHORT = ["GBPUSD", "USDCHF", "USDJPY"]
ALL = SYMBOLS_FULL + SYMBOLS_SHORT
TIMEFRAME = "M15"

from scripts.edge_diagnosis.run import all_variants, build_config  # noqa
DET = [v for v in all_variants() if ({"ob_fvg_proximity_atr", "enable_sweep_filter", "enable_ote_filter"} & set(v.config_overrides.keys()))]


def precache(symbol: str, variant_key: str):
    cache_dir = ROOT / "results" / "edge_diagnosis" / "_ctx"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = cache_dir / f"{symbol}__{variant_key}.pkl"
    if cpath.exists():
        print(f"[precache] {symbol}/{variant_key} ya cacheado, skip", flush=True)
        return
    v = next(x for x in DET if x.key == variant_key)
    cfg = build_config(v)
    print(f"[precache] construyendo {symbol}/{variant_key}...", flush=True)
    ctx = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
    with open(cpath, "wb") as f:
        pickle.dump(ctx, f)
    print(f"[precache] {symbol}/{variant_key} guardado: {len(ctx)} bars", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()
    syms = [args.symbol] if args.symbol else ALL
    n = 0
    for s in syms:
        for v in DET:
            precache(s, v.key)
            n += 1
    print(f"[precache] FIN ({n} contextos detector_affecting)", flush=True)

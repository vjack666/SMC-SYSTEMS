"""Rebuild M5/M15/H1 (and optional H4/D1) parquets from existing M1.

R5 helper: when HistData M1 already covers 3-4+ years but MT5 capped M15 at
~50k bars (~2y), rebuild LTF/ITF from local M1 without re-download.

Does NOT overwrite H4/D1 by default (those often have longer MT5 history).

Usage:
  python scripts/rebuild_tf_from_m1.py --symbols EURUSD XAUUSD
  python scripts/rebuild_tf_from_m1.py --symbols EURUSD --tfs M5 M15 H1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_RESAMPLE = {
    "M5": "5min",
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}


def _normalize_m1(df: pd.DataFrame) -> pd.DataFrame:
    if "time" not in df.columns:
        # index-based
        if str(df.index.dtype).startswith("datetime"):
            df = df.reset_index()
            if "index" in df.columns and "time" not in df.columns:
                df = df.rename(columns={"index": "time"})
        else:
            raise ValueError("M1 parquet needs a time column")
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        if c not in df.columns:
            raise ValueError(f"M1 missing column {c}")
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = df["tick_volume"] if "tick_volume" in df.columns else 0
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time")
    return df.reset_index(drop=True)


def _resample(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = m1.set_index("time").sort_index()
    ohlc = x.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    ohlc = ohlc.dropna(subset=["open", "high", "low", "close"]).reset_index()
    ohlc["tick_volume"] = ohlc["volume"]
    return ohlc


def rebuild(symbol: str, raw: Path, tfs: list[str]) -> dict:
    path_m1 = raw / f"{symbol}_M1.parquet"
    if not path_m1.exists() or path_m1.stat().st_size < 1000:
        return {"symbol": symbol, "ok": False, "error": f"missing {path_m1.name}"}
    m1 = _normalize_m1(pd.read_parquet(path_m1))
    out = {
        "symbol": symbol,
        "ok": True,
        "M1": len(m1),
        "M1_range": f"{m1['time'].min()} -> {m1['time'].max()}",
        "files": [],
    }
    print(f"=== {symbol} M1 n={len(m1):,}  {m1['time'].min()} -> {m1['time'].max()}", flush=True)
    for tf in tfs:
        rule = _RESAMPLE.get(tf)
        if not rule:
            print(f"  [SKIP] unknown TF {tf}", flush=True)
            continue
        r = _resample(m1, rule)
        path = raw / f"{symbol}_{tf}.parquet"
        r.to_parquet(path, index=False)
        out[tf] = len(r)
        out["files"].append(path.name)
        years = (r["time"].max() - r["time"].min()).days / 365.25
        print(
            f"  [OK] {path.name} n={len(r):,}  "
            f"{r['time'].min()} -> {r['time'].max()}  ~{years:.2f}y",
            flush=True,
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild TFs from local M1 parquet")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "XAUUSD"])
    ap.add_argument(
        "--tfs",
        nargs="+",
        default=["M5", "M15", "H1"],
        help="TFs to rebuild (default M5 M15 H1; avoid H4/D1 unless intended)",
    )
    ap.add_argument("--raw", type=str, default="data/raw")
    args = ap.parse_args()
    raw = Path(args.raw)
    results = []
    for sym in args.symbols:
        results.append(rebuild(sym.upper(), raw, [t.upper() for t in args.tfs]))
    print("\n===== SUMMARY =====", flush=True)
    for r in results:
        print(r, flush=True)
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

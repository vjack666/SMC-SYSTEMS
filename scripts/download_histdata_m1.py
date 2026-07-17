"""Download free multi-year M1 from HistData.com and build TF parquets.

HistData: M1 (and tick) free. We download M1, save parquet, resample to
M5/M15/H1/H4/D1 for SMC-SYSTEMS (data/raw/{SYMBOL}_{TF}.parquet).

Requires: pip install histdata pandas pyarrow

Example:
  python scripts/download_histdata_m1.py --symbols EURUSD XAUUSD --from-year 2022
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from histdata import download_hist_data as dl
from histdata.api import Platform, TimeFrame

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


def _parse_ascii_csv(text: str) -> pd.DataFrame:
    # YYYYMMDD HHMMSS;O;H;L;C;V
    df = pd.read_csv(
        io.StringIO(text),
        sep=";",
        header=None,
        names=["datetime", "open", "high", "low", "close", "volume"],
    )
    df["time"] = pd.to_datetime(df["datetime"], format="%Y%m%d %H%M%S", utc=True)
    df = df.drop(columns=["datetime"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time")


def _download_pair_year(pair: str, year: int, month: int | None, tmp: Path) -> Path | None:
    pair_l = pair.lower()
    try:
        fn = dl(
            year=str(year),
            month=str(month) if month is not None else None,
            pair=pair_l,
            time_frame=TimeFrame.ONE_MINUTE,
            platform=Platform.GENERIC_ASCII,
            output_directory=str(tmp),
        )
        return Path(fn)
    except Exception as e:
        print(f"  [WARN] {pair} {year}-{month}: {e}", flush=True)
        return None


def _load_zip_csv(zpath: Path) -> pd.DataFrame:
    parts = []
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if not name.lower().endswith(".csv"):
                continue
            text = z.read(name).decode("utf-8", errors="replace")
            parts.append(_parse_ascii_csv(text))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _resample_ohlc(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
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
    return ohlc


def download_symbol(
    symbol: str,
    from_year: int,
    to_year: int,
    out_dir: Path,
    tmp: Path,
) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    now = datetime.now(timezone.utc)
    years = list(range(from_year, to_year + 1))

    for year in years:
        if year < now.year:
            print(f"  [{symbol}] M1 year {year} ...", flush=True)
            z = _download_pair_year(symbol, year, None, tmp)
            if z and z.exists():
                df = _load_zip_csv(z)
                print(f"       +{len(df):,} bars", flush=True)
                if len(df):
                    frames.append(df)
        else:
            # current year: month by month
            for month in range(1, now.month + 1):
                print(f"  [{symbol}] M1 {year}-{month:02d} ...", flush=True)
                z = _download_pair_year(symbol, year, month, tmp)
                if z and z.exists():
                    df = _load_zip_csv(z)
                    print(f"       +{len(df):,} bars", flush=True)
                    if len(df):
                        frames.append(df)

    if not frames:
        return {"symbol": symbol, "ok": False, "error": "no data"}

    m1 = pd.concat(frames, ignore_index=True)
    m1 = m1.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    # optional tick_volume alias for MT5-style consumers
    if "tick_volume" not in m1.columns:
        m1["tick_volume"] = m1["volume"]

    out_dir.mkdir(parents=True, exist_ok=True)
    path_m1 = out_dir / f"{symbol}_M1.parquet"
    m1.to_parquet(path_m1, index=False)
    print(f"  [OK] {path_m1.name} n={len(m1):,}  {m1['time'].min()} -> {m1['time'].max()}", flush=True)

    stats = {"symbol": symbol, "ok": True, "M1": len(m1), "files": [path_m1.name]}
    for tf, rule in _RESAMPLE.items():
        r = _resample_ohlc(m1, rule)
        if "tick_volume" not in r.columns and "volume" in r.columns:
            r["tick_volume"] = r["volume"]
        path = out_dir / f"{symbol}_{tf}.parquet"
        r.to_parquet(path, index=False)
        stats[tf] = len(r)
        stats["files"].append(path.name)
        print(
            f"  [OK] {path.name} n={len(r):,}  {r['time'].min()} -> {r['time'].max()}",
            flush=True,
        )
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="HistData free M1 -> multi-TF parquets")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "XAUUSD"])
    ap.add_argument("--from-year", type=int, default=2022)
    ap.add_argument("--to-year", type=int, default=datetime.now(timezone.utc).year)
    ap.add_argument("--output", type=str, default="data/raw")
    ap.add_argument("--tmp", type=str, default="data/histdata_tmp")
    args = ap.parse_args()

    out = Path(args.output)
    tmp = Path(args.tmp)
    print(
        f"HistData free download M1 {args.from_year}->{args.to_year} "
        f"symbols={args.symbols}",
        flush=True,
    )
    print("Note: free third-party data (not FundedNext). Times in UTC.", flush=True)

    results = []
    for sym in args.symbols:
        print(f"\n=== {sym} ===", flush=True)
        results.append(
            download_symbol(sym, args.from_year, args.to_year, out, tmp / sym)
        )

    print("\n===== SUMMARY =====", flush=True)
    for r in results:
        print(r, flush=True)


if __name__ == "__main__":
    main()

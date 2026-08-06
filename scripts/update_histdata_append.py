"""Append reciente de M1 desde HistData y resamplea solo los TF pedidos.

Diferencia con download_histdata_m1.py: ese REESCRIBE todos los parquet desde
`--from-year` (pierde historico previo si usas un año reciente, o baja millones
de barras si usas 2022). Este script hace APPEND incremental y QUIRURGICO:

  1. Lee el M1 existente en data/raw/<SYM>_M1.parquet.
  2. Descarga solo los meses POSTERIORES a su ultima fecha (desde HistData).
  3. Concatena, dedup por timestamp, y resamplea SOLO los TF pedidos
     (por defecto M1 M5) -> escribe esos parquet y nada mas.

Asi se actualizan M1/M5 sin tocar M15/H1/H4/D1 (que pueden venir de MT5 y ya
estar al dia). No pierde el historico 2022-2025.

Ejemplo:
  python scripts/update_histdata_append.py --symbols EURUSD
  python scripts/update_histdata_append.py --symbols EURUSD XAUUSD --tfs M1 M5

Nota: HistData gratis suele retrasar 1-2 dias el mes en curso; si el mes
actual no esta disponible, se appendea hasta el ultimo mes completo.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.download_histdata_m1 as base  # reusa parsers/descargador

_RESAMPLE = base._RESAMPLE  # M5..D1


def _last_month_present(m1_path: Path) -> tuple[int, int] | None:
    if not m1_path.exists():
        return None
    df = pd.read_parquet(m1_path)
    if df.empty:
        return None
    t = pd.to_datetime(df["time"], utc=True)
    last = t.max()
    return last.year, last.month


def append_symbol(symbol: str, tfs: list[str], out_dir: Path, tmp: Path) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    m1_path = out_dir / f"{symbol}_M1.parquet"

    # 1) M1 existente
    if m1_path.exists():
        m1_old = pd.read_parquet(m1_path)
        print(f"  [{symbol}] M1 existente n={len(m1_old):,} "
              f"hasta {m1_old['time'].max()}", flush=True)
    else:
        m1_old = pd.DataFrame()
        print(f"  [{symbol}] M1 no existe, se descargara desde 2022", flush=True)

    # 2) Determinar meses faltantes
    last = _last_month_present(m1_path)
    now = datetime.now(timezone.utc)
    if last is None:
        years_months = [(y, m) for y in range(2022, now.year + 1)
                        for m in range(1, 13)]
    else:
        ly, lm = last
        # siguiente mes al ultimo presente
        start = (ly, lm + 1) if lm < 12 else (ly + 1, 1)
        years_months = []
        y, m = start
        while (y, m) <= (now.year, now.month):
            years_months.append((y, m))
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1

    if not years_months:
        print(f"  [{symbol}] ya esta al dia (M1). Nada que appendear.", flush=True)
        return {"symbol": symbol, "ok": True, "appended": 0, "skipped": True}

    print(f"  [{symbol}] meses a appendear: "
          f"{years_months[0]} .. {years_months[-1]}", flush=True)

    # 3) Descargar meses faltantes
    frames: list[pd.DataFrame] = []
    for y, m in years_months:
        z = base._download_pair_year(symbol, y, m, tmp / symbol)
        if z and Path(z).exists():
            df = base._load_zip_csv(Path(z))
            if len(df):
                frames.append(df)
                print(f"       +{y}-{m:02d}: {len(df):,} barras", flush=True)

    if not frames:
        print(f"  [{symbol}] ningun mes nuevo disponible aun en HistData.", flush=True)
        return {"symbol": symbol, "ok": True, "appended": 0, "no_new": True}

    new_m1 = pd.concat(frames, ignore_index=True)
    # 4) Concatenar + dedup
    if len(m1_old):
        combined = pd.concat([m1_old, new_m1], ignore_index=True)
    else:
        combined = new_m1
    combined = (combined.drop_duplicates(subset=["time"], keep="last")
                .sort_values("time").reset_index(drop=True))

    if "tick_volume" not in combined.columns and "volume" in combined.columns:
        combined["tick_volume"] = combined["volume"]

    combined.to_parquet(m1_path, index=False)
    print(f"  [OK] {m1_path.name} n={len(combined):,}  "
          f"{combined['time'].min()} -> {combined['time'].max()}", flush=True)

    stats = {"symbol": symbol, "ok": True,
             "M1_total": len(combined),
             "M1_new": len(new_m1)}

    # 5) Resamplear SOLO los TF pedidos (no todos)
    for tf in tfs:
        if tf == "M1":
            continue  # ya escrito
        if tf not in _RESAMPLE:
            print(f"  [SKIP] TF desconocido: {tf}", flush=True)
            continue
        r = base._resample_ohlc(combined, _RESAMPLE[tf])
        if "tick_volume" not in r.columns and "volume" in r.columns:
            r["tick_volume"] = r["volume"]
        path = out_dir / f"{symbol}_{tf}.parquet"
        r.to_parquet(path, index=False)
        stats[tf] = len(r)
        print(f"  [OK] {path.name} n={len(r):,}  "
              f"{r['time'].min()} -> {r['time'].max()}", flush=True)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Append M1 HistData + resample TF pedidos")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD"])
    ap.add_argument("--tfs", nargs="+", default=["M1", "M5"],
                    help="TF a regenerar tras appendear M1 (no se tocan los demas)")
    ap.add_argument("--output", type=str, default="data/raw")
    ap.add_argument("--tmp", type=str, default="data/histdata_tmp")
    args = ap.parse_args()

    out = Path(args.output)
    tmp = Path(args.tmp)
    print(f"Append HistData -> {args.output} symbols={args.symbols} tfs={args.tfs}",
          flush=True)
    results = []
    for sym in args.symbols:
        print(f"\n=== {sym} ===", flush=True)
        results.append(append_symbol(sym, args.tfs, out, tmp / sym))

    print("\n===== SUMMARY =====", flush=True)
    for r in results:
        print(r, flush=True)


if __name__ == "__main__":
    main()

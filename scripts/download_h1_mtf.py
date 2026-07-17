"""Descarga H1 desde MT5 (MetaQuotes-Demo) para los pares que NO tienen H1 local.

Cubre el MISMO rango que el M5 ya disponible: 2026-01-18 -> hoy (~6 meses).
MT5 demo rechaza rangos > ~30 dias (-2 Invalid params), asi que baja en
ventanas de 30 dias deslizandose hacia adelante y acumula.

Pares objetivo (sin H1 en data/raw): GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF.
EURUSD y XAUUSD ya tienen H1 -> se saltan.

Reusa el formato de columnas de _data_legacy._download_frame para parquet compatible.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path("data/raw")
# Mismos campos y orden que _data_legacy._download_frame
COLS = ["time", "open", "high", "low", "close", "tick_volume", "spread"]

TARGETS = ["GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]
SINCE = datetime(2026, 1, 18)  # fecha de inicio del M5 disponible
STEP = 25  # dias (dejamos margen bajo el limite de 30d del broker)


def download_h1(symbol: str) -> int:
    end = datetime.now()
    start = SINCE
    rows: list = []
    cursor = start
    guard = 0
    while cursor < end and guard < 300:
        guard += 1
        win_end = min(cursor + timedelta(days=STEP), end)
        block = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, cursor, win_end)
        if block is not None and len(block) > 0:
            # evitar solapamiento: solo velas con time > ultima ya tenida
            seen = rows[-1][0] if rows else -1
            for r in block:
                if r[0] > seen:
                    rows.append(tuple(r))
        cursor = win_end
    if not rows:
        print(f"  [!] {symbol}: 0 velas H1")
        return 0
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close",
                                     "tick_volume", "spread", "real_volume"])
    df = df[COLS].copy()
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"{symbol}_H1.parquet"
    df.to_parquet(out, index=False)
    print(f"  [OK] {symbol} H1: {len(df)} velas -> {out} "
          f"({df['time'].min().date()}..{df['time'].max().date()})")
    return len(df)


def main() -> int:
    if not mt5.initialize():
        print(f"[!] initialize fallo: {mt5.last_error()}")
        return 3
    acc = mt5.account_info()
    print(f"[*] Cuenta {acc.login} server={acc.server}")
    print(f"[*] Descargando H1 {SINCE.date()}..hoy para: {', '.join(TARGETS)}\n")
    total = 0
    for sym in TARGETS:
        if mt5.symbol_info(sym) is None:
            print(f"  [!] {sym}: NOT FOUND")
            continue
        total += download_h1(sym)
    mt5.shutdown()
    print(f"\n[*] Total velas H1 descargadas: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

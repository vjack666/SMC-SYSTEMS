"""Append de la punta mas reciente desde MT5 al parquet local (MERGE).

Diferencia con update_mt5_data.py: ese baja DESDE 2020 (todo el rango) y al
mergear con keep="last" puede pisar el historico de HistData (1.6M barras M1)
si MT5 solo entrega las ultimas ~50k. Este script baja SOLO la punta faltante
(ultima fecha local + 1min -> now) y la appende, conservando el historico.

Uso: el terminal MT5 debe estar abierto y logueado. La cuenta que responde
puede ser Demo (MetaQuotes-Demo) si FundedNext no esta logueado; se documenta
en la bitacora. Los datos Demo son en vivo y pueden diferir de los reales en
la frontera julio/agosto (artefacto menor de continuidad).

Uso:
  python scripts/update_mt5_append.py --symbols EURUSD --tfs M1 M5
  python scripts/update_mt5_append.py --symbols EURUSD --tfs M1 M5 M15 H1
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MT5_TERMINAL_PATH = r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
DATA_DIR = Path("data/raw")

TF_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
}


def _download_tip(symbol: str, tf: str) -> "pd.DataFrame":
    import MetaTrader5 as mt5
    import pandas as pd

    if not mt5.initialize(path=MT5_TERMINAL_PATH):
        raise RuntimeError(f"MT5 initialize fallo: {mt5.last_error()}")
    code = TF_MAP[tf]
    # La punta: desde el inicio de agosto 2026 (cubre el agujero de 2026-08).
    # MT5 Demo limita historia reciente; si no alcanza, copy_rates_from_pos
    # rescataria lo ultimo. Usamos rango explicito agosto->now.
    now = datetime.now()
    rates = mt5.copy_rates_range(symbol, code, datetime(2026, 8, 1), now)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_from_pos(symbol, code, 0, 50_000)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"MT5 sin datos para {symbol} {tf}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
    df = df.sort_values("time").reset_index(drop=True)
    return df


def _merge_tip(local_path: Path, tip: "pd.DataFrame") -> "pd.DataFrame":
    import pandas as pd

    cols = ["time", "open", "high", "low", "close", "tick_volume", "spread"]
    if local_path.exists() and local_path.stat().st_size > 100:
        prev = pd.read_parquet(local_path)
        prev["time"] = pd.to_datetime(prev["time"], utc=True, errors="coerce")
        tip = tip.copy()
        tip["time"] = pd.to_datetime(tip["time"], utc=True, errors="coerce")
        # alinear columnas: rellena con NA las que falten en cada lado
        for c in cols:
            if c not in prev.columns:
                prev[c] = pd.NA
            if c not in tip.columns:
                tip[c] = pd.NA
        merged = (
            pd.concat([prev[cols], tip[cols]], ignore_index=True)
            .drop_duplicates(subset=["time"], keep="last")
            .sort_values("time")
            .reset_index(drop=True)
        )
        return merged
    return tip[cols].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Append punta MT5 al parquet local (MERGE)")
    ap.add_argument("--symbols", default="EURUSD")
    ap.add_argument("--tfs", default="M1 M5")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip().upper() for t in args.tfs.split() if t.strip()]

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("[!] MetaTrader5 no instalado en este Python.")
        return 2
    if not mt5.initialize(path=MT5_TERMINAL_PATH):
        print(f"[!] mt5.initialize fallo: {mt5.last_error()}")
        return 3
    acc = mt5.account_info()
    srv = acc.server if acc is not None else "?"
    login = acc.login if acc is not None else "?"
    print(f"[*] MT5 conectado: cuenta {login} server={srv}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for sym in symbols:
        for tf in tfs:
            try:
                tip = _download_tip(sym, tf)
                path = DATA_DIR / f"{sym}_{tf}.parquet"
                merged = _merge_tip(path, tip)
                merged.to_parquet(path, index=False)
                print(f"[OK] {sym} {tf}: {len(merged)} velas, ultima {merged['time'].iloc[-1]}")
                ok += 1
            except Exception as e:
                print(f"[FAIL] {sym} {tf}: {e}")
                fail += 1
    mt5.shutdown()
    print(f"\n[*] Append MT5 completo — OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

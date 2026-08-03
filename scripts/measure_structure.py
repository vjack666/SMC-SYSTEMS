"""T9 — Backtest runner de BOS/CHOCH.

Consumo:
- Carga M15 desde validate_m15_parquet().
- Resamplea a H4.
- Llama a engine.bos.structure.detect_market_structure().
- Emite métricas de BOS/CHOCH y trend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from engine.bos.structure import StructureConfig, detect_market_structure
from ict_backtest.sesgo.reloj.datos import validate_m15_parquet


REPO_ROOT = Path(__file__).resolve().parent.parent


def _resample_to_h4(df: pd.DataFrame) -> pd.DataFrame:
    o = df["open"].resample("4h", label="left", closed="left").first()
    h = df["high"].resample("4h", label="left", closed="left").max()
    l = df["low"].resample("4h", label="left", closed="left").min()
    c = df["close"].resample("4h", label="left", closed="left").last()
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()


def run_structure(symbol: str = "EURUSD", max_bars: int = 2000) -> dict:
    validated = validate_m15_parquet(symbol)
    m15_df = validated.df.sort_index()
    if max_bars and max_bars > 0:
        m15_df = m15_df.iloc[:max_bars]
    frame = _resample_to_h4(m15_df)
    config = StructureConfig(swing_lookback=5, confirm_bars=2)
    ms = detect_market_structure(frame, config)
    d = ms.frame
    return {
        "symbol": symbol.upper(),
        "timeframe": "H4",
        "max_bars": max_bars,
        "total_bars": len(d),
        "bos_bullish": int((d["bos_dir"] == 1).sum()),
        "bos_bearish": int((d["bos_dir"] == -1).sum()),
        "choch_bullish": int((d["choch_dir"] == 1).sum()),
        "choch_bearish": int((d["choch_dir"] == -1).sum()),
        "bos_active": int((d["bos_status"] == "active").sum()),
        "bos_invalidated": int((d["bos_status"] == "invalidated").sum()),
        "choch_active": int((d["choch_status"] == "active").sum()),
        "choch_invalidated": int((d["choch_status"] == "invalidated").sum()),
        "trend_bullish": int((d["trend"] == "BULLISH").sum()),
        "trend_bearish": int((d["trend"] == "BEARISH").sum()),
        "trend_ranging": int((d["trend"] == "RANGING").sum()),
    }


def main() -> int:
    symbol = os.environ.get("SMCS_STRUCTURE_SYMBOL", "EURUSD")
    max_bars = int(os.environ.get("SMCS_STRUCTURE_MAX_BARS", 2000))
    report = run_structure(symbol=symbol, max_bars=max_bars)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

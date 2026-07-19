from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import os
from datetime import datetime
from indicators import add_atr, add_ema, add_rsi, add_stochastic
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from detectors.displacement import detect_displacement
from detectors.zones import compute_zones
from ict_backtest.market_structure import StructureConfig, detect_market_structure
from agents.orchestrator import AgentOrchestrator


def download_cached(symbol: str, year: int, tf=mt5.TIMEFRAME_M15) -> pd.DataFrame | None:
    rates = mt5.copy_rates_range(symbol, tf, datetime(year, 1, 1), datetime(year, 12, 31))
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def build_dataset(symbol: str = "EURUSD", years: list[int] = [2023, 2024]) -> pd.DataFrame:
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed")

    frames = []
    for year in years:
        df = download_cached(symbol, year)
        if df is not None:
            frames.append(df)
            print(f"  {symbol} {year}: {len(df)} bars")
    mt5.shutdown()

    if not frames:
        raise RuntimeError("No data downloaded")

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

    # Forward labels
    fc = df["close"].shift(-12)
    df["direction"] = np.where(fc > df["close"], 1, np.where(fc < df["close"], -1, 0)).astype(int)
    df["pnl_r"] = (fc - df["close"]) / df["close"]
    df["win"] = (df["pnl_r"] > 0).astype(int)

    # Indicators
    df["atr"] = add_atr(df, 14)
    df["ema_fast"] = add_ema(df, 20)
    df["ema_slow"] = add_ema(df, 50)
    df["rsi"] = add_rsi(df, 14)
    df["atr_ratio"] = df["atr"] / df["atr"].rolling(20).mean().replace(0.0, np.nan)
    st = add_stochastic(df)
    df["stoch_k"] = st["stoch_k"]
    df["stoch_d"] = st["stoch_d"]

    df["macro_direction"] = "RANGING"
    df["d1_direction"] = "RANGING"
    df["trend_score"] = 0.0
    df["trend_confidence"] = 1.0
    df["regime_state"] = "NORMAL"

    # Detectores — estructura canonica (unica fuente de BOS/CHOCH)
    ms = detect_market_structure(df, StructureConfig(swing_lookback=5, confirm_bars=2, atr_period=14))
    df["bos_dir"] = ms["bos_dir"].astype(int).values
    df["choch_dir"] = ms["choch_dir"].astype(int).values
    df["bos_direction"] = ms["bos_dir"].map({1: "BULLISH", -1: "BEARISH"}).fillna("NONE").astype(str).values
    df["choch_signal"] = ms["choch_dir"].map({1: "CHOCH_BULLISH", -1: "CHOCH_BEARISH"}).fillna("NONE").astype(str).values
    df["bos_status"] = ms["bos_status"].where(ms["bos_dir"] != 0, "none").values
    df["choch_status"] = ms["choch_status"].values
    df = detect_fvg(df)
    df = detect_order_blocks(df)
    df = detect_displacement(df)
    df = compute_zones(df)

    # Orchestrator
    orch = AgentOrchestrator()
    df = orch.analyze_context(df)

    return df


if __name__ == "__main__":
    print("Building real EURUSD dataset from MT5 cache...")
    df = build_dataset("EURUSD", [2023, 2024])
    os.makedirs("data/ml/real", exist_ok=True)
    out = "data/ml/real/v4_EURUSD_2023_2024.parquet"
    df.to_parquet(out, index=False)
    wr = df["win"].mean()
    print(f"\nSaved: {out}")
    print(f"  Rows: {len(df):,}  Cols: {len(df.columns)}  WR: {wr:.1%}")

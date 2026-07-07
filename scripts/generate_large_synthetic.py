from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from signals.pipeline import add_indicators, add_risk_filters, compute_signals
from signals.config import ScalpingConfig
from detectors import detect_all
from agents.orchestrator import Orchestrator


def generate_multi_regime(
    n_bars: int = 10_000,
    seed: int = 42,
    start_price: float = 1.1000,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n1 = n_bars // 3
    n2 = n_bars // 3
    n3 = n_bars - n1 - n2

    prices = np.zeros(n_bars, dtype=float)
    prices[0] = start_price

    # regime 1: uptrend
    for i in range(1, n1):
        prices[i] = prices[i - 1] + 0.0003 + rng.normal(0.0, 0.002)

    # regime 2: downtrend
    for i in range(n1, n1 + n2):
        prices[i] = prices[i - 1] - 0.0003 + rng.normal(0.0, 0.002)

    # regime 3: ranging
    base = prices[n1 + n2 - 1]
    for i in range(n1 + n2, n_bars):
        prices[i] = base + rng.normal(0.0, 0.001)

    prices = np.maximum(prices, start_price * 0.85)
    # add some swings
    swing_idx = rng.integers(50, n_bars - 1, size=n_bars // 100)
    for idx in swing_idx:
        prices[idx:] += rng.choice([-1, 1]) * abs(rng.normal(0.0, 0.005))

    highs = prices + abs(rng.normal(0.0, 0.003, size=n_bars))
    lows = prices - abs(rng.normal(0.0, 0.003, size=n_bars))
    opens = np.zeros(n_bars, dtype=float)
    opens[0] = prices[0]
    for i in range(1, n_bars):
        opens[i] = prices[i - 1] + rng.normal(0.0, 0.001)

    times = pd.date_range("2022-01-01", periods=n_bars, freq="15min", tz="UTC")
    volume = rng.integers(100, 10000, size=n_bars)

    return pd.DataFrame({
        "time": times,
        "open": np.maximum(opens, start_price * 0.85),
        "high": np.maximum(highs, opens),
        "low": np.minimum(lows, opens),
        "close": prices,
        "tick_volume": volume,
    })


def add_forward_labels(df: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    df = df.copy()
    future_close = df["close"].shift(-horizon)
    df["direction"] = np.where(
        future_close > df["close"], 1,
        np.where(future_close < df["close"], -1, 0),
    ).astype(int)
    df["pnl_r"] = (future_close - df["close"]) / df["close"]
    df["win"] = (df["pnl_r"] > 0).astype(int)
    return df


def build_synthetic_dataset(n_bars: int = 10_000, seed: int = 42, horizon: int = 12) -> pd.DataFrame:
    df = generate_multi_regime(n_bars=n_bars, seed=seed)
    df = add_forward_labels(df, horizon=horizon)

    df = add_indicators(df)
    df = detect_all(df)
    df = add_risk_filters(df)

    cfg = ScalpingConfig()
    orch = Orchestrator(cfg)

    df = orch.analyze_context(df)
    df = compute_signals(df, config=cfg)

    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-bars", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--output", default="data/ml/synthetic/v4_synthetic.parquet")
    args = parser.parse_args()

    print(f"Generating {args.n_bars} bars (seed={args.seed}, horizon={args.horizon})...")
    df = build_synthetic_dataset(n_bars=args.n_bars, seed=args.seed, horizon=args.horizon)
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_parquet(args.output, index=False)
    print(f"Saved: {args.output}")
    print(f"  Rows: {len(df)}  Columns: {len(df.columns)}")
    print(f"  Win rate: {df['win'].mean():.3f}  Signal count: {(df['signal_direction'] != 0).sum()}")

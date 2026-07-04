from __future__ import annotations

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from indicators import add_atr, add_ema, add_rsi, add_stochastic
from agents.orchestrator import AgentOrchestrator
from detectors.bos import BosConfig, detect_bos
from detectors.choch import detect_choch
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from detectors.displacement import detect_displacement
from detectors.zones import compute_zones

def main():
    n = 10_000
    rng = np.random.default_rng(42)
    n1 = n // 3
    p = np.zeros(n)
    p[0] = 1.1
    for i in range(1, n1):
        p[i] = p[i-1] + 0.0003 + rng.normal(0, 0.002)
    for i in range(n1, 2*n1):
        p[i] = p[i-1] - 0.0003 + rng.normal(0, 0.002)
    for i in range(2*n1, n):
        p[i] = p[2*n1-1] + rng.normal(0, 0.001)
    p = np.maximum(p, 0.935)

    closes = p
    opens = np.array([p[0]] + list(p[:-1] + rng.normal(0, 0.001, n-1)))
    highs = p + abs(rng.normal(0, 0.003, n))
    lows = p - abs(rng.normal(0, 0.003, n))
    opens = np.maximum(opens, 0.935)

    df = pd.DataFrame({
        "time": pd.date_range("2022-01-01", periods=n, freq="15min", tz="UTC"),
        "open": opens, "high": highs, "low": lows, "close": closes,
        "tick_volume": rng.integers(100, 10000, n),
    })

    fc = df["close"].shift(-12)
    df["direction"] = np.where(fc > df["close"], 1, np.where(fc < df["close"], -1, 0)).astype(int)
    df["pnl_r"] = (fc - df["close"]) / df["close"]
    df["win"] = (df["pnl_r"] > 0).astype(int)

    df["atr"] = add_atr(df, 14)
    df["ema_fast"] = add_ema(df, 20)
    df["ema_slow"] = add_ema(df, 50)
    df["rsi"] = add_rsi(df, 14)
    st = add_stochastic(df)
    df["stoch_k"] = st["stoch_k"]
    df["stoch_d"] = st["stoch_d"]
    df["macro_direction"] = "RANGING"
    df["d1_direction"] = "RANGING"
    df["trend_score"] = 0.0
    df["trend_confidence"] = 1.0
    df["regime_state"] = "NORMAL"
    df["atr_ratio"] = df["atr"] / df["atr"].rolling(20).mean().replace(0.0, np.nan)

    df = detect_bos(df, BosConfig(followthrough_bars=18))
    df = detect_choch(df)
    df = detect_fvg(df)
    df = detect_order_blocks(df)
    df = detect_displacement(df)
    df = compute_zones(df)

    orch = AgentOrchestrator()
    df = orch.analyze_context(df)

    os.makedirs("data/ml/synthetic", exist_ok=True)
    out = "data/ml/synthetic/v4_synthetic.parquet"
    df.to_parquet(out, index=False)
    wr = df["win"].mean()
    print(f"Done: {out}  ({len(df)} rows, {len(df.columns)} cols, WR={wr:.1%})")

if __name__ == "__main__":
    main()

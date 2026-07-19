from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from indicators import add_atr, add_ema, add_rsi, add_stochastic
from agents.orchestrator import AgentOrchestrator
from agents.ict_agent import ICTAgent
from agents.wyckoff_agent import WyckoffAgent
from agents.structure_agent import StructureAgent
from agents.decision_agent import DecisionAgent
from agents.base import AnalysisResult
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from detectors.displacement import detect_displacement
from detectors.zones import compute_zones
from ict_backtest.market_structure import StructureConfig, detect_market_structure


def generate_multi_regime(n_bars: int = 5_000, seed: int = 42, start_price: float = 1.1000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n1 = n_bars // 3
    n2 = n_bars // 3
    n3 = n_bars - n1 - n2
    prices = np.zeros(n_bars, dtype=float)
    prices[0] = start_price
    for i in range(1, n1):
        prices[i] = prices[i - 1] + 0.0003 + rng.normal(0.0, 0.002)
    for i in range(n1, n1 + n2):
        prices[i] = prices[i - 1] - 0.0003 + rng.normal(0.0, 0.002)
    base = prices[n1 + n2 - 1]
    for i in range(n1 + n2, n_bars):
        prices[i] = base + rng.normal(0.0, 0.001)
    prices = np.maximum(prices, start_price * 0.85)
    highs = prices + abs(rng.normal(0.0, 0.003, size=n_bars))
    lows = prices - abs(rng.normal(0.0, 0.003, size=n_bars))
    opens = np.zeros(n_bars, dtype=float)
    opens[0] = prices[0]
    for i in range(1, n_bars):
        opens[i] = prices[i - 1] + rng.normal(0.0, 0.001)
    times = pd.date_range("2022-01-01", periods=n_bars, freq="15min", tz="UTC")
    volume = rng.integers(100, 10000, size=n_bars)
    return pd.DataFrame({
        "time": times, "open": np.maximum(opens, start_price * 0.85),
        "high": np.maximum(highs, opens), "low": np.minimum(lows, opens),
        "close": prices, "tick_volume": volume,
    })


def add_forward_labels(df: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    future_close = df["close"].shift(-horizon)
    df["direction"] = np.where(future_close > df["close"], 1, np.where(future_close < df["close"], -1, 0)).astype(int)
    df["pnl_r"] = (future_close - df["close"]) / df["close"]
    df["win"] = (df["pnl_r"] > 0).astype(int)
    return df


def add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["atr"] = add_atr(df, 14)
    df["ema_fast"] = add_ema(df, 20)
    df["ema_slow"] = add_ema(df, 50)
    df["rsi"] = add_rsi(df, 14)
    stoch = add_stochastic(df)
    df["stoch_k"] = stoch["stoch_k"]
    df["stoch_d"] = stoch["stoch_d"]
    df["macro_direction"] = "RANGING"
    df["d1_direction"] = "RANGING"
    df["trend_score"] = 0.0
    df["trend_confidence"] = 1.0
    df["regime_state"] = "NORMAL"
    return df


def evaluate_signals(df: pd.DataFrame, decision_col: str, bias_col: str) -> dict[str, Any]:
    valid = df[df[decision_col].notna()].copy()
    valid = valid[valid[decision_col] >= 0.50]
    valid = valid[valid[bias_col].isin(["BULLISH", "BEARISH"])]

    if len(valid) < 3:
        return {"signals": 0, "win_rate": 0.0, "avg_conf": 0.0, "avg_pnl_r": 0.0, "total_pnl_r": 0.0, "sharpe": 0.0}

    correct = ((valid[bias_col] == "BULLISH") & (valid["direction"] == 1)) | ((valid[bias_col] == "BEARISH") & (valid["direction"] == -1))
    wr = correct.mean()
    sharpe = valid["pnl_r"].mean() / (valid["pnl_r"].std() + 1e-9) * (252 * 96) ** 0.5

    return {
        "signals": len(valid),
        "signal_rate": len(valid) / len(df),
        "win_rate": float(wr),
        "avg_conf": float(valid[decision_col].mean()),
        "avg_pnl_r": float(valid["pnl_r"].mean()),
        "total_pnl_r": float(valid["pnl_r"].sum()),
        "sharpe": float(sharpe),
    }


def evaluate_agent(df: pd.DataFrame, agent_name: str, agent) -> dict[str, Any]:
    results = []
    lookback = 40
    for i in range(lookback, len(df)):
        window = df.iloc[max(0, i - lookback): i + 1].reset_index(drop=True)
        row = df.iloc[i]
        result = agent.analyze(window, len(window) - 1)
        results.append({
            "bias": result.bias,
            "confidence": result.confidence,
            "direction": row["direction"],
            "pnl_r": row["pnl_r"],
        })

    if not results:
        return {"name": agent_name, "signals": 0, "win_rate": 0.0, "avg_conf": 0.0, "sharpe": 0.0}

    rdf = pd.DataFrame(results)
    return evaluate_signals(rdf, "confidence", "bias") | {"name": agent_name}


def evaluate_ensemble(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    orch = AgentOrchestrator()
    df = orch.analyze_context(df)

    return evaluate_signals(df, "agent_decision_confidence", "agent_decision_bias") | {"name": "ENSEMBLE"}


def evaluate_disabled_ensemble(df: pd.DataFrame, disable: list[str]) -> dict[str, Any]:
    ict = ICTAgent() if "ict" not in disable else None
    wyckoff = WyckoffAgent() if "wyckoff" not in disable else None
    structure = StructureAgent() if "structure" not in disable else None
    decision = DecisionAgent()

    result_rows = []
    lookback = 40
    for i in range(lookback, len(df)):
        window = df.iloc[max(0, i - lookback): i + 1].reset_index(drop=True)
        row = df.iloc[i]
        bias, confidence = None, None

        ict_r = ict.analyze(window, len(window) - 1) if ict else AnalysisResult(agent_name="ICT", bias="NEUTRAL", confidence=0.0, detected_events=[], evidence={}, invalidation_conditions=[])
        wyckoff_r = wyckoff.analyze(window, len(window) - 1) if wyckoff else AnalysisResult(agent_name="WYCKOFF", bias="NEUTRAL", confidence=0.0, detected_events=[], evidence={}, invalidation_conditions=[])
        structure_r = structure.analyze(window, len(window) - 1) if structure else AnalysisResult(agent_name="STRUCTURE", bias="NEUTRAL", confidence=0.0, detected_events=[], evidence={}, invalidation_conditions=[])

        decision_result, _ = decision.decide(ict=ict_r, wyckoff=wyckoff_r, structure=structure_r)
        result_rows.append({
            "bias": decision_result.bias,
            "confidence": decision_result.confidence,
            "direction": row["direction"],
            "pnl_r": row["pnl_r"],
        })

    if not result_rows:
        return {"name": f"ENSEMBLE -{'+'.join(disable).upper()}", "signals": 0, "win_rate": 0.0, "sharpe": 0.0}

    rdf = pd.DataFrame(result_rows)
    label = f"ENSEMBLE -{' + '.join(a.upper() for a in disable)}"
    return evaluate_signals(rdf, "confidence", "bias") | {"name": label}


def print_report(results: list[dict]):
    print(f"\n{'='*90}")
    print(f"  ABLATION STUDY - AGENT CONTRIBUTION ANALYSIS")
    print(f"{'='*90}")
    print(f"{'Agent':<30s} {'Signals':>8s} {'Rate':>7s} {'WinRate':>8s} {'AvgConf':>8s} {'AvgPnl':>10s} {'Sharpe':>8s}")
    print(f"{'-'*90}")
    for r in results:
        wr = f"{r['win_rate']:.1%}" if r['win_rate'] else "N/A"
        conf = f"{r['avg_conf']:.3f}" if r.get('avg_conf', 0) else "N/A"
        pnl = f"{r['avg_pnl_r']:.6f}" if r['avg_pnl_r'] else "N/A"
        shp = f"{r['sharpe']:.2f}" if r['sharpe'] else "N/A"
        rate = f"{r['signal_rate']:.1%}" if r.get('signal_rate', 0) else "N/A"
        print(f"{r['name']:<30s} {r['signals']:>8d} {rate:>7s} {wr:>8s} {conf:>8s} {pnl:>10s} {shp:>8s}")
    print(f"{'='*90}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-bars", type=int, default=3_000)
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t0 = time.time()
    print(f"Generating {args.n_bars} synthetic bars (seed={args.seed})...")
    df = generate_multi_regime(n_bars=args.n_bars, seed=args.seed)
    df = add_forward_labels(df, horizon=args.horizon)
    df = add_basic_indicators(df)
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
    print(f"  {len(df)} bars generated. Win rate: {df['win'].mean():.1%}")

    ict_agent = ICTAgent()
    wyckoff_agent = WyckoffAgent()
    structure_agent = StructureAgent()

    print(f"\n{'='*90}")
    print(f"  PHASE 1: Individual Agent Performance")
    print(f"{'='*90}")
    results = []
    for name, agent in [("ICT", ict_agent), ("WYCKOFF", wyckoff_agent), ("STRUCTURE", structure_agent)]:
        r = evaluate_agent(df, name, agent)
        results.append(r)
        wr = f"{r['win_rate']:.1%}" if r['win_rate'] else "N/A"
        print(f"  {name:<15s} signals={r['signals']:>5d}  rate={r.get('signal_rate',0):.1%}  WR={wr}  Sharpe={r['sharpe']:.2f}")

    print(f"\n{'='*90}")
    print(f"  PHASE 2: Ensemble Ablation (remove one agent at a time)")
    print(f"{'='*90}")
    full = evaluate_disabled_ensemble(df, [])
    results.append(full)
    print(f"  {'ENSEMBLE (ALL)':<25s} signals={full['signals']:>5d}  rate={full['signal_rate']:.1%}  WR={full['win_rate']:.1%}  Sharpe={full['sharpe']:.2f}")

    configs = [
        (["ict"], "NO ICT"),
        (["wyckoff"], "NO WYCKOFF"),
        (["structure"], "NO STRUCTURE"),
        (["ict", "wyckoff"], "NO ICT+WYCKOFF"),
        (["ict", "structure"], "NO ICT+STRUCTURE"),
        (["wyckoff", "structure"], "NO WYCKOFF+STRUCTURE"),
    ]
    for disable, label in configs:
        r = evaluate_disabled_ensemble(df, disable)
        results.append(r)
        delta_wr = r['win_rate'] - full['win_rate']
        delta_sh = r['sharpe'] - full['sharpe']
        arrow = "UP" if delta_wr > 0.005 else "DOWN" if delta_wr < -0.005 else "FLAT"
        print(f"  {label:<25s} signals={r['signals']:>5d}  WR={r['win_rate']:.1%} ({delta_wr:+.1%})  Sharpe={r['sharpe']:.2f} ({delta_sh:+.2f})  {arrow}")

    print_report(results)

    baseline = full['win_rate']
    print(f"\n  {'='*80}")
    print(f"  KEY INSIGHTS")
    print(f"  {'='*80}")
    for r in results:
        if r['name'] == 'ENSEMBLE':
            continue
        delta = r['win_rate'] - baseline
        impact = "BETTER THAN ENSEMBLE" if delta > 0 else "WORSE THAN ENSEMBLE" if delta < 0 else "MATCHES ENSEMBLE"
        print(f"  {r['name']:<25s} WR={r['win_rate']:.1%} vs Ensemble {baseline:.1%} (delta={delta:+.1%}) -> {impact}")

    print(f"\n  Total time: {time.time()-t0:.1f}s")

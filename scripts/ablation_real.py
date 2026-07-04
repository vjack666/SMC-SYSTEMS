from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from agents.ict_agent import ICTAgent
from agents.wyckoff_agent import WyckoffAgent
from agents.structure_agent import StructureAgent
from agents.decision_agent import DecisionAgent
from agents.base import AnalysisResult


def evaluate(rdf: pd.DataFrame) -> dict:
    valid = rdf[(rdf["confidence"] >= 0.50) & (rdf["bias"].isin(["BULLISH", "BEARISH"]))]
    if len(valid) < 3:
        return {"signals": 0, "win_rate": 0.0, "sharpe": 0.0, "avg_conf": 0.0}
    correct = ((valid["bias"] == "BULLISH") & (valid["direction"] == 1)) | (
        (valid["bias"] == "BEARISH") & (valid["direction"] == -1))
    wr = correct.mean()
    sharpe = valid["pnl_r"].mean() / (valid["pnl_r"].std() + 1e-9) * (252 * 96) ** 0.5
    return {"signals": len(valid), "win_rate": float(wr), "sharpe": float(sharpe),
            "avg_conf": float(valid["confidence"].mean()), "avg_pnl": float(valid["pnl_r"].mean())}


def run():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/ml/USDCHF/v4_USDCHF.parquet"
    df = pd.read_parquet(path)
    future = df["close"].shift(-12)
    df["direction"] = np.where(future > df["close"], 1, np.where(future < df["close"], -1, 0)).astype(int)
    df["pnl_r"] = (future - df["close"]) / df["close"]

    print(f"\nDataset: {Path(path).stem}  ({len(df)} rows, win rate={df['pnl_r'].gt(0).mean():.1%})")
    lookback = 40

    ict = ICTAgent()
    wyc = WyckoffAgent()
    strct = StructureAgent()
    dec = DecisionAgent()

    # individual agents
    indiv = {"ICT": ict, "WYCKOFF": wyc, "STRUCTURE": strct}
    raw: dict[str, list] = {k: [] for k in indiv}
    for i in range(lookback, len(df)):
        win = df.iloc[i - lookback : i + 1].reset_index(drop=True)
        row = df.iloc[i]
        for name, ag in indiv.items():
            r = ag.analyze(win, len(win) - 1)
            raw[name].append({"bias": r.bias, "confidence": r.confidence, "direction": row["direction"], "pnl_r": row["pnl_r"]})

    print(f"\n{'='*65}")
    print(f"  INDIVIDUAL AGENTS")
    print(f"{'='*65}")
    print(f"  {'Agent':<12s} {'Signals':>7s} {'WinRate':>8s} {'Sharpe':>8s} {'AvgConf':>8s}")
    print(f"  {'-'*50}")
    for name, rows in raw.items():
        r = evaluate(pd.DataFrame(rows))
        print(f"  {name:<12s} {r['signals']:>7d} {r['win_rate']:>7.1%} {r['sharpe']:>7.2f} {r['avg_conf']:>7.3f}")

    # ensemble (all)
    print(f"\n{'='*65}")
    print(f"  ENSEMBLE (Decision Agent)")
    print(f"{'='*65}")
    ens_rows = []
    for i in range(lookback, len(df)):
        win = df.iloc[i - lookback : i + 1].reset_index(drop=True)
        row = df.iloc[i]
        dr, _ = dec.decide(ict=ict.analyze(win, len(win) - 1), wyckoff=wyc.analyze(win, len(win) - 1),
                            structure=strct.analyze(win, len(win) - 1))
        ens_rows.append({"bias": dr.bias, "confidence": dr.confidence, "direction": row["direction"], "pnl_r": row["pnl_r"]})
    full_r = evaluate(pd.DataFrame(ens_rows))
    print(f"  {'ALL AGENTS':<12s} {full_r['signals']:>7d} {full_r['win_rate']:>7.1%} {full_r['sharpe']:>7.2f} {full_r['avg_conf']:>7.3f}")

    # ablation
    print(f"\n  {'='*65}")
    print(f"  ABLATION (remove one)")
    print(f"  {'='*65}")
    print(f"  {'Config':<20s} {'Signals':>7s} {'WinRate':>8s} {'Sharpe':>8s} {'vs Full':>8s}")
    print(f"  {'-'*55}")
    for label, disable in [("NO ICT", ["ict"]), ("NO WYCKOFF", ["wyckoff"]), ("NO STRUCTURE", ["structure"])]:
        a_rows = []
        for i in range(lookback, len(df)):
            win = df.iloc[i - lookback : i + 1].reset_index(drop=True)
            row = df.iloc[i]
            ict_r = ict.analyze(win, len(win) - 1) if "ict" not in disable else AnalysisResult("ICT", "NEUTRAL", 0.0, [], {}, [])
            wyc_r = wyc.analyze(win, len(win) - 1) if "wyckoff" not in disable else AnalysisResult("WYCKOFF", "NEUTRAL", 0.0, [], {}, [])
            str_r = strct.analyze(win, len(win) - 1) if "structure" not in disable else AnalysisResult("STRUCTURE", "NEUTRAL", 0.0, [], {}, [])
            dr, _ = dec.decide(ict=ict_r, wyckoff=wyc_r, structure=str_r)
            a_rows.append({"bias": dr.bias, "confidence": dr.confidence, "direction": row["direction"], "pnl_r": row["pnl_r"]})
        r = evaluate(pd.DataFrame(a_rows))
        delta = r["win_rate"] - full_r["win_rate"]
        arrow = "BETTER" if delta > 0.02 else "WORSE" if delta < -0.02 else "SAME"
        print(f"  {label:<20s} {r['signals']:>7d} {r['win_rate']:>7.1%} {r['sharpe']:>7.2f} {delta:>+7.1%} ({arrow})")

    print()


if __name__ == "__main__":
    run()

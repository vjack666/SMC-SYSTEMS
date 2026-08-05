from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.pullback import build_pullback_view, summarize_pullback_view


SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")


def main() -> None:
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    last_snapshots: list[pd.DataFrame] = []

    for symbol in SYMBOLS:
        view = build_pullback_view(symbol=symbol, timeframe="M15", data_dir=Path("data/mt5"))
        stats = summarize_pullback_view(view)
        stats["symbol"] = symbol
        summary_rows.append(stats)

        cols = [
            "time",
            "symbol",
            "macro_direction",
            "trend_alignment",
            "regime_state",
            "pullback_side",
            "pullback_state",
            "pullback_score",
            "pullback_ready",
            "trend_confidence",
        ]
        snap = view.copy()
        snap["symbol"] = symbol
        last_snapshots.append(snap[cols].tail(300))

    summary_df = pd.DataFrame(summary_rows)
    summary_out = results_dir / "pullback_audit_summary.json"
    summary_out.write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")

    combined = pd.concat(last_snapshots, ignore_index=True)
    combined.to_csv(results_dir / "pullback_view_latest.csv", index=False)

    global_stats = {
        "symbols": list(SYMBOLS),
        "total_bars_analyzed": int(summary_df["total_bars"].sum()),
        "total_valid_pullbacks": int(summary_df["valid_pullbacks"].sum()),
        "global_valid_rate": float(summary_df["valid_pullbacks"].sum() / summary_df["total_bars"].sum()),
        "mean_pullback_score": float(summary_df["avg_pullback_score"].mean()),
        "summary_file": str(summary_out),
        "snapshot_file": "results/pullback_view_latest.csv",
    }
    (results_dir / "pullback_audit_global.json").write_text(json.dumps(global_stats, indent=2), encoding="utf-8")

    print(json.dumps(global_stats, indent=2))


if __name__ == "__main__":
    main()

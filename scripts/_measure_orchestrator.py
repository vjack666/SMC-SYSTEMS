"""
Orchestrator effect measurement (Ítem A, large dataset).

Compares the signal set generated WITH vs WITHOUT the AgentOrchestrator
(langgraph) for each symbol, on the full local H4 history. This isolates
whether the orchestrator — not the ML quality filter — is what collapses
trade count (the 60->1 collapse seen in the original Exp A).

This is fast: one context pass per symbol (orchestrator.analyze_context is
a single langgraph run per symbol, not the full per-signal backtest loop).

Usage (repo root, probe venv):
    python scripts/_measure_orchestrator.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legacy.backtest import CombinedBacktestConfig  # noqa: E402
from signals import ScalpingConfig, build_scalping_context  # noqa: E402
from signals.pipeline import AgentOrchestrator  # noqa: E402
from data import load_frame, apply_time_window  # noqa: E402


SYMS = ["EURUSD", "GBPUSD", "XAUUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"]
TF = "H4"
DATA_DIR = Path("data/raw")


def _signal_count(ctx: pd.DataFrame, min_conf: float) -> int:
    valid = ctx[(ctx["signal_direction"] != 0) & (ctx["signal_confidence"] >= min_conf)]
    return int(len(valid))


def main() -> int:
    cfg = CombinedBacktestConfig(
        data_dir=DATA_DIR, symbols=tuple(SYMS), timeframe=TF,
        use_ml_quality_filter=True,
    )
    scalping_cfg = ScalpingConfig(**cfg.scalping_config) if isinstance(cfg.scalping_config, dict) else cfg.scalping_config
    min_conf = float(cfg.min_confidence)

    per_sym: dict[str, dict[str, int]] = {}
    tot_off = tot_on = 0

    for symbol in SYMS:
        frame = load_frame(cfg.data_dir, symbol, cfg.timeframe, auto_download=False)
        frame = apply_time_window(frame, cfg.start_time, cfg.end_time)

        ctx_off = build_scalping_context(
            symbol=symbol, timeframe=cfg.timeframe, data_dir=cfg.data_dir,
            config=scalping_cfg, orchestrator=None,
        )
        ctx_on = build_scalping_context(
            symbol=symbol, timeframe=cfg.timeframe, data_dir=cfg.data_dir,
            config=scalping_cfg, orchestrator=AgentOrchestrator(),
        )

        n_off = _signal_count(ctx_off, min_conf)
        n_on = _signal_count(ctx_on, min_conf)
        tot_off += n_off
        tot_on += n_on
        per_sym[symbol] = {
            "signals_no_orch": n_off,
            "signals_with_orch": n_on,
            "ratio": round(n_on / n_off, 3) if n_off else None,
        }
        print(f"  {symbol}: no_orch={n_off}  with_orch={n_on}  ratio={per_sym[symbol]['ratio']}")

    print(f"\nTOTAL signals  no_orchestrator={tot_off}   with_orchestrator={tot_on}")
    print(f"Orchestrator reduces signal set to {tot_on/max(tot_off,1):.1%} of baseline.")
    out = {"min_confidence": min_conf, "total_no_orch": tot_off, "total_with_orch": tot_on,
           "per_symbol": per_sym}
    Path("scripts/_orchestrator_measure.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

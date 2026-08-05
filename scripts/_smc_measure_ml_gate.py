"""Measure ML quality-filter effect in isolation (fast, no orchestrator).

Generates signals WITHOUT the orchestrator, then applies the ML model gate
and reports: pass-rate, and PF/WR of accepted vs rejected sets.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from backtest.engine import (
    CombinedBacktestConfig,
    _build_signals_from_context,
    _load_ml_model,
    _predict_quality_probability,
    _simulate_trade_with_stats,
)
from data import apply_time_window, load_frame
from features import FeatureEngine
from regime import detect_regimes
from risk import DynamicThresholdConfig, mode_threshold_add, threshold_for_regime
from signals import ScalpingConfig, build_scalping_context

SYMBOLS = ["EURUSD", "USDCHF"]
TF = "M15"
DATA_DIR = Path("data/raw")
MAX_BARS = 15000


def main() -> None:
    cfg = CombinedBacktestConfig(
        data_dir=DATA_DIR, symbols=tuple(SYMBOLS), timeframe=TF,
        use_ml_quality_filter=True,
    )
    model = _load_ml_model(cfg.ml_model_path)
    print(f"ML model loaded: {model is not None}  ({cfg.ml_model_path.name})")
    if model is None:
        print("No model -> abort")
        return

    scalping_cfg = cfg.scalping_config
    fe = FeatureEngine()
    thr_cfg = cfg.threshold_engine

    accepted, rejected = [], []
    n_signals = 0
    for sym in SYMBOLS:
        frame = load_frame(DATA_DIR, sym, TF, auto_download=False)
        frame = apply_time_window(frame, None, None)
        if MAX_BARS:
            frame = frame.tail(MAX_BARS).reset_index(drop=True)
        ctx = build_scalping_context(symbol=sym, timeframe=TF, data_dir=DATA_DIR,
                                     config=scalping_cfg)
        ctx = detect_regimes(ctx)
        if MAX_BARS:
            ctx = ctx.tail(MAX_BARS).reset_index(drop=True)
        signals = _build_signals_from_context(sym, ctx, cfg.min_confidence)
        n_signals += len(signals)
        cmap = {str(r["time"]): r for _, r in ctx.iterrows()}
        for sig in signals:
            row = cmap.get(sig.time)
            if row is None:
                continue
            regime = str(row.get("market_regime", "RANGING"))
            dyn = min(0.95, threshold_for_regime(regime, thr_cfg))
            core = fe.extract_features(ctx, int(row.name))
            frow = {**core, "timestamp": sig.time,
                    "sl_distance": abs(sig.entry - sig.stop_loss),
                    "tp_distance": abs(sig.take_profit - sig.entry),
                    "rr_ratio": abs(sig.take_profit - sig.entry) / max(abs(sig.entry - sig.stop_loss), 1e-9),
                    "expected_hold_bars": cfg.max_hold_bars,
                    "ml_probability": float(sig.confidence), "ml_threshold": float(dyn),
                    "governor_mode": "NORMAL"}
            from agents.orchestrator import AGENT_COLUMNS
            for ac in AGENT_COLUMNS:
                frow[ac] = row.get(ac, None)
            prob = _predict_quality_probability(model, frow, fallback=sig.confidence)
            gate_open = prob >= dyn
            trade, stats = _simulate_trade_with_stats(frame, sig, cfg.max_hold_bars)
            if trade is None:
                continue
            rec = {"sym": sym, "pnl_r": trade.pnl_r, "win": int(trade.pnl_r > 0),
                   "prob": prob, "thr": dyn}
            (accepted if gate_open else rejected).append(rec)

    def _pf(rows):
        if not rows:
            return 0.0
        gp = sum(r["pnl_r"] for r in rows if r["pnl_r"] > 0)
        gl = abs(sum(r["pnl_r"] for r in rows if r["pnl_r"] < 0))
        return float("inf") if gl == 0 else gp / gl

    def _wr(rows):
        return sum(r["win"] for r in rows) / len(rows) if rows else 0.0

    acc_pf, acc_wr = _pf(accepted), _wr(accepted)
    rej_pf, rej_wr = _pf(rejected), _wr(rejected)
    print(f"\nTotal base signals: {n_signals}")
    print(f"Accepted by ML gate: {len(accepted)} ({len(accepted)/max(n_signals,1)*100:.1f}%)")
    print(f"Rejected by ML gate: {len(rejected)} ({len(rejected)/max(n_signals,1)*100:.1f}%)")
    print(f"\nACCEPTED  -> WR {acc_wr:.1%}  PF {acc_pf:.3f}")
    print(f"REJECTED  -> WR {rej_wr:.1%}  PF {rej_pf:.3f}")
    print(f"\nML gate lift (accepted PF / rejected PF): "
          f"{acc_pf/rej_pf if rej_pf else float('inf'):.2f}x")


if __name__ == "__main__":
    main()

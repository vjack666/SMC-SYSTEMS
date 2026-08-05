"""
ML-filter effect measurement (Ítem A) — parametrizable.

For a given symbol/timeframe/max_bars, builds the scalping context (optionally
with the real AgentOrchestrator so AGENT_COLUMNS are populated, mirroring
production ML_ON), generates the raw signals, then applies the REAL ml quality
model to each signal and counts how many survive the filter.

Reproduces the Exp A setup:  python scripts/_measure_ml_filter.py \
    --symbol EURUSD --timeframe M15 --max-bars 5000 --with-orchestrator

Usage (repo root, probe venv):
    python scripts/_measure_ml_filter.py [--symbol S] [--timeframe TF] \
        [--max-bars N] [--with-orchestrator]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import CombinedBacktestConfig  # noqa: E402
from backtest.engine import (  # noqa: E402
    threshold_for_regime,
    GovernorPool,
    GovernorConfig,
    DynamicThresholdConfig,
    _build_signals_from_context,
    _load_ml_model,
    _predict_quality_probability,
    AGENT_COLUMNS,
)
from risk import mode_threshold_add, mode_risk_multiplier  # noqa: E402
from signals import ScalpingConfig, build_scalping_context  # noqa: E402
from signals.pipeline import AgentOrchestrator  # noqa: E402
from regime import detect_regimes  # noqa: E402
from data import load_frame, apply_time_window  # noqa: E402

DATA_DIR = Path("data/raw")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--timeframe", default="H4")
    ap.add_argument("--max-bars", type=int, default=None)
    ap.add_argument("--with-orchestrator", action="store_true",
                    help="Populate AGENT_COLUMNS via the real orchestrator (production ML_ON).")
    args = ap.parse_args()

    cfg = CombinedBacktestConfig(
        data_dir=DATA_DIR, symbols=(args.symbol,), timeframe=args.timeframe,
        use_ml_quality_filter=True, ml_model_path=Path("ml/models/quality_filter.pkl"),
        max_bars=args.max_bars,
    )
    scalping_cfg = ScalpingConfig(**cfg.scalping_config) if isinstance(cfg.scalping_config, dict) else cfg.scalping_config
    threshold_cfg = DynamicThresholdConfig(**cfg.threshold_engine) if isinstance(cfg.threshold_engine, dict) else cfg.threshold_engine
    gov_cfg = GovernorPool(GovernorConfig(**cfg.risk_governor) if isinstance(cfg.risk_governor, dict) else cfg.risk_governor)

    ml_model = _load_ml_model(cfg.ml_model_path)
    from features import FeatureEngine
    fe = FeatureEngine()

    orch = AgentOrchestrator() if args.with_orchestrator else None
    frame = load_frame(cfg.data_dir, args.symbol, cfg.timeframe, auto_download=False)
    frame = apply_time_window(frame, cfg.start_time, cfg.end_time)
    context = build_scalping_context(
        symbol=args.symbol, timeframe=cfg.timeframe, data_dir=cfg.data_dir,
        config=scalping_cfg, orchestrator=orch,
    )
    context = apply_time_window(context, cfg.start_time, cfg.end_time)
    context = detect_regimes(context)
    if cfg.max_bars is not None and int(cfg.max_bars) > 0:
        context = context.tail(int(cfg.max_bars)).reset_index(drop=True)

    signals = _build_signals_from_context(args.symbol, context, cfg.min_confidence)
    context_map = {str(row["time"]): row for _, row in context.iterrows()}
    gov = gov_cfg.get_state(args.symbol)

    raw = len(signals)
    passed = 0
    for signal in signals:
        row = context_map.get(signal.time)
        if row is None:
            continue
        regime = str(row.get("market_regime", "RANGING"))
        dt = threshold_for_regime(regime, threshold_cfg)
        gov = gov_cfg.next(args.symbol, gov)
        dt = min(0.95, dt + mode_threshold_add(gov.mode))
        feat = fe.extract_features(context, int(row.name))
        frow = {
            **feat, "timestamp": signal.time,
            "sl_distance": abs(signal.entry - signal.stop_loss),
            "tp_distance": abs(signal.take_profit - signal.entry),
            "rr_ratio": abs(signal.take_profit - signal.entry) / max(abs(signal.entry - signal.stop_loss), 1e-9),
            "expected_hold_bars": cfg.max_hold_bars,
            "ml_probability": float(signal.confidence),
            "ml_threshold": float(dt),
            "governor_mode": gov.mode,
            "risk_multiplier": mode_risk_multiplier(gov.mode),
        }
        for agent_col in AGENT_COLUMNS:
            frow[agent_col] = row.get(agent_col, None)
        prob = _predict_quality_probability(ml_model, frow, fallback=signal.confidence)
        if prob >= dt:
            passed += 1

    pct = 100 * passed / max(raw, 1)
    print(f"{args.symbol} {args.timeframe} max_bars={args.max_bars} "
          f"orchestrator={bool(orch)}: raw={raw} pass_ml={passed} ({pct:.1f}%)")
    out = {"symbol": args.symbol, "timeframe": args.timeframe, "max_bars": args.max_bars,
           "with_orchestrator": bool(orch), "raw_signals": raw, "pass_ml": passed, "pct": pct}
    Path(f"scripts/_ml_filter_{args.symbol}_{args.timeframe}_{args.max_bars or 'all'}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

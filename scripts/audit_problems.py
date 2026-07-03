"""Runtime audit script — writes NDJSON to debug log for hypothesis validation."""
from __future__ import annotations

import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "debug-95547b.log"
SESSION = "95547b"
RUN_ID = "audit-v1"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    entry = {
        "sessionId": SESSION,
        "runId": RUN_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
  # region agent log
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
  # endregion


def main() -> None:
    from smc_successor.agents.orchestrator import AgentOrchestrator
    from smc_successor.fixtures.synthetic_ohlcv import generate_synthetic_ohlcv
    from smc_successor.risk import GovernorPool
    from smc_successor.signals.pipeline import ScalpingConfig, build_scalping_context

    # Hypothesis A: backtest path never passes orchestrator
    import inspect
    from smc_successor.backtest.engine import run_combined_backtest
    src = inspect.getsource(run_combined_backtest)
    log("A", "audit:backtest", "backtest orchestrator wiring", {
        "build_scalping_context_has_orchestrator_arg": "orchestrator" in src,
        "orchestrator_passed_in_backtest": "orchestrator=" in src and "AgentOrchestrator" in src,
    })

    # Hypothesis B: ML dataset signals built before agent analysis
    from smc_successor.ml.dataset_builder import _build_context_truncated
    trunc_src = inspect.getsource(_build_context_truncated)
    log("B", "audit:ml_dataset", "ML dataset agent ordering", {
        "context_truncated_uses_orchestrator_none": "orchestrator=None" in trunc_src,
        "analyze_context_called_after": "analyze_context" in inspect.getsource(
            __import__("smc_successor.ml.dataset_builder", fromlist=["build_ml_dataset"]).build_ml_dataset
        ),
    })

    # Hypothesis C: day_drawdown equals total_drawdown in governor
    pool = GovernorPool()
    pool.update_from_trade("EURUSD", -2.0)
    pool.update_from_trade("EURUSD", -3.0)
    state = pool.get_state("EURUSD")
    log("C", "audit:governor", "governor drawdown fields", {
        "day_drawdown_pct": state.day_drawdown_pct,
        "total_drawdown_pct": state.total_drawdown_pct,
        "identical": state.day_drawdown_pct == state.total_drawdown_pct,
        "consecutive_losses": state.consecutive_losses,
        "mode": state.mode,
    })

    # Hypothesis D: volume/micro filters unused in confluence
    synth = generate_synthetic_ohlcv(n_bars=200, seed=7)
    from smc_successor.detectors import detect_bos, detect_choch, detect_fvg, detect_order_blocks
    from smc_successor.indicators import add_atr, add_ema, add_rsi
    frame = detect_bos(synth)
    frame = detect_choch(frame)
    frame = detect_fvg(frame)
    frame = detect_order_blocks(frame)
    frame["atr"] = add_atr(frame, 14)
    frame["ema_fast"] = add_ema(frame, 20)
    frame["ema_slow"] = add_ema(frame, 50)
    frame["rsi"] = add_rsi(frame, 14)
    import numpy as np
    frame["atr_ratio"] = frame["atr"] / frame["atr"].rolling(20).mean().replace(0.0, np.nan)
    frame["macro_direction"] = "BULLISH"
    frame["trend_confidence"] = 0.8
    frame["regime_state"] = "RANGING"
    from smc_successor.signals.pipeline import _session_filter, _last_anchor
    frame["filter_trend"] = True
    frame["filter_session"] = _session_filter(frame["time"], "EURUSD", False)
    frame["filter_atr"] = True
    frame["filter_ob_fvg"] = True
    frame["filter_bos"] = True
    frame["filter_volume"] = False
    frame["filter_micro"] = False
    frame["filter_choch"] = True
    frame["filter_swing"] = True
    frame["filter_agents"] = True
    confluence_no_vol = (
        int(frame["filter_trend"].iloc[-1])
        + int(frame["filter_bos"].iloc[-1])
        + int(frame["filter_ob_fvg"].iloc[-1])
        + int(frame["filter_choch"].iloc[-1])
        + int(frame["filter_swing"].iloc[-1])
    )
    log("D", "audit:pipeline", "unused filters in confluence", {
        "filter_volume_false": bool(~frame["filter_volume"].iloc[-1]),
        "filter_micro_false": bool(~frame["filter_micro"].iloc[-1]),
        "confluence_score_without_volume": confluence_no_vol,
        "volume_in_confluence_formula": False,
        "micro_in_confluence_formula": False,
    })

    # Hypothesis E: ICT agent never returns BEARISH bias
    from smc_successor.agents.ict_agent import ICTAgent
    ict = ICTAgent()
    bearish_biases = []
    for i in range(50, 150):
        row_df = frame.iloc[max(0, i - 30): i + 1].copy()
        row_df["macro_direction"] = "BEARISH"
        row_df["bos_direction"] = -1
        row_df["choch_signal"] = "NONE"
        result = ict.analyze(row_df.reset_index(drop=True), len(row_df) - 1)
        if result.bias == "BEARISH":
            bearish_biases.append(i)
    log("E", "audit:ict_agent", "ICT bearish bias on bearish trend", {
        "bearish_bias_count": len(bearish_biases),
        "sample_biases": [
            ict.analyze(
                frame.iloc[max(0, i - 30): i + 1].assign(macro_direction="BEARISH", bos_direction=-1).reset_index(drop=True),
                min(30, i),
            ).bias
            for i in [80, 100, 120]
        ],
    })

    # Hypothesis F: agent filter not applied when orchestrator runs post-hoc (synthetic)
    from smc_successor.detectors import detect_displacement, compute_zones, ZoneConfig
    synth2 = generate_synthetic_ohlcv(n_bars=400, seed=11)
    synth2 = detect_bos(synth2)
    synth2 = detect_choch(synth2)
    synth2 = detect_fvg(synth2)
    synth2 = detect_order_blocks(synth2)
    synth2 = detect_displacement(synth2)
    synth2 = compute_zones(synth2, ZoneConfig(swing_lookback=20))
    synth2["atr"] = add_atr(synth2, 14)
    synth2["ema_fast"] = add_ema(synth2, 20)
    synth2["ema_slow"] = add_ema(synth2, 50)
    synth2["rsi"] = add_rsi(synth2, 14)
    synth2["atr_ratio"] = synth2["atr"] / synth2["atr"].rolling(20).mean().replace(0.0, np.nan)
    synth2["macro_direction"] = "BULLISH"
    synth2["trend_confidence"] = 0.7
    synth2["regime_state"] = "RANGING"
    synth2["d1_trend"] = "BULLISH"
    synth2["trend_score"] = 40.0
    synth2["d1_direction"] = "BULLISH"
    orch = AgentOrchestrator()
    # Simulate pipeline on synth without load_frame (no MT5 parquet available)
    mini = synth2.copy()
    mini["filter_trend"] = mini["macro_direction"].isin(["BULLISH", "BEARISH"])
    mini["filter_session"] = _session_filter(mini["time"], "EURUSD", False)
    mini["filter_atr"] = mini["atr_ratio"].fillna(0.0) > 1.0
    mini["filter_ob_fvg"] = True
    mini["filter_bos"] = True
    mini["filter_volume"] = True
    mini["filter_choch"] = True
    mini["filter_swing"] = True
    mini_no = mini.copy()
    mini_no["filter_agents"] = True
    mini_with = orch.analyze_context(mini.copy())
    mini_with_recomputed = mini.copy()
    decision_conf = mini_with["agent_decision_confidence"].fillna(0.0)
    decision_bias = mini_with["agent_decision_bias"].fillna("NEUTRAL")
    mini_with_recomputed["filter_agents"] = (
        (decision_conf >= 0.50) & ((decision_bias == "BULLISH") | (decision_bias == "BEARISH"))
    )
    log("F", "audit:orchestrator", "post-hoc agent analysis vs signals", {
        "filter_agents_all_true_without_orch": bool(mini_no["filter_agents"].all()),
        "filter_agents_pass_rate_with_real_agent_cols": float(mini_with_recomputed["filter_agents"].mean()),
        "agent_decision_neutral_count": int((mini_with["agent_decision_bias"] == "NEUTRAL").sum()),
        "agent_decision_bullish_count": int((mini_with["agent_decision_bias"] == "BULLISH").sum()),
        "agent_decision_bearish_count": int((mini_with["agent_decision_bias"] == "BEARISH").sum()),
        "post_hoc_would_change_filter_agents": bool(
            (mini_no["filter_agents"] != mini_with_recomputed["filter_agents"]).any()
        ),
    })

    print(f"Audit complete. Log: {LOG_PATH}")


if __name__ == "__main__":
    main()

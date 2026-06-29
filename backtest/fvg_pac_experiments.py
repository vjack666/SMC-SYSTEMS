from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backtest.fvg_mitigation_backtest import MitigationBacktestConfig, _build_events, _risk_usd, _simulate_trade
from modules.bos.detector import BosConfig, detect_bos
from modules.choch.detector import detect_choch
from modules.fvg.backtest import _load
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import score_frame
from modules.ob.detector import detect_order_blocks
from pac_sequence.feature_builder import build_pac_feature_row, build_prev_day_levels
from pac_sequence.state_machine import StateMachineConfig, run_state_machine
from pac_sequence.validation import (
    check_no_lookahead,
    check_reproducibility,
    run_walk_forward_probabilities,
    write_validation_snapshot,
)


@dataclass(frozen=True)
class PACExperimentConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    model_path: Path = Path("modules/fvg/models/fvg_v3.pkl")
    confidence_threshold: float = 0.62
    initial_capital_usd: float = 6000.0
    risk_pct_per_trade: float = 0.005
    atr_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    rr_ratio: float = 3.0
    max_hold_bars: int = 16
    train_split: float = 0.6
    mitigation_lookahead_bars: int = 300
    ttl_bars: int = 64
    mitigation_method: str = "wick"
    ml_threshold_e: float = 0.55
    verify_baseline_with_existing_artifacts: bool = True


def _session_bucket(ts: pd.Timestamp) -> str:
    hour = int(pd.to_datetime(ts, utc=True).hour)
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "overlap"
    if 17 <= hour < 22:
        return "new_york"
    return "off_session"


def _structure_event(row: pd.Series, direction: int) -> str:
    bos = int(pd.to_numeric(row.get("bos_direction", 0), errors="coerce"))
    choch = str(row.get("choch_signal", "NONE")).upper()
    if (direction == 1 and bos > 0) or (direction == -1 and bos < 0):
        return "bos"
    if (direction == 1 and "BULLISH" in choch) or (direction == -1 and "BEARISH" in choch):
        return "choch"
    return "none"


def _metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "total_trades": 0,
            "winrate": np.nan,
            "profit_factor": np.nan,
            "expectancy": np.nan,
            "average_rr": np.nan,
            "max_drawdown": np.nan,
            "sharpe": np.nan,
            "calmar": np.nan,
            "equity_final": 0.0,
        }

    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    if pnl.empty:
        return {
            "total_trades": 0,
            "winrate": np.nan,
            "profit_factor": np.nan,
            "expectancy": np.nan,
            "average_rr": np.nan,
            "max_drawdown": np.nan,
            "sharpe": np.nan,
            "calmar": np.nan,
            "equity_final": 0.0,
        }

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else float("inf")
    eq = pnl.cumsum()
    dd = float(abs((eq - eq.cummax()).min()))

    std = float(pnl.std(ddof=0))
    sharpe = float((pnl.mean() / std) * np.sqrt(len(pnl))) if std > 0 else np.nan

    avg_win = float(wins.mean()) if not wins.empty else np.nan
    avg_loss = float(abs(losses.mean())) if not losses.empty else np.nan
    if np.isfinite(avg_win) and np.isfinite(avg_loss) and avg_loss > 0:
        avg_rr = float(avg_win / avg_loss)
    elif np.isfinite(avg_win):
        avg_rr = float("inf")
    else:
        avg_rr = np.nan

    equity_final = float(pnl.sum())
    calmar = float(equity_final / dd) if dd > 0 else float("inf")

    return {
        "total_trades": int(len(pnl)),
        "winrate": float((pnl > 0).mean()),
        "profit_factor": pf,
        "expectancy": float(pnl.mean()),
        "average_rr": avg_rr,
        "max_drawdown": dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "equity_final": equity_final,
    }


def _encode_for_ml(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    data = frame.copy()
    cat_cols = ["ob_state", "session_bucket", "structure_event", "structure_scale", "side", "symbol"]
    for col in cat_cols:
        data[f"{col}_code"] = data[col].astype("category").cat.codes.astype(float)

    feature_cols = [
        "bars_since_fvg_creation",
        "bars_since_mitigation",
        "mitigation_depth_pct",
        "mitigation_touch_count",
        "distance_prev_day_high",
        "distance_prev_day_low",
        "distance_eqh",
        "distance_eql",
        "ob_overlap_with_fvg",
        "hour_sin",
        "hour_cos",
    ] + [f"{col}_code" for col in cat_cols]

    return data, feature_cols


def _build_audit_summary(
    out_dir: Path,
    comparison: pd.DataFrame,
    feature_importance: pd.DataFrame,
    baseline_check: dict[str, object],
    validation_payload: dict[str, object],
) -> None:
    row = {r["experiment_id"]: r for r in comparison.to_dict(orient="records")}

    def _delta(exp: str, metric: str) -> float:
        if "A" not in row or exp not in row:
            return float("nan")
        return float(row[exp][metric]) - float(row["A"][metric])

    lines = [
        "# Audit Summary PAC/FVG",
        "",
        "## Baseline Consistency",
        f"- baseline_consistent: {baseline_check.get('baseline_consistent')}",
        f"- baseline_reference: {baseline_check.get('reference')}",
        "",
        "## Preguntas de negocio",
        f"1. Mitigacion aporta edge: delta_expectancy_B_vs_A={_delta('B', 'expectancy'):.6f}, delta_pf_B_vs_A={_delta('B', 'profit_factor'):.6f}",
        f"2. Estructura aporta edge: delta_expectancy_C_vs_B={float(row.get('C', {}).get('expectancy', np.nan)) - float(row.get('B', {}).get('expectancy', np.nan)):.6f}",
        f"3. Sesiones aportan edge: delta_expectancy_D_vs_C={float(row.get('D', {}).get('expectancy', np.nan)) - float(row.get('C', {}).get('expectancy', np.nan)):.6f}",
        f"4. ML aporta edge real: delta_expectancy_E_vs_D={float(row.get('E', {}).get('expectancy', np.nan)) - float(row.get('D', {}).get('expectancy', np.nan)):.6f}",
        f"5. Configuracion optima por expectancy: {comparison.sort_values('expectancy', ascending=False).iloc[0]['experiment_id'] if not comparison.empty else 'N/A'}",
        "6. Variables explicativas principales: ver feature_importance.csv",
        "7. Reglas candidatas a produccion: solo experimentos pass_success_criteria=true",
        "8. Evidencia tabular: comparison_table.csv + symbol_breakdown.csv + expectancy_report.csv + drawdown_report.csv",
        "",
        "## Validacion tecnica",
        f"- no_lookahead_ok: {validation_payload.get('no_lookahead', {}).get('ok')}",
        f"- no_lookahead_violations: {validation_payload.get('no_lookahead', {}).get('violations')}",
        f"- walk_forward_folds: {validation_payload.get('walk_forward', {}).get('n_folds')}",
        f"- walk_forward_auc_mean: {validation_payload.get('walk_forward', {}).get('auc_mean')}",
    ]

    if not feature_importance.empty:
        lines.append("")
        lines.append("## Top Feature Importance (ML E)")
        for _, r in feature_importance.head(10).iterrows():
            lines.append(f"- {r['feature']}: {float(r['importance']):.6f}")

    (out_dir / "audit_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pac_experiments(experiment: str = "ALL", config: PACExperimentConfig | None = None) -> dict[str, object]:
    if config is None:
        config = PACExperimentConfig()

    selected = [experiment] if experiment in {"A", "B", "C", "D", "E"} else ["A", "B", "C", "D", "E"]

    # E requires D candidates; ensure D is always processed when E is selected.
    process_set: list[str] = list(selected)
    if "E" in selected and "D" not in process_set:
        process_set.append("D")

    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = joblib.load(config.model_path)
    base_model = payload["model"]
    risk_usd = _risk_usd(
        MitigationBacktestConfig(
            initial_capital_usd=config.initial_capital_usd,
            risk_pct_per_trade=config.risk_pct_per_trade,
        )
    )

    trade_rows: dict[str, list[dict[str, object]]] = {k: [] for k in ["A", "B", "C", "D", "E"]}
    transition_rows: list[dict[str, object]] = []
    invalidation_rows: list[dict[str, object]] = []
    e_candidates: list[dict[str, object]] = []

    for symbol in config.symbols:
        frame = _load(config.data_dir, symbol)
        frame = detect_fvg(frame)
        frame = detect_bos(frame, BosConfig(followthrough_bars=18))
        frame = detect_choch(frame)
        frame = detect_order_blocks(frame)

        split = int(len(frame) * config.train_split)
        scored = score_frame(frame.iloc[split:].copy(), base_model).reset_index(drop=True)
        levels = build_prev_day_levels(scored)

        high_arr = pd.to_numeric(scored["high"], errors="coerce").to_numpy(dtype=float)
        low_arr = pd.to_numeric(scored["low"], errors="coerce").to_numpy(dtype=float)
        close_arr = pd.to_numeric(scored["close"], errors="coerce").to_numpy(dtype=float)
        atr_arr = pd.to_numeric(scored["atr"], errors="coerce").to_numpy(dtype=float)

        events = _build_events(scored, config.confidence_threshold, config.mitigation_lookahead_bars)
        if events.empty:
            continue

        for event_no, ev in events.reset_index(drop=True).iterrows():
            create_idx = int(ev["create_idx"])
            direction = int(ev["direction"])
            side = str(ev["side"])
            setup_id = f"{symbol}_{create_idx}_{side}_{event_no}"

            sm_result = run_state_machine(
                scored=scored,
                create_idx=create_idx,
                direction=direction,
                zone_low=float(ev["zone_low"]),
                zone_high=float(ev["zone_high"]),
                config=StateMachineConfig(ttl_bars=config.ttl_bars, mitigation_method=config.mitigation_method),
                setup_id=setup_id,
            )
            transition_rows.extend(sm_result["transitions"])
            invalidation_rows.extend(sm_result["invalidations"])

            idx_A = create_idx
            idx_B = int(ev["retest_idx"]) if pd.notna(ev["retest_idx"]) else None
            idx_C = int(sm_result["entry_idx"]) if sm_result["entry_idx"] is not None else None
            idx_D = idx_C
            if idx_D is not None:
                sb = _session_bucket(pd.to_datetime(scored.iloc[idx_D]["time"], utc=True))
                if sb not in {"london", "new_york", "overlap"}:
                    idx_D = None

            exp_to_idx = {"A": idx_A, "B": idx_B, "C": idx_C, "D": idx_D}

            for exp_id, entry_idx in exp_to_idx.items():
                if exp_id not in process_set or entry_idx is None:
                    continue

                row = scored.iloc[int(entry_idx)]
                feature_row = build_pac_feature_row(
                    scored=scored,
                    idx=int(entry_idx),
                    create_idx=create_idx,
                    mitigation_idx=sm_result["mitigation_idx"],
                    direction=direction,
                    zone_low=float(ev["zone_low"]),
                    zone_high=float(ev["zone_high"]),
                    touch_count=int(sm_result["touch_count"]),
                    structure_scale="internal",
                    structure_event=_structure_event(row, direction),
                    imbalance_state="mitigated" if sm_result["mitigation_idx"] is not None else "new",
                    mitigation_method=config.mitigation_method,
                    levels=levels,
                )

                for sl_mult in config.atr_multipliers:
                    entry_price = float(ev["create_close"]) if exp_id == "A" else float(ev["limit_price"])
                    if exp_id in {"C", "D"}:
                        entry_price = float(pd.to_numeric(row["close"], errors="coerce"))

                    pnl_r, hold = _simulate_trade(
                        high_arr=high_arr,
                        low_arr=low_arr,
                        close_arr=close_arr,
                        atr_arr=atr_arr,
                        entry_idx=int(entry_idx),
                        entry_price=entry_price,
                        direction=direction,
                        sl_mult=float(sl_mult),
                        rr_ratio=config.rr_ratio,
                        max_hold_bars=config.max_hold_bars,
                    )

                    base_trade = {
                        "experiment": exp_id,
                        "setup_id": setup_id,
                        "symbol": symbol,
                        "side": side,
                        "create_time": str(ev["create_time"]),
                        "entry_time": str(scored.iloc[int(entry_idx)]["time"]),
                        "exit_time": str(scored.iloc[min(int(entry_idx) + int(hold), len(scored) - 1)]["time"]),
                        "entry_idx": int(entry_idx),
                        "sl_atr_mult": float(sl_mult),
                        "ml_confidence": float(ev["ml_confidence"]),
                        "pnl_r": float(pnl_r),
                        "pnl_usd": float(pnl_r * risk_usd),
                        "holding_bars": int(hold),
                        "session_bucket": _session_bucket(pd.to_datetime(scored.iloc[int(entry_idx)]["time"], utc=True)),
                        "structure_event": feature_row["structure_event"],
                        "structure_scale": feature_row["structure_scale"],
                        "ob_state": feature_row["ob_state"],
                        **feature_row,
                    }
                    trade_rows[exp_id].append(base_trade)

                    if exp_id == "D":
                        cand = dict(base_trade)
                        cand["target_win"] = int(float(pnl_r) > 0.0)
                        e_candidates.append(cand)

    # Experiment E: D + ML with walk-forward OOF probabilities.
    feature_importance = pd.DataFrame(columns=["feature", "importance"])
    if "E" in selected:
        e_df = pd.DataFrame(e_candidates)
        if not e_df.empty:
            encoded, ml_features = _encode_for_ml(e_df)
            probs, wf_report, model = run_walk_forward_probabilities(encoded, ml_features, "target_win", n_splits=5)
            encoded["ml_oof_probability"] = probs
            keep = encoded["ml_oof_probability"].fillna(0.0) >= float(config.ml_threshold_e)
            trade_rows["E"] = encoded[keep].drop(columns=["target_win"]).to_dict(orient="records")

            if model is not None:
                feature_importance = pd.DataFrame(
                    {
                        "feature": ml_features,
                        "importance": model.feature_importances_,
                    }
                ).sort_values("importance", ascending=False)

            validation_payload = {
                "walk_forward": wf_report,
                "samples_for_ml": int(len(encoded)),
                "threshold": float(config.ml_threshold_e),
            }
        else:
            validation_payload = {"walk_forward": {"n_folds": 0}, "samples_for_ml": 0, "threshold": float(config.ml_threshold_e)}
    else:
        validation_payload = {"walk_forward": {"n_folds": 0}, "samples_for_ml": 0, "threshold": float(config.ml_threshold_e)}

    # Persist experiment trade logs.
    for exp_id in selected:
        df = pd.DataFrame(trade_rows.get(exp_id, []))
        df.to_csv(out_dir / f"experiment_{exp_id}.csv", index=False)

    transition_df = pd.DataFrame(transition_rows)
    invalidation_df = pd.DataFrame(invalidation_rows)
    transition_df.to_csv(out_dir / "state_transition_log.csv", index=False)
    invalidation_df.to_csv(out_dir / "invalidation_log.csv", index=False)

    # Comparison and reports.
    comparison_rows: list[dict[str, object]] = []
    expectancy_rows: list[dict[str, object]] = []
    drawdown_rows: list[dict[str, object]] = []
    symbol_rows: list[dict[str, object]] = []

    base_metrics = _metrics(pd.DataFrame(trade_rows.get("A", []))) if "A" in selected else None

    for exp_id in selected:
        df = pd.DataFrame(trade_rows.get(exp_id, []))
        m = _metrics(df)
        delta_pf = float(m["profit_factor"] - base_metrics["profit_factor"]) if base_metrics is not None and np.isfinite(base_metrics["profit_factor"]) and np.isfinite(m["profit_factor"]) else np.nan
        delta_exp = float(m["expectancy"] - base_metrics["expectancy"]) if base_metrics is not None and np.isfinite(base_metrics["expectancy"]) and np.isfinite(m["expectancy"]) else np.nan
        delta_dd = float(m["max_drawdown"] - base_metrics["max_drawdown"]) if base_metrics is not None and np.isfinite(base_metrics["max_drawdown"]) and np.isfinite(m["max_drawdown"]) else np.nan

        pass_success = bool(
            base_metrics is None
            or (
                (np.isfinite(delta_exp) and delta_exp > 0)
                or (np.isfinite(delta_pf) and delta_pf > 0)
                or (np.isfinite(delta_dd) and delta_dd < 0)
            )
        )

        comparison_rows.append(
            {
                "experiment_id": exp_id,
                **m,
                "delta_pf_vs_A": delta_pf,
                "delta_expectancy_vs_A": delta_exp,
                "delta_dd_vs_A": delta_dd,
                "pass_success_criteria": pass_success,
            }
        )

        if not df.empty:
            by_symbol = df.groupby(["symbol", "side"], dropna=False).apply(lambda x: pd.Series(_metrics(x))).reset_index()
            for _, sr in by_symbol.iterrows():
                symbol_rows.append({"experiment_id": exp_id, **sr.to_dict()})

            exp_session = df.groupby("session_bucket", dropna=False)["pnl_r"].agg(["count", "mean"]).reset_index()
            for _, er in exp_session.iterrows():
                expectancy_rows.append(
                    {
                        "experiment_id": exp_id,
                        "session_bucket": er["session_bucket"],
                        "trades": int(er["count"]),
                        "expectancy": float(er["mean"]),
                    }
                )

            dd_symbol = df.groupby("symbol", dropna=False).apply(lambda x: pd.Series(_metrics(x))).reset_index()
            for _, dr in dd_symbol.iterrows():
                drawdown_rows.append(
                    {
                        "experiment_id": exp_id,
                        "symbol": dr["symbol"],
                        "max_drawdown": float(dr["max_drawdown"]),
                        "equity_final": float(dr["equity_final"]),
                    }
                )

    comparison_df = pd.DataFrame(comparison_rows)
    expectancy_df = pd.DataFrame(expectancy_rows)
    drawdown_df = pd.DataFrame(drawdown_rows)
    symbol_df = pd.DataFrame(symbol_rows)

    comparison_df.to_csv(out_dir / "comparison_table.csv", index=False)
    expectancy_df.to_csv(out_dir / "expectancy_report.csv", index=False)
    drawdown_df.to_csv(out_dir / "drawdown_report.csv", index=False)
    symbol_df.to_csv(out_dir / "symbol_breakdown.csv", index=False)
    feature_importance.to_csv(out_dir / "feature_importance.csv", index=False)

    legacy_metrics = pd.read_csv(out_dir / "fvg_mitigation_metrics.csv") if (out_dir / "fvg_mitigation_metrics.csv").exists() else pd.DataFrame()
    legacy_a = legacy_metrics[(legacy_metrics.get("strategy") == "A_immediate") & (legacy_metrics.get("side") == "ALL")]
    new_a = pd.DataFrame(trade_rows.get("A", []))

    baseline_check = {
        "baseline_consistent": bool(not new_a.empty and not legacy_a.empty and int(len(new_a)) == int(legacy_a["total_trades"].sum())),
        "reference": {
            "metrics": "results/fvg_mitigation_metrics.csv",
            "trade_log": "results/fvg_mitigation_trade_log.csv",
            "comparison_summary": "results/fvg_mitigation_comparison_summary.json",
        },
        "legacy_total_trades_sum": int(legacy_a["total_trades"].sum()) if not legacy_a.empty else 0,
        "new_total_trades": int(len(new_a)),
    }

    # Validation snapshot.
    no_look = check_no_lookahead(pd.DataFrame(trade_rows.get("A", [])))
    validation_payload["no_lookahead"] = no_look
    write_validation_snapshot(out_dir / "validation_snapshot.json", validation_payload)

    repro_payload = check_reproducibility(
        [
            out_dir / "comparison_table.csv",
            out_dir / "state_transition_log.csv",
            out_dir / "invalidation_log.csv",
            out_dir / "expectancy_report.csv",
            out_dir / "drawdown_report.csv",
            out_dir / "symbol_breakdown.csv",
        ]
    )
    write_validation_snapshot(out_dir / "reproducibility_snapshot.json", repro_payload)

    _build_audit_summary(out_dir, comparison_df, feature_importance, baseline_check, validation_payload)

    summary = {
        "selected_experiments": selected,
        "files": {
            "comparison_table": "results/comparison_table.csv",
            "state_transition_log": "results/state_transition_log.csv",
            "invalidation_log": "results/invalidation_log.csv",
            "expectancy_report": "results/expectancy_report.csv",
            "drawdown_report": "results/drawdown_report.csv",
            "symbol_breakdown": "results/symbol_breakdown.csv",
            "feature_importance": "results/feature_importance.csv",
            "audit_summary": "results/audit_summary.md",
            "validation_snapshot": "results/validation_snapshot.json",
            "reproducibility_snapshot": "results/reproducibility_snapshot.json",
        },
        "baseline_check": baseline_check,
    }

    (out_dir / "pac_experiments_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

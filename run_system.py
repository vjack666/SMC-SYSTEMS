from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from backtest.combined_backtest import (
    CombinedBacktestConfig,
    generate_prop_firm_report,
    metrics_pass_thresholds,
    run_combined_backtest,
    run_calibration,
    run_filter_diagnosis,
    run_oos_backtest,
    run_per_symbol,
)
from data.mt5.downloader import DownloadConfig, run_download
from ml.feature_pipeline import build_feature_pipeline
from ml.train_quality_model import TrainingConfig, train_quality_model


RESULTS_DIR = Path("results")
DATA_DIR = Path("data/mt5")
SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
TIMEFRAMES = ("M15", "H1", "H4", "D1")


@dataclass(frozen=True)
class SystemStatus:
    mt5_available: bool
    data_refreshed: bool
    filter_diagnosis_file: str
    calibration_log_file: str
    training_summary_file: str
    combined_metrics_file: str
    oos_metrics_file: str
    per_symbol_metrics_files: list[str]
    prop_report_file: str
    status_file: str


def _mt5_available() -> bool:
    return importlib.util.find_spec("MetaTrader5") is not None


def _expected_parquet_paths(symbols: Iterable[str], timeframes: Iterable[str]) -> list[Path]:
    return [DATA_DIR / f"{symbol}_{timeframe}.parquet" for symbol in symbols for timeframe in timeframes]


def _is_data_fresh(max_age_hours: int = 24) -> bool:
    expected = _expected_parquet_paths(SYMBOLS, TIMEFRAMES)
    if any(not path.exists() for path in expected):
        return False

    latest_mtime = max(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) for path in expected)
    return datetime.now(tz=timezone.utc) - latest_mtime < timedelta(hours=max_age_hours)


def _refresh_data_if_needed() -> bool:
    if _is_data_fresh(24):
        print("Data freshness check: existing parquet files are <24h old, skipping MT5 download.")
        return False

    if not _mt5_available():
        print("MetaTrader5 package unavailable. Skipping download and using local data if present.")
        return False

    print("Data freshness check: stale or missing files found, downloading fresh MT5 data.")
    config = DownloadConfig(output_dir=DATA_DIR)
    run_download(config)
    return True


def _print_console_matrix(metrics: dict[str, float | int]) -> None:
    print("\n=== SYSTEM MATRIX ===")
    print(f"{'Metric':<26} | {'Value':>12}")
    print(f"{'-' * 26}-+-{'-' * 12}")
    ordered = [
        "total_trades",
        "win_rate",
        "profit_factor",
        "max_drawdown_r",
        "max_drawdown_pct",
        "max_daily_drawdown_pct",
        "sharpe_ratio",
        "expectancy_r",
    ]
    for key in ordered:
        value = metrics.get(key, "n/a")
        if isinstance(value, float):
            print(f"{key:<26} | {value:>12.4f}")
        else:
            print(f"{key:<26} | {value:>12}")


def _load_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _relative_degradation(in_sample: float, oos: float) -> float:
    base = max(abs(in_sample), 1e-9)
    return (in_sample - oos) / base


def _build_overfit_flags(in_sample: dict[str, float | int], oos: dict[str, float | int]) -> tuple[bool, list[str]]:
    checks = ["win_rate", "profit_factor", "sharpe_ratio", "expectancy_r"]
    warnings: list[str] = []
    overfit = False
    for key in checks:
        ins = float(in_sample.get(key, 0.0))
        out = float(oos.get(key, 0.0))
        if _relative_degradation(ins, out) > 0.30:
            overfit = True
            warnings.append(f"OOS degradation >30% on {key}: IS={ins:.4f}, OOS={out:.4f}")
    return overfit, warnings


def _symbol_viability(symbol_metrics: dict[str, float | int]) -> bool:
    return (
        int(symbol_metrics.get("total_trades", 0)) >= 5
        and float(symbol_metrics.get("profit_factor", 0.0)) >= 1.0
        and float(symbol_metrics.get("expectancy_r", 0.0)) >= 0.0
    )


def _write_status_file(
    status: SystemStatus,
    in_sample: dict[str, float | int],
    oos: dict[str, float | int],
    per_symbol: dict[str, dict[str, float | int]],
    warnings: list[str],
    enabled_symbols: list[str],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    is_pass = metrics_pass_thresholds(in_sample)
    oos_pass = metrics_pass_thresholds(oos)
    symbol_pass = {symbol: metrics_pass_thresholds(metrics) for symbol, metrics in per_symbol.items()}
    ready = is_pass and oos_pass and all(symbol_pass.values()) and not warnings

    reasons: list[str] = []
    if not is_pass:
        reasons.append("In-sample thresholds not met.")
    if not oos_pass:
        reasons.append("Out-of-sample thresholds not met.")
    if not all(symbol_pass.values()):
        reasons.append("One or more symbols failed thresholds.")
    reasons.extend(warnings)

    payload = {
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "system": asdict(status),
        "status": "READY" if ready else "NOT_READY",
        "checks": {
            "in_sample_pass": is_pass,
            "out_of_sample_pass": oos_pass,
            "per_symbol_pass": symbol_pass,
            "overfit_detected": bool(warnings),
        },
        "enabled_symbols": enabled_symbols,
        "in_sample": in_sample,
        "out_of_sample": oos,
        "per_symbol": per_symbol,
        "reasons": reasons,
    }
    (RESULTS_DIR / "status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _consistency_check() -> dict[str, object]:
    metrics = _load_json(RESULTS_DIR / "combined_metrics.json", {})
    status = _load_json(RESULTS_DIR / "status.json", {})
    trades_path = RESULTS_DIR / "combined_trades.csv"
    trades_rows = 0
    if trades_path.exists():
        try:
            trades_rows = int(len(pd.read_csv(trades_path)))
        except (OSError, ValueError):
            trades_rows = 0

    total_trades = int(float((metrics or {}).get("total_trades", 0))) if isinstance(metrics, dict) else 0
    consistent = bool(total_trades == trades_rows)
    return {
        "consistent": consistent,
        "total_trades_metrics": total_trades,
        "rows_combined_trades_csv": trades_rows,
        "status_flag": (status or {}).get("status", "UNKNOWN") if isinstance(status, dict) else "UNKNOWN",
    }


def _write_audit_report(
    in_sample: dict[str, float | int],
    oos: dict[str, float | int],
    per_symbol: dict[str, dict[str, float | int]],
    consistency: dict[str, object],
) -> None:
    lines = [
        "# Audit Report",
        "",
        f"- Timestamp UTC: {datetime.now(tz=timezone.utc).isoformat()}",
        f"- Consistency metrics vs trades CSV: {consistency.get('consistent')}",
        f"- total_trades(metrics): {consistency.get('total_trades_metrics')}",
        f"- rows(combined_trades.csv): {consistency.get('rows_combined_trades_csv')}",
        "",
        "## In-Sample",
        f"- Trades: {int(in_sample.get('total_trades', 0))}",
        f"- WinRate: {float(in_sample.get('win_rate', 0.0)):.4f}",
        f"- PF: {float(in_sample.get('profit_factor', 0.0)):.4f}",
        f"- MaxDD%: {float(in_sample.get('max_drawdown_pct', 0.0)):.4f}",
        "",
        "## Out-of-Sample",
        f"- Trades: {int(oos.get('total_trades', 0))}",
        f"- WinRate: {float(oos.get('win_rate', 0.0)):.4f}",
        f"- PF: {float(oos.get('profit_factor', 0.0)):.4f}",
        f"- MaxDD%: {float(oos.get('max_drawdown_pct', 0.0)):.4f}",
        "",
        "## Per Symbol",
    ]
    for symbol, metrics in per_symbol.items():
        lines.append(
            f"- {symbol}: trades={int(metrics.get('total_trades', 0))}, "
            f"wr={float(metrics.get('win_rate', 0.0)):.4f}, "
            f"pf={float(metrics.get('profit_factor', 0.0)):.4f}, "
            f"dd={float(metrics.get('max_drawdown_pct', 0.0)):.4f}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_walk_forward(base: CombinedBacktestConfig) -> pd.DataFrame:
    frame = pd.read_parquet(base.data_dir / f"{base.symbols[0]}_{base.timeframe}.parquet")
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    start = frame["time"].min()
    end = frame["time"].max()

    rows: list[dict[str, object]] = []
    cursor = start
    while cursor + pd.DateOffset(months=4) <= end:
        train_start = cursor
        train_end = cursor + pd.DateOffset(months=3)
        test_start = train_end
        test_end = cursor + pd.DateOffset(months=4)
        cfg = CombinedBacktestConfig(
            **{
                **asdict(base),
                "start_time": str(test_start),
                "end_time": str(test_end),
            }
        )
        try:
            m, _ = run_combined_backtest(cfg)
        except RuntimeError:
            m = {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "expectancy_r": 0.0,
            }
        rows.append(
            {
                "train_start": str(train_start),
                "train_end": str(train_end),
                "test_start": str(test_start),
                "test_end": str(test_end),
                **m,
            }
        )
        cursor = cursor + pd.DateOffset(months=1)

    wf = pd.DataFrame(rows)
    wf.to_csv(RESULTS_DIR / "walk_forward_report.csv", index=False)
    return wf


def _run_monte_carlo(base_metrics: dict[str, float | int], trades_df: pd.DataFrame) -> dict[str, object]:
    pnl = pd.to_numeric(trades_df.get("pnl_r", pd.Series(dtype=float)), errors="coerce").dropna().astype(float)
    if pnl.empty:
        report = {"runs": 0, "ruin_probability": 1.0, "p5_expectancy": 0.0, "p95_expectancy": 0.0}
        (RESULTS_DIR / "monte_carlo_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    sims = []
    n = len(pnl)
    arr = pnl.to_numpy()
    rng = np.random.default_rng(42)
    for _ in range(500):
        sample = rng.choice(arr, size=n, replace=True)
        spread_noise = rng.normal(0.0, 0.05, size=n)
        slip_noise = rng.normal(0.0, 0.03, size=n)
        stressed = sample - spread_noise - slip_noise
        eq = np.cumsum(stressed)
        dd = eq - np.maximum.accumulate(eq)
        sims.append(
            {
                "expectancy": float(stressed.mean()),
                "max_dd": float(abs(dd.min())),
                "ruin": bool(abs(dd.min()) > 8.0),
            }
        )

    exp_vals = np.array([s["expectancy"] for s in sims], dtype=float)
    ruin = float(np.mean([1.0 if s["ruin"] else 0.0 for s in sims]))
    report = {
        "runs": len(sims),
        "ruin_probability": ruin,
        "p5_expectancy": float(np.quantile(exp_vals, 0.05)),
        "p95_expectancy": float(np.quantile(exp_vals, 0.95)),
        "base_metrics": base_metrics,
    }
    (RESULTS_DIR / "monte_carlo_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _write_final_diagnostic(
    in_sample: dict[str, float | int],
    oos: dict[str, float | int],
    wf: pd.DataFrame,
    mc: dict[str, object],
    status_payload: dict[str, Any],
    model_metrics: dict[str, Any],
) -> None:
    lines = [
        "# Final Funding Diagnostic",
        "",
        "## Global Metrics",
        f"- PF: {float(in_sample.get('profit_factor', 0.0)):.4f}",
        f"- WR: {float(in_sample.get('win_rate', 0.0)):.4f}",
        f"- Sharpe: {float(in_sample.get('sharpe_ratio', 0.0)):.4f}",
        f"- Expectancy: {float(in_sample.get('expectancy_r', 0.0)):.4f}",
        f"- Max DD%: {float(in_sample.get('max_drawdown_pct', 0.0)):.4f}",
        f"- Daily DD%: {float(in_sample.get('max_daily_drawdown_pct', 0.0)):.4f}",
        "",
        "## OOS Metrics",
        f"- Trades: {int(oos.get('total_trades', 0))}",
        f"- PF: {float(oos.get('profit_factor', 0.0)):.4f}",
        f"- WR: {float(oos.get('win_rate', 0.0)):.4f}",
        "",
        "## Walk Forward",
        f"- Windows: {int(len(wf))}",
        "",
        "## Monte Carlo",
        f"- Ruin Probability: {float(mc.get('ruin_probability', 1.0)):.4f}",
        f"- P5 Expectancy: {float(mc.get('p5_expectancy', 0.0)):.4f}",
        "",
        "## ML Diagnostics",
        f"- Model: {model_metrics.get('model', 'n/a')}",
        f"- ROC AUC: {float(model_metrics.get('roc_auc', 0.0)):.4f}",
        f"- Brier: {float(model_metrics.get('brier_score', 1.0)):.4f}",
        "",
        "## Final Status",
        f"- {status_payload.get('status', 'NOT_READY')}",
    ]
    (RESULTS_DIR / "final_funding_diagnostic.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    refreshed = _refresh_data_if_needed()

    print("Running filter diagnosis (E1)...")
    run_filter_diagnosis(CombinedBacktestConfig())

    best_config = CombinedBacktestConfig()
    best_in_sample: dict[str, float | int] = {
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "max_drawdown_r": 0.0,
        "max_drawdown_pct": 0.0,
        "max_daily_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "expectancy_r": 0.0,
    }
    best_score = -1e9

    model_metrics: dict[str, Any] = {}
    for iteration in range(1, 6):
        print(f"\n[ITERATION {iteration}] Running calibration and baseline backtest...")
        chosen_config, in_sample = run_calibration(best_config)

        if int(in_sample.get("total_trades", 0)) == 0:
            print(f"[ITERATION {iteration}] Calibration produced 0 trades. Ending optimization loop early.")
            if best_score <= -1e8:
                best_config = chosen_config
                best_in_sample = in_sample
                best_score = -1e7
            break

        try:
            _, _ = run_combined_backtest(chosen_config)
        except RuntimeError:
            pass

        dataset_path = RESULTS_DIR / "ml_trade_dataset.csv"
        if dataset_path.exists():
            ds = pd.read_csv(dataset_path)
            ds, schema = build_feature_pipeline(ds)
            (RESULTS_DIR / "dataset_schema_snapshot.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
            ds.to_csv(dataset_path, index=False)

            print(f"[ITERATION {iteration}] Training ML quality filter...")
            model_metrics = train_quality_model(
                TrainingConfig(
                    dataset_path=dataset_path,
                    model_dir=Path("ml/models"),
                    metrics_path=Path("ml/model_metrics.json"),
                    importance_path=Path("ml/feature_importance.csv"),
                )
            )
            chosen_config = CombinedBacktestConfig(
                **{
                    **asdict(chosen_config),
                    "use_ml_quality_filter": True,
                    "ml_model_path": Path("ml/models/quality_filter.pkl"),
                }
            )

            try:
                in_sample, _ = run_combined_backtest(chosen_config)
            except RuntimeError:
                pass

        score = (
            float(in_sample.get("profit_factor", 0.0)) * 2.0
            + float(in_sample.get("sharpe_ratio", 0.0))
            + float(in_sample.get("expectancy_r", 0.0))
            - float(in_sample.get("max_drawdown_pct", 0.0)) * 0.25
            - float(in_sample.get("max_daily_drawdown_pct", 0.0)) * 0.5
        )
        if score > best_score:
            best_score = score
            best_config = chosen_config
            best_in_sample = in_sample

        if (
            float(in_sample.get("profit_factor", 0.0)) > 1.40
            and float(in_sample.get("max_drawdown_pct", 999.0)) < 8.0
            and float(in_sample.get("max_daily_drawdown_pct", 999.0)) < 4.0
            and float(in_sample.get("sharpe_ratio", -99.0)) > 1.0
            and float(in_sample.get("expectancy_r", -99.0)) > 0.0
            and int(in_sample.get("total_trades", 0)) >= 200
        ):
            print(f"[ITERATION {iteration}] Funding thresholds reached in-sample. Stopping optimization loop.")
            break

    chosen_config = best_config
    in_sample = best_in_sample

    print("Running out-of-sample validation (F)...")
    oos = run_oos_backtest(chosen_config)

    print("Running per-symbol validation (G)...")
    per_symbol = run_per_symbol(chosen_config)

    training_summary = _load_json(RESULTS_DIR / "training_summary.json", {})
    if not isinstance(training_summary, dict):
        training_summary = {}

    overfit, warnings = _build_overfit_flags(in_sample, oos)
    if overfit:
        print("Overfit warning: OOS degradation above 30% detected.")

    enabled_symbols = [s for s, m in per_symbol.items() if _symbol_viability(m)]
    if not enabled_symbols:
        enabled_symbols = list(chosen_config.symbols)

    chosen_scalping = (
        chosen_config.scalping_config
        if isinstance(chosen_config.scalping_config, dict)
        else asdict(chosen_config.scalping_config)
    )

    report_payload = {
        "in_sample": in_sample,
        "out_of_sample": oos,
        "per_symbol": per_symbol,
        "calibration_history": _load_json(RESULTS_DIR / "calibration_log.json", []),
        "training_summary": training_summary,
        "recommended": {
            **chosen_scalping,
            "min_confidence": chosen_config.min_confidence,
            "enabled_symbols": enabled_symbols,
        },
        "warnings": warnings,
    }
    generate_prop_firm_report(report_payload)

    consistency = _consistency_check()
    _write_audit_report(in_sample, oos, per_symbol, consistency)

    try:
        _, combined_trades_df = run_combined_backtest(chosen_config)
    except RuntimeError:
        combined_trades_df = pd.DataFrame()

    wf = _run_walk_forward(chosen_config)
    mc = _run_monte_carlo(in_sample, combined_trades_df)

    print("\n=== IN-SAMPLE ===")
    _print_console_matrix(in_sample)
    print("\n=== OUT-OF-SAMPLE ===")
    _print_console_matrix(oos)

    print("\n=== PER-SYMBOL STATUS ===")
    for symbol, metrics in per_symbol.items():
        status_label = "PASS" if metrics_pass_thresholds(metrics) else "FAIL"
        print(
            f"{symbol}: {status_label} | trades={int(metrics.get('total_trades', 0))} | "
            f"wr={float(metrics.get('win_rate', 0.0)):.4f} | pf={float(metrics.get('profit_factor', 0.0)):.4f}"
        )

    status = SystemStatus(
        mt5_available=_mt5_available(),
        data_refreshed=refreshed,
        filter_diagnosis_file=str(RESULTS_DIR / "filter_diagnosis.json"),
        calibration_log_file=str(RESULTS_DIR / "calibration_log.json"),
        training_summary_file=str(RESULTS_DIR / "training_summary.json"),
        combined_metrics_file=str(RESULTS_DIR / "combined_metrics.json"),
        oos_metrics_file=str(RESULTS_DIR / "oos_metrics.json"),
        per_symbol_metrics_files=[str(RESULTS_DIR / f"metrics_{symbol}.json") for symbol in SYMBOLS],
        prop_report_file=str(RESULTS_DIR / "prop_firm_report.md"),
        status_file=str(RESULTS_DIR / "status.json"),
    )
    _write_status_file(status, in_sample, oos, per_symbol, warnings, enabled_symbols)

    readiness = _load_json(RESULTS_DIR / "status.json", {})
    final_state = "NOT_READY"
    reasons: list[str] = []
    if isinstance(readiness, dict):
        final_state = str(readiness.get("status", "NOT_READY"))
        loaded_reasons = readiness.get("reasons", [])
        if isinstance(loaded_reasons, list):
            reasons = [str(item) for item in loaded_reasons]

    print("\nRun complete. Artifacts generated:")
    print(f"- {status.filter_diagnosis_file}")
    print(f"- {status.calibration_log_file}")
    print(f"- {status.training_summary_file}")
    print(f"- {status.combined_metrics_file}")
    print(f"- {status.oos_metrics_file}")
    for file_path in status.per_symbol_metrics_files:
        print(f"- {file_path}")
    print(f"- {status.prop_report_file}")
    print(f"- {status.status_file}")
    print(f"\nOVERALL: {final_state}")
    for reason in reasons:
        print(f"- {reason}")

    if isinstance(readiness, dict):
        _write_final_diagnostic(
            in_sample=in_sample,
            oos=oos,
            wf=wf,
            mc=mc,
            status_payload=readiness,
            model_metrics=model_metrics,
        )


if __name__ == "__main__":
    main()

"""
FASE 11 – Walk-Forward Validation (Opción A)
Dividir datos 70/30 por fecha, analizar retención de métricas.
Valida si el Experimento E mantiene su edge en período histórico OOS.
"""
from __future__ import annotations

import json
import sys
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path("results/forward_validation")
OUT.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="darkgrid", palette="muted")
plt.rcParams.update({"figure.dpi": 120, "figure.figsize": (12, 6)})


def _load_and_split() -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Carga experiment_E y divide en 70/30 por fecha."""
    df = pd.read_csv(Path("results/experiment_E.csv"))
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df = df.sort_values("exit_time").reset_index(drop=True)
    
    split_idx = int(len(df) * 0.70)
    split_date = df.loc[split_idx, "exit_time"]
    
    df_train = df[df["exit_time"] <= split_date].copy()
    df_forward = df[df["exit_time"] > split_date].copy()
    
    print(f"Split date: {split_date}")
    print(f"Train period: {df_train['exit_time'].min()} → {df_train['exit_time'].max()}")
    print(f"Forward period (OOS): {df_forward['exit_time'].min()} → {df_forward['exit_time'].max()}")
    print(f"Train trades: {len(df_train)} | Forward trades: {len(df_forward)}")
    
    return df_train, df_forward, split_date


def _calculate_metrics(df: pd.DataFrame) -> dict:
    """Calcula métricas estándar."""
    if len(df) == 0:
        return {
            "total_trades": 0,
            "winrate": 0.0,
            "profit_factor": 1.0,
            "expectancy": 0.0,
            "avg_rr": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "equity_final": 0.0,
        }
    
    wins = (df["pnl_r"] > 0).sum()
    losses = (df["pnl_r"] < 0).sum()
    pnl_total = df["pnl_r"].sum()
    
    pf = 1.0
    if losses > 0:
        gross_profit = df[df["pnl_r"] > 0]["pnl_r"].sum()
        gross_loss = abs(df[df["pnl_r"] < 0]["pnl_r"].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 1.0
    
    expectancy = pnl_total / len(df)
    
    avg_rr = df["risk_r"].mean() if "risk_r" in df.columns else 1.0
    
    cumulative_pnl = df["pnl_r"].cumsum()
    peak = cumulative_pnl.cummax()
    drawdown = peak - cumulative_pnl
    max_drawdown = drawdown.max()
    
    daily_returns = df.groupby(pd.to_datetime(df.get("exit_time", pd.Timestamp.now())).dt.floor("D"))["pnl_r"].sum()
    if len(daily_returns) > 1:
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        calmar = daily_returns.mean() / (drawdown.max() + 1e-6)
    else:
        sharpe = 0.0
        calmar = 0.0
    
    return {
        "total_trades": len(df),
        "winrate": wins / len(df) if len(df) > 0 else 0.0,
        "profit_factor": pf,
        "expectancy": expectancy,
        "avg_rr": avg_rr,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "calmar": calmar,
        "equity_final": cumulative_pnl.iloc[-1] if len(cumulative_pnl) > 0 else 0.0,
    }


def _build_comparison(df_backtest: pd.DataFrame, df_forward: pd.DataFrame) -> pd.DataFrame:
    """Compara métricas entre backtest y forward."""
    metrics_backtest = _calculate_metrics(df_backtest)
    metrics_forward = _calculate_metrics(df_forward)
    
    comparison = []
    for key in metrics_backtest.keys():
        bt = metrics_backtest[key]
        fw = metrics_forward[key]
        delta_abs = fw - bt
        delta_pct = (fw / bt * 100 - 100) if bt != 0 and bt != 1 else 0.0
        
        comparison.append({
            "metric": key,
            "backtest_E": bt,
            "forward": fw,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
        })
    
    return pd.DataFrame(comparison)


def _build_breakdowns(df_forward: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Genera breakdowns por símbolo, lado y sesión."""
    by_symbol_rows = []
    for symbol, group in df_forward.groupby("symbol"):
        metrics = _calculate_metrics(group)
        metrics["symbol"] = symbol
        by_symbol_rows.append(metrics)
    by_symbol = pd.DataFrame(by_symbol_rows)
    
    by_side_rows = []
    for side, group in df_forward.groupby("side"):
        metrics = _calculate_metrics(group)
        metrics["side"] = side
        by_side_rows.append(metrics)
    by_side = pd.DataFrame(by_side_rows)
    
    by_session_rows = []
    for session, group in df_forward.groupby("session_bucket"):
        metrics = _calculate_metrics(group)
        metrics["session_bucket"] = session
        by_session_rows.append(metrics)
    by_session = pd.DataFrame(by_session_rows)
    
    return by_symbol, by_side, by_session


def _generate_report(
    df_backtest: pd.DataFrame,
    df_forward: pd.DataFrame,
    comparison: pd.DataFrame,
    by_symbol: pd.DataFrame,
    by_side: pd.DataFrame,
    by_session: pd.DataFrame,
) -> str:
    """Genera el reporte final de validación."""
    
    metrics_bt = _calculate_metrics(df_backtest)
    metrics_fw = _calculate_metrics(df_forward)
    
    expectancy_retention = (metrics_fw["expectancy"] / metrics_bt["expectancy"] * 100) if metrics_bt["expectancy"] != 0 else 0
    pf_retention = (metrics_fw["profit_factor"] / metrics_bt["profit_factor"] * 100) if metrics_bt["profit_factor"] != 0 else 0
    
    if expectancy_retention > 80:
        classification = "EXCELENTE"
    elif expectancy_retention >= 60:
        classification = "ACEPTABLE"
    elif expectancy_retention >= 40:
        classification = "DÉBIL"
    else:
        classification = "POSIBLE SOBREAJUSTE"
    
    report = []
    report.append("# Forward Validation Report (Walk-Forward 70/30)\n")
    report.append(f"Backtest periodo: {df_backtest['exit_time'].min()} → {df_backtest['exit_time'].max()}\n")
    report.append(f"Forward periodo: {df_forward['exit_time'].min()} → {df_forward['exit_time'].max()}\n")
    
    report.append("\n## 1. Métricas Principales\n")
    report.append(f"- Total trades (BT): {metrics_bt['total_trades']} | (FW): {metrics_fw['total_trades']}\n")
    report.append(f"- Winrate (BT): {metrics_bt['winrate']:.2%} | (FW): {metrics_fw['winrate']:.2%}\n")
    report.append(f"- Profit Factor (BT): {metrics_bt['profit_factor']:.2f} | (FW): {metrics_fw['profit_factor']:.2f}\n")
    report.append(f"- Expectancy (BT): {metrics_bt['expectancy']:.4f}R | (FW): {metrics_fw['expectancy']:.4f}R\n")
    report.append(f"- Max Drawdown (BT): {metrics_bt['max_drawdown']:.2f} | (FW): {metrics_fw['max_drawdown']:.2f}\n")
    
    report.append("\n## 2. Retention Analysis\n")
    report.append(f"- Expectancy Retention: {expectancy_retention:.1f}%\n")
    report.append(f"- Profit Factor Retention: {pf_retention:.1f}%\n")
    report.append(f"- Classification: **{classification}**\n")
    
    report.append("\n## 3. By Symbol\n")
    for _, row in by_symbol.iterrows():
        report.append(f"### {row['symbol']}\n")
        report.append(f"- Trades: {row['total_trades']} | Winrate: {row['winrate']:.2%} | Expectancy: {row['expectancy']:.4f}R\n")
    
    report.append("\n## 4. By Side\n")
    for _, row in by_side.iterrows():
        report.append(f"### {row['side']}\n")
        report.append(f"- Trades: {row['total_trades']} | Winrate: {row['winrate']:.2%} | Expectancy: {row['expectancy']:.4f}R\n")
    
    report.append("\n## 5. By Session\n")
    for _, row in by_session.iterrows():
        report.append(f"### {row['session_bucket']}\n")
        report.append(f"- Trades: {row['total_trades']} | Winrate: {row['winrate']:.2%} | Expectancy: {row['expectancy']:.4f}R\n")
    
    report.append("\n## 6. Pass/Fail Criteria\n")
    criteria = {
        "PF > 1.20": metrics_fw["profit_factor"] > 1.20,
        "Expectancy positive": metrics_fw["expectancy"] > 0,
        "Drawdown controlled": metrics_fw["max_drawdown"] < 2.0,
        "Expectancy retention ≥ 60%": expectancy_retention >= 60,
        "PF retention ≥ 60%": pf_retention >= 60,
    }
    
    all_pass = all(criteria.values())
    
    for criterion, passed in criteria.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        report.append(f"- {criterion}: {status}\n")
    
    report.append("\n## 7. Recommendation\n")
    if all_pass:
        report.append("**PROMOTE TO PAPER TRADING** – Model maintains edge in OOS period.\n")
        confidence = 85
    elif expectancy_retention >= 60 and metrics_fw["profit_factor"] > 1.0:
        report.append("**CONDITIONAL PAPER TRADING** – Monitor closely for degradation.\n")
        confidence = 70
    else:
        report.append("**DO NOT PROMOTE** – Significant degradation detected. Investigate.\n")
        confidence = 40
    
    report.append(f"\nConfidence Level: {confidence}%\n")
    
    return "\n".join(report)


def main():
    print("=== FORWARD VALIDATION (Walk-Forward 70/30 Historical OOS) ===\n")
    
    # Load and split
    df_train, df_forward, split_date = _load_and_split()
    
    # Save model snapshot
    model_info = {
        "method": "Walk-Forward Historical Split",
        "split_date": str(split_date),
        "train_data_size": len(df_train),
        "forward_data_size": len(df_forward),
        "train_period": f"{df_train['exit_time'].min()} to {df_train['exit_time'].max()}",
        "forward_period": f"{df_forward['exit_time'].min()} to {df_forward['exit_time'].max()}",
    }
    (OUT / "model_snapshot.json").write_text(json.dumps(model_info, indent=2))
    
    # Calculate all metrics
    comparison = _build_comparison(df_train, df_forward)
    by_symbol, by_side, by_session = _build_breakdowns(df_forward)
    
    # Save outputs
    df_forward.to_csv(OUT / "forward_signals.csv", index=False)
    comparison.to_csv(OUT / "forward_vs_backtest.csv", index=False)
    by_symbol.to_csv(OUT / "forward_by_symbol.csv", index=False)
    by_side.to_csv(OUT / "forward_by_side.csv", index=False)
    by_session.to_csv(OUT / "forward_by_session.csv", index=False)
    
    # Generate report
    report = _generate_report(df_train, df_forward, comparison, by_symbol, by_side, by_session)
    (OUT / "forward_validation_report.md").write_text(report, encoding="utf-8")
    
    print("\n=== FORWARD VALIDATION COMPLETE ===")
    print(f"Results saved to {OUT}/")


if __name__ == "__main__":
    main()

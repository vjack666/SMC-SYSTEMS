"""
PAPER TRADING – Model Drift Detection (PSI)
Monitorea cambios en distribuciones de features y alertas automáticas.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


PT_ROOT = Path("paper_trading")
PT_LOGS = PT_ROOT / "logs"


def calculate_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """
    Calcula Population Stability Index entre dos distribuciones.
    
    PSI < 0.10: No significant difference
    PSI 0.10-0.20: Small difference, monitor
    PSI 0.20-0.30: Meaningful difference, investigate
    PSI > 0.30: Major shift, alert
    """
    # Discretize into bins
    breaks = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breaks[0] = expected.min() - 1e-6
    breaks[-1] = expected.max() + 1e-6
    
    expected_percents = np.histogram(expected, breaks)[0] / len(expected)
    actual_percents = np.histogram(actual, breaks)[0] / len(actual)
    
    # Avoid log(0)
    expected_percents = np.where(expected_percents == 0, 1e-6, expected_percents)
    actual_percents = np.where(actual_percents == 0, 1e-6, actual_percents)
    
    psi = np.sum((actual_percents - expected_percents) * np.log(actual_percents / expected_percents))
    
    return float(psi)


class ModelDriftMonitor:
    """Monitorea drift del modelo en tiempo real."""
    
    def __init__(self, backtest_data_path: Path = Path("results/experiment_E.csv")):
        self.backtest_data = pd.read_csv(backtest_data_path)
        self.monitoring_log = PT_LOGS / "model_monitoring.csv"
        self.alerts_log = PT_ROOT / "alerts.log"
    
    def calculate_monitoring_metrics(self, paper_data: pd.DataFrame) -> dict:
        """Calcula métricas de monitoreo y PSI."""
        
        # Signals generated vs executed
        signals_generated = len(paper_data)
        signals_executed = len(paper_data[paper_data["result"] != "PENDING"])
        execution_rate = signals_executed / signals_generated if signals_generated > 0 else 0
        
        # ML score stats
        avg_ml_score = paper_data["ml_score"].mean() if "ml_score" in paper_data.columns else 0
        
        # Expectancy
        paper_data["pnl_r"] = pd.to_numeric(paper_data["pnl_r"], errors="coerce")
        avg_expectancy = paper_data["pnl_r"].mean() if "pnl_r" in paper_data.columns else 0
        
        # PSI calculations
        psi_scores = {}
        drift_detected = False
        
        # ML Score PSI
        if "ml_score" in paper_data.columns and "ml_confidence" in self.backtest_data.columns:
            backtest_scores = self.backtest_data["ml_confidence"].dropna().values
            paper_scores = paper_data["ml_score"].dropna().values
            if len(backtest_scores) > 10 and len(paper_scores) > 10:
                psi_scores["ml_score"] = calculate_psi(backtest_scores, paper_scores)
        
        # Mitigation depth PSI
        if "mitigation_depth_pct" in paper_data.columns and "mitigation_depth_pct" in self.backtest_data.columns:
            backtest_md = self.backtest_data["mitigation_depth_pct"].dropna().values
            paper_md = paper_data["mitigation_depth_pct"].dropna().values
            if len(backtest_md) > 10 and len(paper_md) > 10:
                psi_scores["mitigation_depth"] = calculate_psi(backtest_md, paper_md)
        
        # Bars since FVG creation PSI
        if "bars_since_fvg_creation" in paper_data.columns and "bars_since_fvg_creation" in self.backtest_data.columns:
            backtest_bars = self.backtest_data["bars_since_fvg_creation"].dropna().values
            paper_bars = paper_data["bars_since_fvg_creation"].dropna().values
            if len(backtest_bars) > 10 and len(paper_bars) > 10:
                psi_scores["bars_since_fvg"] = calculate_psi(backtest_bars, paper_bars)
        
        # Session bucket PSI (categorical)
        if "session_bucket" in paper_data.columns and "session_bucket" in self.backtest_data.columns:
            backtest_sessions = self.backtest_data["session_bucket"].value_counts(normalize=True)
            paper_sessions = paper_data["session_bucket"].value_counts(normalize=True)
            all_sessions = set(backtest_sessions.index) | set(paper_sessions.index)
            psi = 0
            for session in all_sessions:
                bt_pct = backtest_sessions.get(session, 1e-6)
                pt_pct = paper_sessions.get(session, 1e-6)
                psi += (pt_pct - bt_pct) * np.log(pt_pct / bt_pct)
            psi_scores["session_bucket"] = float(psi)
        
        # Check for drift
        max_psi = max(psi_scores.values()) if psi_scores else 0
        if max_psi > 0.20:
            drift_detected = True
        
        model_status = "CRITICAL" if max_psi > 0.30 else ("WARNING" if drift_detected else "OK")
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "signals_generated": signals_generated,
            "signals_executed": signals_executed,
            "execution_rate": execution_rate,
            "avg_ml_score": avg_ml_score,
            "avg_expectancy": avg_expectancy,
            "psi_scores": psi_scores,
            "max_psi": max_psi,
            "drift_detected": drift_detected,
            "model_status": model_status,
        }
    
    def log_monitoring_event(self, metrics: dict):
        """Registra evento de monitoreo."""
        # Append to monitoring log
        if self.monitoring_log.exists():
            monitoring_df = pd.read_csv(self.monitoring_log)
        else:
            monitoring_df = pd.DataFrame()
        
        new_row = {
            "date": metrics["date"],
            "signals_generated": metrics["signals_generated"],
            "signals_executed": metrics["signals_executed"],
            "execution_rate": metrics["execution_rate"],
            "avg_ml_score": metrics["avg_ml_score"],
            "avg_expectancy": metrics["avg_expectancy"],
            "score_distribution_psi": metrics["psi_scores"].get("ml_score", None),
            "mitigation_depth_psi": metrics["psi_scores"].get("mitigation_depth", None),
            "bars_since_fvg_psi": metrics["psi_scores"].get("bars_since_fvg", None),
            "session_bucket_psi": metrics["psi_scores"].get("session_bucket", None),
            "max_psi": metrics["max_psi"],
            "psi_alert_level": "CRITICAL" if metrics["max_psi"] > 0.30 else ("WARNING" if metrics["drift_detected"] else "OK"),
            "model_status": metrics["model_status"],
        }
        
        monitoring_df = pd.concat([monitoring_df, pd.DataFrame([new_row])], ignore_index=True)
        monitoring_df.to_csv(self.monitoring_log, index=False)
    
    def check_alerts(self, metrics: dict) -> list[str]:
        """Genera alertas basadas en métricas."""
        alerts = []
        
        # PSI alerts
        if metrics["max_psi"] > 0.30:
            alerts.append(f"🚨 CRITICAL: Model drift detected (PSI={metrics['max_psi']:.3f})")
        elif metrics["max_psi"] > 0.20:
            alerts.append(f"⚠️ WARNING: Potential model drift (PSI={metrics['max_psi']:.3f})")
        
        # Execution rate alert
        if metrics["signals_generated"] > 0 and metrics["execution_rate"] < 0.5:
            alerts.append(f"⚠️ Low execution rate: {metrics['execution_rate']:.1%}")
        
        return alerts


if __name__ == "__main__":
    # Test
    monitor = ModelDriftMonitor()
    
    # Load test data
    paper_df = pd.DataFrame({
        "ml_score": np.random.normal(0.65, 0.08, 50),
        "mitigation_depth_pct": np.random.normal(0.25, 0.15, 50),
        "bars_since_fvg_creation": np.random.normal(10, 5, 50),
        "session_bucket": np.random.choice(["london", "new_york", "overlap"], 50),
        "pnl_r": np.random.normal(0.02, 0.1, 50),
        "result": ["EXECUTED"] * 40 + ["PENDING"] * 10,
    })
    
    metrics = monitor.calculate_monitoring_metrics(paper_df)
    print("✅ Monitoring metrics calculated")
    print(json.dumps(metrics, indent=2, default=str))

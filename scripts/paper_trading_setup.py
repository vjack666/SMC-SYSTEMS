"""
PAPER TRADING VALIDATION SYSTEM – Core Setup
Configuración, templates y gestión de estado del sistema de validación en papel.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


PT_ROOT = Path("paper_trading")
PT_ROOT.mkdir(exist_ok=True)

PT_DATA = PT_ROOT / "data"
PT_DATA.mkdir(exist_ok=True)

PT_LOGS = PT_ROOT / "logs"
PT_LOGS.mkdir(exist_ok=True)

PT_REPORTS = PT_ROOT / "reports"
PT_REPORTS.mkdir(exist_ok=True)


@dataclass
class PaperTradingConfig:
    """Configuración del sistema de paper trading."""
    experiment_name: str = "Experiment_E"
    start_date: str = datetime.now().strftime("%Y-%m-%d")
    capital_virtual_usd: float = 25000.0
    risk_pct_per_trade: float = 0.005  # 0.5%
    min_duration_days: int = 60
    target_duration_days: int = 90
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    sessions_focus: tuple[str, ...] = ("new_york", "overlap")
    symbols_priority: tuple[str, ...] = ("XAUUSD", "GBPUSD", "EURUSD")
    
    # Criterios de aprobación
    min_profit_factor: float = 1.30
    min_expectancy_r: float = 0.15
    max_drawdown_multiplier: float = 1.5  # vs backtest
    min_trades_for_approval: int = 150
    psi_threshold_warning: float = 0.20
    psi_threshold_critical: float = 0.30
    
    # Simulación de fondeo
    ftmo_target_pct: float = 0.10  # +10%
    ftmo_max_daily_loss_pct: float = 0.05  # 5% diario
    ftmo_max_total_loss_pct: float = 0.10  # 10% total
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    def save(self, path: Optional[Path] = None) -> Path:
        if path is None:
            path = PT_ROOT / "config.json"
        path.write_text(self.to_json(), encoding="utf-8")
        return path


def create_signal_template() -> pd.DataFrame:
    """Crea template vacío para logging de señales."""
    columns = [
        "signal_id", "timestamp_signal", "symbol", "side", "session_bucket",
        "structure_event", "fvg_creation_time", "fvg_mitigation_time", "bos_time",
        "entry_price", "stop_price", "target_price", "ml_score", "risk_r",
        "spread_estimated", "slippage_estimated", "result", "pnl_r", "pnl_usd",
        "entry_time", "exit_time", "holding_bars", "bars_since_fvg_creation",
        "mitigation_depth_pct", "notes"
    ]
    return pd.DataFrame(columns=columns)


def create_daily_metrics_template() -> pd.DataFrame:
    """Crea template para métricas diarias."""
    columns = [
        "date", "trades", "wins", "losses", "winrate", "profit_factor",
        "expectancy", "daily_pnl_r", "daily_pnl_usd", "equity", "drawdown",
        "drawdown_pct", "sharpe_daily", "signal_count", "avg_ml_score"
    ]
    return pd.DataFrame(columns=columns)


def create_weekly_metrics_template() -> pd.DataFrame:
    """Crea template para métricas semanales."""
    columns = [
        "week_start", "week_end", "trades", "wins", "losses", "winrate",
        "profit_factor", "expectancy", "weekly_pnl_r", "weekly_pnl_usd",
        "equity_start", "equity_end", "max_drawdown", "max_drawdown_pct"
    ]
    return pd.DataFrame(columns=columns)


def create_monitoring_template() -> pd.DataFrame:
    """Crea template para monitoreo de drift del modelo."""
    columns = [
        "date", "signals_generated", "signals_executed", "execution_rate",
        "avg_ml_score", "avg_expectancy", "prediction_drift",
        "score_distribution_psi", "mitigation_depth_psi", "bars_since_fvg_psi",
        "session_bucket_psi", "distance_eqh_psi", "distance_eql_psi",
        "max_psi", "psi_alert_level", "model_status"
    ]
    return pd.DataFrame(columns=columns)


def create_funding_dashboard_template() -> pd.DataFrame:
    """Crea template para simulación de fondeo."""
    columns = [
        "date", "equity", "equity_change_pct",
        "ftmo_status", "ftmo_target_equity", "ftmo_distance_to_target_pct",
        "ftmo_daily_dd", "ftmo_daily_dd_pct", "ftmo_total_dd", "ftmo_total_dd_pct",
        "fiveers_status", "fiveers_phase", "fundednext_status",
        "alerts", "alert_level"
    ]
    return pd.DataFrame(columns=columns)


def initialize_paper_trading_system() -> dict:
    """Inicializa el sistema completo de paper trading."""
    config = PaperTradingConfig()
    config.save()
    
    # Create templates
    signals = create_signal_template()
    signals.to_csv(PT_DATA / "paper_trading_signals.csv", index=False)
    
    daily = create_daily_metrics_template()
    daily.to_csv(PT_LOGS / "daily_performance.csv", index=False)
    
    weekly = create_weekly_metrics_template()
    weekly.to_csv(PT_LOGS / "weekly_performance.csv", index=False)
    
    monitoring = create_monitoring_template()
    monitoring.to_csv(PT_LOGS / "model_monitoring.csv", index=False)
    
    funding = create_funding_dashboard_template()
    funding.to_csv(PT_LOGS / "funding_dashboard.csv", index=False)
    
    # Create initial status file
    status = {
        "initialized": datetime.now().isoformat(),
        "status": "READY",
        "trades_logged": 0,
        "signals_generated": 0,
        "signals_executed": 0,
        "total_pnl_r": 0.0,
        "total_pnl_usd": 0.0,
        "current_equity": config.capital_virtual_usd,
        "alerts": [],
    }
    
    (PT_ROOT / "status.json").write_text(json.dumps(status, indent=2))
    
    return {
        "config_path": str(config.save()),
        "signals_csv": str(PT_DATA / "paper_trading_signals.csv"),
        "daily_metrics": str(PT_LOGS / "daily_performance.csv"),
        "weekly_metrics": str(PT_LOGS / "weekly_performance.csv"),
        "monitoring_log": str(PT_LOGS / "model_monitoring.csv"),
        "funding_dashboard": str(PT_LOGS / "funding_dashboard.csv"),
        "status_file": str(PT_ROOT / "status.json"),
        "message": "Paper trading system initialized successfully",
    }


if __name__ == "__main__":
    result = initialize_paper_trading_system()
    print("✅ PAPER TRADING SYSTEM INITIALIZED")
    print(json.dumps(result, indent=2))

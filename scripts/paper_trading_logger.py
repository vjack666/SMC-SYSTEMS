"""
PAPER TRADING – Signal Logger and Real-Time Metrics
Registra señales conforme son generadas y calcula métricas en tiempo real.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


PT_ROOT = Path("paper_trading")
PT_DATA = PT_ROOT / "data"
PT_LOGS = PT_ROOT / "logs"


class PaperTradingLogger:
    """Sistema de logging para paper trading."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or PT_ROOT / "config.json"
        self.signals_csv = PT_DATA / "paper_trading_signals.csv"
        self.status_file = PT_ROOT / "status.json"
        self._load_config()
    
    def _load_config(self):
        """Carga la configuración."""
        config_json = self.config_path.read_text()
        self.config = json.loads(config_json)
    
    def log_signal(
        self,
        symbol: str,
        side: str,
        session_bucket: str,
        ml_score: float,
        entry_price: float,
        stop_price: float,
        target_price: float,
        fvg_creation_time: str,
        fvg_mitigation_time: Optional[str] = None,
        bos_time: Optional[str] = None,
        bars_since_fvg_creation: Optional[int] = None,
        mitigation_depth_pct: Optional[float] = None,
        structure_event: str = "fvg",
        **kwargs
    ) -> str:
        """
        Registra una nueva señal.
        Retorna signal_id para trackeo.
        """
        signal_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
        
        signal = {
            "signal_id": signal_id,
            "timestamp_signal": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "session_bucket": session_bucket,
            "structure_event": structure_event,
            "fvg_creation_time": fvg_creation_time,
            "fvg_mitigation_time": fvg_mitigation_time,
            "bos_time": bos_time,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "ml_score": ml_score,
            "risk_r": None,
            "spread_estimated": kwargs.get("spread_estimated", 0.00005),
            "slippage_estimated": kwargs.get("slippage_estimated", 0.00002),
            "result": "PENDING",
            "pnl_r": None,
            "pnl_usd": None,
            "entry_time": None,
            "exit_time": None,
            "holding_bars": None,
            "bars_since_fvg_creation": bars_since_fvg_creation,
            "mitigation_depth_pct": mitigation_depth_pct,
            "notes": kwargs.get("notes", ""),
        }
        
        if not self.signals_csv.exists():
            df = pd.DataFrame([signal])
        else:
            df = pd.read_csv(self.signals_csv)
            df = pd.concat([df, pd.DataFrame([signal])], ignore_index=True)
        
        df.to_csv(self.signals_csv, index=False)
        self._update_status("signals_generated", 1)
        
        return signal_id
    
    def log_trade_execution(
        self,
        signal_id: str,
        entry_time: str,
        entry_price_actual: float,
        pnl_r: Optional[float] = None,
        pnl_usd: Optional[float] = None,
        exit_time: Optional[str] = None,
        holding_bars: Optional[int] = None,
        result: str = "EXECUTED",
    ):
        """Registra la ejecución y resultado de un trade."""
        df = pd.read_csv(self.signals_csv)
        
        idx = df[df["signal_id"] == signal_id].index
        if len(idx) == 0:
            raise ValueError(f"Signal {signal_id} not found")
        
        df.loc[idx[0], "entry_time"] = entry_time
        df.loc[idx[0], "exit_time"] = exit_time
        df.loc[idx[0], "pnl_r"] = pnl_r
        df.loc[idx[0], "pnl_usd"] = pnl_usd
        df.loc[idx[0], "holding_bars"] = holding_bars
        df.loc[idx[0], "result"] = result
        
        if result in ["TP_HIT", "SL_HIT", "CLOSED"]:
            df.loc[idx[0], "result"] = result
        
        df.to_csv(self.signals_csv, index=False)
        self._update_status("signals_executed", 1)
        if pnl_r:
            self._update_status("total_pnl_r", pnl_r)
        if pnl_usd:
            self._update_status("total_pnl_usd", pnl_usd)
    
    def _update_status(self, key: str, delta_value: float):
        """Actualiza el archivo de estado."""
        status = json.loads(self.status_file.read_text())
        
        if isinstance(status.get(key), (int, float)):
            status[key] += delta_value
        
        status["last_update"] = datetime.now().isoformat()
        self.status_file.write_text(json.dumps(status, indent=2))
    
    def calculate_daily_metrics(self, date: Optional[str] = None) -> dict:
        """Calcula métricas del día especificado."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        df = pd.read_csv(self.signals_csv)
        df["exit_time"] = pd.to_datetime(df["exit_time"], errors="coerce")
        
        # Filter trades executed on the given date
        daily_trades = df[
            df["exit_time"].dt.floor("D") == pd.to_datetime(date)
        ].copy()
        
        if len(daily_trades) == 0:
            return {
                "date": date,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "winrate": 0.0,
                "profit_factor": 1.0,
                "expectancy": 0.0,
                "daily_pnl_r": 0.0,
                "daily_pnl_usd": 0.0,
                "equity": 0.0,
                "drawdown": 0.0,
                "drawdown_pct": 0.0,
            }
        
        daily_trades["pnl_r"] = pd.to_numeric(daily_trades["pnl_r"], errors="coerce")
        daily_trades["pnl_usd"] = pd.to_numeric(daily_trades["pnl_usd"], errors="coerce")
        
        wins = (daily_trades["pnl_r"] > 0).sum()
        losses = (daily_trades["pnl_r"] < 0).sum()
        total = len(daily_trades)
        
        pnl_total = daily_trades["pnl_r"].sum()
        pnl_usd_total = daily_trades["pnl_usd"].sum()
        
        pf = 1.0
        if losses > 0:
            gross_profit = daily_trades[daily_trades["pnl_r"] > 0]["pnl_r"].sum()
            gross_loss = abs(daily_trades[daily_trades["pnl_r"] < 0]["pnl_r"].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 1.0
        
        expectancy = pnl_total / total if total > 0 else 0.0
        
        return {
            "date": date,
            "trades": total,
            "wins": wins,
            "losses": losses,
            "winrate": wins / total if total > 0 else 0.0,
            "profit_factor": pf,
            "expectancy": expectancy,
            "daily_pnl_r": pnl_total,
            "daily_pnl_usd": pnl_usd_total,
            "equity": pnl_usd_total,
            "drawdown": 0.0,
            "drawdown_pct": 0.0,
        }
    
    def get_status(self) -> dict:
        """Retorna el estado actual del sistema."""
        return json.loads(self.status_file.read_text())


if __name__ == "__main__":
    # Test
    logger = PaperTradingLogger()
    
    # Log a sample signal
    signal_id = logger.log_signal(
        symbol="EURUSD",
        side="LONG",
        session_bucket="new_york",
        ml_score=0.72,
        entry_price=1.0850,
        stop_price=1.0800,
        target_price=1.0950,
        fvg_creation_time="2026-05-31 15:00:00",
        bars_since_fvg_creation=5,
        mitigation_depth_pct=0.15,
    )
    
    print(f"✅ Signal logged: {signal_id}")
    print(f"Status: {logger.get_status()}")

"""
PAPER TRADING – Funding Simulation Dashboard
Simula cumplimiento de reglas de fondeo en tiempo real.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


PT_ROOT = Path("paper_trading")
PT_LOGS = PT_ROOT / "logs"


class FundingSimulator:
    """Simula diferentes plataformas de fondeo."""
    
    def __init__(self, initial_capital_usd: float = 25000.0):
        self.initial_capital = initial_capital_usd
        self.funding_dashboard = PT_LOGS / "funding_dashboard.csv"
    
    def evaluate_ftmo(
        self,
        current_equity: float,
        daily_trades: pd.DataFrame,
        daily_pnl_r: float,
    ) -> dict:
        """
        Evalúa cumplimiento de reglas FTMO.
        
        Objetivo: +10% en 60 días
        Max daily loss: 5%
        Max total loss: 10%
        """
        target_equity = self.initial_capital * 1.10
        distance_to_target_pct = (current_equity - self.initial_capital) / (target_equity - self.initial_capital) * 100 if target_equity > self.initial_capital else 0
        distance_to_target_pct = min(distance_to_target_pct, 100)  # Cap at 100%
        
        daily_dd_pct = abs(daily_pnl_r) if daily_pnl_r < 0 else 0.0
        total_dd = self.initial_capital - current_equity
        total_dd_pct = total_dd / self.initial_capital * 100
        
        daily_breach = daily_dd_pct > 5.0
        total_breach = total_dd_pct > 10.0
        target_reached = current_equity >= target_equity
        
        status = "PASSED" if target_reached else ("FAILED" if (daily_breach or total_breach) else "IN_PROGRESS")
        
        return {
            "platform": "FTMO",
            "status": status,
            "target_equity": target_equity,
            "distance_to_target_pct": distance_to_target_pct,
            "daily_dd_pct": daily_dd_pct,
            "total_dd_pct": total_dd_pct,
            "daily_breach": daily_breach,
            "total_breach": total_breach,
        }
    
    def evaluate_5ers(
        self,
        current_equity: float,
        phase: int = 1,
    ) -> dict:
        """
        Evalúa cumplimiento de reglas 5ERS.
        
        Phase 1: +10% en 60 días, max daily loss 5%, max total loss 10%
        Phase 2: +5% en 60 días, max daily loss 5%, max total loss 10%
        """
        if phase == 1:
            target_pct = 0.10
            duration_days = 60
            max_daily_loss = 0.05
            max_total_loss = 0.10
        elif phase == 2:
            target_pct = 0.05
            duration_days = 60
            max_daily_loss = 0.05
            max_total_loss = 0.10
        else:
            target_pct = 0.02
            duration_days = 60
            max_daily_loss = 0.05
            max_total_loss = 0.10
        
        target_equity = self.initial_capital * (1 + target_pct)
        distance_to_target_pct = (current_equity - self.initial_capital) / (target_equity - self.initial_capital) * 100 if target_pct > 0 else 0
        distance_to_target_pct = min(distance_to_target_pct, 100)
        
        total_dd = self.initial_capital - current_equity
        total_dd_pct = total_dd / self.initial_capital
        
        total_breach = total_dd_pct > max_total_loss
        target_reached = current_equity >= target_equity
        
        status = "PASSED" if target_reached else ("FAILED" if total_breach else "IN_PROGRESS")
        
        return {
            "platform": "5ERS",
            "phase": phase,
            "status": status,
            "target_equity": target_equity,
            "distance_to_target_pct": distance_to_target_pct,
            "total_dd_pct": total_dd_pct,
            "max_total_loss_pct": max_total_loss * 100,
        }
    
    def evaluate_fundednext(
        self,
        current_equity: float,
        phase: int = 1,
    ) -> dict:
        """
        Evalúa cumplimiento de reglas FundedNext.
        Similar a 5ERS con variaciones.
        """
        if phase == 1:
            target_pct = 0.10
            max_total_loss = 0.08
        else:
            target_pct = 0.05
            max_total_loss = 0.05
        
        target_equity = self.initial_capital * (1 + target_pct)
        distance_to_target_pct = (current_equity - self.initial_capital) / (target_equity - self.initial_capital) * 100 if target_pct > 0 else 0
        distance_to_target_pct = min(distance_to_target_pct, 100)
        
        total_dd = self.initial_capital - current_equity
        total_dd_pct = total_dd / self.initial_capital
        
        total_breach = total_dd_pct > max_total_loss
        target_reached = current_equity >= target_equity
        
        status = "PASSED" if target_reached else ("FAILED" if total_breach else "IN_PROGRESS")
        
        return {
            "platform": "FundedNext",
            "phase": phase,
            "status": status,
            "target_equity": target_equity,
            "distance_to_target_pct": distance_to_target_pct,
            "total_dd_pct": total_dd_pct,
        }
    
    def evaluate_all(
        self,
        current_equity: float,
        daily_pnl_r: float,
        daily_trades: pd.DataFrame,
    ) -> dict:
        """Evalúa todas las plataformas."""
        ftmo = self.evaluate_ftmo(current_equity, daily_trades, daily_pnl_r)
        fiveers = self.evaluate_5ers(current_equity, phase=1)
        fundednext = self.evaluate_fundednext(current_equity, phase=1)
        
        # Determine overall alert level
        alert_level = "OK"
        alerts = []
        
        if ftmo["daily_breach"]:
            alert_level = "CRITICAL"
            alerts.append("FTMO: Daily loss limit breached")
        
        if ftmo["total_breach"]:
            alert_level = "CRITICAL"
            alerts.append("FTMO: Total loss limit breached")
        
        if fiveers["status"] == "FAILED":
            alert_level = "CRITICAL"
            alerts.append("5ERS: Total loss limit breached")
        
        if fundednext["status"] == "FAILED":
            alert_level = "CRITICAL"
            alerts.append("FundedNext: Total loss limit breached")
        
        if not alerts and any(p["distance_to_target_pct"] > 80 for p in [ftmo, fiveers, fundednext] if "distance_to_target_pct" in p):
            alert_level = "WARNING"
            alerts.append("Approaching target on multiple platforms")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_equity": current_equity,
            "equity_change_pct": (current_equity - self.initial_capital) / self.initial_capital * 100,
            "ftmo": ftmo,
            "fiveers": fiveers,
            "fundednext": fundednext,
            "alert_level": alert_level,
            "alerts": alerts,
        }
    
    def log_funding_event(self, evaluation: dict):
        """Registra evento de evaluación de fondeo."""
        if self.funding_dashboard.exists():
            dashboard_df = pd.read_csv(self.funding_dashboard)
        else:
            dashboard_df = pd.DataFrame()
        
        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "equity": evaluation["current_equity"],
            "equity_change_pct": evaluation["equity_change_pct"],
            "ftmo_status": evaluation["ftmo"]["status"],
            "ftmo_target_equity": evaluation["ftmo"]["target_equity"],
            "ftmo_distance_to_target_pct": evaluation["ftmo"]["distance_to_target_pct"],
            "ftmo_daily_dd_pct": evaluation["ftmo"]["daily_dd_pct"],
            "ftmo_total_dd_pct": evaluation["ftmo"]["total_dd_pct"],
            "fiveers_status": evaluation["fiveers"]["status"],
            "fundednext_status": evaluation["fundednext"]["status"],
            "alerts": " | ".join(evaluation["alerts"]) if evaluation["alerts"] else "",
            "alert_level": evaluation["alert_level"],
        }
        
        dashboard_df = pd.concat([dashboard_df, pd.DataFrame([new_row])], ignore_index=True)
        dashboard_df.to_csv(self.funding_dashboard, index=False)


if __name__ == "__main__":
    # Test
    simulator = FundingSimulator(initial_capital_usd=25000.0)
    
    evaluation = simulator.evaluate_all(
        current_equity=26000.0,
        daily_pnl_r=0.02,
        daily_trades=pd.DataFrame(),
    )
    
    print("✅ Funding simulation completed")
    print(f"Status: {evaluation['alert_level']}")
    print(f"FTMO: {evaluation['ftmo']['status']} ({evaluation['ftmo']['distance_to_target_pct']:.1f}% to target)")

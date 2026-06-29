"""
Backtest engine using structural stop losses.

This module simulates trades using origin swing-based stops instead of ATR-based stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .detector import calculate_structural_stop


@dataclass(frozen=True)
class StructuralBacktestConfig:
    """Configuration for structural stop loss backtest."""
    
    data_dir: Path = Path("data/mt5")
    symbols: list[str] = None
    max_hold_bars: int = 100
    rr_ratio: float = 2.0
    lookback_origin: int = 20
    
    def __post_init__(self):
        if self.symbols is None:
            object.__setattr__(self, "symbols", ["EURUSD", "GBPUSD", "XAUUSD"])


def _load_market_data(data_dir: Path, symbol: str) -> pd.DataFrame | None:
    """Load H1 OHLC data for a symbol."""
    parquet_path = data_dir / f"{symbol}_H1.parquet"
    if not parquet_path.exists():
        return None
    return pd.read_parquet(parquet_path)


def _simulate_trade_structural(
    frame: pd.DataFrame,
    entry_idx: int,
    direction: int,
    rr_ratio: float,
    max_hold_bars: int,
    lookback_origin: int,
) -> tuple[float, int, dict[str, float]]:
    """
    Simulate a single trade using structural stop loss.
    
    Args:
        frame: OHLC dataframe
        entry_idx: index of entry candle
        direction: 1 for LONG, -1 for SHORT
        rr_ratio: risk/reward ratio for target
        max_hold_bars: maximum holding period
        lookback_origin: lookback for origin swing detection
    
    Returns:
        (pnl_r, hold_bars, audit_dict)
    """
    # Calculate structural stop
    stop = calculate_structural_stop(frame, entry_idx, direction, lookback_origin)
    
    if stop is None:
        return 0.0, 0, {"reason": "no_structural_stop"}
    
    entry_price = float(frame.iloc[entry_idx]["close"])
    sl = stop.structural_stop_price
    risk = abs(entry_price - sl)
    
    if risk <= 0.0:
        return 0.0, 0, {"reason": "invalid_risk"}
    
    tp = entry_price + (risk * rr_ratio) if direction == 1 else entry_price - (risk * rr_ratio)
    
    mfe_r = -1e9
    mae_r = 1e9
    
    for step in range(1, max_hold_bars + 1):
        j = entry_idx + step
        if j >= len(frame):
            break
        
        row = frame.iloc[j]
        high = float(row["high"])
        low = float(row["low"])
        
        if direction == 1:
            step_mfe = (high - entry_price) / risk
            step_mae = (low - entry_price) / risk
            mfe_r = max(mfe_r, step_mfe)
            mae_r = min(mae_r, step_mae)
            
            # Check SL hit
            if low <= sl:
                return -1.0, step, {
                    "reason": "sl_hit",
                    "exit_price": sl,
                    "mfe": mfe_r,
                    "mae": mae_r,
                    "origin_swing_price": stop.origin_swing_price,
                    "stop_distance_atr": stop.stop_distance_atr,
                }
            
            # Check TP hit
            if high >= tp:
                return rr_ratio, step, {
                    "reason": "tp_hit",
                    "exit_price": tp,
                    "mfe": mfe_r,
                    "mae": mae_r,
                    "origin_swing_price": stop.origin_swing_price,
                    "stop_distance_atr": stop.stop_distance_atr,
                }
        else:
            step_mfe = (entry_price - low) / risk
            step_mae = (entry_price - high) / risk
            mfe_r = max(mfe_r, step_mfe)
            mae_r = min(mae_r, step_mae)
            
            # Check SL hit
            if high >= sl:
                return -1.0, step, {
                    "reason": "sl_hit",
                    "exit_price": sl,
                    "mfe": mfe_r,
                    "mae": mae_r,
                    "origin_swing_price": stop.origin_swing_price,
                    "stop_distance_atr": stop.stop_distance_atr,
                }
            
            # Check TP hit
            if low <= tp:
                return rr_ratio, step, {
                    "reason": "tp_hit",
                    "exit_price": tp,
                    "mfe": mfe_r,
                    "mae": mae_r,
                    "origin_swing_price": stop.origin_swing_price,
                    "stop_distance_atr": stop.stop_distance_atr,
                }
    
    # Timeout: close at last price
    exit_price = float(frame.iloc[min(entry_idx + max_hold_bars, len(frame) - 1)]["close"])
    pnl_r = (exit_price - entry_price) / risk if direction == 1 else (entry_price - exit_price) / risk
    
    return pnl_r, max_hold_bars, {
        "reason": "timeout",
        "exit_price": exit_price,
        "mfe": mfe_r,
        "mae": mae_r,
        "origin_swing_price": stop.origin_swing_price,
        "stop_distance_atr": stop.stop_distance_atr,
    }


def run_structural_backtest(config: StructuralBacktestConfig | None = None) -> tuple[dict, pd.DataFrame]:
    """
    Run backtest using structural stop losses.
    
    Returns:
        (metrics_dict, trades_dataframe)
    """
    if config is None:
        config = StructuralBacktestConfig()
    
    trades: list[dict] = []
    
    for symbol in config.symbols:
        frame = _load_market_data(config.data_dir, symbol)
        if frame is None:
            print(f"Warning: No data found for {symbol}")
            continue
        
        # Simple signal generation: every 50 bars, alternate direction
        for idx in range(50, len(frame) - config.max_hold_bars, 50):
            direction = 1 if idx % 100 < 50 else -1
            
            pnl_r, hold_bars, audit = _simulate_trade_structural(
                frame, idx, direction, config.rr_ratio, config.max_hold_bars, config.lookback_origin
            )
            
            trade = {
                "symbol": symbol,
                "entry_idx": idx,
                "entry_time": str(frame.iloc[idx]["time"]),
                "direction": direction,
                "side": "LONG" if direction == 1 else "SHORT",
                "pnl_r": float(pnl_r),
                "holding_bars": hold_bars,
                "exit_reason": audit.get("reason", "unknown"),
                "mfe": audit.get("mfe", np.nan),
                "mae": audit.get("mae", np.nan),
                "structural_stop": audit.get("origin_swing_price", np.nan),
                "stop_distance_atr": audit.get("stop_distance_atr", np.nan),
            }
            trades.append(trade)
    
    df_trades = pd.DataFrame(trades)
    
    # Calculate metrics
    metrics = {
        "total_trades": len(df_trades),
        "wins": int((df_trades["pnl_r"] > 0).sum()),
        "losses": int((df_trades["pnl_r"] < 0).sum()),
        "winrate": float((df_trades["pnl_r"] > 0).mean()) if len(df_trades) > 0 else 0.0,
    }
    
    if (df_trades["pnl_r"] > 0).any() and (df_trades["pnl_r"] < 0).any():
        gross_win = float(df_trades[df_trades["pnl_r"] > 0]["pnl_r"].sum())
        gross_loss = abs(float(df_trades[df_trades["pnl_r"] < 0]["pnl_r"].sum()))
        metrics["profit_factor"] = gross_win / gross_loss if gross_loss > 0 else np.inf
    else:
        metrics["profit_factor"] = np.nan
    
    metrics["expectancy"] = float(df_trades["pnl_r"].mean()) if len(df_trades) > 0 else 0.0
    metrics["std_dev"] = float(df_trades["pnl_r"].std()) if len(df_trades) > 0 else 0.0
    
    return metrics, df_trades

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from modules.choch.detector import CHOCH_BEARISH, CHOCH_BULLISH, detect_choch
from modules.choch.ml_model import score_frame, train_model


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    confidence_threshold: float = 0.62
    rr_ratio: float = 2.0
    max_hold_bars: int = 16


def _load(data_dir: Path, symbol: str) -> pd.DataFrame:
    path = data_dir / f"{symbol}_M15.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _simulate(frame: pd.DataFrame, idx: int, direction: int, rr_ratio: float, max_hold_bars: int) -> float:
    atr = float(frame.iloc[idx]["atr"])
    if not np.isfinite(atr) or atr <= 0.0:
        return 0.0

    entry = float(frame.iloc[idx]["close"])
    sl = entry - atr if direction == 1 else entry + atr
    tp = entry + (atr * rr_ratio) if direction == 1 else entry - (atr * rr_ratio)

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        high = float(frame.iloc[j]["high"])
        low = float(frame.iloc[j]["low"])
        if direction == 1:
            if low <= sl:
                return -1.0
            if high >= tp:
                return rr_ratio
        else:
            if high >= sl:
                return -1.0
            if low <= tp:
                return rr_ratio

    close_out = float(frame.iloc[min(idx + max_hold_bars, len(frame) - 1)]["close"])
    return (close_out - entry) / atr if direction == 1 else (entry - close_out) / atr


def run_backtest(config: BacktestConfig | None = None) -> dict[str, float | int]:
    if config is None:
        config = BacktestConfig()

    trades: list[float] = []
    for symbol in config.symbols:
        frame = _load(config.data_dir, symbol)
        frame = detect_choch(frame)
        frame["atr"] = _compute_atr(frame)

        split = int(len(frame) * 0.6)
        model = train_model(frame.iloc[:split].copy())
        scored = score_frame(frame.iloc[split:].copy(), model)

        bullish = (scored["choch_signal"] == CHOCH_BULLISH) & (scored["ml_confidence"] >= config.confidence_threshold)
        bearish = (scored["choch_signal"] == CHOCH_BEARISH) & (scored["ml_confidence"] >= config.confidence_threshold)

        for idx in scored.index[bullish]:
            trades.append(_simulate(scored, scored.index.get_loc(idx), 1, config.rr_ratio, config.max_hold_bars))
        for idx in scored.index[bearish]:
            trades.append(_simulate(scored, scored.index.get_loc(idx), -1, config.rr_ratio, config.max_hold_bars))

    if not trades:
        raise RuntimeError("No CHOCH trades produced.")

    pnl = pd.Series(trades, dtype=float)
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else float("inf")
    eq = pnl.cumsum()
    dd = float((eq - eq.cummax()).min())

    metrics: dict[str, float | int] = {
        "total_trades": int(len(pnl)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": pf,
        "max_drawdown_r": dd,
        "expectancy_r": float(pnl.mean()),
    }
    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "choch_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from modules.trend.ml_model import (
    build_feature_frame,
    predict_positive_proba,
    save_model,
    train_walk_forward,
)
from modules.trend.session_filter import london_newyork_session_mask


@dataclass(frozen=True)
class BacktestConfig:
    data_dir: Path = Path("data/mt5")
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
    confidence_threshold: float = 0.65
    swing_window_bars: int = 10
    max_swing_amplitude_atr: float = 1.5
    rr_ratio: float = 2.0
    max_hold_bars: int = 20


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    pnl_r: float


def _load_frame(base_dir: Path, symbol: str, timeframe: str) -> pd.DataFrame:
    path = base_dir / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _simulate_trade(frame: pd.DataFrame, idx: int, direction: int, rr_ratio: float, max_hold_bars: int) -> float:
    atr = float(frame.iloc[idx]["atr"])
    if not np.isfinite(atr) or atr <= 0.0:
        return 0.0

    entry = float(frame.iloc[idx]["close"])
    sl_distance = atr
    tp_distance = atr * rr_ratio

    sl = entry - sl_distance if direction == 1 else entry + sl_distance
    tp = entry + tp_distance if direction == 1 else entry - tp_distance

    for step in range(1, max_hold_bars + 1):
        next_idx = idx + step
        if next_idx >= len(frame):
            break
        row = frame.iloc[next_idx]
        high = float(row["high"])
        low = float(row["low"])

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

    final_idx = min(idx + max_hold_bars, len(frame) - 1)
    final_close = float(frame.iloc[final_idx]["close"])
    if direction == 1:
        return (final_close - entry) / sl_distance
    return (entry - final_close) / sl_distance


def _max_drawdown(equity: pd.Series) -> float:
    peaks = equity.cummax()
    dd = equity - peaks
    return float(dd.min())


def _max_daily_drawdown_pct(times: pd.Series, pnl_r: pd.Series, risk_per_trade_pct: float = 1.0) -> float:
    df = pd.DataFrame({"time": pd.to_datetime(times, utc=True), "pnl_r": pnl_r})
    if df.empty:
        return 0.0

    df["date"] = df["time"].dt.date
    worst = 0.0
    for _, group in df.groupby("date"):
        day_equity_pct = group["pnl_r"].cumsum() * risk_per_trade_pct
        day_peak = day_equity_pct.cummax()
        day_dd = day_equity_pct - day_peak
        worst = min(worst, float(day_dd.min()))
    return worst


def _sharpe(pnl_r: pd.Series) -> float:
    if pnl_r.empty:
        return 0.0
    std = float(pnl_r.std(ddof=0))
    if std == 0.0:
        return 0.0
    return float((pnl_r.mean() / std) * np.sqrt(252.0))


def _compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_prev_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_prev_close = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _ema_trend(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["time", "close", "high", "low"]].copy().reset_index(drop=True)
    data["atr"] = _compute_atr(data, 14)
    ema_fast = data["close"].ewm(span=20, adjust=False).mean()
    ema_slow = data["close"].ewm(span=50, adjust=False).mean()

    spread = (ema_fast - ema_slow) / data["atr"].replace(0.0, np.nan)
    trend = pd.Series("RANGING", index=data.index, dtype=object)
    trend[spread > 0.01] = "BULLISH"
    trend[spread < -0.01] = "BEARISH"

    return pd.DataFrame({"time": data["time"], "trend": trend})


def run_backtest(config: BacktestConfig | None = None) -> dict[str, float | int]:
    if config is None:
        config = BacktestConfig()

    symbol_frames: dict[str, pd.DataFrame] = {}
    combined_features: List[pd.DataFrame] = []

    for symbol in config.symbols:
        d1 = _load_frame(config.data_dir, symbol, "D1")
        h4 = _load_frame(config.data_dir, symbol, "H4")
        m15 = _load_frame(config.data_dir, symbol, "M15")

        d1_trend = _ema_trend(d1).rename(columns={"trend": "d1_trend"})
        h4_trend = _ema_trend(h4).rename(columns={"trend": "h4_trend"})

        base = m15[["time", "open", "high", "low", "close", "tick_volume"]].copy().sort_values("time")
        base = pd.merge_asof(base, d1_trend.sort_values("time"), on="time", direction="backward")
        base = pd.merge_asof(base, h4_trend.sort_values("time"), on="time", direction="backward")

        agree = (
            base["d1_trend"].isin(["BULLISH", "BEARISH"])
            & (base["d1_trend"] == base["h4_trend"])
        )
        macro = pd.Series(np.where(agree, base["d1_trend"], "RANGING"), index=base.index)

        ema_fast = base["close"].ewm(span=20, adjust=False).mean()
        ema_slow = base["close"].ewm(span=50, adjust=False).mean()

        micro = pd.Series(["UNCLEAR"] * len(base), index=base.index)
        micro[(macro == "BULLISH") & (ema_fast > ema_slow)] = "CONTINUATION"
        micro[(macro == "BULLISH") & (ema_fast <= ema_slow)] = "PULLBACK"
        micro[(macro == "BEARISH") & (ema_fast < ema_slow)] = "CONTINUATION"
        micro[(macro == "BEARISH") & (ema_fast >= ema_slow)] = "PULLBACK"

        agreement = pd.Series(agree.astype(float), index=base.index)
        consecutive = pd.Series(0.0, index=base.index)
        run = 0
        prev = "RANGING"
        for idx, value in enumerate(macro.tolist()):
            if value in ("BULLISH", "BEARISH") and value == prev:
                run += 1
            elif value in ("BULLISH", "BEARISH"):
                run = 1
            else:
                run = 0
            consecutive.iloc[idx] = float(run)
            prev = value

        feature_frame = build_feature_frame(base, macro, micro, agreement, consecutive)
        feature_frame["symbol"] = symbol

        combined_features.append(feature_frame)
        symbol_frames[symbol] = feature_frame

    train_set = pd.concat(combined_features, ignore_index=True)
    train_set = train_set.iloc[::20].reset_index(drop=True)
    model, _ = train_walk_forward(train_set)
    save_model(model)

    trades: List[TradeResult] = []
    for symbol in config.symbols:
        frame = symbol_frames[symbol].copy()
        scoreable = frame.dropna(subset=[
            "atr_ratio",
            "swing_amplitude_atr",
            "candle_body_ratio_10",
            "distance_from_last_swing_atr",
            "volume_trend_slope_10",
            "d1_h4_agreement",
            "micro_state_encoded",
            "consecutive_structure_count",
        ])
        probs = predict_positive_proba(model, scoreable[[
            "atr_ratio",
            "swing_amplitude_atr",
            "candle_body_ratio_10",
            "distance_from_last_swing_atr",
            "volume_trend_slope_10",
            "d1_h4_agreement",
            "micro_state_encoded",
            "consecutive_structure_count",
        ]])

        frame["ml_confidence"] = np.nan
        frame.loc[scoreable.index, "ml_confidence"] = probs

        swing_high = frame["high"].rolling(config.swing_window_bars).max()
        swing_low = frame["low"].rolling(config.swing_window_bars).min()
        swing_amplitude_atr = (swing_high - swing_low) / frame["atr"].replace(0.0, np.nan)

        session_ok = london_newyork_session_mask(frame["time"])
        amplitude_ok = swing_amplitude_atr >= config.max_swing_amplitude_atr

        valid = (
            (frame["macro_trend"].isin(["BULLISH", "BEARISH"]))
            & (frame["d1_h4_agreement"] >= 1.0)
            & (frame["micro_state"] == "CONTINUATION")
            & session_ok
            & amplitude_ok.fillna(False)
            & (frame["ml_confidence"] > config.confidence_threshold)
        )

        for idx in frame.index[valid]:
            if idx + 1 >= len(frame):
                break
            direction = 1 if frame.loc[idx, "macro_trend"] == "BULLISH" else -1
            pnl_r = _simulate_trade(frame, int(idx), direction, config.rr_ratio, config.max_hold_bars)
            exit_idx = min(int(idx) + config.max_hold_bars, len(frame) - 1)
            trades.append(
                TradeResult(
                    symbol=symbol,
                    entry_time=str(frame.loc[idx, "time"]),
                    exit_time=str(frame.loc[exit_idx, "time"]),
                    direction=direction,
                    pnl_r=float(pnl_r),
                )
            )

    if not trades:
        raise RuntimeError("No trend trades produced in backtest.")

    pnl = pd.Series([t.pnl_r for t in trades], dtype=float)
    times = pd.Series([t.entry_time for t in trades], dtype="string")
    equity = pnl.cumsum()

    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = float(losses.sum()) if not losses.empty else 0.0
    profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0.0 else float("inf")

    max_dd_r = _max_drawdown(equity)
    metrics: dict[str, float | int] = {
        "total_trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(profit_factor),
        "max_drawdown_r": float(max_dd_r),
        "max_drawdown_pct": float(abs(max_dd_r) * 1.0),
        "max_daily_drawdown_pct": float(abs(_max_daily_drawdown_pct(times, pnl))),
        "sharpe_ratio": float(_sharpe(pnl)),
        "expectancy_r": float(pnl.mean()),
    }

    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "trend_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out / "trend_trades.json").write_text(
        json.dumps([asdict(t) for t in trades], indent=2), encoding="utf-8"
    )

    return metrics


def main() -> None:
    print(
        "Starting Trend module backtest on EURUSD/GBPUSD/XAUUSD, "
        "M15 entries with D1+H4 confirmation. This may take several minutes."
    )
    metrics = run_backtest()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

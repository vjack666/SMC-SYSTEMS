from __future__ import annotations

import sys
from pathlib import Path

import joblib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.bos.detector import BosConfig, detect_bos
from modules.choch.detector import CHOCH_BEARISH, CHOCH_BULLISH, detect_choch
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import score_frame
from modules.ob.detector import detect_order_blocks


TARGET_SYMBOL = "EURUSD"
LAST_N_TRADES = 3
PREFERRED_SL = 1.5
STRATEGY_PRIORITY = {"B_mitigation": 0, "A_immediate": 1}


def _load_symbol(symbol: str) -> pd.DataFrame:
    path = Path("data/mt5") / f"{symbol}_M15.parquet"
    frame = pd.read_parquet(path).copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def _prepare_scored(symbol: str) -> pd.DataFrame:
    base = _load_symbol(symbol)
    base = detect_fvg(base)

    split = int(len(base) * 0.6)
    scored = base.iloc[split:].copy().reset_index(drop=True)

    payload = joblib.load("modules/fvg/models/fvg_v3.pkl")
    model = payload["model"]
    scored = score_frame(scored, model)

    scored = detect_bos(scored, BosConfig(followthrough_bars=8))
    scored = detect_choch(scored)
    scored = detect_order_blocks(scored)
    return scored


def _entry_price(row: pd.Series, scored: pd.DataFrame, create_idx: int, entry_idx: int) -> float:
    strategy = str(row["strategy"])
    side = str(row["side"])

    if strategy == "A_immediate":
        return float(scored.iloc[entry_idx]["close"])

    prev2_high = float(pd.to_numeric(scored["high"].shift(2).iloc[create_idx], errors="coerce"))
    prev2_low = float(pd.to_numeric(scored["low"].shift(2).iloc[create_idx], errors="coerce"))
    hi = float(scored.iloc[create_idx]["high"])
    lo = float(scored.iloc[create_idx]["low"])

    if side == "LONG":
        zone_high = lo
        return float(zone_high)

    zone_low = hi
    _ = prev2_low
    _ = prev2_high
    return float(zone_low)


def _draw_candles(ax: plt.Axes, data: pd.DataFrame, width: float = 0.008) -> None:
    for _, r in data.iterrows():
        t = mdates.date2num(r["time"])
        o = float(r["open"])
        h = float(r["high"])
        l = float(r["low"])
        c = float(r["close"])
        color = "#26a69a" if c >= o else "#ef5350"

        ax.vlines(t, l, h, color=color, linewidth=1.0, alpha=0.9)
        bottom = min(o, c)
        body_h = max(abs(c - o), 1e-8)
        ax.add_patch(
            Rectangle(
                (t - width / 2.0, bottom),
                width,
                body_h,
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.9,
            )
        )


def _trade_levels(trade: pd.Series, scored: pd.DataFrame, create_idx: int, entry_idx: int) -> tuple[float, float, float, int]:
    side = str(trade["side"])
    sl_mult = float(trade["sl_atr_mult"])
    entry_px = _entry_price(trade, scored, create_idx, entry_idx)
    atr = float(scored.iloc[entry_idx]["atr"])
    rr = 3.0
    sl_dist = atr * sl_mult
    direction = 1 if side == "LONG" else -1

    if direction == 1:
        sl_px = entry_px - sl_dist
        tp_px = entry_px + (sl_dist * rr)
    else:
        sl_px = entry_px + sl_dist
        tp_px = entry_px - (sl_dist * rr)

    return entry_px, sl_px, tp_px, direction


def _plot_single_trade(ax: plt.Axes, trade: pd.Series) -> dict[str, object]:
    symbol = str(trade["symbol"])
    side = str(trade["side"])
    strategy = str(trade["strategy"])
    sl_mult = float(trade["sl_atr_mult"])

    scored = _prepare_scored(symbol)

    create_time = pd.Timestamp(trade["create_time"])
    entry_time = pd.Timestamp(trade["entry_time"])

    create_idx = int(scored.index[scored["time"] == create_time][0])
    entry_idx = int(scored.index[scored["time"] == entry_time][0])

    entry_px, sl_px, tp_px, _ = _trade_levels(trade, scored, create_idx, entry_idx)

    left = max(0, entry_idx - 120)
    right = min(len(scored), entry_idx + 80)
    view = scored.iloc[left:right].copy()

    ax.set_facecolor("#111827")
    _draw_candles(ax, view)

    times_num = mdates.date2num(view["time"])

    bos_bull = view[view["bos_direction"] == 1]
    bos_bear = view[view["bos_direction"] == -1]
    ax.scatter(mdates.date2num(bos_bull["time"]), bos_bull["high"] * 1.0002, marker="^", s=18, c="#00e676", label="BOS Bull")
    ax.scatter(mdates.date2num(bos_bear["time"]), bos_bear["low"] * 0.9998, marker="v", s=18, c="#ff5252", label="BOS Bear")

    choch_bull = view[view["choch_signal"] == CHOCH_BULLISH]
    choch_bear = view[view["choch_signal"] == CHOCH_BEARISH]
    ax.scatter(mdates.date2num(choch_bull["time"]), choch_bull["high"] * 1.0005, marker="*", s=55, c="#40c4ff", label="CHOCH Bull")
    ax.scatter(mdates.date2num(choch_bear["time"]), choch_bear["low"] * 0.9995, marker="*", s=55, c="#ffab40", label="CHOCH Bear")

    fvg_bull = view[view["fvg_bullish"] == 1]
    fvg_bear = view[view["fvg_bearish"] == 1]
    ax.scatter(mdates.date2num(fvg_bull["time"]), fvg_bull["low"] * 0.9997, marker="s", s=18, c="#7c4dff", label="FVG Bull")
    ax.scatter(mdates.date2num(fvg_bear["time"]), fvg_bear["high"] * 1.0003, marker="s", s=18, c="#ff1744", label="FVG Bear")

    ob_bull = view[view["ob_bullish"].astype(bool)]
    ob_bear = view[view["ob_bearish"].astype(bool)]
    ax.scatter(mdates.date2num(ob_bull["time"]), ob_bull["low"] * 0.9992, marker="D", s=16, c="#69f0ae", label="OB Bull")
    ax.scatter(mdates.date2num(ob_bear["time"]), ob_bear["high"] * 1.0008, marker="D", s=16, c="#ff8a80", label="OB Bear")

    entry_t_num = mdates.date2num(entry_time)
    ax.scatter([entry_t_num], [entry_px], marker="X", s=90, c="#ffd54f", edgecolors="#000000", linewidths=0.8, label="Entry")
    ax.axhline(entry_px, color="#ffd54f", linestyle="-", linewidth=1.0, alpha=0.9, label="Entry Px")
    ax.axhline(sl_px, color="#ef5350", linestyle="--", linewidth=1.0, alpha=0.9, label="SL")
    ax.axhline(tp_px, color="#26a69a", linestyle="--", linewidth=1.0, alpha=0.9, label="TP")

    x0 = times_num.min()
    x1 = times_num.max()
    ax.fill_between([x0, x1], [entry_px, entry_px], [sl_px, sl_px], color="#ef5350", alpha=0.08)
    ax.fill_between([x0, x1], [entry_px, entry_px], [tp_px, tp_px], color="#26a69a", alpha=0.08)

    ax.set_title(
        (
            f"{symbol} M15 | {strategy} {side} | SL {sl_mult} ATR | "
            f"Entry {entry_time} | pnl_r={float(trade['pnl_r']):.3f}"
        ),
        color="white",
        fontsize=10,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    ax.tick_params(axis="x", colors="#cfd8dc", labelsize=8)
    ax.tick_params(axis="y", colors="#cfd8dc", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#455a64")
    ax.grid(True, alpha=0.15, color="#90a4ae")

    return {
        "symbol": symbol,
        "timeframe": "M15",
        "strategy": strategy,
        "side": side,
        "sl_atr_mult": sl_mult,
        "entry_time": str(entry_time),
        "entry_price": float(entry_px),
        "sl_price": float(sl_px),
        "tp_price": float(tp_px),
        "pnl_r": float(trade["pnl_r"]),
    }


def main() -> None:
    trades = pd.read_csv("results/fvg_mitigation_trade_log.csv")
    trades["entry_time"] = pd.to_datetime(trades["entry_time"], utc=True)
    trades["create_time"] = pd.to_datetime(trades["create_time"], utc=True)

    trades = trades[trades["symbol"] == TARGET_SYMBOL].copy()
    if trades.empty:
        raise RuntimeError(f"No trades found for {TARGET_SYMBOL}.")

    trades["strategy_rank"] = trades["strategy"].map(STRATEGY_PRIORITY).fillna(99).astype(int)
    trades["sl_distance"] = (pd.to_numeric(trades["sl_atr_mult"], errors="coerce") - PREFERRED_SL).abs()

    # Keep a single representative trade per entry timestamp to avoid SL duplicates.
    dedup = trades.sort_values(["entry_time", "strategy_rank", "sl_distance", "create_time"]).drop_duplicates(
        subset=["entry_time"], keep="first"
    )
    last_trades = dedup.sort_values("entry_time").tail(LAST_N_TRADES).reset_index(drop=True)
    if len(last_trades) < LAST_N_TRADES:
        raise RuntimeError(f"Only found {len(last_trades)} unique trades for {TARGET_SYMBOL}.")

    fig, axes = plt.subplots(3, 1, figsize=(16, 16), sharex=False)
    fig.patch.set_facecolor("#111827")

    meta_trades: list[dict[str, object]] = []
    for i, trade in enumerate(last_trades.itertuples(index=False)):
        trade_series = pd.Series(trade._asdict())
        meta_trades.append(_plot_single_trade(axes[i], trade_series))

    handles, labels = axes[0].get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    axes[0].legend(
        uniq.values(),
        uniq.keys(),
        loc="upper left",
        fontsize=7,
        frameon=True,
        facecolor="#263238",
        edgecolor="#546e7a",
        labelcolor="white",
    )

    fig.suptitle("Last 3 Backtest Trades | Entry + SL/TP + BOS/FVG/CHOCH/OB", color="white", fontsize=14)

    out = Path("results")
    out.mkdir(parents=True, exist_ok=True)
    img_path = out / "last_3_backtest_trades_EURUSD_visual.png"
    meta_path = out / "last_3_backtest_trades_EURUSD_visual_meta.json"

    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    fig.savefig(img_path, dpi=170)
    plt.close(fig)

    meta = {
        "count": int(len(meta_trades)),
        "timeframe": "M15",
        "symbol_filter": TARGET_SYMBOL,
        "selection": {
            "unique_by": "entry_time",
            "preferred_sl": PREFERRED_SL,
            "strategy_priority": STRATEGY_PRIORITY,
        },
        "trades": meta_trades,
        "image": str(img_path),
    }
    meta_path.write_text(pd.Series(meta).to_json(indent=2), encoding="utf-8")

    print(f"Saved: {img_path}")
    print(f"Meta: {meta_path}")


if __name__ == "__main__":
    main()

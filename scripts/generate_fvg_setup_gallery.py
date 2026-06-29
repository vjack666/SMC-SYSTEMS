from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules.fvg.backtest import _load
from modules.fvg.detector import detect_fvg
from modules.fvg.ml_model import score_frame


CONFIDENCE_THRESHOLD = 0.62
LOOKAHEAD_BARS = 300
PREFERRED_SL = 1.5
DEFAULT_WINNERS = 20
DEFAULT_LOSERS = 20


def _intersects_zone(low: float, high: float, zone_low: float, zone_high: float) -> bool:
    return (low <= zone_high) and (high >= zone_low)


def _prepare_scored(symbol: str) -> pd.DataFrame:
    base = _load(Path("data/mt5"), symbol)
    base = detect_fvg(base)
    split = int(len(base) * 0.6)
    scored = base.iloc[split:].copy().reset_index(drop=True)

    payload = joblib.load("modules/fvg/models/fvg_v3.pkl")
    model = payload["model"]
    scored = score_frame(scored, model)
    return scored


def _build_event_table(scored: pd.DataFrame, threshold: float, lookahead: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    low_arr = pd.to_numeric(scored["low"], errors="coerce").to_numpy(dtype=float)
    high_arr = pd.to_numeric(scored["high"], errors="coerce").to_numpy(dtype=float)
    close_arr = pd.to_numeric(scored["close"], errors="coerce").to_numpy(dtype=float)
    atr_arr = pd.to_numeric(scored["atr"], errors="coerce").to_numpy(dtype=float)
    conf_arr = pd.to_numeric(scored["ml_confidence"], errors="coerce").to_numpy(dtype=float)
    bull_arr = scored["fvg_bullish"].astype(bool).to_numpy()
    bear_arr = scored["fvg_bearish"].astype(bool).to_numpy()
    time_arr = scored["time"].to_numpy()

    prev2_high = pd.to_numeric(scored["high"].shift(2), errors="coerce").to_numpy(dtype=float)
    prev2_low = pd.to_numeric(scored["low"].shift(2), errors="coerce").to_numpy(dtype=float)

    qualified = np.where((conf_arr >= threshold) & (bull_arr | bear_arr))[0]

    for i in qualified:
        is_bull = bool(bull_arr[i])
        direction = 1 if is_bull else -1
        side = "LONG" if direction == 1 else "SHORT"

        create_close = float(close_arr[i])
        atr_create = float(atr_arr[i])
        conf = float(conf_arr[i])
        if not np.isfinite(atr_create) or atr_create <= 0.0:
            continue

        if direction == 1:
            zone_low = float(prev2_high[i])
            zone_high = float(low_arr[i])
            limit_price = zone_high
        else:
            zone_low = float(high_arr[i])
            zone_high = float(prev2_low[i])
            limit_price = zone_low

        if (not np.isfinite(zone_low)) or (not np.isfinite(zone_high)):
            continue
        if zone_high < zone_low:
            zone_low, zone_high = zone_high, zone_low

        abandoned = False
        first_mitigation_idx: int | None = None
        retest_idx: int | None = None

        j_end = min(len(scored), i + 1 + max(1, int(lookahead)))
        for j in range(i + 1, j_end):
            low_j = float(low_arr[j])
            high_j = float(high_arr[j])
            if not np.isfinite(low_j) or not np.isfinite(high_j):
                continue

            touched_zone = _intersects_zone(low_j, high_j, zone_low, zone_high)
            if first_mitigation_idx is None and touched_zone:
                first_mitigation_idx = j

            if not abandoned:
                if direction == 1:
                    abandoned = low_j > zone_high
                else:
                    abandoned = high_j < zone_low
                continue

            if touched_zone:
                retest_idx = j
                break

        rows.append(
            {
                "create_idx": int(i),
                "create_time": pd.Timestamp(time_arr[i]),
                "direction": int(direction),
                "side": side,
                "create_close": create_close,
                "atr_create": atr_create,
                "zone_low": zone_low,
                "zone_high": zone_high,
                "zone_size_atr": float((zone_high - zone_low) / atr_create) if atr_create > 0 else np.nan,
                "limit_price": float(limit_price),
                "ml_confidence": conf,
                "first_mitigation_idx": first_mitigation_idx,
                "retest_idx": retest_idx,
            }
        )

    return pd.DataFrame(rows)


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


def _select_trade_set(trades: pd.DataFrame, winners: int, losers: int) -> pd.DataFrame:
    # Keep one representative row per event, preferring SL closest to 1.5 ATR.
    data = trades.copy()
    data["sl_distance"] = (pd.to_numeric(data["sl_atr_mult"], errors="coerce") - PREFERRED_SL).abs()
    keys = ["symbol", "strategy", "side", "create_time", "entry_time"]
    dedup = data.sort_values(["entry_time", "sl_distance"]).drop_duplicates(subset=keys, keep="first")

    dedup = dedup[dedup["strategy"] == "B_mitigation"].copy()
    dedup = dedup.sort_values("entry_time")

    wins = dedup[dedup["pnl_r"] > 0].tail(winners)
    losses = dedup[dedup["pnl_r"] < 0].tail(losers)

    wins = wins.assign(label="WIN")
    losses = losses.assign(label="LOSS")
    selected = pd.concat([wins, losses], ignore_index=True)
    return selected.sort_values(["label", "entry_time"], ascending=[True, True]).reset_index(drop=True)


def _plot_trade_image(trade: pd.Series, scored: pd.DataFrame, events: pd.DataFrame, out_path: Path) -> dict[str, object]:
    create_time = pd.Timestamp(trade["create_time"])
    entry_time = pd.Timestamp(trade["entry_time"])
    side = str(trade["side"])
    direction = 1 if side == "LONG" else -1

    # Match event by create_time + side; pick closest retest to trade entry.
    ev = events[(events["create_time"] == create_time) & (events["side"] == side)].copy()
    if ev.empty:
        raise RuntimeError(f"No matching event found for {trade['symbol']} {create_time} {side}")

    if ev["retest_idx"].notna().any():
        entry_idx_true = int(scored.index[scored["time"] == entry_time][0])
        ev = ev[ev["retest_idx"].notna()].copy()
        ev["delta"] = (ev["retest_idx"].astype(int) - entry_idx_true).abs()
        ev = ev.sort_values("delta")
    ev_row = ev.iloc[0]

    create_idx = int(ev_row["create_idx"])
    entry_idx = int(scored.index[scored["time"] == entry_time][0])
    first_mit_idx = int(ev_row["first_mitigation_idx"]) if pd.notna(ev_row["first_mitigation_idx"]) else None

    zone_low = float(ev_row["zone_low"])
    zone_high = float(ev_row["zone_high"])
    zone_color = "#00c853" if direction == 1 else "#d50000"

    entry_price = float(ev_row["limit_price"])
    atr_entry = float(pd.to_numeric(scored.iloc[entry_idx]["atr"], errors="coerce"))
    sl_mult = float(trade["sl_atr_mult"])
    rr = 3.0

    sl_dist = atr_entry * sl_mult
    if direction == 1:
        sl_price = entry_price - sl_dist
        tp_price = entry_price + (sl_dist * rr)
    else:
        sl_price = entry_price + sl_dist
        tp_price = entry_price - (sl_dist * rr)

    left = max(0, create_idx - 30)
    right = min(len(scored), entry_idx + 31)
    view = scored.iloc[left:right].copy()

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    _draw_candles(ax, view)

    x0 = mdates.date2num(view["time"].iloc[0])
    x1 = mdates.date2num(view["time"].iloc[-1])

    # FVG zone as transparent rectangle across visible window.
    ax.add_patch(
        Rectangle(
            (x0, zone_low),
            x1 - x0,
            zone_high - zone_low,
            facecolor=zone_color,
            edgecolor=zone_color,
            linewidth=1.2,
            alpha=0.18,
            zorder=0,
        )
    )

    ct = mdates.date2num(pd.Timestamp(ev_row["create_time"]))
    et = mdates.date2num(entry_time)
    ax.axvline(ct, color="#4fc3f7", linestyle="--", linewidth=1.2, alpha=0.85, label="FVG Create")
    if first_mit_idx is not None:
        mt = mdates.date2num(pd.Timestamp(scored.iloc[first_mit_idx]["time"]))
        ax.axvline(mt, color="#ffeb3b", linestyle=":", linewidth=1.2, alpha=0.9, label="Mitigation")

    ax.axvline(et, color="#ffd54f", linestyle="-", linewidth=1.5, alpha=0.95, label="Entry Candle")
    ax.annotate(
        "ENTRY",
        xy=(et, entry_price),
        xytext=(et, entry_price + (abs(entry_price) * 0.0009)),
        color="#ffd54f",
        fontsize=11,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#ffd54f", lw=1.2),
    )

    ax.axhline(entry_price, color="#ffd54f", linestyle="-", linewidth=1.2, label="Entry")
    ax.axhline(sl_price, color="#ff5252", linestyle="--", linewidth=1.2, label="SL")
    ax.axhline(tp_price, color="#00e676", linestyle="--", linewidth=1.2, label="TP")

    ax.fill_between([x0, x1], [entry_price, entry_price], [sl_price, sl_price], color="#ff5252", alpha=0.10)
    ax.fill_between([x0, x1], [entry_price, entry_price], [tp_price, tp_price], color="#00e676", alpha=0.10)

    txt = (
        f"FVG Size: {float(ev_row['zone_size_atr']):.2f} ATR\n"
        f"ML Confidence: {float(trade['ml_confidence']):.2f}\n"
        f"ATR: {atr_entry:.5f}\n"
        f"SL: {sl_mult:.1f} ATR\n"
        f"RR: 1:3"
    )
    ax.text(
        0.015,
        0.98,
        txt,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        color="white",
        bbox=dict(facecolor="#1e293b", edgecolor="#64748b", alpha=0.92, boxstyle="round,pad=0.35"),
    )

    ax.set_title(
        f"{trade['label']} | {trade['symbol']} M15 | {trade['strategy']} {trade['side']} | "
        f"Entry {entry_time} | pnl_r={float(trade['pnl_r']):.3f}",
        color="white",
        fontsize=12,
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    ax.tick_params(axis="x", colors="#cbd5e1")
    ax.tick_params(axis="y", colors="#cbd5e1")
    for spine in ax.spines.values():
        spine.set_color("#475569")
    ax.grid(True, alpha=0.15, color="#94a3b8")

    handles, labels = ax.get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    ax.legend(
        uniq.values(),
        uniq.keys(),
        loc="upper right",
        fontsize=8,
        frameon=True,
        facecolor="#1e293b",
        edgecolor="#64748b",
        labelcolor="white",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)

    return {
        "file": str(out_path),
        "label": str(trade["label"]),
        "symbol": str(trade["symbol"]),
        "strategy": str(trade["strategy"]),
        "side": str(trade["side"]),
        "create_time": str(create_time),
        "entry_time": str(entry_time),
        "sl_atr_mult": float(sl_mult),
        "pnl_r": float(trade["pnl_r"]),
        "entry_price": float(entry_price),
        "sl_price": float(sl_price),
        "tp_price": float(tp_price),
        "fvg_size_atr": float(ev_row["zone_size_atr"]),
        "ml_confidence": float(trade["ml_confidence"]),
        "atr_entry": float(atr_entry),
        "first_mitigation_time": str(pd.Timestamp(scored.iloc[first_mit_idx]["time"])) if first_mit_idx is not None else None,
    }


def main() -> None:
    trades = pd.read_csv("results/fvg_mitigation_trade_log.csv")
    trades["entry_time"] = pd.to_datetime(trades["entry_time"], utc=True)
    trades["create_time"] = pd.to_datetime(trades["create_time"], utc=True)

    selected = _select_trade_set(trades, DEFAULT_WINNERS, DEFAULT_LOSERS)
    if selected.empty:
        raise RuntimeError("No trades selected for gallery generation.")

    out_dir = Path("results/setup_examples")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Remove previous generated PNGs to keep gallery clean.
    for old in out_dir.glob("trade_*.png"):
        old.unlink(missing_ok=True)

    by_symbol = {symbol: _prepare_scored(symbol) for symbol in sorted(selected["symbol"].unique())}
    events_by_symbol = {
        symbol: _build_event_table(by_symbol[symbol], CONFIDENCE_THRESHOLD, LOOKAHEAD_BARS)
        for symbol in by_symbol
    }

    manifests: list[dict[str, object]] = []
    for i, trade in enumerate(selected.itertuples(index=False), start=1):
        tr = pd.Series(trade._asdict())
        symbol = str(tr["symbol"])
        out_path = out_dir / f"trade_{i:03d}.png"
        item = _plot_trade_image(tr, by_symbol[symbol], events_by_symbol[symbol], out_path)
        manifests.append(item)

    manifest_df = pd.DataFrame(manifests)
    manifest_csv = out_dir / "manifest.csv"
    manifest_json = out_dir / "manifest.json"
    manifest_df.to_csv(manifest_csv, index=False)
    manifest_json.write_text(json.dumps(manifests, indent=2), encoding="utf-8")

    summary = {
        "output_dir": str(out_dir),
        "total_images": int(len(manifests)),
        "winners": int((manifest_df["label"] == "WIN").sum()),
        "losers": int((manifest_df["label"] == "LOSS").sum()),
        "manifest_csv": str(manifest_csv),
        "manifest_json": str(manifest_json),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

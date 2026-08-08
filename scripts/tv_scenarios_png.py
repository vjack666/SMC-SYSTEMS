"""Standalone visual aid: render TradingView-style PNGs for tv_scenarios.json setups 1-5.

NOT wired into the trading loop. Human review only.
"""
import json
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "results", "tv_scenarios.json")
OUT = os.path.join(ROOT, "results", "tv")

BG = "#0e1117"
PANEL = "#0e1117"
GRID = "#1e2530"
TXT = "#d1d4dc"
UP = "#26a69a"
DN = "#ef5350"
LVL_COLOR = {"Alta": "#26a69a", "Media": "#ff9800", "Baja": "#ef5350"}


def parse_ts(s):
    return datetime.fromisoformat(str(s))


def draw(sc, path):
    candles = sc["candles"]
    n = len(candles)
    o = [c[1] for c in candles]
    h = [c[2] for c in candles]
    lo = [c[3] for c in candles]
    cl = [c[4] for c in candles]
    times = [parse_ts(c[0]) for c in candles]

    fig, ax = plt.subplots(figsize=(14, 7.5), dpi=130)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    for i in range(n):
        col = UP if cl[i] >= o[i] else DN
        ax.plot([i, i], [lo[i], h[i]], color=col, linewidth=0.9, solid_capstyle="round", zorder=3)
        body_lo = min(o[i], cl[i])
        body_h = max(abs(cl[i] - o[i]), 1e-6)
        ax.add_patch(Rectangle((i - 0.32, body_lo), 0.64, body_h,
                               facecolor=col, edgecolor=col, linewidth=0.6, zorder=4))

    entry, sl, tp = sc["entry"], sc["sl"], sc["tp"]
    lines = [(entry, "#26a69a", "ENTRY"), (sl, "#ef5350", "SL"), (tp, "#2196f3", "TP")]
    for price, col, lab in lines:
        ax.axhline(price, color=col, linewidth=1.2, linestyle="--", alpha=0.95, zorder=5)
        ax.text(n - 0.3, price, f" {lab} {price:.5f}", color="#0e1117", fontsize=9,
                fontweight="bold", va="center", ha="left", zorder=7,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=col, edgecolor="none"))

    # entry candle marker
    ei = int(sc["entry_idx_in_candles"])
    ei = max(0, min(ei, n - 1))
    ax.scatter([ei], [lo[ei] - (max(h) - min(lo)) * 0.04], marker="^", s=170,
               color="#ffd54f", edgecolors="#0e1117", linewidths=0.8, zorder=8)
    ax.axvline(ei, color="#ffd54f", linewidth=0.7, alpha=0.25, zorder=2)

    # bias / POI band at top
    lvl = sc.get("lvl", "Media")
    bc = LVL_COLOR.get(lvl, "#ff9800")
    ymin, ymax = min(lo), max(h)
    pad = (ymax - ymin) * 0.14 or 0.001
    top = ymax + pad
    ax.add_patch(Rectangle((-0.5, ymax + pad * 0.35), n, pad * 0.5,
                           facecolor=bc, alpha=0.18, edgecolor=bc, linewidth=0.8, zorder=1))
    ax.text(n / 2.0, ymax + pad * 0.6,
            f"SESGO / POI: {lvl.upper()}   ·   conf {sc.get('conf', '—')}   ·   tier {sc.get('tier', '—')}",
            color=bc, fontsize=10, fontweight="bold", ha="center", va="center", zorder=6)

    ax.set_ylim(ymin - pad * 0.55, top)
    ax.set_xlim(-1, n + 6)

    # axes styling
    ax.grid(color=GRID, linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)
    for s in ("top", "left"):
        ax.spines[s].set_visible(False)
    for s in ("bottom", "right"):
        ax.spines[s].set_color(GRID)
    ax.yaxis.tick_right()
    ax.tick_params(colors=TXT, labelsize=9)
    step = max(1, n // 10)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([times[i].strftime("%d %b\n%H:%M") for i in range(0, n, step)], fontsize=8)

    ax.set_title(f"EURUSD M15 — Setup {sc['n']} ({lvl})",
                 color="#ffffff", fontsize=15, fontweight="bold", loc="left", pad=16)
    ax.text(0, 1.015, f"entry {parse_ts(sc['ts']).strftime('%Y-%m-%d %H:%M UTC')}",
            transform=ax.transAxes, color="#787b86", fontsize=9, va="bottom")

    handles = [Line2D([], [], color=c, ls="--", label=l) for _, c, l in lines]
    handles.append(Line2D([], [], color="#ffd54f", marker="^", ls="", label="Vela de entrada"))
    leg = ax.legend(handles=handles, loc="upper left", frameon=True, fontsize=9)
    leg.get_frame().set_facecolor("#161b22")
    leg.get_frame().set_edgecolor(GRID)
    for t in leg.get_texts():
        t.set_color(TXT)

    fig.tight_layout()
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(SRC, encoding="utf-8"))
    done = []
    for sc in data:
        if int(sc["n"]) not in (1, 2, 3, 4, 5):
            continue
        p = os.path.join(OUT, f"scenario_{sc['n']}.png")
        draw(sc, p)
        done.append((p, os.path.getsize(p)))
    for p, s in done:
        print(f"{p}  {s} bytes")


if __name__ == "__main__":
    main()

"""Generate TradingView-style MULTI-TF setup charts from results/tv_scenarios_multitf.json.

Each element of tv_scenarios_multitf.json has:
  n, ts, lvl (Alta|Media|Baja), entry, sl, tp, bias_dir,
  panels: {D1,H4,H1,M15,M5} each with
      candles: list of [time, open, high, low, close] (real bars for that TF)
      entry_idx: index of the key candle
      role: theory text for that TF

Output: results/tv/scenario_<n>.png  for n in [LO, HI] (default 1..5).

Layout: 5 stacked subplots (D1 top -> M5 bottom). Each panel draws its own candles
with auto-scaled Y (ranges differ by ~10x across TF, a shared Y would crush the
lower TF). M15 and M5 also draw ENTRY(green)/SL(red)/TP(blue) hlines + triangle on
entry_idx. Figure title: 'EURUSD - Setup N - Sesgo X - Nivel LVL'.

Style: dark fintech bg (#0e1117), green/red candles (close>=open green), clean axes.

Usage:
  python scripts/gen_tv_setups_multitf.py [--json PATH] [--lo 1] [--hi 5] [--outdir DIR]
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Rectangle


BG = "#0e1117"
GRID = "#1c2230"
UP = "#26a69a"
DOWN = "#ef5350"
ENTRY_C = "#26a69a"
SL_C = "#ef5350"
TP_C = "#42a5f5"
LVL_COLORS = {"Alta": "#26a69a", "Media": "#ff9800", "Baja": "#ef5350"}
TF_ORDER = ["D1", "H4", "H1", "M15", "M5"]


def fmt_price(p):
    return f"{p:.5f}"


def plot_setup(s, outdir):
    n = s["n"]
    lvl = s["lvl"]
    bias = s["bias_dir"]
    entry = s["entry"]; sl = s["sl"]; tp = s["tp"]
    panels = s["panels"]

    fig, axes = plt.subplots(
        len(TF_ORDER), 1, figsize=(16, 14), dpi=110, sharex=False)
    fig.patch.set_facecolor(BG)

    # Figure-level title
    fig.suptitle(
        f"EURUSD — Setup {n} — Sesgo {bias} — Nivel {lvl}",
        color="#e6edf3", fontsize=15, fontweight="bold", y=0.995)

    for ax, tf in zip(axes, TF_ORDER):
        ax.set_facecolor(BG)
        p = panels[tf]
        candles = p["candles"]
        times = [str(c[0]) for c in candles]
        opens = [c[1] for c in candles]
        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        closes = [c[4] for c in candles]
        x = list(range(len(candles)))
        eidx = p["entry_idx"]
        role = p["role"]

        width = 0.6
        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = UP if c >= o else DOWN
            ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=2)
            rect = Rectangle((i - width/2, min(o, c)), width, abs(c - o),
                             facecolor=color, edgecolor=color, zorder=2)
            ax.add_patch(rect)

        # title per subplot = TF + role
        ax.set_title(f"{tf} — {role}".upper(),
                     color="#e6edf3", fontsize=10, fontweight="bold",
                     loc="left", pad=4)

        # ENTRY/SL/TP lines + triangle on M15 and M5
        if tf in ("M15", "M5"):
            rng = (max(highs) - min(lows)) or 1.0
            nudge = rng * 0.013
            specs = sorted([("ENTRY", entry, ENTRY_C), ("SL", sl, SL_C),
                            ("TP", tp, TP_C)], key=lambda t: t[1])
            for k, (label, price, color) in enumerate(specs):
                ax.axhline(price, color=color, linewidth=1.2, linestyle="-", zorder=3)
                dy = (k - 1) * nudge
                ax.text(len(candles) - 1.2, price + dy,
                        f"{label} {fmt_price(price)}",
                        color=color, fontsize=8, fontweight="bold",
                        va="center", ha="right", clip_on=False,
                        bbox=dict(facecolor=BG, edgecolor=color, linewidth=0.6,
                                  boxstyle="round,pad=0.2"), zorder=8)

            # highlight entry candle + triangle
            ax.add_patch(Rectangle((eidx - width/2 - 0.15, lows[eidx]),
                                   width + 0.3, highs[eidx] - lows[eidx],
                                   facecolor="none", edgecolor="#ffd54f",
                                   linewidth=1.6, zorder=4))
            ax.scatter([eidx], [highs[eidx]], marker="^", s=120, color="#ffd54f",
                       zorder=6, edgecolors="#000", linewidths=0.5)

        ax.set_xlim(-1, len(candles))
        if tf in ("M15", "M5"):
            lo = min(min(lows), sl, entry, tp)
            hi = max(max(highs), sl, entry, tp)
        else:
            lo, hi = min(lows), max(highs)
        pad = (hi - lo) * 0.10
        ax.set_ylim(lo - pad, hi + pad)
        ax.tick_params(axis="x", colors="#8b949e", labelsize=7)
        ax.tick_params(axis="y", colors="#8b949e", labelsize=7)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.5f}"))
        step = max(1, len(candles) // 6)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([times[i][5:16] for i in x[::step]],
                           rotation=30, ha="right")
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(True, axis="y", color=GRID, linewidth=0.5, alpha=0.6)
        ax.grid(False, axis="x")

    fig.subplots_adjust(left=0.07, right=0.93, top=0.95, bottom=0.05,
                        hspace=0.28)
    out = os.path.join(outdir, f"scenario_{n}.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json",
                    default=r"C:\Users\v_jac\Desktop\SMC-SYSTEMS\results\tv_scenarios_multitf.json")
    ap.add_argument("--lo", type=int, default=1)
    ap.add_argument("--hi", type=int, default=5)
    ap.add_argument("--outdir",
                    default=r"C:\Users\v_jac\Desktop\SMC-SYSTEMS\results\tv")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    with open(args.json) as f:
        data = json.load(f)
    by_n = {s["n"]: s for s in data}
    for n in range(args.lo, args.hi + 1):
        if n not in by_n:
            print(f"setup {n} not in json - skipped")
            continue
        out = plot_setup(by_n[n], args.outdir)
        print(f"Saved {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()

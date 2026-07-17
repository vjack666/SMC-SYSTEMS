"""Construye la estructura ICT M15 de EURUSD frame a frame (ultimos 6 meses).

Estilo TradingView (fondo oscuro #131722, velas verde/rojo TV, zonas como
rectangulos con borde + label de precio). Pinta: Order Block, FVG, BSL/SSL,
BOS y CHOCH activos, linea premium/discount 50%, OTE. NO es precio en vivo:
avanza sobre el historico M15 cerrado y genera un PNG por ~120 velas (1 dia M15)
mostrando solo las velas y zonas ICT detectadas HASTA ese punto.

Reusa detectors del proyecto (detect_fvg, detect_liquidity, analyze_timeframe).
Agg, sin ventana. Salida: results/mapa_m15_build/EURUSD_M15_frame_XXXX.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from detectors.fvg import detect_fvg
from detectors.liquidity import detect_liquidity
from detectors.killzones import detect_killzones
from rutina_eurusd import analyze_timeframe

SYMBOL = "EURUSD"
TF = "M15"
OUT = BASE / "results" / "mapa_m15_build"
OUT.mkdir(parents=True, exist_ok=True)
STEP = 120          # velas por frame (~1 dia M15)
SINCE = "2026-01-18"

# Paleta TradingView
BG = "#131722"
GRID = "#2a2e39"
UP = "#26a69a"       # verde TV
DOWN = "#ef5350"     # rojo TV
TXT = "#d1d4dc"
FVG_UP = "#26a69a"
FVG_DN = "#ef5350"
OB_UP = "#0f9d8a"
OB_DN = "#e0485a"
BSL = "#f23645"      # rojo TV liquidity
SSL = "#f7b955"      # naranja TV liquidity
BOS = "#2962ff"      # azul TV
CHOCH = "#ff9800"    # naranja
OTE = "#ba68c8"      # morado zona entrada


def _zone_box(ax, y0, y1, x0, x1, edge, fill, label):
    """Rectangulo estilo TV: borde nítido + relleno tenue + label de precio."""
    ax.add_patch(Rectangle((x0, y0), x1 - x0, max(y1 - y0, 1e-6),
                           facecolor=fill, edgecolor=edge, lw=1.0, alpha=0.85,
                           zorder=2))
    ax.text(x1, y1, f"{label} {y1:.5f}", fontsize=7, color=edge, alpha=1.0,
            va="bottom", ha="right", zorder=6)


def _hline(ax, y, color, label, x1, ls="--"):
    ax.axhline(y, color=color, lw=1.0, ls=ls, alpha=0.9, zorder=3)
    ax.text(x1, y, f"{label} {y:.5f}", fontsize=7, color=color, alpha=1.0,
            va="bottom", ha="right", zorder=6)


def _candles(ax, d: pd.DataFrame) -> None:
    for i, row in d.iterrows():
        color = UP if row["close"] >= row["open"] else DOWN
        ax.plot([i, i], [row["low"], row["high"]], color=color, lw=1.0, zorder=4)
        bh = abs(row["close"] - row["open"])
        ax.add_patch(Rectangle((i - 0.35, min(row["open"], row["close"])), 0.7,
                               max(bh, 1e-6), facecolor=color, edgecolor=color, lw=0.4, zorder=4))
    ax.set_xlim(-1, len(d))
    ax.set_ylim(d["low"].min() * 0.9992, d["high"].max() * 1.0008)


def render_frame(df_full: pd.DataFrame, upto: int, idx: int) -> None:
    d = df_full.iloc[:upto].reset_index(drop=True)
    if len(d) < 30:
        return
    info = analyze_timeframe(d, TF)
    dd = detect_killzones(detect_liquidity(d.copy()))
    fig, ax = plt.subplots(1, 1, figsize=(15, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.grid(color=GRID, lw=0.5, ls=":", zorder=0)
    ax.set_axisbelow(True)
    _candles(ax, d)
    x1 = len(d) - 1
    lo, hi = d["low"].min(), d["high"].max()

    # Premium / discount 50%
    z0, z1 = info.get("zone_low", lo), info.get("zone_high", hi)
    if z0 and z1:
        mid = (z0 + z1) / 2
        ax.axhline(mid, color="#787b86", lw=0.7, ls=":", alpha=0.7, zorder=3)
        ax.text(x1, mid, f"PD 50% {mid:.5f}", fontsize=7, color="#787b86",
                va="bottom", ha="right", zorder=6)

    # Order Block activo
    if info.get("ob_bottom") is not None:
        edge = OB_UP if info.get("ob_dir") == "bullish" else OB_DN
        _zone_box(ax, info["ob_bottom"], info["ob_top"], -1, x1, edge, edge, "OB")

    # FVG activos
    try:
        fvg = detect_fvg(dd)
        for _, r in fvg.iterrows():
            if bool(r.get("fvg_active")):
                top = float(r.get("fvg_top", r["close"]))
                bot = float(r.get("fvg_bottom", r["close"]))
                edge = FVG_UP if r.get("fvg_type") != "bearish" else FVG_DN
                _zone_box(ax, bot, top, -1, x1, edge, edge, "FVG")
                break
    except Exception:
        pass

    # BSL / SSL
    if "bsl_price" in dd.columns and dd["bsl_price"].notna().any():
        lvl = float(dd.dropna(subset=["bsl_price"]).iloc[-1]["bsl_price"])
        if lo <= lvl <= hi:
            _hline(ax, lvl, BSL, "BSL", x1)
    if "ssl_price" in dd.columns and dd["ssl_price"].notna().any():
        lvl = float(dd.dropna(subset=["ssl_price"]).iloc[-1]["ssl_price"])
        if lo <= lvl <= hi:
            _hline(ax, lvl, SSL, "SSL", x1)

    # BOS activo (nivel real de analyze_timeframe)
    bs = str(info.get("bos_status", ""))
    if bs == "active":
        lvl = info.get("bos_level")
        try:
            lvl = float(lvl)
            if lo <= lvl <= hi:
                _hline(ax, lvl, BOS, "BOS", x1, ls="-")
        except (TypeError, ValueError):
            pass

    # CHOCH activo (marcar con banda + texto; analyze_timeframe no expone nivel)
    if str(info.get("choch_status", "")) == "active":
        ax.text(0.01, 0.97, "CHOCH ACTIVO", transform=ax.transAxes, va="top",
                ha="left", fontsize=8, color=CHOCH, alpha=1.0, zorder=6,
                bbox=dict(boxstyle="round", fc=BG, ec=CHOCH, alpha=0.6))

    # OTE (zona de entrada)
    ote = info.get("ote_short") if info.get("bias", "").upper().startswith("SHORT") else info.get("ote_long")
    if ote and len(ote) == 2 and ote[0] and ote[1]:
        try:
            _zone_box(ax, float(min(ote)), float(max(ote)), -1, x1, OTE, OTE, "OTE")
        except (TypeError, ValueError):
            pass

    last_t = str(d.iloc[-1]["time"])[:16]
    ax.set_title(f"{SYMBOL} {TF} · estructura ICT (TradingView) · hasta {last_t} · vela {upto}/{len(df_full)}",
                 color=TXT, fontsize=10, fontweight="bold", loc="left")
    ax.set_ylabel(TF, fontsize=10, color=TXT)
    ax.tick_params(colors="#787b86")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    out = OUT / f"{SYMBOL}_{TF}_frame_{idx:04d}.png"
    fig.savefig(out, dpi=110, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def main() -> int:
    df = pd.read_parquet(BASE / "data" / "raw" / f"{SYMBOL}_{TF}.parquet")
    df = df[df["time"] >= pd.Timestamp(SINCE, tz="UTC")].reset_index(drop=True)
    n = len(df)
    print(f"[*] {SYMBOL} {TF}: {n} velas desde {SINCE}")
    print(f"[*] frames cada {STEP} velas -> ~{n // STEP} imagenes -> {OUT}")
    idx = 0
    for upto in range(STEP, n + 1, STEP):
        render_frame(df, upto, idx)
        idx += 1
    render_frame(df, n, idx)
    print(f"[*] Listo: {idx + 1} frames en {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fase F - Auditoria VISUAL (paso 1 de 3, sin modificar detectores).

Objetivo: demostrar que el motor "ve" las mismas estructuras que un trader ICT.
NO se evalua Profit Factor. NO se concluye si un detector esta mal.
Solo se dibuja, con rectangulos (zonas) y niveles, lo que los detectores
reales marcaron en velas reales de los 36 trades.

Salida:
  results/auditoria_visual/<trade_id>.png  (1 plot por trade)
  results/auditoria_visual/index.html       (galeria navegable)

Lectura honesta:
  - FVG / OB se dibujan como RECTANGULOS (zonas), no lineas.
  - BOS / CHOCH como niveles horizontales con etiqueta.
  - Sweep como punto en la mecha.
  - Premium/Discount: NO existe en el motor (tesis 20 lo marca pendiente) ->
    se senala como "no computado", no se inventa.
  - Entry / SL / TP: se dibujan si el backtest los dejo en el contexto; si no,
    se marca "no disponible" (no se inventa precio).
"""
from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ict_backtest.data_feed import load_tf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from ict_backtest.data_feed import build_features, load_frames

ROOT = Path(__file__).resolve().parent.parent
CTX_PATH = ROOT / "results" / "backtests" / "2026-07-18_6m_mtf" / "EURUSD" / "contexts.json"
OUT = ROOT / "results" / "auditoria_visual"
OUT.mkdir(parents=True, exist_ok=True)

WINDOW_BEFORE = 40
WINDOW_AFTER = 25


def load_contexts() -> list[dict]:
    return json.loads(CTX_PATH.read_text())


def make_plot(df: pd.DataFrame, ctx: dict, trade_idx: int) -> str | None:
    """Dibuja la ventana del trade con todas las estructuras detectadas.
    `df` ya es el M15 con features, recortado a la ventana del trade."""
    etime = pd.Timestamp(ctx["entry_time"])
    idxs = df.index[df["time"] == etime]
    if len(idxs) == 0:
        diffs = (df["time"] - etime).abs()
        i0 = int(diffs.idxmin())
    else:
        i0 = int(idxs[0])
    lo = max(0, i0 - WINDOW_BEFORE)
    hi = min(len(df), i0 + WINDOW_AFTER)
    sub = df.iloc[lo:hi].reset_index(drop=True)
    if len(sub) < 5:
        return None

    fig, ax = plt.subplots(figsize=(13, 6))
    # --- velas OHLC ---
    for j, r in sub.iterrows():
        color = "#26a69a" if r["close"] >= r["open"] else "#ef5350"
        ax.plot([j, j], [r["low"], r["high"]], color="black", lw=0.6)
        ax.plot([j - 0.3, j + 0.3], [r["open"], r["open"]], color=color, lw=1.2)
        ax.plot([j - 0.3, j + 0.3], [r["close"], r["close"]], color=color, lw=1.2)

    # --- FVG como RECTANGULO (zona) ---
    for j, r in sub.iterrows():
        if bool(r.get("fvg_bullish", False)):
            top = float(r["low"])  # low[i]
            bot = float(sub.iloc[j - 2]["high"]) if j - 2 >= 0 else top
            ax.add_patch(Rectangle((j - 0.4, bot), 0.8, top - bot,
                                   facecolor="#2196f3", alpha=0.28,
                                   edgecolor="#1565c0", lw=1.0))
            ax.text(j, top + (top - bot) * 0.1, "FVG", color="#1565c0", fontsize=7, ha="center")
        elif bool(r.get("fvg_bearish", False)):
            bot = float(r["high"])
            top = float(sub.iloc[j - 2]["low"]) if j - 2 >= 0 else bot
            ax.add_patch(Rectangle((j - 0.4, bot), 0.8, top - bot,
                                   facecolor="#fb8c00", alpha=0.28,
                                   edgecolor="#e65100", lw=1.0))
            ax.text(j, bot - (top - bot) * 0.1, "FVG", color="#e65100", fontsize=7, ha="center")

    # --- Order Block como RECTANGULO (zona) ---
    for j, r in sub.iterrows():
        if bool(r.get("ob_bullish", False)) or bool(r.get("ob_bearish", False)):
            top = float(r["ob_top"]) if pd.notna(r.get("ob_top")) else float(r["high"])
            bot = float(r["ob_bottom"]) if pd.notna(r.get("ob_bottom")) else float(r["low"])
            c = "#4caf50" if bool(r.get("ob_bullish", False)) else "#9c27b0"
            ax.add_patch(Rectangle((j - 0.4, bot), 0.8, top - bot,
                                   facecolor=c, alpha=0.30, edgecolor=c, lw=1.0))
            ax.text(j, (top + bot) / 2, "OB", color=c, fontsize=7, ha="center", va="center")

    # --- BOS niveles ---
    for j, r in sub.iterrows():
        if r.get("bos_dir", 0) != 0 and pd.notna(r.get("bos_level")):
            lvl = float(r["bos_level"])
            ax.hlines(lvl, j - 1, j + 1, color="#00bcd4", lw=1.4)
            ax.text(j + 1.2, lvl, f"BOS{'+' if r['bos_dir']>0 else '-'}",
                    color="#00bcd4", fontsize=7)

    # --- CHOCH niveles ---
    for j, r in sub.iterrows():
        if r.get("choch_dir", 0) != 0:
            lvl = float(r["close"])
            ax.hlines(lvl, j - 1, j + 1, color="#ffeb3b", lw=1.4)
            ax.text(j + 1.2, lvl, f"CHOCH{'+' if r['choch_dir']>0 else '-'}",
                    color="#fbc02d", fontsize=7)

    # --- Sweep (punto en mecha) ---
    for j, r in sub.iterrows():
        if bool(r.get("liquidity_sweep_up", False)):
            ax.plot(j, r["high"], "v", color="#d32f2f", markersize=7)
        if bool(r.get("liquidity_sweep_down", False)):
            ax.plot(j, r["low"], "^", color="#d32f2f", markersize=7)

    # --- Entry vertical + flecha direccion ---
    ej = sub.index[sub["time"] == etime]
    ej = int(ej[0]) if len(ej) else len(sub) // 2
    eprice = float(sub.iloc[ej]["close"])
    ax.axvline(ej, color="black", lw=1.0, ls="--")
    direction = int(ctx.get("direction", 0))
    ax.annotate("ENTRY", (ej, eprice),
                xytext=(ej, eprice),
                color="black", fontsize=8,
                arrowprops=dict(arrowstyle="->" if direction < 0 else "->",
                                color="black"))

    # --- Premium/Discount: honestamente no computado por el motor ---
    ax.text(0.01, 0.98,
            "Premium/Discount: NO computado por el motor (tesis 20 lo marca pendiente)",
            transform=ax.transAxes, fontsize=7, color="#757575",
            va="top", ha="left")

    ax.set_title(f"Trade {trade_idx+1} | {ctx['symbol']} | dir={direction} | "
                 f"phase_log={ctx.get('phase_log')}", fontsize=9)
    ax.set_xlabel("barra M15")
    ax.set_ylabel("precio")
    ax.set_xticks([])
    plt.tight_layout()

    out_png = OUT / f"trade_{trade_idx+1:02d}.png"
    fig.savefig(out_png, dpi=90)
    plt.close(fig)
    return out_png.name


def main() -> None:
    ctxs = load_contexts()

    gallery = []
    for i, ctx in enumerate(ctxs):
        etime = pd.Timestamp(ctx["entry_time"])
        # ventana corta alrededor del entry: solo M15, recortado antes de features
        start = etime - pd.Timedelta(minutes=15 * (WINDOW_BEFORE + 5))
        end = etime + pd.Timedelta(minutes=15 * (WINDOW_AFTER + 5))
        m15 = load_tf("EURUSD", "M15", start=start, end=end)
        if "time" in m15.columns:
            m15["time"] = pd.to_datetime(m15["time"])
        else:
            m15 = m15.reset_index()
            m15["time"] = pd.to_datetime(m15["time"]) if "time" in m15.columns else m15.index.to_series()
        name = make_plot(m15, ctx, i)
        if name:
            gallery.append((i + 1, name, ctx.get("direction"), ctx.get("phase_log")))

    # index.html
    html = ["<html><head><meta charset='utf-8'><title>Auditoria Visual</title>",
            "<style>body{font-family:monospace;background:#111;color:#ddd}"
            "table{border-collapse:collapse}td{padding:4px;border:1px solid #333}"
            "img{width:600px;border:1px solid #444}</style></head><body>",
            "<h2>Auditoria Visual - lo que el motor DETECTO (sin concluir)</h2>",
            "<p>FVG/OB = rectangulos (zonas). BOS/CHOCH = niveles. Sweep = punto. "
            "Premium/Discount NO computado. No se modifico ningun detector.</p>",
            "<table>"]
    for num, name, direction, phase in gallery:
        html.append(f"<tr><td>#{num}</td><td>dir={direction}</td>"
                    f"<td>{phase}</td><td><img src='{name}'></td></tr>")
    html.append("</table></body></html>")
    (OUT / "index.html").write_text("\n".join(html), encoding="utf-8")

    print(f"Generados {len(gallery)} plots en {OUT}")
    print(f"Galeria: {OUT / 'index.html'}")
    # NO abrimos navegador en headless; el usuario abre el HTML.


if __name__ == "__main__":
    main()

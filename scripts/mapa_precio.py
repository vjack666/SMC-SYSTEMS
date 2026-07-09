"""
Mapa visual del precio EURUSD — estilo TradingView, para Ruben (no para IA).

Dibuja 3 panels (D1 / H4 / M15) con velas REALES de MT5 y pinta las zonas
que ya detecta la rutina (OB, FVG, zona premium/discount, OTE). En M15 marca
ENTRADA / SL / TP del plan de trade. Explicaciones en espanol plano (dummies).

Reusa analyze_timeframe() de rutina_eurusd.py -> mismas zonas que la ficha.
Solo LEE los parquet y dibuja; no envia nada a ningun lado.

Uso:
  C:\\Python314\\python.exe scripts\\mapa_precio.py
  C:\\Python314\\python.exe scripts\\mapa_precio.py --symbol EURUSD --save
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana, solo archivo
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from rutina_eurusd import analyze_timeframe, compute_trade_plan, build_verdict  # noqa: E402
from detectors.liquidity import detect_liquidity  # noqa: E402
from detectors.killzones import detect_killzones  # noqa: E402
from detectors.gaps import detect_nwog_ndog  # noqa: E402
from detectors.fib import fib_levels  # noqa: E402
from detectors.fvg import detect_fvg  # noqa: E402

OUT_DIR = BASE / "docs" / "diario"
SYMBOL = "EURUSD"


def _candles(ax, df: pd.DataFrame, n: int = 80) -> None:
    """Dibuja velas verde bosque / rojo burdeos (estilo ICT limpio, fondo claro)."""
    d = df.iloc[-n:].reset_index(drop=True)
    up = "#1b5e3c"
    down = "#7a1f2b"
    for i, row in d.iterrows():
        color = up if row["close"] >= row["open"] else down
        # mecha
        ax.plot([i, i], [row["low"], row["high"]], color=color, lw=1.0, zorder=4)
        # cuerpo
        body_h = abs(row["close"] - row["open"])
        ax.add_patch(
            Rectangle((i - 0.3, min(row["open"], row["close"])), 0.6, max(body_h, 1e-6),
                      facecolor=color, edgecolor=color, lw=0.4, zorder=4)
        )
    ax.set_xlim(-1, len(d))
    ax.set_ylim(d["low"].min() * 0.9995, d["high"].max() * 1.0005)


def _zone_rect(ax, y0: float, y1: float, x0: float, x1: float, color: str, alpha: float, label: str) -> None:
    """Zona semitransparente (axhspan) — NO tapa velas. alpha fijo ~0.18."""
    ax.axhspan(y0, y1, xmin=x0, xmax=x1, facecolor=color, alpha=alpha, zorder=2)
    # etiqueta opaca al borde derecho
    ax.text(x1, y1, label, fontsize=7, color=color, alpha=1.0,
            va="bottom", ha="right", zorder=5)


def panel(ax, df, tf: str, info: dict, n: int = 80, show_plan: bool = False) -> None:
    # fondo claro + grid punteado (estilo ICT limpio)
    ax.set_facecolor("#f5f5f5")
    ax.grid(color="#e0e0e0", lw=0.6, ls=":", zorder=0)
    ax.set_axisbelow(True)

    _candles(ax, df, n)
    d = df.iloc[-n:].reset_index(drop=True)
    x1 = len(d) - 1

    # Killzones: banda vertical muy sutil por sesion
    if "kz" in df.columns:
        km = {"NY": "#9aa5b1", "LDN_OPEN": "#9aa5b1", "LDN_CLOSE": "#9aa5b1", "ASIA": "#9aa5b1"}
        for name in set(km):
            idxs = [i for i, k in enumerate(df["kz"].iloc[-n:]) if name in str(k)]
            for i in idxs:
                ax.axvspan(i - 0.5, i + 0.5, color=km[name], alpha=0.07, zorder=1)

    # Liquidez (BSL rojo / SSL naranja) — LINEA discontinua, NO rectangulo
    lo, hi = d["low"].min(), d["high"].max()
    if "bsl_price" in df.columns and df["bsl_price"].notna().any():
        last = df.dropna(subset=["bsl_price"]).iloc[-1]
        lvl = float(last["bsl_price"])
        if lo <= lvl <= hi:  # solo si esta en el rango visible
            ax.axhline(lvl, color="#c0392b", ls="--", lw=0.8, alpha=0.7, zorder=3)
            ax.text(x1, lvl, f"BSL {lvl:.5f}", fontsize=7, color="#c0392b", alpha=1.0,
                    va="bottom", ha="right", zorder=5)
    if "ssl_price" in df.columns and df["ssl_price"].notna().any():
        last = df.dropna(subset=["ssl_price"]).iloc[-1]
        lvl = float(last["ssl_price"])
        if lo <= lvl <= hi:
            ax.axhline(lvl, color="#e08e45", ls="--", lw=0.8, alpha=0.7, zorder=3)
            ax.text(x1, lvl, f"SSL {lvl:.5f}", fontsize=7, color="#e08e45", alpha=1.0,
                    va="bottom", ha="right", zorder=5)

    # NWOG/NDOG: cajas punteadas violeta suave
    gaps = detect_nwog_ndog(df)
    for g in gaps[-2:]:
        gi0 = df.index.get_loc(g["x0"]) if g["x0"] in df.index else 0
        ax.add_patch(Rectangle((gi0 - 0.5, g["bot"]), n, g["top"] - g["bot"],
                               fill=False, edgecolor="#8a7fbd", lw=1, ls=":",
                               zorder=2))

    # FVG (verde/rojo medio) — zona tenue
    try:
        fvg = detect_fvg(df.iloc[-max(n, 200):])
        for _, row in fvg.iterrows():
            if bool(row.get("fvg_active")):
                top = float(row.get("fvg_top", row["close"]))
                bot = float(row.get("fvg_bottom", row["close"]))
                col = "#2e7d4f" if row.get("fvg_type") != "bearish" else "#b23a48"
                _zone_rect(ax, bot, top, -1, x1, col, 0.18, "FVG")
                break
    except Exception:
        pass

    # zona premium/discount: linea 50% punteada (sin relleno)
    z0, z1 = info["zone_low"], info["zone_high"]
    mid = (z0 + z1) / 2
    ax.axhline(mid, color="#555555", lw=0.6, ls=":", alpha=0.6, zorder=3)
    ax.text(0.02, 0.97, "Premium / Discount",
            transform=ax.transAxes, va="top", ha="left", fontsize=7,
            color="#555555", alpha=1.0, zorder=5)
    # OB activo (verde medio)
    if info["ob_bottom"] is not None:
        col = "#2e7d4f" if info["ob_dir"] == "bullish" else "#b23a48"
        _zone_rect(ax, info["ob_bottom"], info["ob_top"], -1, x1, col, 0.18, "Order Block")

    # texto explicacion (dummies)
    ob_txt = f"OB: {info['ob_dir']} [{info['ob_bottom']:.5f}-{info['ob_top']:.5f}]" \
        if info["ob_bottom"] is not None else "OB: -"
    txt = (
        f"{tf}  | sesgo: {info['trend']}\n"
        f"zona: {info['zone']}\n"
        f"{ob_txt}\n"
        f"FVG: {info.get('fvg_state','-')}"
    )
    ax.text(0.02, 0.90, txt, transform=ax.transAxes, va="top", ha="left",
            fontsize=8, color="#2c3e50",
            bbox=dict(boxstyle="round", fc="#ffffff", ec="none", alpha=0.75), zorder=6)
    ax.set_ylabel(tf, fontsize=10, color="#2c3e50")
    ax.tick_params(colors="#555555")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color="#e0e0e0", lw=0.6, ls=":", zorder=0)


def save_tf_png(sym: str, tf: str, df: pd.DataFrame, info: dict, out_dir: Path) -> Path:
    """Genera UN PNG por temporalidad (estilo ICT limpio) con zonas ICT pintadas."""
    n = {"D1": 60, "H4": 80, "M15": 90}.get(tf, 80)
    fig, ax = plt.subplots(1, 1, figsize=(13, 6))
    fig.patch.set_facecolor("#f5f5f5")
    panel(ax, df, tf, info, n=n)

    # plan de trade solo en M15
    if tf == "M15":
        plan = compute_trade_plan(build_verdict(
            analyze_timeframe(pd.read_parquet(BASE / "data" / "raw" / f"{sym}_D1.parquet"), "D1"),
            analyze_timeframe(pd.read_parquet(BASE / "data" / "raw" / f"{sym}_H4.parquet"), "H4"),
            info), info)
        if plan is not None:
            ax.axhline(plan["entry"], color="#2c3e50", lw=1.0, label="ENTRADA", zorder=5)
            ax.axhline(plan["sl"], color="#7a1f2b", lw=0.8, ls="--", label="STOP LOSS", zorder=5)
            ax.axhline(plan["tp"], color="#1b5e3c", lw=0.8, ls="--", label="TAKE PROFIT", zorder=5)

    ax.set_title(f"{sym} {tf} — análisis ICT (datos reales MT5)",
                 color="#2c3e50", fontsize=11, fontweight="bold", loc="left")
    out = out_dir / f"{sym}_{tf}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def main() -> int:
    ap = __import__("argparse").ArgumentParser(description="Mapa visual EURUSD por timeframe")
    ap.add_argument("--symbol", default=SYMBOL)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    sym = args.symbol.upper()

    d1 = analyze_timeframe(pd.read_parquet(BASE / "data" / "raw" / f"{sym}_D1.parquet"), "D1")
    h4 = analyze_timeframe(pd.read_parquet(BASE / "data" / "raw" / f"{sym}_H4.parquet"), "H4")
    m15 = analyze_timeframe(pd.read_parquet(BASE / "data" / "raw" / f"{sym}_M15.parquet"), "M15")

    d1df = pd.read_parquet(BASE / "data" / "raw" / f"{sym}_D1.parquet")
    h4df = pd.read_parquet(BASE / "data" / "raw" / f"{sym}_H4.parquet")
    m15df = pd.read_parquet(BASE / "data" / "raw" / f"{sym}_M15.parquet")

    # Enriquecer con conceptos ICT (port LuxAlgo) — SOLO para pintar
    d1df = detect_killzones(detect_liquidity(d1df))
    h4df = detect_killzones(detect_liquidity(h4df))
    m15df = detect_killzones(detect_liquidity(m15df))

    out_dir = OUT_DIR if args.save else BASE / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    for tf, df, info in (("D1", d1df, d1), ("H4", h4df, h4), ("M15", m15df, m15)):
        p = save_tf_png(sym, tf, df, info, out_dir)
        print(f"[*] {tf} guardado en {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

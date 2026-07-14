"""scripts/plot_trade_structsl.py — Foto real de UN trade Turtle Soup (SL estructural).

Regenera las senales sobre EURUSD (M15 recortado a las ultimas N velas para
velocidad), simula el primer trade y plotea:
  - velas M15 (cuerpo + mecha)
  - la mecha del sweep (nivel sweep_low/sweep_high que ancla el SL)
  - entry, SL estructural (mecha +- buffer), TP en liquidez opuesta
No es un esquema: son datos reales del motor con el parche aplicado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.engine import (  # noqa: E402
    build_signals_from_frames, simulate_trade,
)
from ict_backtest.market_structure import detect_market_structure  # noqa: E402

SYMBOL = "EURUSD"
HTF, LTF = "H4", "M15"
NVELAS = 3000  # recorte para velocidad (no 7 anos)


def _slice(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.iloc[-n:].copy() if len(df) > n else df.copy()


def main() -> None:
    print(f"[1/4] Cargando {SYMBOL} {HTF}->{LTF} (recorte {NVELAS} velas M15) ...", flush=True)
    frames = load_frames(SYMBOL, (HTF, LTF, "D1"))
    frames = {tf: _slice(df, NVELAS if tf == LTF else len(df)) for tf, df in frames.items()}
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[LTF]
    htf_df = ms[HTF]
    print(f"      M15: {len(ltf_df)} velas", flush=True)

    print("[2/4] Generando senales (CT, tp-mode liquidity) ...", flush=True)
    signals = build_signals_from_frames(
        SYMBOL, frames, bias_by_tf={}, model="intradia", htf=HTF, ltf=LTF,
        counter_trend=True, tp_mode="liquidity", require_displacement=True,
    )
    print(f"      {len(signals)} senales", flush=True)
    if not signals:
        print("Sin senales en el recorte. Aumenta NVELAS.")
        return

    print("[3/4] Simulando primer trade ...", flush=True)
    sig = signals[0]
    trade, meta = simulate_trade(ltf_df, sig, max_hold_bars=16)
    print(f"      entry={sig.entry} dir={sig.direction} SL={sig.stop_loss} TP={sig.take_profit}", flush=True)
    print(f"      salida={meta['exit_reason']} pnl={trade.pnl_r if trade else None}", flush=True)

    # Indice de entrada en el df recortado (sig.time es el timestamp del trade)
    tgt = pd.Timestamp(sig.time)
    times = ltf_df["time"].values
    ei = int(np.argmin(np.abs(times - tgt.to_datetime64())))
    start = max(0, ei - 40)
    end = min(len(ltf_df), ei + 60)
    win = ltf_df.iloc[start:end]

    print("[4/4] Plot ...", flush=True)
    fig, ax = plt.subplots(figsize=(13, 6))
    for _, r in win.iterrows():
        color = "#26a69a" if r["close"] >= r["open"] else "#ef5350"
        ax.plot([r.name, r.name], [r["low"], r["high"]], color=color, lw=0.8, zorder=1)
        body_h = abs(r["close"] - r["open"])
        ax.add_patch(Rectangle((r.name - 0.4, min(r["open"], r["close"])), 0.8, max(body_h, 1e-6),
                               color=color, zorder=2))

    # Niveles
    ax.axhline(sig.entry, color="white", lw=1.0, ls="--", label=f"Entry {sig.entry:.5f}")
    ax.axhline(sig.stop_loss, color="#ff4d4d", lw=1.2, label=f"SL estructural {sig.stop_loss:.5f}")
    ax.axhline(sig.take_profit, color="#4dd0e1", lw=1.2, label=f"TP liquidez {sig.take_profit:.5f}")

    # Marca de entrada
    ax.scatter([ei], [sig.entry], color="yellow", s=90, zorder=5, marker="*", label="Entrada")

    # Mechas de sweep cercanas (donde se anclo el SL)
    sweep_col = "sweep_low" if sig.direction == 1 else "sweep_high"
    sw = win[sweep_col].dropna()
    for t, v in sw.items():
        ax.axhline(v, color="#ffb74d", lw=0.6, ls=":", alpha=0.7)
        ax.text(t, v, " sweep", color="#ffb74d", fontsize=7, va="bottom")

    ax.set_title(f"{SYMBOL} Turtle Soup (SL estructural) — {meta['exit_reason']} "
                 f"PNL={trade.pnl_r:+.2f}R" if trade else f"{SYMBOL} Turtle Soup")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylabel("Precio")
    out = ROOT / "docs" / "ict" / "logs" / f"trade_{SYMBOL}_structsl.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    print(f"=== Guardado: {out} ===", flush=True)


if __name__ == "__main__":
    main()

"""Grafico H1 EURUSD (ultimos ~7 dias) con la ultima estructura del motor.

Marca el ULTIMO BOS activo con una linea horizontal desde su nacimiento
(nivel del swing opuesto que se rompio) hasta la vela donde el precio lo
rompio (close cruza el nivel). Tambien marca el CHOCH activo mas reciente.

Uso engine.bos.detect_market_structure (mismo motor del backtest/HTF).
Solo lectura: no modifica nada.
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from engine.bos import detect_market_structure, StructureConfig


def load_h1(symbol: str, days: int = 7) -> pd.DataFrame:
    df = pd.read_parquet(f"data/raw/{symbol}_H1.parquet")
    df = df.sort_values("time").reset_index(drop=True)
    cutoff = df["time"].max() - pd.Timedelta(days=days)
    return df[df["time"] >= cutoff].reset_index(drop=True)


def main():
    symbol = "EURUSD"
    days = 30
    df = load_h1(symbol, days)
    print(f"{symbol} H1: {len(df)} velas, {df['time'].min()} -> {df['time'].max()}")

    res = detect_market_structure(df, StructureConfig())
    fr = res.frame

    # --- sesgo por estructura del frame H1 (misma logica del motor) ---
    from engine.plan import _bias_from_frame
    bias = _bias_from_frame(fr, fr["time"].iloc[-1])

    # --- extraer el BOS activo "de fondo" (el que define la tendencia) ---
    # Criterio del trader: el BOS de la direccion del sesgo (alcista si H1
    # BULLISH) mas antiguo que siga vivo. Si no hay alcista, el bajista mas
    # antiguo. Marcamos su nacimiento (swing opuesto) y su ruptura (close cruza).
    bos_events = fr[(fr["bos_dir"] != 0) & (fr["bos_status"] == "active")]
    if len(bos_events) == 0:
        print("No hay BOS activo en la ventana.")
        return
    bias_dir = 1 if bias == "BULLISH" else (-1 if bias == "BEARISH" else 0)
    cand = bos_events[bos_events["bos_dir"] == bias_dir] if bias_dir != 0 else bos_events
    if len(cand) == 0:
        cand = bos_events
    # el de mayor recorrido: el mas antiguo por indice de nacimiento
    chosen = None
    best_birth = None
    for idx, row in cand.iterrows():
        lvl = float(row["bos_level"])
        bm = (fr["bos_level"] == lvl) & (fr.index <= idx)
        birth = int(fr.loc[bm].index[0]) if bm.any() else int(idx)
        if best_birth is None or birth < best_birth:
            best_birth = birth
            chosen = (int(idx), int(row["bos_dir"]), lvl, birth)
    bos_idx, bos_dir, bos_level, _ = chosen
    # nacimiento temporal = la vela del swing opuesto que el BOS rompio
    # (una vel antes del evento BOS en el frame anotado).
    birth_idx = max(0, bos_idx - 1)

    # ruptura: la vela del evento BOS (close ya cruzo el nivel).
    break_idx = bos_idx

    # --- CHOCH activo mas reciente (marca del trader) ---
    ch = fr[(fr["choch_dir"] != 0) & (fr["choch_status"] == "active")]
    ch_idx = int(ch.index[-1]) if len(ch) else None
    ch_dir = int(ch.iloc[-1]["choch_dir"]) if ch_idx is not None else 0
    ch_level = (float(fr.iloc[ch_idx]["choch_proj_level"])
                if (ch_idx is not None and not pd.isna(fr.iloc[ch_idx]["choch_proj_level"]))
                else np.nan)

    print(f"Bias H1 (estructura): {bias}")
    print(f"BOS dir={bos_dir} nivel={bos_level:.5f} nace@{fr.iloc[birth_idx]['time']} "
          f"rompe@{fr.iloc[break_idx]['time']}")

    # --- plot ---
    fig, ax = plt.subplots(figsize=(15, 7))
    x = np.arange(len(df))
    up = df["close"] >= df["open"]
    ax.vlines(x[up], df["low"][up], df["high"][up], color="#26a69a", lw=0.7)
    ax.vlines(x[~up], df["low"][~up], df["high"][~up], color="#ef5350", lw=0.7)
    ax.scatter(x[up], df["open"][up], color="#26a69a", s=3)
    ax.scatter(x[~up], df["open"][~up], color="#ef5350", s=3)

    # linea horizontal del BOS: desde nacimiento hasta el FIN de la ventana
    bx0, bx1 = birth_idx, len(df) - 1
    col = "#00e5ff" if bos_dir > 0 else "#ff9100"
    ax.hlines(bos_level, bx0, bx1, color=col, lw=1.6,
              label=f"BOS {'ALC' if bos_dir > 0 else 'BAJ'} nivel {bos_level:.5f}")
    ax.scatter([bx0], [bos_level], color=col, marker="D", s=45, zorder=5,
               label="nacimiento (swing opuesto)")
    ax.scatter([break_idx], [bos_level], color=col, marker="*", s=200, zorder=5,
               label="ruptura (close cruza)")

    # CHOCH activo
    if ch_idx is not None:
        ccol = "#76ff03" if ch_dir > 0 else "#ff1744"
        ax.hlines(ch_level, ch_idx, len(df) - 1, color=ccol, lw=1.2, ls="--",
                  label=f"CHOCH {'ALC' if ch_dir > 0 else 'BAJ'} {ch_level:.5f}")

    ax.set_title(f"{symbol} H1 — ultimos {days} dias | Bias {bias} | "
                 f"BOS {'alcista' if bos_dir > 0 else 'bajista'} nace {fr.iloc[birth_idx]['time']:%m-%d} "
                 f"rompe {fr.iloc[break_idx]['time']:%m-%d %H:%M}", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %Hh"))
    fig.autofmt_xdate()

    out = "results/h1_bos_marcado.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"Grafico guardado: {out}")


if __name__ == "__main__":
    main()

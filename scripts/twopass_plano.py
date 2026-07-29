"""Dibuja un plano de trading detallado: precios M15, señales M15 y confirmaciones M5."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta

from ict_backtest.data_feed import build_features, build_objects
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.event_engine import run_semantic
from ict_backtest.sequence import SequenceConfig

SYMBOL = "EURUSD"
RAW = Path("data/raw")

# ---------------------------
# Cargar datos últimos 30 días
# ---------------------------
m15_raw = pd.read_parquet(RAW / f"{SYMBOL}_M15.parquet")
m5_raw = pd.read_parquet(RAW / f"{SYMBOL}_M5.parquet")
m15_raw["time"] = pd.to_datetime(m15_raw["time"], utc=True)
m5_raw["time"] = pd.to_datetime(m5_raw["time"], utc=True)
cut = m15_raw["time"].max() - pd.Timedelta(days=30)
m15 = m15_raw[m15_raw["time"] >= cut].reset_index(drop=True)
m5 = m5_raw[m5_raw["time"] >= cut].reset_index(drop=True)

m15_f = build_features(m15)
h4_f = build_features(m5)

def htf_fn(i):
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False}

# ---------------------------
# Ejecutar análisis completo
# ---------------------------
sigs = run_semantic(
    m15_f,
    htf_fn,
    SequenceConfig(),
    ltf_tf="M15",
    max_hold=200,
    ltf_df=m15_f,
    est_htf_ctx_fn=None,
    exec_df=m5,
    exec_tf="M5",
    price_tolerance_pips=20,
)

# Filtrar señales con alguna confirmación M5
sigs_with_conf = [s for s in sigs if s.get("exec_m5_score", 0) > 0]
print(f"Señales M15 totales: {len(sigs)}")
print(f"Con confirmación M5: {len(sigs_with_conf)}")

# ---------------------------
# Helper: convertir a DataFrame para plots
# ---------------------------
sig_df = pd.DataFrame(sigs)
if "bar_index" in sig_df.columns:
    sig_df = sig_df.dropna(subset=["bar_index"])
    sig_df["bar_index"] = sig_df["bar_index"].astype(int)

# ---------------------------
# Plot: estilo "plano de trading"
# ---------------------------
fig, axes = plt.subplots(
    2, 1, figsize=(18, 11), dpi=140,
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
)
ax_price = axes[0]
ax_vol = axes[1]

# Eje X en tiempo
times = mdates.date2num(m15["time"])

# --- Velas japonesas ---
width = 0.006 * (times[1] - times[0]) if len(times) > 1 else 0.0003
for i, row in m15.iterrows():
    t = mdates.date2num(row["time"])
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    color = "#26a69a" if c >= o else "#ef5350"
    ax_price.plot([t, t], [l, h], color=color, linewidth=0.7, zorder=1)
    body_bottom = min(o, c)
    body_height = abs(c - o) if abs(c - o) > 0.00001 else 0.00001
    rect = Rectangle((t - width / 2, body_bottom), width, body_height,
                     facecolor=color, edgecolor=color, zorder=2)
    ax_price.add_patch(rect)

# --- Línea de precio de cierre (media móvil visual) ---
ax_price.plot(times, m15["close"].values, color="#1e88e5", linewidth=0.9,
             alpha=0.5, zorder=1, label="Close M15")

# --- Zonas M15 (BOS/FVG) ---
for _, sig in sig_df.iterrows():
    bar_i = int(sig["bar_index"])
    if bar_i < 0 or bar_i >= len(m15):
        continue
    t_sig = mdates.date2num(m15.iloc[bar_i]["time"])
    zh, zl = sig.get("zone_high", 0), sig.get("zone_low", 0)
    if zh <= 0 or zl <= 0:
        continue
    score = sig.get("exec_m5_score", 0)
    alpha = 0.15 + min(score * 0.08, 0.45)
    color_zone = "#66bb6a" if score >= 5 else ("#ffa726" if score >= 2 else "#ef5350")
    ax_price.axhspan(zl, zh, xmin=t_sig - 0.02, xmax=t_sig + 0.08,
                     color=color_zone, alpha=alpha, zorder=0)
    ax_price.annotate(
        f"s={score}",
        xy=(t_sig, zh),
        xytext=(t_sig, zh + 0.0008),
        fontsize=6,
        color=color_zone,
        ha="center",
        rotation=60,
    )

# --- Puntos de entrada sugeridos (score alto) ---
high_score = [s for s in sigs_with_conf if s.get("exec_m5_score", 0) >= 5]
med_score = [s for s in sigs_with_conf if 2 <= s.get("exec_m5_score", 0) <= 4]
low_score = [s for s in sigs_with_conf if s.get("exec_m5_score", 0) == 1]

for group, color, size in [
    (high_score, "#00e676", 90),
    (med_score, "#ffa726", 60),
    (low_score, "#ef5350", 40),
]:
    xs, ys = [], []
    for sig in group:
        bar_i = int(sig["bar_index"])
        if bar_i < 0 or bar_i >= len(m15):
            continue
        xs.append(mdates.date2num(m15.iloc[bar_i]["time"]))
        ys.append(sig.get("zone_high", 0) + 0.0005)
    if xs:
        ax_price.scatter(xs, ys, c=color, s=size, marker="^",
                         edgecolors="white", linewidths=0.5, zorder=5)

# --- 5 cm de margen derecho (aprox 0.07 en escala fech = ~5 cm en 90 días) ---
last_time = times[-1]
margin = (times[-1] - times[0]) * 0.07
ax_price.set_xlim(times[0], last_time + margin)

# Formato eje X
ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%b %d", tz=matplotlib.rcParams["timezone"]))
ax_price.xaxis.set_major_locator(mdates.AutoDateLocator())
plt.setp(ax_price.get_xticklabels(), rotation=30, ha="right", fontsize=8)

# Eje Y precio
ax_price.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.5f"))
ax_price.set_ylabel("Precio (EURUSD)", fontsize=10)
ax_price.set_title(f"Plano de Trading: {SYMBOL} M15 | Two-Pass M5 Score | últ. 30 días",
                   fontsize=14, fontweight="bold", pad=12)
ax_price.grid(True, which="major", color="#444", alpha=0.3, linewidth=0.5)
ax_price.grid(True, which="minor", color="#666", alpha=0.15, linewidth=0.3)

# --- Volumen (usar tick volume si existe, si no, rango como proxy) ---
vol_series = m15.get("tick_volume", m15.get("volume", pd.Series([0] * len(m15))))
ax_vol.bar(times, vol_series.values, width=width * 1.2, color="#1e88e5", alpha=0.4)
ax_vol.set_ylabel("Volumen", fontsize=9)
ax_vol.grid(True, which="major", color="#444", alpha=0.2)

# --- Leyendas ---
legend_elements = [
    matplotlib.lines.Line2D([0], [0], color="#00e676", marker="^", markersize=8,
                            label="Score M5 ≥5 (high)", linestyle="None", markerfacecolor="#00e676"),
    matplotlib.lines.Line2D([0], [0], color="#ffa726", marker="^", markersize=8,
                            label="Score M5 2-4 (med)", linestyle="None", markerfacecolor="#ffa726"),
    matplotlib.lines.Line2D([0], [0], color="#ef5350", marker="^", markersize=8,
                            label="Score M5 =1 (low)", linestyle="None", markerfacecolor="#ef5350"),
    Rectangle((0, 0), 1, 1, facecolor="#66bb6a", alpha=0.4, label="Zona M5 score≥5"),
    Rectangle((0, 0), 1, 1, facecolor="#ffa726", alpha=0.4, label="Zona M5 score 2-4"),
    Rectangle((0, 0), 1, 1, facecolor="#ef5350", alpha=0.4, label="Zona M5 score 1"),
]
ax_price.legend(handles=legend_elements, loc="upper left", fontsize=8,
                framealpha=0.8, edgecolor="#666")

# Anotación de métricas en el gráfico
total_sigs = len(sigs)
high_n = len(high_score)
med_n = len(med_score)
low_n = len(low_score)
textstr = (
    f"Total señales M15: {total_sigs}\n"
    f"Con confirmación M5: {len(sigs_with_conf)}\n"
    f"Score altos (≥5): {high_n}\n"
    f"Score medios (2-4): {med_n}\n"
    f"Score bajos (=1): {low_n}"
)
ax_price.text(
    0.98, 0.97, textstr,
    transform=ax_price.transAxes,
    fontsize=9, verticalalignment="top", horizontalalignment="right",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e1e1e", alpha=0.8, edgecolor="#666"),
    color="white",
)

# Guardar
out = Path("scripts/twopass_plano.png")
plt.savefig(out, dpi=140, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print(f"Plano guardado en: {out}")

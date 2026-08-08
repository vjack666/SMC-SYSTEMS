"""scripts/build_operational_report.py — Informe operacional estilo clase YouTube.

Lee results/funnel_authority_filter.json (enriquecido por audit_funnel_authority_filter.py)
con los 25 setups reales (entry/sl/tp/authority) y produce:
  - docs/operational_report_EURUSD.md  (analisis D1/H4/H1/M15/M5 + precio referencia)
  - results/operational_report_EURUSD.png (funil + autoridad + niveles por setup)

NOTA HONESTA: el motor opera sobre datos HISTORICOS (no hay feed en vivo). Los setups
son los 25 reales de la auditoria (A), no "senales de hoy en vivo".
"""
from __future__ import annotations

import json
import os

import pandas as pd

from engine.bias.narrative import compute_htf_bias
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.data_feed import load_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
DOCS = os.path.join(ROOT, "docs")

TF_CHAIN = ("D1", "H4", "H1", "M15", "M5")


def tf_state_at(frame: pd.DataFrame, t, lookback: int) -> dict:
    """Estado de UN tf en el timestamp t (geometria pura, sin look-ahead)."""
    ft = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    mask = ft <= t
    if not mask.any():
        return {"bars": 0}
    i = int(mask.sum() - 1)
    win = frame.iloc[: i + 1].reset_index(drop=True)
    if len(win) < lookback:
        return {"bars": len(win)}
    return {
        "bars": len(win),
        "close": float(win["close"].iloc[-1]),
        "high": float(win["high"].iloc[-1]),
        "low": float(win["low"].iloc[-1]),
        "last_high": float(win["high"].iloc[-lookback:].max()),
        "last_low": float(win["low"].iloc[-lookback:].min()),
    }


def main() -> None:
    with open(os.path.join(RESULTS, "funnel_authority_filter.json")) as f:
        data = json.load(f)
    det = data["detalle"]
    ms = load_frames("EURUSD", timeframes=TF_CHAIN)
    frames = {tf: ms[tf] for tf in TF_CHAIN}

    # Precomputar estructura M15 UNA vez (gate duro) para contar CHOCH por setup
    m15_full = ms["M15"].copy()
    m15_t = pd.to_datetime(m15_full["time"], utc=True, errors="coerce")
    fr15_full = detect_market_structure(m15_full, StructureConfig(exp012_choch=True)).frame
    # Sesgo HTF: cache por indice H1 (los setups estan ordenados en el tiempo)
    _bias_cache: dict = {}

    rows = []
    for entry in det:
        ts_str = entry[0]
        lvl = entry[1]
        conf = entry[2] if len(entry) > 2 else None
        tier = entry[3] if len(entry) > 3 else None
        price_entry = entry[5] if len(entry) > 5 else None
        sl = entry[6] if len(entry) > 6 else None
        tp = entry[7] if len(entry) > 7 else None
        t = pd.Timestamp(ts_str)

        # Sesgo HTF canonico (D1/H4/H1) en el momento del setup — cache por H1 idx
        d1_idx = int((pd.to_datetime(frames["D1"]["time"], utc=True, errors="coerce") <= t).sum())
        h4_idx = int((pd.to_datetime(frames["H4"]["time"], utc=True, errors="coerce") <= t).sum())
        h1_idx = int((pd.to_datetime(frames["H1"]["time"], utc=True, errors="coerce") <= t).sum())
        key = (d1_idx, h4_idx, h1_idx)
        if key not in _bias_cache:
            d1 = frames["D1"].iloc[:d1_idx]
            h4 = frames["H4"].iloc[:h4_idx]
            h1 = frames["H1"].iloc[:h1_idx]
            _bias_cache[key] = compute_htf_bias(d1, h4, h1) if len(d1) > 2 and len(h4) > 2 and len(h1) > 2 else None
        bias = _bias_cache[key]

        # Estructura M15 y M5 en el setup
        m15_mask = m15_t <= t
        m15_i = int(m15_mask.sum() - 1) if m15_mask.any() else 0
        m15_st = tf_state_at(m15_full, t, 10)
        m5_st = tf_state_at(frames["M5"], t, 10)
        m15_choch = int((fr15_full.iloc[:m15_i + 1]["choch_dir"] != 0).sum()) if m15_i > 0 else 0

        rows.append({
            "ts": ts_str, "lvl": lvl, "conf": conf, "tier": tier,
            "entry": price_entry, "sl": sl, "tp": tp,
            "bias_dir": bias.direction if bias else "n/a",
            "bias_aligned": bool(bias.aligned) if bias else False,
            "m15_close": m15_st.get("close"), "m15_hl": (m15_st.get("last_high"), m15_st.get("last_low")),
            "m5_close": m5_st.get("close"),
            "m15_choch_censurado": m15_choch,
        })

    # --- Markdown ---
    n = len(rows)
    alta = sum(1 for r in rows if r["lvl"] == "Alta")
    media = sum(1 for r in rows if r["lvl"] == "Media")
    baja = sum(1 for r in rows if r["lvl"] == "Baja")
    aligned = sum(1 for r in rows if r["bias_aligned"])

    md = []
    md.append("# 📚 INFORME PARA NOVATOS — Cómo el motor lee el EURUSD\n")
    md.append("")
    md.append("> 💡 **LEE ESTO PRIMERO:** este informe NO es señal de 'compra ahora'. \n")
    md.append("> El motor trabaja con datos del pasado (una auditoría), no tiene conexión \n")
    md.append("> en vivo. Lo que ves abajo son ejemplos REALES de cómo el motor encontró \n")
    md.append("> oportunidades en el mes pasado, para que aprendas la lógica. Es como \n")
    md.append("> ver una clase grabada de YouTube, no operar en directo.\n")
    md.append("")
    md.append(f"**De qué trata:** estudié {n} oportunidades reales en EURUSD. "
              f"Abajo te explico cada una en lenguaje simple.\n")
    md.append("")
    md.append("## 1. La idea en una frase\n")
    md.append("")
    md.append("El motor mira el mercado como quien mira un edificio desde lejos para cerca:")
    md.append("")
    md.append("- 🏢 **D1 / H4 / H1 (los pisos altos)** = ¿Hacia dónde va el mercado en general? "
              "(arriba = alcista, abajo = bajista). Esto es el **SESGO**.")
    md.append("- 🚪 **M15 (la puerta)** = ¿En qué punto exacto el precio rompió algo importante? "
              "Ahí está la **ESTRUCTURA**.")
    md.append("- 🔑 **M5 (la cerradura)** = ¿Dónde tocó el precio el nivel para entrar? "
              "Esa es la **EJECUCIÓN**.")
    md.append("")
    md.append("Si los tres pisos dicen 'sube', el motor solo busca entrar comprando. "
              "Si dicen 'baja', solo busca entrar vendiendo. Simple.\n")
    md.append("")
    md.append("## 2. ¿El mercado está de acuerdo con el motor?\n")
    md.append("")
    md.append(f"De las {n} oportunidades, solo **{aligned}** estaban alineadas con la "
              f"dirección general del mercado ({100*aligned/max(n,1):.0f}%). "
              "Esto es bueno: significa que el motor es **selectivo** y no entra a lo loco. "
              "Mejor pocas buenas que muchas malas.\n")
    md.append("")
    md.append(f"De esas {n}, la calidad fue:")
    md.append(f"- 🟢 **Alta (muy buena):** {alta} oportunidades ({100*alta/max(n,1):.0f}%)")
    md.append(f"- 🟠 **Media (buena):** {media} oportunidades ({100*media/max(n,1):.0f}%)")
    md.append(f"- 🔴 **Baja (débil):** {baja} oportunidades ({100*baja/max(n,1):.0f}%)")
    pct_am = 100*(alta+media)/max(n,1)
    md.append(f"**{pct_am:.0f}% de las oportunidades eran de calidad Alta o Media.** "
              "El filtro descarta las débiles para no operar basura.\n")
    md.append("")
    md.append("## 3. El filtro (cuántas 'ideas' sobreviven)\n")
    md.append("")
    md.append("El motor ve muchas cosas, pero la mayoría no sirven. Imagina un embudo:")
    f = data.get("funnel", {})
    md.append(f"- 💧 Vio **{f.get('SWEEP')}** 'barridas de liquidez' (el precio va a cazar "
              "stop losses de otros).")
    md.append(f"- ✨ De esas, **{f.get('DISPLACE')}** tuvieron un movimiento real fuerte.")
    md.append(f"- 🔨 De esas, **{f.get('BOS')}** rompieron la estructura (el mercado cambió de dirección).")
    md.append(f"- ✅ Al final, **{f.get('ENTRY')}** fueron setups completos, y el filtro de "
              f"calidad dejó **{n}** buenas.\n")
    md.append("")
    md.append(f"O sea: de {f.get('SWEEP')} ideas iniciales, solo quedaron {n} dignas de considerar. "
              "El filtro quita el ruido.\n")
    md.append("")
    md.append("## 4. Las oportunidades reales (dónde mirar el precio)\n")
    md.append("")
    md.append("Cada fila es una oportunidad que el motor encontró. Los números son **precios**:")
    md.append("- **Entry** = dónde el motor sugería entrar.")
    md.append("- **SL (stop loss)** = dónde poner el límite de pérdida (si te equivocas, sales ahí).")
    md.append("- **TP (take profit)** = dónde cobrar el beneficio.")
    md.append("")
    md.append("| # | Cuándo (UTC) | Calidad | Dirección | Entrar en | SL | TP |")
    md.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        e = f"{r['entry']:.5f}" if r["entry"] else "n/a"
        s = f"{r['sl']:.5f}" if r["sl"] else "n/a"
        p = f"{r['tp']:.5f}" if r["tp"] else "n/a"
        md.append(f"| {i} | {r['ts'][:16]} | {r['lvl']} | {r['bias_dir']} | {e} | {s} | {p} |")
    md.append("")
    md.append("📌 **Cómo leerlo:** si la fila dice 'BULLISH' (alcista), tú buscarías COMPRAR "
              "cerca del precio 'Entrar en', pondrías el SL un poco debajo, y el TP un poco arriba. "
              "Si dice 'BEARISH' (bajista), al revés: vender, SL arriba, TP abajo.\n")
    md.append("")
    md.append("## 5. ¿Por qué no te digo 'opera esto hoy'?\n")
    md.append("")
    md.append("- Este motor analiza el **pasado**, no el momento actual. No está conectado a "
              "una plataforma en vivo (como MT5 o Quotex) que le dé el precio de ahora mismo.")
    md.append("- Los datos que usé terminan en agosto pasado. No sé qué pasó hoy.")
    md.append("- Para tener señales de 'hoy', habría que conectar el motor a una fuente en vivo "
              "y que mirara el mercado vela por vela. Eso es otro trabajo.")
    md.append("- Lo que te di es la **enseñanza**: cómo piensa el motor y dónde miraría el precio. "
              "Con eso ya puedes empezar a entender el método.\n")
    md.append("")
    md.append("## 6. La gráfica (para verlo de un vistazo)\n")
    md.append("")
    md.append("![informe operacional](../results/operational_report_EURUSD.png)\n")
    md.append("")
    md.append("**Qué significa cada dibujo:**")
    md.append("- 📊 **Izquierda:** el embudo (cuántas ideas se descartan hasta quedar pocas buenas).")
    md.append("- 🥧 **Centro:** qué porcentaje eran de calidad Alta / Media / Baja.")
    md.append("- 📈 **Derecha:** los precios de entrada (verde), pérdida (rojo) y ganancia (azul) "
              "de cada oportunidad, una al lado de otra.\n")
    md.append("")
    md.append("---")
    md.append("💻 Generado por scripts/build_operational_report.py · datos: results/funnel_authority_filter.json")

    out_md = os.path.join(DOCS, "operational_report_EURUSD.md")
    with open(out_md, "w", encoding="utf-8") as _fh:
        _fh.write("\n".join(md))
    print(f"[report] markdown -> {out_md} ({n} setups)")

    # --- Gráfica ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    # (a) Funil
    ax = axes[0]
    fk = ["SWEEP", "DISPLACE", "BOS", "ENTRY"]
    fv = [f.get(k, 0) for k in fk]
    ax.bar(fk, fv, color=["#888", "#bbb", "#4a90d9", "#2ecc71"])
    ax.set_title("Funil del motor (supervivencia)")
    for i, v in enumerate(fv):
        ax.text(i, v + 1, str(v), ha="center")
    # (b) Autoridad
    ax = axes[1]
    ax.pie([alta, media, baja], labels=[f"Alta {alta}", f"Media {media}", f"Baja {baja}"],
           colors=["#2ecc71", "#f39c12", "#e74c3c"], autopct="%1.0f%%")
    ax.set_title("Autoridad de los setups (filtro POI)")
    # (c) Niveles entry/sl/tp
    ax = axes[2]
    xs = list(range(1, n + 1))
    es = [r["entry"] for r in rows if r["entry"]]
    sls = [r["sl"] for r in rows if r["sl"]]
    tps = [r["tp"] for r in rows if r["tp"]]
    ax.plot(xs, es, "o-", label="Entry", color="#2ecc71")
    ax.plot(xs, sls, "x--", label="SL", color="#e74c3c")
    ax.plot(xs, tps, "s--", label="TP", color="#3498db")
    ax.set_title("Precio de referencia por setup")
    ax.set_xlabel("setup #")
    ax.legend()
    plt.tight_layout()
    out_png = os.path.join(RESULTS, "operational_report_EURUSD.png")
    plt.savefig(out_png, dpi=110)
    print(f"[report] grafica -> {out_png}")

    print(f"[report] listo. setups={n} alineados={aligned}")


if __name__ == "__main__":
    main()

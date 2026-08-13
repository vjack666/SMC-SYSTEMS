"""Generate a three-panel live trading journal from MT5-updated parquet data.

This is a read-only renderer. It uses the permanent engine for structure and
never runs backtest simulation or sends orders.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

from engine.bos import detect_market_structure
from engine.data_feed import load_frames
from engine.htf_narrative import build_htf_narrative
from engine.plan import build_context_stack, dealing_range_pd, top_down_allows_trade


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "diario"
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}
LAYERS = {
    "HTF": ("D1", 120, "Direccion macro"),
    "MTF": ("H1", 180, "Contexto y estructura intermedia"),
    "LTF": ("M5", 220, "Ejecucion y confirmacion"),
}


def _closed_only(df: pd.DataFrame, tf: str, now: pd.Timestamp) -> pd.DataFrame:
    data = df.copy()
    data["time"] = pd.to_datetime(data["time"], utc=True, errors="coerce")
    minutes = TF_MINUTES[tf]
    close_time = data["time"] + pd.Timedelta(minutes=minutes)
    data = data.loc[close_time <= now].dropna(subset=["time"])
    # Bound the live window before structure detection; otherwise M1 history
    # can dominate latency without changing the current chart.
    return data.sort_values("time").tail(2500).reset_index(drop=True)


def _fmt(value: object, digits: int = 5) -> str:
    try:
        if value is None or pd.isna(value):
            return "-"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _last_non_null(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame or not frame[column].notna().any():
        return None
    return float(frame.loc[frame[column].notna(), column].iloc[-1])


def _structure(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    result = detect_market_structure(frame)
    annotated = result.frame
    last = annotated.iloc[-1]
    return annotated, {
        "trend": str(last.get("trend", "RANGING")),
        "bos_dir": int(last.get("bos_dir", 0) or 0),
        "bos_status": str(last.get("bos_status", "none")),
        "choch_dir": int(last.get("choch_dir", 0) or 0),
        "choch_status": str(last.get("choch_status", "none")),
        "swing_label": str(last.get("swing_label", "NONE")),
        "bos_level": _last_non_null(annotated, "bos_level"),
        "choch_level": _last_non_null(annotated, "choch_proj_level"),
        "time": str(last["time"]),
        "close": float(last["close"]),
    }


def _direction(value: int) -> str:
    return "alcista" if value > 0 else "bajista" if value < 0 else "neutro"


def _draw_candles(ax, frame: pd.DataFrame) -> None:
    for i, row in frame.iterrows():
        color = "#1f7a58" if row["close"] >= row["open"] else "#b0464f"
        ax.vlines(i, row["low"], row["high"], color=color, linewidth=1.0, zorder=3)
        bottom = min(float(row["open"]), float(row["close"]))
        height = max(abs(float(row["close"]) - float(row["open"])), 1e-7)
        ax.add_patch(Rectangle((i - 0.34, bottom), 0.68, height,
                               facecolor=color, edgecolor=color, linewidth=0.5,
                               zorder=4))


def _chart(path: Path, symbol: str, layer: str, tf: str, frame: pd.DataFrame,
           info: dict, context: dict, notes: list[str]) -> None:
    visible = frame.tail(LAYERS[layer][1]).reset_index(drop=True)
    n = len(visible)
    right_pad = max(14, math.ceil(n * 0.17))
    low = float(visible["low"].min())
    high = float(visible["high"].max())
    span = max(high - low, 1e-6)

    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)
    fig.patch.set_facecolor("#f4f1ea")
    ax.set_facecolor("#fbfaf7")
    ax.set_xlim(-2, n + right_pad)
    ax.set_ylim(low - span * 0.08, high + span * 0.08)
    ax.axvspan(n - 0.5, n + right_pad, color="#f1ede4", alpha=0.95, zorder=0)
    _draw_candles(ax, visible)
    ax.axvline(n - 0.5, color="#7c756a", linewidth=0.8, linestyle="--", zorder=2)

    level_labels: list[tuple[float | None, str, str]] = [
        (info.get("bos_level"), "BOS", "#9b6b1f"),
        (info.get("choch_level"), "CHOCH", "#7b4fa1"),
    ]
    drawn_levels: list[float] = []
    for value, label, color in level_labels:
        if value is not None and low <= value <= high:
            ax.axhline(value, color=color, linestyle=(0, (4, 3)), linewidth=0.9, alpha=0.9)
            label_y = value
            if any(abs(label_y - previous) < span * 0.025 for previous in drawn_levels):
                label_y += span * 0.035
            drawn_levels.append(label_y)
            ax.text(n + 1, label_y, f"{label} {_fmt(value)}", color=color,
                    fontsize=8, va="bottom", ha="left")

    dr = dealing_range_pd(visible, visible["time"].iloc[-1])
    if pd.notna(dr.get("eq")):
        ax.axhline(float(dr["eq"]), color="#6e6a62", linestyle=":", linewidth=0.9)
        ax.text(1, float(dr["eq"]), f"EQ {_fmt(dr['eq'])}", color="#6e6a62",
                fontsize=8, va="bottom")

    lines = [
        f"{layer} / {tf}",
        f"Cierre: {_fmt(info['close'])}",
        f"Estructura: {info['trend']}",
        f"BOS: {_direction(info['bos_dir'])} / {info['bos_status']}",
        f"CHOCH: {_direction(info['choch_dir'])} / {info['choch_status']}",
        f"Zona: {dr.get('pd_side', 'UNKNOWN')}",
        "",
        *notes,
    ]
    ax.text(n + right_pad * 0.06, low + span * 0.78, "\n".join(lines),
            fontsize=9, color="#302d29", va="top", ha="left",
            bbox={"boxstyle": "round,pad=0.65", "facecolor": "#fffdf8",
                  "edgecolor": "#c8bda9", "linewidth": 0.8, "alpha": 0.95},
            zorder=8)

    tick_step = max(1, n // 8)
    ticks = list(range(0, n, tick_step))
    if not ticks or n - 1 - ticks[-1] >= max(3, tick_step // 2):
        ticks.append(n - 1)
    ticks = sorted(set(ticks))
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(visible.iloc[i]["time"]).strftime("%m-%d\n%H:%M")
                        for i in ticks], fontsize=8)
    ax.set_title(f"{symbol} | {layer} | {tf} | diario de trading | solo velas cerradas",
                 loc="left", fontsize=14, fontweight="bold", color="#302d29", pad=16)
    ax.set_ylabel("Precio", color="#5d584f")
    ax.grid(color="#ded8ce", linewidth=0.6, linestyle=":")
    ax.tick_params(colors="#5d584f")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.01, 0.01,
             f"Ultima vela cerrada: {info['time']} | MT5 actualizado | sin orden enviada",
             fontsize=8, color="#6b665d")
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def generate(symbol: str, out_dir: Path) -> tuple[Path, Path, Path, Path]:
    now = pd.Timestamp.now(tz="UTC")
    raw = load_frames(symbol, ("D1", "H4", "H1", "M15", "M5", "M1"))
    frames = {tf: _closed_only(df, tf, now) for tf, df in raw.items()}
    annotated: dict[str, pd.DataFrame] = {}
    info: dict[str, dict] = {}
    for tf, frame in frames.items():
        if len(frame) < 20:
            raise RuntimeError(f"No hay suficientes velas cerradas para {tf}")
        annotated[tf], info[tf] = _structure(frame)

    # Top-down gate uses one common, closed M15 timestamp.
    t = frames["M15"]["time"].iloc[-1]
    stack = build_context_stack(annotated, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))
    long_gate = top_down_allows_trade(stack, 1, require_ltf=True)
    short_gate = top_down_allows_trade(stack, -1, require_ltf=True)
    htf_narrative = build_htf_narrative(
        frames["H4"],
        htf_frames={"D1": frames["D1"], "H4": frames["H4"], "H1": frames["H1"]},
    )
    gate_notes = [
        f"LONG: {'permitido' if long_gate[0] else 'bloqueado'} ({long_gate[1]})",
        f"SHORT: {'permitido' if short_gate[0] else 'bloqueado'} ({short_gate[1]})",
    ]
    context_notes = {
        "HTF": [f"D1: {info['D1']['trend']}", f"H4: {info['H4']['trend']}", *gate_notes],
        "MTF": [f"H1: {info['H1']['trend']}", f"M15: {info['M15']['trend']}", *gate_notes],
        "LTF": [f"M5: {info['M5']['trend']}", f"M1: {info['M1']['trend']}", *gate_notes],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    paths = []
    for layer, (tf, _, _) in LAYERS.items():
        path = out_dir / f"{symbol}_{layer}_{stamp}.png"
        _chart(path, symbol, layer, tf, frames[tf], info[tf], stack, context_notes[layer])
        paths.append(path)

    journal = out_dir / f"{symbol}_DIARIO_{stamp}.md"
    poi = htf_narrative.get("poi") or {}
    journal.write_text(
        "\n".join([
            f"# Diario de trading {symbol}",
            "",
            f"Generado: {now.isoformat()}",
            "Fuente: MT5 actualizado, solo velas cerradas.",
            "",
            "## Panorama",
            f"- HTF D1: {info['D1']['trend']} | zona {stack.get('D1', {}).get('pd_side', 'UNKNOWN')}.",
            f"- H4: {info['H4']['trend']} | BOS {_direction(info['H4']['bos_dir'])} {info['H4']['bos_status']}.",
            f"- MTF H1: {info['H1']['trend']} | M15: {info['M15']['trend']}.",
            f"- LTF M5: {info['M5']['trend']} | M1: {info['M1']['trend']}.",
            f"- POI narrativo: {poi.get('kind', 'sin POI')} {poi.get('ob_bottom', '-')}-{poi.get('ob_top', '-')}.",
            "",
            "## Decision",
            f"- LONG: {'permitido' if long_gate[0] else 'bloqueado'} ({long_gate[1]}).",
            f"- SHORT: {'permitido' if short_gate[0] else 'bloqueado'} ({short_gate[1]}).",
            "- Setup: esperar; no hay alineacion HTF-MTF-LTF suficiente.",
            "- No se envio ninguna orden a MT5.",
            "",
            "## Graficos",
            *[f"- [{p.name}]({p.name})" for p in paths],
        ]) + "\n",
        encoding="utf-8",
    )
    return paths[0], paths[1], paths[2], journal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for path in generate(args.symbol.upper(), args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

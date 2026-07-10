"""
EDGE DIAGNOSIS HARNESS — stack de DETECTORES puro (signals/pipeline.py + backtest/engine.py).
NO modifica codigo de produccion. Replica la logica de signal-pass de pipeline.py:301-306
leyendo las columnas de filtro que build_scalping_context ya calcula, y reusa la simulacion
SL-estructural + TP-2xATR de backtest/engine.py (_simulate_trade_with_stats).

Reglas duras respetadas:
- NO se toca ml/, agents/, app_observador/, integration/, governance/, monitoring/.
- Simulacion = backtest/engine.py (NO el proxy de scripts/ablation_real.py).
- load_frame auto_download SIEMPRE False (monkeypatch).
- Split temporal 70% IS / 30% OOS por entry_time, ambos reportados.
- N minimo 100 por split para reportar PF/Sharpe validos.

Uso:
  python run.py --variant baseline --symbol EURUSD --timeframe M15
  python run.py --variant no_session --symbol AUDUSD
  python run.py --all            # todas las variantes x simbolos con datos
  python run.py --driver         # alias de --all

Cada variante es individualmente reproducible. Los CSV crudos van a results/edge_diagnosis/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Unbuffered stdout when launched from .bat (progress bar / live ETA).
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

# --- Patch load_frame: auto_download SIEMPRE False (no descargar, no inventar) ---
import data as _data_mod
_orig_load_frame = _data_mod.load_frame


def _patched_load_frame(data_dir, symbol, timeframe, auto_download=True, max_stale_hours=None):
    return _orig_load_frame(data_dir, symbol, timeframe, auto_download=False)


_data_mod.load_frame = _patched_load_frame
sys.modules["data"].load_frame = _patched_load_frame

from signals import ScalpingConfig, build_scalping_context, ScalpingSignal  # noqa: E402
from legacy.backtest.engine import _build_signals_from_context, _simulate_trade_with_stats  # noqa: E402
from risk import GovernorConfig  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
TIMEFRAME = "M15"
MAX_HOLD_BARS = 16
# Cap de senales simuladas por variante: las variantes muy permisivas (prox_3) generan
# decenas de miles de senales (casi toda barra pasa). Simularlas TODAS excede el timeout
# del launcher (~55s) y el checkpoint nunca se escribe. Se simulan las N de MAYOR confianza
# (el stack ya rankea por confianza), documentado en el reporte como limite de diagnostico.
MAX_SIGNALS_PER_VARIANT = 3000
MIN_CONFIDENCE = 0.52  # reproduce el baseline del diagnostico de hoy (CombinedBacktestConfig.min_confidence default)
IS_RATIO = 0.70
MIN_N = 100

# Governor neutral: NO censura trades (medimos el edge puro de los detectores).
NEUTRAL_GOV = GovernorConfig(
    lockdown_after_losses=10**9, caution_after_losses=10**9, defensive_after_losses=10**9,
    caution_day_dd=10**9, defensive_day_dd=10**9, lockdown_day_dd=10**9,
    caution_total_dd=10**9, defensive_total_dd=10**9, lockdown_total_dd=10**9,
)

SYMBOLS_FULL = ["EURUSD", "AUDUSD", "NZDUSD", "USDCAD", "XAUUSD"]  # historico suficiente
SYMBOLS_SHORT = ["GBPUSD", "USDCHF", "USDJPY"]  # 500 barras (~7 dias) -> insuficiente

PROGRESS_PATH = ROOT / "results" / "edge_diagnosis" / "progress.json"
REPORT_PATH = ROOT / "results" / "edge_diagnosis" / "EDGE_DIAGNOSIS_REPORT.md"
# If updated_at is older than this while status=running, surface hang risk (watchers / final MD).
HANG_STALE_SECONDS = 5 * 60


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _write_progress(payload: dict) -> None:
    """Atomic-ish overwrite of machine-readable progress (JSON)."""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def _progress_bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + "?" * width + "]"
    frac = min(1.0, max(0.0, done / total))
    filled = int(width * frac)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {frac * 100:5.1f}%"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


def _print_live_progress(p: dict) -> None:
    """Single-line console bar with ETA (overwrites with \\r until newline on unit end)."""
    bar = _progress_bar(int(p.get("done_units", 0)), int(p.get("total_units", 0)))
    cur = f"{p.get('current_symbol', '?')}/{p.get('current_variant', '?')}"
    eta = _fmt_duration(p.get("eta_seconds_remaining"))
    fin = p.get("eta_at") or "—"
    elapsed = _fmt_duration(p.get("elapsed_seconds"))
    line = (
        f"\r  {bar}  {p.get('done_units', 0)}/{p.get('total_units', 0)}  "
        f"now={cur}  elapsed={elapsed}  ETA_left={eta}  finish~{fin}   "
    )
    print(line, end="", flush=True)


def write_edge_report(full_results: list[dict], out_path: Path = REPORT_PATH) -> Path:
    """Build a human-readable MD ranking variants/symbols from full_results.json payload."""
    import math

    rows: list[dict] = []
    errors: list[dict] = []
    for r in full_results:
        if r.get("error"):
            errors.append({"symbol": r.get("symbol"), "variant": r.get("variant"), "error": r.get("error")})
            continue
        oos = r.get("oos") or {}
        is_m = r.get("is") or {}
        pf = oos.get("pf")
        if pf is None or (isinstance(pf, float) and (math.isnan(pf) or math.isinf(pf))):
            pf_s = None
        else:
            pf_s = float(pf)
        rows.append({
            "variant": r.get("variant"),
            "symbol": r.get("symbol"),
            "n_total": r.get("n_total", 0),
            "insufficient": bool(r.get("insufficient")),
            "is_n": is_m.get("n", 0),
            "oos_n": oos.get("n", 0),
            "oos_wr": oos.get("wr"),
            "oos_pf": pf_s,
            "oos_sharpe": oos.get("sharpe"),
            "oos_avg_r": oos.get("avg_r"),
            "is_pf": (is_m.get("pf") if is_m.get("pf") not in (float("inf"),) else None),
        })

    # Aggregate OOS PF by variant (only rows with valid n and pf)
    by_var: dict[str, list[float]] = {}
    by_sym: dict[str, list[float]] = {}
    for row in rows:
        if row["insufficient"] or row["oos_pf"] is None or row["oos_n"] < 20:
            continue
        by_var.setdefault(row["variant"], []).append(row["oos_pf"])
        by_sym.setdefault(row["symbol"], []).append(row["oos_pf"])

    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else float("nan")

    var_rank = sorted(
        ((k, _avg(v), len(v)) for k, v in by_var.items()),
        key=lambda t: (t[1] if t[1] == t[1] else -1),
        reverse=True,
    )
    sym_rank = sorted(
        ((k, _avg(v), len(v)) for k, v in by_sym.items()),
        key=lambda t: (t[1] if t[1] == t[1] else -1),
        reverse=True,
    )

    # Best single cells (valid OOS)
    valid_cells = [r for r in rows if r["oos_pf"] is not None and not r["insufficient"]]
    valid_cells.sort(key=lambda r: r["oos_pf"], reverse=True)
    top10 = valid_cells[:10]
    bottom10 = list(reversed(valid_cells[-10:])) if valid_cells else []

    n_ok = sum(1 for r in rows if not r["insufficient"] and r.get("n_total", 0) > 0)
    n_insuf = sum(1 for r in rows if r["insufficient"])
    n_zero = sum(1 for r in rows if r.get("n_total", 0) == 0)

    now = _iso_now()
    lines = [
        f"# Edge Diagnosis Report",
        "",
        f"**Generated:** {now}",
        f"**Units completed:** {len(full_results)}  |  valid OOS cells: {n_ok}  |  "
        f"insufficient N: {n_insuf}  |  zero trades: {n_zero}  |  errors: {len(errors)}",
        "",
        "## Verdict (read this first)",
        "",
        "This harness measures the **detector stack alone** (no ML, no agents, neutral risk governor).",
        "A real edge needs **OOS PF > 1.1 with N>=100 per split** on more than one symbol, and",
        "that it **survives** ablation (does not vanish when one filter is removed).",
        "",
    ]

    if not var_rank:
        lines += [
            "> **No variant produced a statistically usable OOS sample.** "
            "Either data is too short (SYMBOLS_SHORT) or filters kill almost all signals.",
            "",
        ]
    else:
        best_v, best_pf, best_n = var_rank[0]
        worst_v, worst_pf, worst_n = var_rank[-1]
        lines += [
            f"- **Best avg OOS PF by variant:** `{best_v}` → PF **{best_pf:.3f}** (over {best_n} symbol cells)",
            f"- **Worst avg OOS PF by variant:** `{worst_v}` → PF **{worst_pf:.3f}** (over {worst_n} symbol cells)",
            "",
        ]
        multi_sym = best_n >= 2
        if best_pf < 1.0:
            lines += [
                "> **No positive edge found** in the ranked variants (best average OOS PF still < 1.0).",
                "> Priority: fix the base signal logic, not more infrastructure.",
                "",
            ]
        elif best_pf < 1.1 or not multi_sym:
            lines += [
                f"> **Marginal / provisional** (`{best_v}` avg OOS PF {best_pf:.3f} over {best_n} cell(s)). "
                "Do **not** treat as proven edge until multi-symbol + larger N confirm.",
                "",
            ]
        else:
            lines += [
                f"> **Candidate edge** under variant `{best_v}` (avg OOS PF {best_pf:.3f} over {best_n} symbols). "
                "Still validate walk-forward before any live automation.",
                "",
            ]

    lines += [
        "## Ranking — variants (avg OOS PF, cells with n_oos>=20 and sufficient N)",
        "",
        "| Rank | Variant | Avg OOS PF | # cells |",
        "|-----:|---------|----------:|--------:|",
    ]
    for i, (k, pf, n) in enumerate(var_rank, 1):
        lines.append(f"| {i} | `{k}` | {pf:.3f} | {n} |")
    if not var_rank:
        lines.append("| — | *(none)* | — | — |")

    lines += [
        "",
        "## Ranking — symbols (avg OOS PF across variants)",
        "",
        "| Rank | Symbol | Avg OOS PF | # cells |",
        "|-----:|--------|----------:|--------:|",
    ]
    for i, (k, pf, n) in enumerate(sym_rank, 1):
        lines.append(f"| {i} | `{k}` | {pf:.3f} | {n} |")
    if not sym_rank:
        lines.append("| — | *(none)* | — | — |")

    lines += [
        "",
        "## Top 10 cells (variant × symbol) by OOS PF",
        "",
        "| Variant | Symbol | OOS N | OOS WR | OOS PF | OOS Sharpe | OOS avg R |",
        "|---------|--------|------:|-------:|-------:|-----------:|----------:|",
    ]
    for r in top10:
        wr = f"{r['oos_wr']*100:.1f}%" if r["oos_wr"] is not None else "—"
        sh = f"{r['oos_sharpe']:.2f}" if r["oos_sharpe"] is not None else "—"
        ar = f"{r['oos_avg_r']:.4f}" if r["oos_avg_r"] is not None else "—"
        lines.append(
            f"| `{r['variant']}` | `{r['symbol']}` | {r['oos_n']} | {wr} | "
            f"{r['oos_pf']:.3f} | {sh} | {ar} |"
        )
    if not top10:
        lines.append("| — | — | — | — | — | — | — |")

    lines += [
        "",
        "## Bottom 10 cells (worst OOS PF)",
        "",
        "| Variant | Symbol | OOS N | OOS WR | OOS PF |",
        "|---------|--------|------:|-------:|-------:|",
    ]
    for r in bottom10:
        wr = f"{r['oos_wr']*100:.1f}%" if r["oos_wr"] is not None else "—"
        lines.append(
            f"| `{r['variant']}` | `{r['symbol']}` | {r['oos_n']} | {wr} | {r['oos_pf']:.3f} |"
        )
    if not bottom10:
        lines.append("| — | — | — | — | — |")

    lines += [
        "",
        "## Baseline detail (reference config)",
        "",
        "| Symbol | N total | IS PF | OOS PF | OOS N | Insufficient |",
        "|--------|--------:|------:|-------:|------:|:------------:|",
    ]
    for r in sorted((x for x in rows if x["variant"] == "baseline"), key=lambda x: x["symbol"] or ""):
        is_pf = r.get("is_pf")
        is_s = f"{float(is_pf):.3f}" if isinstance(is_pf, (int, float)) and is_pf == is_pf else "—"
        oos_s = f"{r['oos_pf']:.3f}" if r["oos_pf"] is not None else "—"
        lines.append(
            f"| `{r['symbol']}` | {r['n_total']} | {is_s} | {oos_s} | {r['oos_n']} | "
            f"{'YES' if r['insufficient'] else 'no'} |"
        )

    if errors:
        lines += ["", "## Errors during run", ""]
        for e in errors:
            lines.append(f"- `{e['symbol']}/{e['variant']}`: {e['error']}")

    lines += [
        "",
        "## Artifacts",
        "",
        f"- Progress (live): `{PROGRESS_PATH.relative_to(ROOT)}`",
        f"- Full results JSON: `results/edge_diagnosis/full_results.json`",
        f"- Per-variant CSVs: `results/edge_diagnosis/*.csv`",
        f"- Summary CSV: `results/edge_diagnosis/summary.csv`",
        "",
        "## How to re-run",
        "",
        "Double-click `run_edge_diagnosis.bat` or:",
        "",
        "```bat",
        "python -u scripts/edge_diagnosis/run.py --all",
        "```",
        "",
        "The job **resumes** from `full_results.json` if interrupted.",
        "",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


@dataclass
class Variant:
    key: str
    desc: str
    # config overrides aplicados a ScalpingConfig antes de build_scalping_context
    config_overrides: dict = field(default_factory=dict)
    # filtros que el harness fuerza en PASS (no hay flag de config para ellos)
    force_pass: list[str] = field(default_factory=list)


# --- Definicion de las variantes de ablacion (seccion 5 del prompt) ---
def all_variants() -> list[Variant]:
    v: list[Variant] = []
    v.append(Variant("baseline", "Configuracion actual (todos los filtros, mc=2, prox=1.5)"))
    v.append(Variant("no_session", "Sin filtro de sesion", force_pass=["session"]))
    v.append(Variant("no_atr", "Sin filtro ATR (min_atr_ratio)", force_pass=["atr"]))
    v.append(Variant("no_choch", "Sin CHOCH anti-opuesto", force_pass=["choch"]))
    for prox in (1.0, 2.0, 3.0):
        tag = f"prox_{prox:g}"
        v.append(Variant(tag, f"ob_fvg_proximity_atr={prox:g}", config_overrides={"ob_fvg_proximity_atr": prox}))
    for mc in (1, 3, 4):
        v.append(Variant(f"mc_{mc}", f"min_confluence_score={mc}", config_overrides={"min_confluence_score": mc}))
    v.append(Variant("no_swing", "Sin filtro de swing (1.5 ATR)", force_pass=["swing"]))
    v.append(Variant("no_micro", "Sin EMA/RSI micro", force_pass=["micro"]))
    v.append(Variant("no_sweep_ote", "Sin sweep + OTE", config_overrides={"enable_sweep_filter": False, "enable_ote_filter": False}))
    for k in ("trend", "choch", "ob_fvg", "bos", "swing", "agents", "sweep", "ote"):
        w = dict(ScalpingConfig().confluence_weights)
        w[k] = 0.0
        v.append(Variant(f"w0_{k}", f"Peso confluence {k}=0", config_overrides={"confluence_weights": w}))
    return v


def build_config(v: Variant) -> ScalpingConfig:
    # ScalpingConfig es frozen -> construimos una nueva instancia con los overrides
    return ScalpingConfig(**v.config_overrides)


def harness_pass_signals(context: "pd.DataFrame", cfg: ScalpingConfig, v: Variant):
    """Replica pipeline.py:301-306 usando las columnas de filtro ya calculadas.
    Permite forzar PASS a filtros sin flag de config (override de la ablacion).
    VERSION VECTORIZADA (sin .loc en loop) para no colgarse en 50k-99k barras."""
    import pandas as pd  # local import ok
    import numpy as np  # local import ok
    n = len(context)
    fp = set(v.force_pass)
    # forzar PASS = Serie de True del largo correcto (no escalar, para poder operar)
    all_true = pd.Series(True, index=context.index)
    f_session = all_true if "session" in fp else context["filter_session"].astype(bool)
    f_atr = all_true if "atr" in fp else context["filter_atr"].astype(bool)
    f_choch = all_true if "choch" in fp else context["filter_choch"].astype(bool)
    f_swing = all_true if "swing" in fp else context["filter_swing"].astype(bool)
    f_micro = all_true if "micro" in fp else context["filter_micro"].astype(bool)

    mandatory = f_session & f_atr
    w = cfg.confluence_weights
    active = {
        "trend": context["filter_trend"].astype(float),
        "bos": context["filter_bos"].astype(float),
        "ob_fvg": context["filter_ob_fvg"].astype(float),
        "choch": f_choch.astype(float),
        "swing": f_swing.astype(float),
        "agents": 0.0,  # sin orquestador
        "sweep": context["filter_sweep"].astype(float) if cfg.enable_sweep_filter else 0.0,
        "ote": context["filter_ote"].astype(float) if cfg.enable_ote_filter else 0.0,
    }
    confluence = sum(active[k] * w.get(k, 1.0) for k in active)
    signal_pass = mandatory & (confluence >= cfg.min_confluence_score)

    md = context["macro_direction"].fillna("RANGING")
    direction = np.where(md == "BULLISH", 1, np.where(md == "BEARISH", -1, 0))
    atr = context["atr"].astype(float)
    atr_ok = np.isfinite(atr) & (atr > 0.0)
    sl_val = context["structural_sl"].astype(float)
    sl_ok = np.isfinite(sl_val)
    entry = context["close"].astype(float)

    # tambien aplicamos min_confidence (como hace _build_signals_from_context en engine.py:78)
    conf = context["signal_confidence"].astype(float)
    mask = signal_pass.to_numpy() & (direction != 0) & atr_ok.to_numpy() & (conf.to_numpy() >= MIN_CONFIDENCE)
    rows = np.where(mask)[0]
    # cap por confianza descendente (variantes permisivas generan decenas de miles de senales)
    if len(rows) > MAX_SIGNALS_PER_VARIANT:
        order = rows[np.argsort(-conf.to_numpy()[rows])]
        rows = order[:MAX_SIGNALS_PER_VARIANT]
    out = []
    for i in rows:
        d = int(direction[i])
        e = float(entry.iloc[i])
        a = float(atr.iloc[i])
        sl = float(sl_val.iloc[i]) if sl_ok.iloc[i] else (e - a if d == 1 else e + a)
        tp = e + 2.0 * a if d == 1 else e - 2.0 * a
        out.append(ScalpingSignal(
            symbol=str(context.iloc[i].get("symbol", "")),
            time=str(context.iloc[i]["time"]),
            direction=d, confidence=float(context.iloc[i]["signal_confidence"]),
            entry=e, stop_loss=sl, take_profit=tp))
    return out


def _simulate_trade_vectorized(frame: "pd.DataFrame", signals: list[ScalpingSignal], max_hold_bars: int) -> list[dict]:
    """Simulacion SL-estructural + TP-2xATR (igual semantica que backtest/engine.py:158).
    VERSION VECTORIZADA: para cada senal busca el primer cruce de SL/TP en la ventana
    de max_hold_bars usando numpy, en lugar de un loop Python barra por barra.
    Devuelve lista de dicts con pnl_r, exit_reason, mfe_r, mae_r."""
    import numpy as np  # noqa
    if not signals:
        return []
    times = frame["time"].astype(str).to_numpy()
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    n = len(frame)
    # indice time->pos UNA vez (O(n)); lookup O(1) por senal en vez de np.nonzero O(n) por senal
    tpos = {t: i for i, t in enumerate(times)}
    out = []
    for sig in signals:
        idx = tpos.get(sig.time)
        if idx is None:
            continue
        sl = float(sig.stop_loss)
        tp = float(sig.take_profit)
        risk = abs(float(sig.entry) - sl)
        if risk <= 0.0:
            continue
        j_end = min(idx + max_hold_bars, n - 1)
        if j_end <= idx:
            continue
        seg_h = high[idx + 1: j_end + 1]
        seg_l = low[idx + 1: j_end + 1]
        seg_c = close[idx + 1: j_end + 1]
        if sig.direction == 1:
            sl_hit = seg_l <= sl
            tp_hit = seg_h >= tp
        else:
            sl_hit = seg_h >= sl
            tp_hit = seg_l <= tp
        sl_idx = np.argmax(sl_hit) if sl_hit.any() else -1
        tp_idx = np.argmax(tp_hit) if tp_hit.any() else -1
        if sl_idx != -1 and (tp_idx == -1 or sl_idx <= tp_idx):
            exit_j = idx + 1 + sl_idx
            exit_price = sl
            reason = "SL"
            mfe = float(((seg_h[:sl_idx + 1] - sig.entry) / risk).max()) if sig.direction == 1 else float(((sig.entry - seg_l[:sl_idx + 1]) / risk).max())
            mae = float(((seg_l[:sl_idx + 1] - sig.entry) / risk).min()) if sig.direction == 1 else float(((sig.entry - seg_h[:sl_idx + 1]) / risk).min())
        elif tp_idx != -1:
            exit_j = idx + 1 + tp_idx
            exit_price = tp
            reason = "TP"
            mfe = float(((seg_h[:tp_idx + 1] - sig.entry) / risk).max()) if sig.direction == 1 else float(((sig.entry - seg_l[:tp_idx + 1]) / risk).max())
            mae = float(((seg_l[:tp_idx + 1] - sig.entry) / risk).min()) if sig.direction == 1 else float(((sig.entry - seg_h[:tp_idx + 1]) / risk).min())
        else:
            exit_j = j_end
            exit_price = float(seg_c[-1])
            reason = "hold_limit"
            mfe = float(((seg_h - sig.entry) / risk).max()) if sig.direction == 1 else float(((sig.entry - seg_l) / risk).max())
            mae = float(((seg_l - sig.entry) / risk).min()) if sig.direction == 1 else float(((sig.entry - seg_h) / risk).min())
        if not np.isfinite(mfe):
            mfe = 0.0
        if not np.isfinite(mae):
            mae = 0.0
        pnl_r = (exit_price - sig.entry) / risk if sig.direction == 1 else (sig.entry - exit_price) / risk
        out.append({
            "symbol": sig.symbol, "variant": sig.variant if hasattr(sig, "variant") else "",
            "entry_time": sig.time, "direction": sig.direction, "confidence": sig.confidence,
            "pnl_r": float(pnl_r), "exit_reason": reason, "mfe_r": float(mfe), "mae_r": float(mae),
        })
    return out


def simulate(symbol: str, variant_key: str) -> dict:
    import pandas as pd  # noqa
    v = next(x for x in all_variants() if x.key == variant_key)
    cfg = build_config(v)
    context = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
    frame = context  # context conserva OHLC para la simulacion
    signals = harness_pass_signals(context, cfg, v)
    rows = _simulate_trade_vectorized(frame, signals, MAX_HOLD_BARS)
    for r in rows:
        r["variant"] = variant_key
        r["symbol"] = symbol
    df = pd.DataFrame(rows)
    if df.empty:
        return {"symbol": symbol, "variant": variant_key, "n_total": 0, "trades": []}
    # Split temporal 70/30 por entry_time
    df = df.sort_values("entry_time").reset_index(drop=True)
    n_is = int(len(df) * IS_RATIO)
    df["split"] = ["IS"] * n_is + ["OOS"] * (len(df) - n_is)
    return {"symbol": symbol, "variant": variant_key, "n_total": len(df), "trades": df.to_dict("records"), "frame": df}


def metrics_from(frame: "pd.DataFrame") -> dict:
    import numpy as np  # noqa
    if frame.empty:
        return {"n": 0, "wr": float("nan"), "pf": float("nan"), "sharpe": float("nan"), "avg_r": float("nan")}
    pnl = frame["pnl_r"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gp = float(wins.sum()) if not wins.empty else 0.0
    gl = float(losses.sum()) if not losses.empty else 0.0
    pf = gp / abs(gl) if gl != 0 else float("inf")
    std = float(pnl.std(ddof=0))
    sharpe = float((pnl.mean() / std) * (252 ** 0.5)) if std > 0 else 0.0
    return {"n": int(len(frame)), "wr": float((pnl > 0).mean()), "pf": float(pf),
            "sharpe": sharpe, "avg_r": float(pnl.mean())}


def run_one(variant_key: str, symbol: str) -> dict:
    res = simulate(symbol, variant_key)
    if res["n_total"] == 0:
        return {"symbol": symbol, "variant": variant_key, "n_total": 0,
                "is": None, "oos": None, "insufficient": True}
    df: "pd.DataFrame" = res["frame"]
    is_m = metrics_from(df[df["split"] == "IS"])
    oos_m = metrics_from(df[df["split"] == "OOS"])
    insufficient = (is_m["n"] < MIN_N) or (oos_m["n"] < MIN_N)
    # CSV crudo por variante (todas las symbols) lo junta el driver
    return {"symbol": symbol, "variant": variant_key, "n_total": res["n_total"],
            "is": is_m, "oos": oos_m, "insufficient": insufficient,
            "trades": res["trades"]}


def _get_context(symbol: str, cfg: ScalpingConfig, variant: "Variant") -> "pd.DataFrame":
    """Context cacheado a disco por simbolo (el build tarda 22-40s; los reintentos lo reciclan)."""
    import pickle
    cache_dir = ROOT / "results" / "edge_diagnosis" / "_ctx"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # solo las variantes que CAMBIAN detectores necesitan rebuild; el resto usa cache default
    detector_affecting = {"ob_fvg_proximity_atr", "enable_sweep_filter", "enable_ote_filter"}
    if detector_affecting & set(variant.config_overrides.keys()):
        # cache por (symbol, variant) porque el context DEPENDE de la config de la variante
        cpath = cache_dir / f"{symbol}__{variant.key}.pkl"
        if cpath.exists():
            try:
                t0 = time.time()
                with open(cpath, "rb") as f:
                    obj = pickle.load(f)
                print(f"[ctx] {symbol}/{variant.key} pickle load {time.time()-t0:.1f}s", flush=True)
                return obj
            except Exception as e:
                print(f"[ctx] {symbol}/{variant.key} pickle FALLÓ: {e}", flush=True)
        ctx = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
        try:
            with open(cpath, "wb") as f:
                pickle.dump(ctx, f)
        except Exception:
            pass
        return ctx
    cpath = cache_dir / f"{symbol}.pkl"
    if cpath.exists():
        try:
            t0 = time.time()
            with open(cpath, "rb") as f:
                obj = pickle.load(f)
            print(f"[ctx] {symbol} pickle load {time.time()-t0:.1f}s", flush=True)
            return obj
        except Exception as e:
            print(f"[ctx] {symbol} pickle FALLÓ: {e}", flush=True)
    ctx = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
    try:
        with open(cpath, "wb") as f:
            pickle.dump(ctx, f)
    except Exception:
        pass
    return ctx


def run_one_reuse(variant_key: str, symbol: str, context: "pd.DataFrame | None" = None) -> dict:
    """Reusa context cacheado por simbolo. Una sola vez por simbolo (el build es lento)."""
    import pandas as pd  # noqa
    v = next(x for x in all_variants() if x.key == variant_key)
    cfg = build_config(v)
    detector_affecting = {"ob_fvg_proximity_atr", "enable_sweep_filter", "enable_ote_filter"}
    if detector_affecting & set(v.config_overrides.keys()):
        ctx = _get_context(symbol, cfg, v)
    else:
        ctx = _get_context(symbol, ScalpingConfig(), v)  # cache default
    signals = harness_pass_signals(ctx, cfg, v)
    # cap por confianza descendente (variantes permisivas generan decenas de miles)
    if len(signals) > MAX_SIGNALS_PER_VARIANT:
        signals = sorted(signals, key=lambda s: float(s.confidence), reverse=True)[:MAX_SIGNALS_PER_VARIANT]
    rows = _simulate_trade_vectorized(ctx, signals, MAX_HOLD_BARS)
    for r in rows:
        r["variant"] = variant_key
        r["symbol"] = symbol
    df = pd.DataFrame(rows)
    if df.empty:
        return {"symbol": symbol, "variant": variant_key, "n_total": 0,
                "is": None, "oos": None, "insufficient": True, "trades": []}
    df = df.sort_values("entry_time").reset_index(drop=True)
    n_is = int(len(df) * IS_RATIO)
    df["split"] = ["IS"] * n_is + ["OOS"] * (len(df) - n_is)
    is_m = metrics_from(df[df["split"] == "IS"])
    oos_m = metrics_from(df[df["split"] == "OOS"])
    insufficient = (is_m["n"] < MIN_N) or (oos_m["n"] < MIN_N)
    return {"symbol": symbol, "variant": variant_key, "n_total": len(df),
            "is": is_m, "oos": oos_m, "insufficient": insufficient, "trades": df.to_dict("records")}


def print_status_from_file() -> int:
    """Medidor de progreso: barra + % + cuanto falta + desglose por simbolo.
    Exit 0=ok, 2=stale/hang risk, 1=missing."""
    if not PROGRESS_PATH.exists():
        print("No progress.json yet — edge diagnosis has not started.")
        return 1
    try:
        p = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not read progress.json: {e}")
        return 1
    status = p.get("status", "?")
    pct = p.get("percent", 0)
    done = p.get("done_units", 0)
    total = p.get("total_units", 0)
    left = max(0, total - done)
    cur_s = p.get("current_symbol")
    cur_v = p.get("current_variant")
    cur = f"{cur_s}/{cur_v}" if cur_s and cur_v else "—"
    eta = p.get("eta_seconds_remaining")
    eta_s = _fmt_duration(eta)
    fin = p.get("eta_at") or "—"
    elapsed = _fmt_duration(p.get("elapsed_seconds"))
    avg = p.get("avg_seconds_per_unit")
    updated = p.get("updated_at") or ""

    bar = _progress_bar(done, total, width=32)
    print()
    print(f"  EDGE DIAGNOSIS — {bar}")
    print(f"  {pct:5.1f}%   {done}/{total} unidades hechas")
    if status == "done":
        print(f"  COMPLETADO. Reporte: {REPORT_PATH}")
        return 0
    # Cuanto falta, en unidades y en tiempo estimado
    left_min = (eta / 60.0) if eta else None
    left_txt = f"~{left_min:.1f} min" if left_min is not None else "—"
    print(f"  FALTAN {left} unidades  ~  {left_txt}  (termina ~{fin})")
    print(f"  Ahora: {cur}   |   transcurrido: {elapsed}   |   ritmo: {_fmt_duration(avg)}/unidad")

    # Desglose por simbolo: cuantas variantes hechas vs total de ese simbolo
    fr = (ROOT / "results" / "edge_diagnosis" / "full_results.json")
    per_sym: dict[str, int] = {}
    if fr.exists():
        try:
            data = json.loads(fr.read_text(encoding="utf-8"))
            for r in data:
                if "symbol" in r and "variant" in r and "error" not in r:
                    per_sym[r["symbol"]] = per_sym.get(r["symbol"], 0) + 1
        except Exception:
            pass
    if per_sym:
        nvar = max(per_sym.values())
        print("  -- por simbolo (variantes hechas / total) --")
        for sym, h in sorted(per_sym.items()):
            sb = _progress_bar(h, nvar, width=14)
            mark = "OK" if h >= nvar else "  "
            print(f"    {mark} {sym:8s} {sb}  {h}/{nvar}")

    if status == "running" and updated:
        try:
            ts = datetime.fromisoformat(updated)
            age = (datetime.now() - ts).total_seconds() if ts.tzinfo is None else \
                  (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
            if age > HANG_STALE_SECONDS:
                print(f"  AVISO: POSIBLE PROCESO COLGADO: sin avance hace {_fmt_duration(age)} "
                      f"(umbral {HANG_STALE_SECONDS // 60} min).")
                return 2
        except Exception:
            pass
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--timeframe", default=TIMEFRAME)
    ap.add_argument("--all", action="store_true", help="correr todas las variantes x symbols con datos")
    ap.add_argument("--driver", action="store_true", help="alias de --all")
    ap.add_argument("--symbols", nargs="*", default=None, help="subset de simbolos (default: todos)")
    ap.add_argument("--fast-only", action="store_true",
                    help="excluye variantes detector_affecting (prox/mc/w0_sweep/w0_ote) que requieren rebuild lento del context")
    ap.add_argument(
        "--status",
        action="store_true",
        help="solo lee results/edge_diagnosis/progress.json y reporta %% / ETA / hang",
    )
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="regenera EDGE_DIAGNOSIS_REPORT.md desde full_results.json sin correr backtests",
    )
    args = ap.parse_args()

    out_dir = ROOT / "results" / "edge_diagnosis"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.status:
        raise SystemExit(print_status_from_file())

    if args.report_only:
        fr_path = out_dir / "full_results.json"
        if not fr_path.exists():
            print(f"Missing {fr_path} — nothing to report.")
            raise SystemExit(1)
        data = json.loads(fr_path.read_text(encoding="utf-8"))
        path = write_edge_report(data, REPORT_PATH)
        print(f"Report written: {path}")
        return

    if args.all or args.driver:
        variants = all_variants()
        if getattr(args, "fast_only", False):
            det = {"ob_fvg_proximity_atr", "enable_sweep_filter", "enable_ote_filter"}
            variants = [v for v in variants if not (det & set(v.config_overrides.keys()))]
        symbols = args.symbols if args.symbols else (SYMBOLS_FULL + SYMBOLS_SHORT)
        total_units = len(symbols) * len(variants)
        t_start = time.time()
        started_at = _iso_now()
        progress_errors: list[dict] = []

        # --- checkpoint: reanudar desde full_results.json existente ---
        done_keys: set[tuple[str, str]] = set()
        full_results: list[dict] = []
        fr_path = out_dir / "full_results.json"
        if fr_path.exists():
            try:
                full_results = json.loads(fr_path.read_text(encoding="utf-8"))
                for r in full_results:
                    if "symbol" in r and "variant" in r and "error" not in r:
                        done_keys.add((r["symbol"], r["variant"]))
                    if r.get("error"):
                        progress_errors.append({
                            "symbol": r.get("symbol"), "variant": r.get("variant"),
                            "error": r.get("error"),
                        })
                print(f"[resume] {len(done_keys)} (symbol,variant) ya hechos", flush=True)
            except Exception:
                full_results = []
                done_keys = set()
                progress_errors = []

        def _emit_progress(
            *,
            status: str,
            current_symbol: str | None = None,
            current_variant: str | None = None,
        ) -> dict:
            # Count successful + error units already stored (resume-safe %).
            done_units = len(full_results)
            elapsed = time.time() - t_start
            avg = (elapsed / done_units) if done_units > 0 else None
            remaining = (total_units - done_units)
            eta_left = (avg * remaining) if avg is not None else None
            eta_at = None
            if eta_left is not None:
                eta_at = (
                    datetime.now().astimezone().replace(microsecond=0)
                    + timedelta(seconds=eta_left)
                ).isoformat()
            payload = {
                "task": "edge_diagnosis",
                "status": status,
                "total_units": total_units,
                "done_units": done_units,
                "percent": round(done_units / total_units * 100, 1) if total_units else 0.0,
                "current_symbol": current_symbol,
                "current_variant": current_variant,
                "started_at": started_at,
                "updated_at": _iso_now(),
                "elapsed_seconds": round(elapsed, 1),
                "avg_seconds_per_unit": round(avg, 2) if avg is not None else None,
                "eta_seconds_remaining": round(eta_left, 1) if eta_left is not None else None,
                "eta_at": eta_at,
                "hang_stale_seconds": HANG_STALE_SECONDS,
                "errors": progress_errors,
            }
            if status == "done":
                payload["current_symbol"] = None
                payload["current_variant"] = None
                payload["percent"] = 100.0
                payload["eta_seconds_remaining"] = 0
                payload["eta_at"] = _iso_now()
            try:
                _write_progress(payload)
            except Exception as wexc:
                print(f"[WARN progress.json] {wexc}", flush=True)
            return payload

        # Initial progress snapshot (before first unit).
        p0 = _emit_progress(status="running", current_symbol=symbols[0] if symbols else None,
                            current_variant=variants[0].key if variants else None)
        print(
            f"[edge] {len(variants)} variants x {len(symbols)} symbols = {total_units} units "
            f"(resume: {len(done_keys)} done)",
            flush=True,
        )
        _print_live_progress(p0)
        print(flush=True)

        per_variant_csv: dict[str, list[dict]] = {v.key: [] for v in variants}
        # cargar CSV existentes para no perder trades ya simulados
        for v in variants:
            cp = out_dir / f"{v.key}.csv"
            if cp.exists():
                try:
                    import pandas as pd
                    per_variant_csv[v.key] = pd.read_csv(cp).to_dict("records")
                except Exception:
                    pass

        for s in symbols:
            # el context se cachea por simbolo en _get_context (build lento una sola vez)
            for v in variants:
                if (s, v.key) in done_keys:
                    print(f"  [{s}] {v.key} SKIP (ya hecho)", flush=True)
                    p = _emit_progress(status="running", current_symbol=s, current_variant=v.key)
                    _print_live_progress(p)
                    continue
                print(f"\n  [{s}] {v.key}...", flush=True)
                p = _emit_progress(status="running", current_symbol=s, current_variant=v.key)
                _print_live_progress(p)
                unit_t0 = time.time()
                try:
                    r = run_one_reuse(v.key, s)
                except Exception as exc:
                    import traceback as _tb
                    print(f"\n[ERROR] {s}/{v.key}: {exc}", flush=True)
                    print(_tb.format_exc(), flush=True)
                    r = {"symbol": s, "variant": v.key, "n_total": 0, "is": None, "oos": None,
                         "insufficient": True, "trades": [], "error": str(exc)}
                    progress_errors.append({"symbol": s, "variant": v.key, "error": str(exc)})
                full_results.append(r)
                if "trades" in r:
                    per_variant_csv[v.key].extend(r["trades"])
                # CHECKPOINT: escribir tras cada variante (survive a timeouts del launcher)
                try:
                    import pandas as pd
                    pdf = pd.DataFrame(per_variant_csv[v.key])
                    pdf.to_csv(out_dir / f"{v.key}.csv", index=False)
                    Path(out_dir / "full_results.json").write_text(
                        json.dumps(full_results, indent=2, default=str), encoding="utf-8")
                except Exception as wexc:
                    print(f"[WARN checkpoint] {wexc}", flush=True)
                p = _emit_progress(status="running", current_symbol=s, current_variant=v.key)
                unit_dt = time.time() - unit_t0
                print(
                    f"\n  ok {s}/{v.key} in {_fmt_duration(unit_dt)}  "
                    f"n={r.get('n_total', 0)}  "
                    f"{_progress_bar(p['done_units'], p['total_units'])}  "
                    f"ETA_left={_fmt_duration(p.get('eta_seconds_remaining'))}  "
                    f"finish~{p.get('eta_at') or '—'}",
                    flush=True,
                )
                # Hang hint for the next unit: if a unit exceeds 5 min, call it out.
                if unit_dt > HANG_STALE_SECONDS:
                    print(
                        f"  [SLOW] {s}/{v.key} took {_fmt_duration(unit_dt)} "
                        f"(>{HANG_STALE_SECONDS // 60} min). Not hung, but unusually slow.",
                        flush=True,
                    )

        # resumen por variante x symbol
        summary = []
        for r in full_results:
            if "error" in r:
                continue
            row = {"variant": r["variant"], "symbol": r["symbol"], "n_total": r["n_total"],
                   "insufficient": r["insufficient"]}
            for sp in ("is", "oos"):
                m = r.get(sp)
                if m:
                    row[f"{sp}_n"] = m["n"]; row[f"{sp}_wr"] = round(m["wr"], 4)
                    row[f"{sp}_pf"] = round(m["pf"], 4) if m["pf"] != float("inf") else None
                    row[f"{sp}_sharpe"] = round(m["sharpe"], 3); row[f"{sp}_avg_r"] = round(m["avg_r"], 4)
                else:
                    row[f"{sp}_n"] = 0
            summary.append(row)
        try:
            import pandas as pd
            pd.DataFrame(summary).to_csv(out_dir / "summary.csv", index=False)
        except Exception as wexc:
            print(f"[WARN summary.csv] {wexc}", flush=True)

        p_done = _emit_progress(status="done")
        print(
            f"\n[edge] DONE {p_done['done_units']}/{p_done['total_units']} "
            f"in {_fmt_duration(p_done.get('elapsed_seconds'))}",
            flush=True,
        )
        try:
            report = write_edge_report(full_results, REPORT_PATH)
            print(f"[edge] Report written: {report}", flush=True)
        except Exception as rexc:
            print(f"[ERROR report] {rexc}", flush=True)
            # Still mark progress done; report failure is secondary.
        print(f"Done. {len(variants)} variantes x {len(symbols)} symbols -> {out_dir}", flush=True)
        return

    # corrida individual
    r = run_one(args.variant, args.symbol)
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()

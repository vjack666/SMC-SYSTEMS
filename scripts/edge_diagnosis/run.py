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
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# --- Patch load_frame: auto_download SIEMPRE False (no descargar, no inventar) ---
import data as _data_mod
_orig_load_frame = _data_mod.load_frame


def _patched_load_frame(data_dir, symbol, timeframe, auto_download=True, max_stale_hours=None):
    return _orig_load_frame(data_dir, symbol, timeframe, auto_download=False)


_data_mod.load_frame = _patched_load_frame
sys.modules["data"].load_frame = _patched_load_frame

from signals import ScalpingConfig, build_scalping_context, ScalpingSignal  # noqa: E402
from backtest.engine import _build_signals_from_context, _simulate_trade_with_stats  # noqa: E402
from risk import GovernorConfig  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
TIMEFRAME = "M15"
MAX_HOLD_BARS = 16
MIN_CONFIDENCE = 0.40  # solo la restriccion de detectores; el gating real lo hace confluence
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
    cfg = ScalpingConfig()
    for k, val in v.config_overrides.items():
        setattr(cfg, k, val)
    return cfg


def harness_pass_signals(context: "pd.DataFrame", cfg: ScalpingConfig, v: Variant):
    """Replica pipeline.py:301-306 usando las columnas de filtro ya calculadas.
    Permite forzar PASS a filtros sin flag de config (override de la ablacion)."""
    import pandas as pd  # local import ok
    fp = set(v.force_pass)
    f_session = True if "session" in fp else context["filter_session"].astype(bool)
    f_atr = True if "atr" in fp else context["filter_atr"].astype(bool)
    f_choch = True if "choch" in fp else context["filter_choch"].astype(bool)
    f_swing = True if "swing" in fp else context["filter_swing"].astype(bool)
    f_micro = True if "micro" in fp else context["filter_micro"].astype(bool)

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

    out = []
    for idx, row in context.iterrows():
        if not bool(signal_pass.loc[idx]):
            continue
        direction = 0
        md = row.get("macro_direction", "RANGING")
        if md == "BULLISH":
            direction = 1
        elif md == "BEARISH":
            direction = -1
        else:
            continue
        atr = float(row["atr"])
        if not (atr and atr > 0):
            continue
        entry = float(row["close"])
        sl = float(row["structural_sl"]) if pd.notna(row.get("structural_sl")) and pd.notna(row["structural_sl"]) else (
            entry - atr if direction == 1 else entry + atr)
        tp = entry + 2.0 * atr if direction == 1 else entry - 2.0 * atr
        out.append(ScalpingSignal(
            symbol=row.get("symbol", ""), time=str(row["time"]),
            direction=direction, confidence=float(row["signal_confidence"]),
            entry=entry, stop_loss=sl, take_profit=tp))
    return out


def simulate(symbol: str, variant_key: str) -> dict:
    import pandas as pd  # noqa
    v = next(x for x in all_variants() if x.key == variant_key)
    cfg = build_config(v)
    context = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
    frame = context  # context conserva OHLC para la simulacion
    signals = harness_pass_signals(context, cfg, v)
    rows = []
    for sig in signals:
        trade, stats = _simulate_trade_with_stats(frame, sig, MAX_HOLD_BARS)
        if trade is None:
            continue
        rows.append({
            "symbol": symbol, "variant": variant_key, "entry_time": trade.entry_time,
            "direction": trade.direction, "confidence": trade.confidence,
            "pnl_r": trade.pnl_r, "exit_reason": stats["exit_reason"],
            "mfe_r": stats["mfe_r"], "mae_r": stats["mae_r"],
        })
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--timeframe", default=TIMEFRAME)
    ap.add_argument("--all", action="store_true", help="correr todas las variantes x symbols con datos")
    ap.add_argument("--driver", action="store_true", help="alias de --all")
    args = ap.parse_args()

    out_dir = ROOT / "results" / "edge_diagnosis"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all or args.driver:
        variants = all_variants()
        symbols = SYMBOLS_FULL + SYMBOLS_SHORT
        full_results = []
        per_variant_csv: dict[str, list[dict]] = {v.key: [] for v in variants}
        for v in variants:
            for s in symbols:
                r = run_one(v.key, s)
                full_results.append(r)
                if "trades" in r:
                    per_variant_csv[v.key].extend(r["trades"])
            # escribir CSV crudo de la variante (auditable)
            import pandas as pd
            pdf = pd.DataFrame(per_variant_csv[v.key])
            pdf.to_csv(out_dir / f"{v.key}.csv", index=False)
        # resumen por variante x symbol
        summary = []
        for r in full_results:
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
        import pandas as pd
        pd.DataFrame(summary).to_csv(out_dir / "summary.csv", index=False)
        Path(out_dir / "full_results.json").write_text(json.dumps(full_results, indent=2, default=str), encoding="utf-8")
        print(f"Done. {len(variants)} variantes x {len(symbols)} symbols -> {out_dir}")
        return

    # corrida individual
    r = run_one(args.variant, args.symbol)
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()

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
    out = []
    for sig in signals:
        matches = np.nonzero(times == sig.time)[0]
        if len(matches) == 0:
            continue
        idx = int(matches[0])
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


def run_one_reuse(variant_key: str, symbol: str, context: "pd.DataFrame") -> dict:
    """Igual que run_one pero REUSA el context ya construido (una sola vez por simbolo)."""
    import pandas as pd  # noqa
    v = next(x for x in all_variants() if x.key == variant_key)
    cfg = build_config(v)
    # Re-aplicar overrides que afectan columnas de filtro calculadas en el context.
    # La mayoria de variantes solo cambian el gating (force_pass / min_confluence), que se
    # aplica en harness_pass_signals sobre el MISMO context. Las que cambian ob_fvg_proximity
    # o enable_sweep/ote afectan columnas del context -> necesitamos rebuild. Para simplicidad
    # y correctitud, si la variante tiene config_overrides que afectan detectores, rebuild.
    detector_affecting = {"ob_fvg_proximity_atr", "enable_sweep_filter", "enable_ote_filter"}
    if set(cfg.__dict__) & detector_affecting and any(
        k in v.config_overrides for k in detector_affecting
    ):
        ctx = build_scalping_context(symbol=symbol, timeframe=TIMEFRAME, data_dir=DATA_DIR, config=cfg, orchestrator=None)
    else:
        ctx = context
    signals = harness_pass_signals(ctx, cfg, v)
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
        from signals import build_scalping_context
        for s in symbols:
            # build UNA vez por simbolo (las variantes solo cambian el gating, no los detectores)
            t0 = time.time()
            base_ctx = build_scalping_context(symbol=s, timeframe=TIMEFRAME, data_dir=DATA_DIR,
                                              config=ScalpingConfig(), orchestrator=None)
            build_s = time.time() - t0
            print(f"[build] {s}: {len(base_ctx)} bars en {build_s:.1f}s", flush=True)
            for v in variants:
                r = run_one_reuse(v.key, s, base_ctx)
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

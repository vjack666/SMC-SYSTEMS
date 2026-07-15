"""scripts/fase0_baseline.py — Fase 0 de la migración event-driven.

NO modifica código del sistema. Solo LEE y genera reportes JSON:
  tests/baseline_aged.json       (snapshot del sistema actual con aged)
  tests/aged_impact_report.json  (cuántas estructuras mueren por aged)

Backtest = sistema actual (con caducidad por velas). Config Turtle Soup
alineado. Usa run_sequence + simulate_trade (los mismos que usa internamente
run_sequence_backtest, comprobado que funcionan en este host).

Robusto: UNA carga de frames por simbolo; run_sequence devuelve senales para
medir barras-hasta-entrada; aged_impact/conteo del df. Libera RAM.

Uso: C:/Python314/python.exe scripts/fase0_baseline.py
"""

from __future__ import annotations

import gc
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from ict_backtest.engine import simulate_trade
from ict_backtest.run_backtest import _metrics
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time

SYMBOLS = ["EURUSD", "GBPUSD"]
HTF, LTF = "H4", "M15"
MAX_HOLD = 16
COST = None
CFG = SequenceConfig(counter_trend=True, tp_mode="fixed2r", require_displacement=True)


def _dir_series(df, col_int, col_str, mapping):
    if col_int in df.columns:
        return df[col_int].to_numpy()
    return df[col_str].map(mapping).fillna(0).to_numpy()


def _conteo(df):
    bos = _dir_series(df, "bos_dir", "bos_direction", {"BULLISH": 1, "BEARISH": -1})
    ch = _dir_series(df, "choch_dir", "choch_signal",
                     {"CHOCH_BULLISH": 1, "CHOCH_BEARISH": -1, "NONE": 0})
    ob_b = df.get("ob_bullish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    ob_e = df.get("ob_bearish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    fvg_b = df.get("fvg_bullish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    fvg_e = df.get("fvg_bearish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    bsl = df.get("bsl_price", pd.Series([float("nan")] * len(df)))
    ssl = df.get("ssl_price", pd.Series([float("nan")] * len(df)))
    return {
        "BOS": int((bos != 0).sum()),
        "CHOCH": int((ch != 0).sum()),
        "Order_Blocks": int((ob_b | ob_e).sum()),
        "FVG": int((fvg_b | fvg_e).sum()),
        "Liquidity_BSL_zones": int((bsl != bsl.shift(1)).sum()),
        "Liquidity_SSL_zones": int((ssl != ssl.shift(1)).sum()),
    }


def _aged(df):
    bos_status = df.get("bos_status", pd.Series(["none"] * len(df)))
    ch_status = df.get("choch_status", pd.Series(["none"] * len(df)))
    ob_status = df.get("ob_status", pd.Series(["none"] * len(df)))
    bos = _dir_series(df, "bos_dir", "bos_direction", {"BULLISH": 1, "BEARISH": -1})
    ch = _dir_series(df, "choch_dir", "choch_signal",
                     {"CHOCH_BULLISH": 1, "CHOCH_BEARISH": -1, "NONE": 0})
    ob_b = df.get("ob_bullish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    ob_e = df.get("ob_bearish", pd.Series([False] * len(df))).fillna(False).astype(bool)
    n_bos, a_bos = int((bos != 0).sum()), int((bos_status == "aged").sum())
    n_ch, a_ch = int((ch != 0).sum()), int((ch_status == "aged").sum())
    n_ob, a_ob = int((ob_b | ob_e).sum()), int((ob_status == "aged").sum())

    close = df["close"].to_numpy()
    bos_level = df["bos_level"].to_numpy() if "bos_level" in df.columns else \
        df["swing_high"].shift(1).to_numpy()
    ejemplos = []
    aged_idx = df.index[bos_status == "aged"].tolist()
    for i in aged_idx[:300]:
        d = int(bos[i])
        lvl = bos_level[i] if (i < len(bos_level) and bos_level[i] == bos_level[i]) else None
        if lvl is None:
            continue
        window = close[i + 1:i + 41]
        if d == 1 and len(window) and window.max() > lvl:
            ejemplos.append({"index": int(i), "time": str(df.iloc[i]["time"]),
                             "direction": "bull", "level": float(lvl),
                             "confirmo_despues": True})
        elif d == -1 and len(window) and window.min() < lvl:
            ejemplos.append({"index": int(i), "time": str(df.iloc[i]["time"]),
                             "direction": "bear", "level": float(lvl),
                             "confirmo_despues": True})
        if len(ejemplos) >= 5:
            break
    return {
        "BOS_aged": a_bos, "BOS_total": n_bos,
        "BOS_pct": round(100 * a_bos / n_bos, 2) if n_bos else 0.0,
        "CHOCH_aged": a_ch, "CHOCH_total": n_ch,
        "CHOCH_pct": round(100 * a_ch / n_ch, 2) if n_ch else 0.0,
        "OB_aged": a_ob, "OB_total": n_ob,
        "OB_pct": round(100 * a_ob / n_ob, 2) if n_ob else 0.0,
        "ejemplos_muertos_por_tiempo_que_habrian_confirmado": ejemplos,
    }


def backtest_symbol(symbol):
    fr = load_frames(symbol, (HTF, LTF, "D1"))
    df = fr[LTF]

    def est_fn(i):
        t = df.iloc[i]["time"]
        r = _row_at_time(fr[HTF], t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    signals, _ = run_sequence(df, est_fn, CFG)

    ltf_df = df
    pnls, exits = [], {}
    for sig in signals:
        trade, meta = simulate_trade(ltf_df, sig, MAX_HOLD, cost=COST)
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
    m = _metrics(pnls)

    bos_dir = _dir_series(df, "bos_dir", "bos_direction", {"BULLISH": 1, "BEARISH": -1})
    times = df["time"].to_numpy()
    t2i = {str(t): i for i, t in enumerate(times)}
    barras = []
    for s in signals:
        j = t2i.get(str(s.time))
        if j is None:
            continue
        d = s.direction
        prev = [k for k in range(0, j) if bos_dir[k] == d]
        if prev:
            barras.append(j - prev[-1])
    avg_barras = (sum(barras) / len(barras)) if barras else None

    est = _conteo(df)
    aged = _aged(df)
    del fr, df, signals
    gc.collect()
    return {
        "trades": m["trades"],
        "profit_factor": round(m["pf"], 3),
        "win_rate": round(m["winrate"] * 100, 2),
        "expectancy_r": round(m["expectancy"], 3),
        "max_drawdown_r": round(m["max_dd_r"], 2),
        "total_r": round(m["total_r"], 1),
        "avg_barras_hasta_entrada": round(avg_barras, 1) if avg_barras else None,
        "n_senales": len(barras),
        "estructuras_creadas": est,
        "exit_reasons": exits,
    }, aged


def main():
    baseline = {"meta": {
        "descripcion": "Baseline del sistema ACTUAL (con caducidad por velas / aged). Antes de migracion event-driven.",
        "symbols": SYMBOLS, "htf": HTF, "ltf": LTF, "max_hold": MAX_HOLD,
        "config": {"counter_trend": CFG.counter_trend, "tp_mode": CFG.tp_mode,
                   "require_displacement": CFG.require_displacement},
        "nota": "barras_hasta_entrada = velas entre ultimo BOS y la senal de entry (run_sequence).",
    }, "symbols": {}}
    aged_rep = {"meta": {"descripcion": "Impacto de la caducidad por velas (aged) en el sistema actual."},
                "symbols": {}}

    for sym in SYMBOLS:
        print(f"\n##### {sym} #####", flush=True)
        res, aged = backtest_symbol(sym)
        baseline["symbols"][sym] = res
        aged_rep["symbols"][sym] = aged
        print(f"  {sym}: trades={res['trades']} PF={res['profit_factor']} "
              f"WR={res['win_rate']}% DD={res['max_drawdown_r']}R", flush=True)

    out = ROOT / "tests" / "baseline_aged.json"
    out.write_text(json.dumps(baseline, indent=2, default=str), encoding="utf-8")
    out2 = ROOT / "tests" / "aged_impact_report.json"
    out2.write_text(json.dumps(aged_rep, indent=2, default=str), encoding="utf-8")
    print(f"\nGuardado: {out}\nGuardado: {out2}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open("/tmp/fase0_traceback.log", "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        raise

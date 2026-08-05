"""scripts/fase0_one.py — Fase 0 por simbolo (aisla RAM del host).

NO modifica codigo del sistema. Mide el backtest REAL (run_sequence +
SL estructural + RR 1:3 + killzone, igual que run_sequence_backtest) y
lo vuelca a tests/baseline_aged.json.

Muestra una BARRA DE PROGRESO VIVA en la misma linea, segundo a segundo
(spinner + tiempo + % real durante la simulacion) para saber que el
proceso sigue vivo y no colgado/OOM.

Uso:  C:/Python314/python.exe scripts/fase0_one.py EURUSD
      C:/Python314/python.exe scripts/fase0_one.py GBPUSD
"""

from __future__ import annotations

import gc
import json
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ict_backtest.engine import ICTSignal, simulate_trade
from ict_backtest.rules import killzone_en
from ict_backtest.run_backtest import (_metrics, calc_structural_sl,
                                       _tp_liquidity, STRUCT_SL_MAX_ATR)
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time
from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure

HTF, LTF = "H4", "M15"
MAX_HOLD = 16
COST = None
CFG = SequenceConfig(counter_trend=True, tp_mode="fixed2r", require_displacement=True)


class LiveProgress:
    """Barra de progreso viva: spinner + tiempo + % real, misma linea, 1 Hz.

    El trabajo pesado (load_frames / detect / secuencia) corre en el hilo
    principal y no reporta %; en esas fases se muestra un spinner + reloj
    (indeterminado) para confirmar que esta vivo. La simulacion SI tiene
    total conocido -> % real.
    """

    def __init__(self):
        self.phase = "iniciando"
        self.current = 0
        self.total = None
        self.t0 = time.time()
        self._stop = False
        self._lock = threading.Lock()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop = True
        self._t.join()
        # limpia la linea de la barra y baja una linea para el resumen
        sys.stdout.write("\r" + " " * 72 + "\r\n")
        sys.stdout.flush()

    def _loop(self):
        spin = "|/-\\"
        i = 0
        while not self._stop:
            with self._lock:
                phase = self.phase
                cur = self.current
                tot = self.total
            elapsed = int(time.time() - self.t0)
            mm, ss = elapsed // 60, elapsed % 60
            if tot:
                pct = int(100 * cur / max(tot, 1))
                bar_len = 22
                filled = int(bar_len * pct / 100)
                bar = "[" + "#" * filled + "-" * (bar_len - filled) + "]"
                line = (f"\r{bar} {pct:3d}% | {phase} | {cur}/{tot} "
                        f"| {mm:02d}:{ss:02d}")
            else:
                sp = spin[i % 4]
                line = (f"\r{sp} cargando... | {phase} | {mm:02d}:{ss:02d} "
                        f"(% real en simulacion)")
            sys.stdout.write(line.ljust(72))
            sys.stdout.flush()
            i += 1
            time.sleep(1)


_prog = LiveProgress()


def run_one(symbol, use_poi=False):
    _prog.phase = "Cargando frames (load_frames)"
    tfs = tuple(dict.fromkeys([HTF, LTF, "D1"]))
    frames = load_frames(symbol, tfs)

    _prog.phase = "Market structure (detect_market_structure)"
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[LTF]
    htf_df = ms.get(HTF, ltf_df)

    def est_htf_fn(i):
        t = ltf_df.iloc[i]["time"]
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}

    # Guarda POI HTF (Fase E / tesis 18): la zona LTF solo cuenta si el HTF
    # tiene un POI (FVG/OB) VIGENTE en esa direccion. Un POI de HTF es un
    # EVENTO (la columna fvg/ob es True solo 1 vela), asi que se mira una
    # VENTANA de las ultimas N velas H4, no la vela puntual. Sin ventana, el
    # filtro queda over-strict y anula el backtest (ver FASE_F_REPORT).
    htf_poi_fn = None
    if use_poi:
        htf_times = list(htf_df["time"].to_numpy())
        def _col(name):
            if name in htf_df.columns:
                return htf_df[name].fillna(False).to_numpy()
            return np.zeros(len(htf_df), dtype=bool)
        htf_fvb = _col("fvg_bullish")
        htf_fve = _col("fvg_bearish")
        htf_obb = _col("ob_bullish")
        htf_obe = _col("ob_bearish")
        POI_WINDOW = 20  # velas H4 ~ 5 dias de vigencia del POI

        def htf_poi_fn(i, target):
            t = ltf_df.iloc[i]["time"]
            # indice de la vela HTF mas cercana (<= t)
            idx = int(np.searchsorted(htf_times, t, side="right") - 1)
            if idx < 0:
                return False
            lo = max(0, idx - POI_WINDOW)
            if target == 1:
                return bool(htf_fvb[lo:idx + 1].any() or htf_obb[lo:idx + 1].any())
            return bool(htf_fve[lo:idx + 1].any() or htf_obe[lo:idx + 1].any())

    _prog.phase = "Secuencia (run_sequence)"
    raw_sigs, phases = run_sequence(ltf_df, est_htf_fn, CFG, htf_poi_fn=htf_poi_fn)

    # Construir senales con SL estructural + RR 1:3 + killzone (igual backtest)
    _prog.phase = "Armando senales (SL estructural + RR 1:3 + killzone)"
    signals = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_row = ltf_df.iloc[s["entry_at"]]
        entry = s["entry"]
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        if risk > STRUCT_SL_MAX_ATR * atr:
            continue
        liq = _tp_liquidity(entry_row, direction)
        tp = liq if liq is not None else (
            entry + 3.0 * risk if direction == 1 else entry - 3.0 * risk)
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        signals.append(ICTSignal(symbol=symbol, time=s["time"], direction=direction,
                                 entry=entry, stop_loss=sl, take_profit=tp,
                                 model="sequence"))

    _prog.phase = "Simulando trades"
    _prog.total = max(len(signals), 1)
    _prog.current = 0
    pnls, exits = [], {}
    for k, sig in enumerate(signals, 1):
        trade, meta = simulate_trade(ltf_df, sig, MAX_HOLD, cost=COST)
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
        _prog.current = k

    m = _metrics(pnls)
    res = {
        "trades": m["trades"], "profit_factor": round(m["pf"], 3),
        "win_rate": round(m["winrate"] * 100, 2), "expectancy_r": round(m["expectancy"], 3),
        "max_drawdown_r": round(m["max_dd_r"], 2), "total_r": round(m["total_r"], 1),
        "n_senales": len(signals), "fases": phases, "exit_reasons": exits,
        "modelo": "sequence (sin aged + POI HTF ACTIVO) — A''" if use_poi
                   else "sequence (sin aged + POI HTF inactivo) — A'",
        "poi_htf_activo": use_poi,
    }
    del frames, ms, ltf_df, htf_df, raw_sigs, signals
    gc.collect()
    return res


def _merge(path, key, value):
    d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    d[key] = value
    path.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    use_poi = (len(sys.argv) > 2 and sys.argv[2] == "poi")
    tag = "A'' (POI HTF ACTIVO)" if use_poi else "A' (sin aged + POI HTF inactivo)"
    print(f"===== {symbol} ({tag}) — backtest event-driven =====", flush=True)
    _prog.start()
    try:
        res = run_one(symbol, use_poi=use_poi)
    finally:
        _prog.stop()
    _merge(ROOT / "tests" / "baseline_aged.json", symbol, res)
    print(f"  {symbol}: trades={res['trades']} PF={res['profit_factor']} "
          f"WR={res['win_rate']}% DD={res['max_drawdown_r']}R "
          f"exit={res['exit_reasons']}", flush=True)
    print(f"  merge -> tests/baseline_aged.json", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open("/tmp/fase0_one_tb.log", "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        raise

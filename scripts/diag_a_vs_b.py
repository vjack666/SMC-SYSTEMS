"""DIAGNOSTICO FORENSE A vs B (solo lectura, NO modifica produccion).

Responde la pregunta: ¿A=0 vs B=6 es regresion del lector MultiTFContext
o simple comparacion de dos etapas distintas del pipeline?

A = evaluate_signals(...)  -> run_sequence + 5 POST-FILTROS (killzone/atr/sl/risk/fill)
B = run_sequence(...) crudo -> SOLO secuencia, SIN post-filtros

El script:
  1. Carga frames (real via load_frames, o --synthetic).
  2. Cuenta B = run_sequence(est_htf_fn_legacy sobre ms[htf]).
  3. Cuenta A = evaluate_signals(frames=...).
  4. Aplica los POST-FILTROS de evaluate_signals a las crudas de B y
     tabula el MOTIVO EXACTO de descarte de cada senal.
  5. Verifica que extract_htf_layer(est_htf_ctx_fn(i), htf) == legacy(i)
     para TODA barra (=> el lector MultiTFContext NO introduce diferencia).
  6. Imprime tabla: entry_at | dir | fill | atr>0 | killzone | sl | risk | ->A?

Uso:
  python scripts/diag_a_vs_b.py EURUSD D1 M15 6
  python scripts/diag_a_vs_b.py --synthetic   # datos controlados, sin parquet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd

from ict_backtest._util import closed_row_at_time, tf_duration
from ict_backtest.canonical import evaluate_signals
from ict_backtest.engine import (calc_structural_sl, fill_entry_price,
                                 STRUCT_SL_MAX_ATR)
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.multitf_context import (build_multitf_context,
                                          extract_htf_layer)
from ict_backtest.rules import killzone_en
from ict_backtest.sequence import run_sequence, SequenceConfig


# --------------------------------------------------------------------------
# Datos sinteticos controlados (SIN parquet): inyectamos el estado ICT para
# que run_sequence produzca senales y poder ejercer CADA post-filtro.
# Esto demuestra la MECANICA de los filtros sin tocar datos reales.
# --------------------------------------------------------------------------
def _build_synthetic() -> dict:
    from ict_backtest.market_structure import detect_market_structure as dms
    # LTF M15: 240 velas empezando lunes 2026-03-02 08:00 UTC (London Open).
    base = pd.Timestamp("2026-03-02 08:00", tz="UTC")
    times = pd.date_range(base, periods=240, freq="15min", tz="UTC")
    import numpy as np
    r = np.random.default_rng(7)
    close = 1.10 + np.cumsum(r.normal(0, 0.0004, 240))
    high = close + np.abs(r.normal(0, 0.0003, 240))
    low = close - np.abs(r.normal(0, 0.0003, 240))
    opn = pd.Series(close).shift(1).fillna(close[0]).to_numpy()
    ltf = pd.DataFrame({
        "time": times, "open": opn, "high": high, "low": low,
        "close": close, "volume": 100.0,
    })
    ltf = dms(ltf)
    # ATR sintetico (>0) para que el post-filtro atr>0 pueda ejercerse.
    import numpy as np
    ltf["atr"] = np.abs(r.normal(0.0006, 0.0002, 240)) + 0.0003
    # HTF D1: 12 velas BULLISH (para target=1 en a-favor).
    d1t = pd.date_range("2026-03-01", periods=12, freq="1D", tz="UTC")
    d1c = 1.10 + 0.001 * np.arange(12)
    d1 = pd.DataFrame({
        "time": d1t, "open": d1c, "high": d1c + 0.002,
        "low": d1c - 0.002, "close": d1c, "volume": 100.0,
    })
    d1 = dms(d1)
    d1["trend"] = "BULLISH"

    # Inyectar 6 secuencias LONG que pasan run_sequence. Cada bloque:
    #   s   : sweep_down=True            -> SWEEP_DONE
    #   s+3 : displacement_bullish=True, fvg_bullish=True -> zona congelada
    #   s+6 : bos_dir=1                 -> BOS_DONE
    #   s+9 : retorno a la zona (low<=zh and high>=zl) -> ENTRY
    # Variamos horario/atr para ejercer los post-filtros.
    starts = [12, 50, 88, 126, 164, 202]
    for k, s in enumerate(starts):
        ltf.loc[s, "liquidity_sweep_down"] = True
        fvg_i = s + 3
        ltf.loc[fvg_i, "displacement_bullish"] = True
        ltf.loc[fvg_i, "fvg_bullish"] = True
        # zona FVG = (high, low) de la vela fvg
        zh = float(ltf.loc[fvg_i, "high"])
        zl = float(ltf.loc[fvg_i, "low"])
        ltf.loc[s + 6, "bos_dir"] = 1
        # vela de retorno: que toque la zona
        ret = s + 9
        ltf.loc[ret, "low"] = min(zl, zh) - 1e-6
        ltf.loc[ret, "high"] = max(zl, zh) + 1e-6
        ltf.loc[ret, "close"] = (zl + zh) / 2.0
        # atr: todas >0 por defecto (random walk ya lo da), pero forzamos
        ltf.loc[ret, "atr"] = max(float(ltf.loc[ret, "atr"]), 0.0005)

    # --- Ejercitar post-filtros sobre senales especificas ---
    # Senal 2 (starts[1]): mover su entry fuera de killzone (02:00 UTC).
    #   Para eso cambiamos el timestamp de TODA la ventana de esa senal.
    #   Simpler: cambiamos el time de la vela de retorno a las 02:00.
    bad_kz = starts[1] + 9
    ltf.loc[bad_kz, "time"] = pd.Timestamp("2026-03-02 02:00", tz="UTC")
    # Senal 3 (starts[2]): atr=0 en entry -> muere en atr>0.
    ltf.loc[starts[2] + 9, "atr"] = 0.0
    # Senal 4 (starts[3]): sweep_row sin estructura -> sl=None.
    #   Ponemos la vela de sweep (starts[3]) con high/low iguales (sin mecha).
    sw = starts[3]
    ltf.loc[sw, "high"] = ltf.loc[sw, "close"]
    ltf.loc[sw, "low"] = ltf.loc[sw, "close"]
    # Senal 5 (starts[4]): riesgo gigante -> risk > MAX_ATR*atr.
    #   Hacemos el sweep muy profundo para que SL quede lejos del entry.
    sw5 = starts[4]
    ltf.loc[sw5, "low"] = ltf.loc[sw5, "close"] - 0.02  # sweep gigante
    ltf.loc[sw5, "atr"] = 0.0003
    # Senal 6 (starts[5]): entry en ULTIMA barra -> fill ValueError.
    #   (starts[5]+9 = 211 < 240, asi que no es ultima; la dejamos pasar
    #    para tener al menos 1 que SI llega a A y mostrar PASS).

    return {"D1": d1, "M15": ltf}


# --------------------------------------------------------------------------
# Post-filtros replica EXACTA de canonical.py:156-186 (los que descartan).
# --------------------------------------------------------------------------
def _post_filter_with_reasons(ltf_df, raw_sigs, fill_mode="next_open"):
    out = []
    rows = []
    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        try:
            entry = fill_entry_price(ltf_df, entry_at, fill_mode)
        except ValueError:
            rows.append((entry_at, direction, "FAIL", "fill_entry_price: ValueError (no next bar)"))
            continue
        atr = float(entry_row.get("atr", 0.0) or 0.0)
        if not (atr > 0):
            rows.append((entry_at, direction, "FAIL", "atr<=0"))
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            rows.append((entry_at, direction, "FAIL", f"killzone={kz!r}"))
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, atr)
        if sl is None:
            rows.append((entry_at, direction, "FAIL", "calc_structural_sl=None"))
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_ATR * atr:
            reason = (f"risk={risk:.5f} > {STRUCT_SL_MAX_ATR}*atr={STRUCT_SL_MAX_ATR*atr:.5f}"
                      if risk > STRUCT_SL_MAX_ATR * atr else "risk<=0")
            rows.append((entry_at, direction, "FAIL", reason))
            continue
        out.append(s)
        rows.append((entry_at, direction, "PASS", "ok"))
    return out, rows


def _verify_reader_identical(ms, ltf, htf):
    """Devuelve lista de barras i donde el lector MultiTFContext difiere del
    legacy 1-nivel. Vacia => NO hay regresion de lectura."""
    ltf_df = ms[ltf]

    def est_htf_ctx_fn(i):
        t = ltf_df.iloc[i]["time"]
        return build_multitf_context(ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"))

    def legacy(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(ms[htf], t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")) if r is not None else "RANGING",
            "sweep_up": bool(r.get("liquidity_sweep_up", False)) if r is not None else False,
            "sweep_down": bool(r.get("liquidity_sweep_down", False)) if r is not None else False,
            "pd_zones": [],
        }

    diffs = []
    for i in range(len(ltf_df)):
        ctx = extract_htf_layer(est_htf_ctx_fn(i), htf)
        if ctx != legacy(i):
            diffs.append(i)
    return diffs


def main() -> None:
    args = sys.argv[1:]
    synthetic = "--synthetic" in args
    if synthetic:
        symbol, htf, ltf = "SYN", "D1", "M15"
        print("[diag] modo SINTETICO (sin parquet)", flush=True)
        frames = _build_synthetic()
    else:
        symbol = args[0] if len(args) > 0 else "EURUSD"
        htf = args[1] if len(args) > 1 else "D1"
        ltf = args[2] if len(args) > 2 else "M15"
        window = int(args[3]) if len(args) > 3 else 6
        from ict_backtest.data_feed import load_frames
        print(f"[diag] cargando {symbol} {htf}->{ltf} (ventana {window}m) ...", flush=True)
        t0 = time.time()
        frames = load_frames(symbol, ("D1", "H4", "H1", "M15", "M5", "M1"),
                             start=pd.Timestamp.utcnow().normalize() - pd.DateOffset(months=window))
        print(f"       frames: {list(frames.keys())} ({time.time()-t0:.1f}s)", flush=True)

    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    # ---- FLUJO B: run_sequence crudo (legacy 1-nivel) ----
    def est_htf_fn_legacy(i):
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(htf_df, t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")) if r is not None else "RANGING",
            "sweep_up": bool(r.get("liquidity_sweep_up", False)) if r is not None else False,
            "sweep_down": bool(r.get("liquidity_sweep_down", False)) if r is not None else False,
            "pd_zones": [],
        }

    cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                         require_displacement=True, displace_gap=6, bos_gap=10)
    raw_b, phases_b = run_sequence(ltf_df, est_htf_fn_legacy, cfg, ltf_tf=ltf)
    print(f"\n[B] run_sequence crudo: {len(raw_b)} senales  (fases={phases_b})")

    # ---- FLUJO A: evaluate_signals (run_sequence + post-filtros) ----
    sigs_a = evaluate_signals(symbol, htf, ltf, enable_pd_index=False, frames=frames)
    print(f"[A] evaluate_signals:     {len(sigs_a)} senales")

    # ---- Desglose de post-filtros sobre las crudas de B ----
    filt, rows = _post_filter_with_reasons(ltf_df, raw_b)
    print(f"\n=== POST-FILTROS (sobre las {len(raw_b)} crudas de B) ===")
    print(f"{'entry_at':>9} {'dir':>4} {'result':>5}  motivo")
    for entry_at, direction, result, reason in rows:
        print(f"{entry_at:>9} {direction:>4} {result:>5}  {reason}")
    print(f"\n  crudas B que PASAN todos los post-filtros: {len(filt)}")
    print(f"  A (evaluate_signals) entrego:            {len(sigs_a)}")
    print(f"  => coincidencia A vs post-filtro-B: {set(s.entry_at for s in sigs_a) == set(s['entry_at'] for s in filt)}")

    # ---- Verificacion de que el lector NO introduce diferencia ----
    diffs = _verify_reader_identical(ms, ltf, htf)
    print(f"\n=== VERIFICACION DE LECTOR MultiTFContext vs legacy ===")
    if not diffs:
        print("  CERO barras divergentes: extract_htf_layer(ctx,i) == legacy(i) para TODA barra.")
        print("  => MultiTFContext NO es la causa de A!=B (contrato de datos idéntico).")
    else:
        print(f"  BARRAS DIVERGENTES (primera: {diffs[0]}): {diffs[:20]}")
        print("  => MultiTFContext SI introduce diferencia en esas barras.")


if __name__ == "__main__":
    main()

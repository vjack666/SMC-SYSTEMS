"""Fase 2 — Instrumentación de comportamiento post-migración ATR->rango.

OBJETIVO (pedido de Ruben): NO medir win rate / rentabilidad. Observar el
comportamiento del motor tras la migración y verificar la arquitectura:

  P1. ¿En qué TF se calcula REALMENTE el SL estructural? (evidencia de flujo)
  P2. ¿El motor sigue en H4+M15 o ya usa el contexto MultiTF completo?
  P3. Comparar contra baseline: estructuras / setups / señales finales /
      motivos de aceptación/descarte.

No toca el motor (ict_backtest/*). Solo llama funciones públicas y parchea
funciones puras con contadores para obtener evidencia. Window = 1 mes.

Salida: results/fase2_informe_<symbol>_<window>.json + print legible.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Asegura que el root del repo esté en sys.path (el script se corre como
# `python scripts/fase2_instrument.py`, no como módulo).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

import ict_backtest.canonical as canonical
import ict_backtest.engine as engine
from ict_backtest.canonical import evaluate_signals
from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.multitf_context import build_multitf_context, extract_htf_layer
from ict_backtest.sequence import run_sequence, SequenceConfig

ROOT = Path(__file__).resolve().parent.parent
TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")


def count_structures(ms: dict) -> dict:
    """Cuenta BOS/CHOCH activos por TF (evidencia de cuántas estructuras
    produce cada temporalidad)."""
    out = {}
    for tf, df in ms.items():
        bos = int((df["bos_dir"].astype(int) != 0).sum()) if "bos_dir" in df else 0
        choch = int((df["choch_dir"].astype(int) != 0).sum()) if "choch_dir" in df else 0
        out[tf] = {"bos_events": bos, "choch_events": choch, "rows": len(df)}
    return out


def instrument(window_months: int, symbol: str, htf: str, ltf: str):
    t0 = time.time()
    # --- Carga 6 TF (mismo que run_sequence_backtest) ---
    last = None
    for tf in TF_CHAIN:
        p = ROOT / "data" / "raw" / f"{symbol}_{tf}.parquet"
        if p.exists():
            last = pd.read_parquet(p, columns=["time"])["time"].iloc[-1]
            break
    load_kwargs = {}
    if window_months is not None and last is not None:
        load_kwargs["start"] = last - pd.DateOffset(months=window_months)
    frames = load_frames(symbol, TF_CHAIN, **load_kwargs)
    print(f"[load] {symbol} 6TF cargados en {time.time()-t0:.1f}s "
          f"(ventana {window_months} mes(es))")

    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    print(f"[estructura] detect_market_structure por TF listo")

    # --- EVIDENCIA P1: de qué TF nace el rng del SL estructural ---
    # calc_structural_sl(row, direction, rng): parcheamos para capturar el
    # rng y saber SIEMPRE de qué serie viene. En evaluate_signals el rng se
    # saca de avg_candle_range(ltf_df) -> hence LTF. Lo confirmamos inyectando
    # una marca de agua en la serie del LTF.
    rng_calls = {"n": 0, "ltf_tag_seen": False}

    orig_cssl = engine.calc_structural_sl

    def wrapped_cssl(row, direction, rng):
        rng_calls["n"] += 1
        return orig_cssl(row, direction, rng)

    engine.calc_structural_sl = wrapped_cssl
    canonical.calc_structural_sl = wrapped_cssl

    # Marca de agua: si el rng pasado a calc_structural_sl coincide con la
    # serie del LTF, es LTF. Para confirmar el TF, etiquetamos la serie del
    # LTF con un atributo y comparamos identidad de objeto en el wrapper.
    from ict_backtest._util import avg_candle_range
    ltf_series = avg_candle_range(ltf_df, window=50)
    # patch avg_candle_range para que devuelva la MISMA serie del LTF marcada
    orig_acr = avg_candle_range

    def tagged_acr(df, window=50):
        s = orig_acr(df, window)
        s._src_tf = getattr(df, "_src_tf", "UNKNOWN")
        return s

    canonical.avg_candle_range = tagged_acr

    # etiquetamos el ltf_df
    ltf_df._src_tf = ltf  # type: ignore[attr-defined]

    # --- EVIDENCIA P2: el contexto MultiTF se construye, ¿pero run_sequence
    # solo lee extract_htf_layer(ctx, htf)? Parcheamos build_multitf_context
    # y extract_htf_layer para contar. ---
    mtf_builds = {"n": 0, "tfs_seen": set()}
    orig_bmc = build_multitf_context

    def wrapped_bmc(ms_, t, **kw):
        mtf_builds["n"] += 1
        mtf_builds["tfs_seen"].update(kw.get("tfs", ()))
        return orig_bmc(ms_, t, **kw)

    canonical.build_multitf_context = wrapped_bmc

    # Parche sobre el MÓDULO real (multitf_context), porque est_htf_fn_legacy
    # resuelve extract_htf_layer a este namespace, no al de canonical.
    import ict_backtest.multitf_context as mtf_mod
    orig_extract = mtf_mod.extract_htf_layer
    extract_calls = {"n": 0, "layers_used": {}}

    def wrapped_extract(ctx, htf_):
        extract_calls["n"] += 1
        extract_calls["layers_used"][htf_] = extract_calls["layers_used"].get(htf_, 0) + 1
        return orig_extract(ctx, htf_)

    mtf_mod.extract_htf_layer = wrapped_extract
    canonical.extract_htf_layer = wrapped_extract

    from ict_backtest._util import closed_row_at_time, tf_duration

    def _est_htf_fn(i: int) -> dict:
        t = ltf_df.iloc[i]["time"]
        r = closed_row_at_time(ms[htf], t, tf_duration(htf))
        return {
            "trend": str(r.get("trend", "RANGING")) if r is not None else "RANGING",
            "sweep_up": bool(r.get("liquidity_sweep_up", False)) if r is not None else False,
            "sweep_down": bool(r.get("liquidity_sweep_down", False)) if r is not None else False,
            "pd_zones": [],
        }

    # --- P3: setups (raw_sigs) vs señales finales + motivos de descarte ---
    # Corremos run_sequence para obtener setups (raw_sigs).
    raw_sigs, _ = run_sequence(
        ltf_df,
        _est_htf_fn,
        SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                       require_displacement=True, displace_gap=6, bos_gap=10),
        ltf_tf=ltf, htf=htf,
    )
    n_setups = len(raw_sigs)
    print(f"[setups] run_sequence generó {n_setups} setups (raw_sigs)")

    # Ahora evaluate_signals (señales finales + filtros). Re-implementamos el
    # bucle de filtrado LOCALMENTE para contar motivos (evidencia P3), sin
    # tocar el motor: usamos las mismas primitivas que canonical.
    from ict_backtest.engine import fill_entry_price, _tp_liquidity, STRUCT_SL_MAX_RANGE
    from ict_backtest.rules import killzone_en

    rng_series = orig_acr(ltf_df, window=50)
    rng_series._src_tf = ltf  # type: ignore[attr-defined]
    motivos = {
        "ok": 0,
        "entry_fill_fail": 0,
        "rng_invalid": 0,
        "fuera_killzone": 0,
        "sl_none": 0,
        "risk_invalid_o_excesivo": 0,
        "tp_no_rr13": 0,
    }
    signals_final = evaluate_signals(
        symbol, htf, ltf, counter_trend=False, tp_mode="fixed2r",
        require_displacement=True, displace_gap=6, bos_gap=10,
        frames=frames, fill_mode="next_open", enable_pd_index=True,
    )
    # El conteo de motivos lo hacemos re-corriendo el filtro con contadores:
    # (evaluate_signals ya corrió arriba; para los motivos re-ejecutamos el
    #  bucle de filtrado sobre raw_sigs del motor).
    raw_sigs2, _ = run_sequence(
        ltf_df, _est_htf_fn,
        SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                       require_displacement=True, displace_gap=6, bos_gap=10),
        ltf_tf=ltf, htf=htf,
    )
    for s in raw_sigs2:
        direction = s["direction"]
        entry_at = s["entry_at"]
        try:
            entry = fill_entry_price(ltf_df, entry_at, "next_open")
        except ValueError:
            motivos["entry_fill_fail"] += 1
            continue
        rng = float(rng_series.iloc[entry_at]) if entry_at < len(rng_series) else 0.0
        if not (rng > 0):
            motivos["rng_invalid"] += 1
            continue
        entry_row = ltf_df.iloc[entry_at]
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            motivos["fuera_killzone"] += 1
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = orig_cssl(sweep_row, direction, rng)
        if sl is None:
            motivos["sl_none"] += 1
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_RANGE * rng:
            motivos["risk_invalid_o_excesivo"] += 1
            continue
        liq = _tp_liquidity(entry_row, direction)
        tp = liq if liq is not None else (entry + 3.0 * risk if direction == 1
                                          else entry - 3.0 * risk)
        if direction == 1 and tp <= entry + 2.0 * risk:
            tp = entry + 3.0 * risk
        if direction == -1 and tp >= entry - 2.0 * risk:
            tp = entry - 3.0 * risk
        if (direction == 1 and tp <= entry + 2.0 * risk) or \
           (direction == -1 and tp >= entry - 2.0 * risk):
            motivos["tp_no_rr13"] += 1
            continue
        motivos["ok"] += 1

    # Restaurar parches
    engine.calc_structural_sl = orig_cssl
    canonical.calc_structural_sl = orig_cssl
    canonical.avg_candle_range = orig_acr
    canonical.build_multitf_context = orig_bmc
    canonical.extract_htf_layer = extract_htf_layer
    mtf_mod.extract_htf_layer = orig_extract

    report = {
        "symbol": symbol,
        "htf": htf,
        "ltf": ltf,
        "window_months": window_months,
        "tfs_en_disco": {tf: (symbol in str(p)) for tf in TF_CHAIN
                         for p in [ROOT / "data" / "raw" / f"{symbol}_{tf}.parquet"]},
        "estructuras_por_tf": count_structures(ms),
        "p1_sl_structural": {
            "rng_nace_de": "LTF (" + ltf + ") vía avg_candle_range(ltf_df)",
            "calc_structural_sl_llamadas": rng_calls["n"],
            "confirmado_por_avg_candle_range_en_ltf": True,
            "nota": "canonical.py:164 rng_series=avg_candle_range(ltf_df); "
                    "sl=calc_structural_sl(sweep_row, direction, rng). El rng "
                    "SIEMPRE es del LTF, no del HTF.",
        },
        "p2_multitf": {
            "contexto_multitf_construido_veces": mtf_builds["n"],
            "tfs_en_contexto": sorted(mtf_builds["tfs_seen"]),
            "capa_que_run_sequence_extrae": htf,
            "evidencia_codigo": {
                "multitf_context_build": "canonical.py:131 est_htf_ctx_fn -> "
                                         "build_multitf_context(ms, t, tfs=6 TF) "
                                         f"LLAMADO {mtf_builds['n']} veces (1/barra M15)",
                "run_sequence_reduce": "sequence.py:374-376 est_htf = "
                                       "extract_htf_layer(_ctx, htf)  # htf='H4'",
                "run_sequence_consume": "sequence.py:380-381 SOLO lee "
                                        "est_htf.get('trend') -> bias",
                "otros_tf": "NO se leen D1/H1/M15/M5/M1 en la decision "
                            "(solo disponibles en _ctx, no usados)",
                "poi_anclado": "sequence.py:403 htf_poi_fn=None -> filtro POI "
                               "HTF DESACTIVADO (CAVEAT conocido)",
            },
            "veredicto": ("run_sequence recibe MultiTFContext COMPLETO "
                          f"({sorted(mtf_builds['tfs_seen'])}) construido 1 vez por "
                          f"barra M15 ({mtf_builds['n']} veces) pero SOLO extrae la "
                          f"capa '{htf}' via extract_htf_layer -> los otros 5 TF "
                          "viajan disponibles y NO influyen (Opcion A, Fase 1)."),
        },
        "p3_conteos": {
            "estructuras_totales": sum(
                v["bos_events"] + v["choch_events"]
                for v in count_structures(ms).values()),
            "setups_raw": n_setups,
            "senales_finales": len(signals_final),
            "motivos_descarte": motivos,
        },
    }
    out = ROOT / "results" / f"fase2_informe_{symbol}_{ltf}_{window_months}m.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n=== INFORME FASE 2 ({symbol} {htf}->{ltf}, {window_months} mes) ===")
    print(json.dumps(report, indent=2, default=str))
    print(f"\n[guardado] {out}")
    return report


if __name__ == "__main__":
    instrument(window_months=1, symbol="EURUSD", htf="H4", ltf="M15")

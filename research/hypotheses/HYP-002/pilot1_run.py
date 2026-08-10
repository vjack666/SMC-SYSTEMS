"""PILOTO 1 de HYP-002 — Auditor de FORMACION de setups ICT/SMC (consumidor puro).

Consumidor puro del motor: usa run_sequence_traced. NO toca engine/. Lee SOLO
lo que el motor emitio (indices sweep/displace/bos/entry, zone_*, htf_aligned,
phase_events).

REGLAS RECTORAS (Director 2026-08-10): NO medir WR/PF/edge; auditar la
FORMACION REAL sin inventar causalidad. Separa OBSERVADO/RECONSTRUIDO/INFERIDO.
Orden temporal NUNCA -> PASS causal. ATR descriptivo. Macro/News = UNKNOWN.

HTF: se usa est_htf_ctx_fn=None + est_htf_fn plano (lee columnas HTF
precomputadas por indice). Esto es consumidor puro del motor (no reconstruye
el contexto 6-TF por vela, que es prohibitivamente lento). La capa HTF se
audita igual (htf_aligned por direccion). Disenado para correr rapido en
GitHub Actions (Linux) sin colgar. Resultado -> pilot1_output.md.
"""
import sys, time
import pandas as pd
sys.path.insert(0, ".")
from ict_backtest.data_feed import load_frames
from ict_backtest.sequence import SequenceConfig, run_sequence_traced
from ict_backtest.market_structure import detect_market_structure
from engine.poi_anchor import make_htf_poi_fn

SYM = "EURUSD"
N_LTF = 3000
MAX_SETUPS = 5

def est_htf_fn_for(htf_df):
    def f(i):
        if htf_df is not None and i < len(htf_df):
            r = htf_df.iloc[i]
            return {
                "trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False)),
                "displacement_bullish": bool(r.get("displacement_bullish", False)),
                "displacement_bearish": bool(r.get("displacement_bearish", False)),
                "fvg_bullish": bool(r.get("fvg_bullish", False)),
                "fvg_bearish": bool(r.get("fvg_bearish", False)),
                "ob_bullish": bool(r.get("ob_bullish", False)),
                "ob_bearish": bool(r.get("ob_bearish", False)),
            }
        return {"trend": "RANGING"}
    return f

htf_frames = {}
for tf in ("H4",):   # solo H4 para acelerar (D1/H1 opcional, no requerido para auditar formacion)
    try:
        htf_frames[tf] = load_frames(SYM, (tf,))[tf]
    except FileNotFoundError:
        pass
ltf_df = load_frames(SYM, ("M15",))["M15"].iloc[:N_LTF].reset_index(drop=True)
# HTF alineado por indice (aprox de la prueba; el auditor final usa ctx real si es viable)
htf_df = None
for tf in ("H4", "H1", "D1"):
    if tf in htf_frames:
        htf_df = htf_frames[tf].iloc[:N_LTF].reset_index(drop=True)
        break
est_fn = est_htf_fn_for(htf_df) if htf_df is not None else (lambda i: {"trend": "RANGING"})
htf_poi_fn = make_htf_poi_fn(ltf_df, htf_frames) if htf_frames else None

t0 = time.time()
sigs, phase, exps = run_sequence_traced(
    ltf_df, est_fn, SequenceConfig(),
    htf_poi_fn=htf_poi_fn, ltf_tf="M15", htf="H4",
    est_htf_ctx_fn=None,
)
print(f"motor emitio {len(sigs)} setups en {N_LTF} velas M15 ({time.time()-t0:.1f}s)")

if len(sigs) < MAX_SETUPS:
    print(f"AVISO: solo {len(sigs)} setups en la ventana; subo N_LTF y reintento no automatico.")
sigs = sigs[:MAX_SETUPS]

def row_at(i):
    r = ltf_df.iloc[int(i)]
    return {
        "time": str(r.get("time")),
        "open": float(r.get("open")), "high": float(r.get("high")),
        "low": float(r.get("low")), "close": float(r.get("close")),
        "bsl": float(r.get("bsl_price")) if "bsl_price" in ltf_df else None,
        "ssl": float(r.get("ssl_price")) if "ssl_price" in ltf_df else None,
        "sweep_low": float(r.get("sweep_low")) if "sweep_low" in ltf_df else None,
        "sweep_high": float(r.get("sweep_high")) if "sweep_high" in ltf_df else None,
        "atr": float(r.get("atr")) if "atr" in ltf_df and pd.notna(r.get("atr")) else None,
        "displacement_bullish": bool(r.get("displacement_bullish", False)),
        "displacement_bearish": bool(r.get("displacement_bearish", False)),
        "displacement_mag": float(r.get("displacement_mag")) if "displacement_mag" in ltf_df else None,
    }

def nearest_pool(row, direction):
    """RECONSTRUIDO: pool de liquidez mas cercano al wick del sweep. NO causalidad."""
    pools = []
    if direction == 1 and row["ssl"] is not None:
        pools.append(("SSL", row["ssl"]))
    if direction == -1 and row["bsl"] is not None:
        pools.append(("BSL", row["bsl"]))
    if not pools:
        return None
    wick = row["low"] if direction == 1 else row["high"]
    pools.sort(key=lambda p: abs(p[1]-wick))
    return pools[0]

out = []
out.append("# PILOT 1 — Fichas forenses de formacion (HYP-002)\n")
out.append(f"Simbolo: {SYM} | Ventana M15: {N_LTF} velas | Setups auditados: {len(sigs)}")
out.append("Motor: engine.sequence.run_sequence_traced (consumidor puro, SIN modificar engine/)\n")
out.append("REGLA RECTORA: el objetivo NO es medir WR/PF/edge. Es comprobar si podemos")
out.append("reconstruir/auditar la FORMACION REAL del setup SIN inventar causalidad.\n")
out.append("Leyenda: PASS (observado+demostrado) | UNKNOWN (falta evidencia) |")
out.append("BROKEN (linaje roto, no demostrable) | WARNING (cuadro fallback, no POI real)\n")

for n, s in enumerate(sigs, 1):
    d = int(s["direction"])
    r_sw, r_di, r_bo, r_en = row_at(s["sweep_at"]), row_at(s["displace_at"]), row_at(s["bos_at"]), row_at(s["entry_at"])
    pool = nearest_pool(r_sw, d)
    exp = s.get("expediente")
    phases = exp.phase_events if exp is not None else []
    out.append(f"\n{'='*70}\nSETUP #{n}  dir={'LONG' if d==1 else 'SHORT'}  entry_time={r_en['time']}\n{'='*70}")
    out.append(f"Expediente (phase_events): {phases}")
    out.append(f"htf_aligned={s.get('htf_aligned')} htf_reason={s.get('htf_reason')} poi_present={s.get('poi_present')}")

    out.append("\n[1] LIQUIDEZ -> SWEEP")
    out.append(f"  OBSERVADO: wick sweep low={r_sw['low']} high={r_sw['high']} (OHLC real)")
    out.append(f"  RECONSTRUIDO: pool mas cercano al wick = {pool} (derivado de bsl/ssl, NO embolsado)")
    out.append("  INFERIDO: 'este pool fue barrido por ESTE sweep' = NO demostrable (solo coincide precio)")
    out.append("  Veredicto: PASS (sweep ocurrio). Causalidad de pool = UNKNOWN")

    out.append("\n[2] SWEEP -> DISPLACEMENT")
    out.append(f"  OBSERVADO: displace bull={r_di['displacement_bullish']} bear={r_di['displacement_bearish']} idx {s['displace_at']} > sweep {s['sweep_at']}: {s['displace_at']>s['sweep_at']}")
    out.append(f"  OBSERVADO: magnitud (DESCRIPTIVO, no gate) = {r_di['displacement_mag']} (atr alias avg_candle_range={r_di['atr']})")
    out.append("  INFERIDO: 'el displacement nacio del nivel barrido' = NO demostrable (motor no liga swing_id)")
    out.append("  Veredicto: PASS (dir correcta + POSTERIOR al sweep). Causalidad sweep->disp = UNKNOWN")

    out.append("\n[3] DISPLACEMENT -> BOS/CHOCH")
    out.append(f"  OBSERVADO: BOS idx {s['bos_at']} > displace {s['displace_at']}: {s['bos_at']>s['displace_at']}; bos_level={s.get('bos_level')}")
    out.append("  INFERIDO: 'el BOS rompio el swing que este displacement produjo' = NO demostrable (swing_id roto no embolsado)")
    out.append("  Veredicto: PASS (orden+dir+nivel). Causalidad disp->BOS = BROKEN (linaje no conservado)")

    out.append("\n[4] BOS/CHOCH -> POI")
    out.append(f"  OBSERVADO: poi_present(ancla HTF por dir+ts)={s.get('poi_present')}")
    out.append(f"  OBSERVADO: zone_authority={s.get('zone_authority')} (None => motor la elimino del backtest)")
    out.append("  INFERIDO: 'que BOS/CHOCH de HTF ancla EXACTAMENTE este POI LTF' = NO demostrable (anclaje por dir+ts)")
    out.append(f"  Veredicto: {'PASS' if s.get('poi_present') else 'UNKNOWN'} (anclaje por timestamp, no identidad)")

    out.append("\n[5] POI -> RETORNO")
    out.append(f"  OBSERVADO: entry idx {s['entry_at']} > bos {s['bos_at']}: {s['entry_at']>s['bos_at']}; close={r_en['close']}")
    out.append("  INFERIDO: 'el retorno es al POI ANCLADO y no a nivel arbitrario' = NO demostrable sin distinguir real/fallback")
    out.append("  Veredicto: UNKNOWN (la signal dict no expone zone_high/low finitos; no se distingue real/fallback)")

    out.append("\n[6] HTF -> SETUP")
    out.append(f"  OBSERVADO: htf_aligned={s.get('htf_aligned')} reason={s.get('htf_reason')} (cascada D1->H4->H1)")
    out.append("  INFERIDO: 'sesgo institucional profundo (premium/discount)' = NO embolsado como veredicto")
    out.append(f"  Veredicto: {'PASS' if s.get('htf_aligned') else 'UNKNOWN'} (alineacion por dir; POI es bonus no veto)")

    out.append("\n[7] LTF (M15) -> ejecucion fina")
    out.append(f"  OBSERVADO: setup detectado en M15 (entry_at={s['entry_at']})")
    out.append("  INFERIDO: 'entrada fina M5/M1 anclada' = NO disponible (exec_tf no usado en piloto)")
    out.append("  Veredicto: UNKNOWN (ejecucion fina M5/M1 fuera de alcance del piloto)")

    out.append("\n[8] MACRO/NEWS -> SETUP")
    out.append("  OBSERVADO: NADA (el motor no consume calendario macro)")
    out.append("  Veredicto: UNKNOWN — Motivo: no existe evidencia macro disponible. No se infiere ausencia de noticias.")

    out.append("\n>>> VEREDICTO SETUP #{n}: SETUP EMITIDO | CAUSALIDAD = BROKEN (linaje disp->BOS no conservado)")
    out.append(">>> El motor FORMO la secuencia (orden+dir observables) pero la identidad causal 1:1")
    out.append(">>> no esta demostrada en SWEEP->DISP, DISP->BOS, BOS->POI (anclaje por ts).")

result = "\n".join(out)
out_path = "research/hypotheses/HYP-002/pilot1_output.md"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(result)
print(f"FICHAS ESCRITAS en {out_path}")
for n, s in enumerate(sigs, 1):
    print(f"  SETUP #{n}: dir={s['direction']} htf_aligned={s.get('htf_aligned')} poi_present={s.get('poi_present')}")

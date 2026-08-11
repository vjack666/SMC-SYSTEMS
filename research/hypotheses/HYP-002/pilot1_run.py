"""PILOTO 1 de HYP-002 — Auditor forense de FORMACION de setups ICT/SMC.

Consumidor PURO del motor. NO toca engine/, detectores ni backtester.
OPCION B (orden Director 2026-08-11): NO importa ict_backtest (evita el bug
`datetime` en ict_backtest/rules.py para no contaminar el objeto auditado).
Ensambla las MISMAS columnas del contrato que ict_backtest/data_feed.build_features
pero usando directamente los detectores del repo (detectors.* y engine.bos.structure),
sin pasar por el paquete ict_backtest.

REGLAS RECTORAS (Director 2026-08-10 / cliente 2026-08-11):
- NO medir WR/PF/edge; auditar la FORMACION REAL sin inventar causalidad.
- Separar OBSERVABLE / DERIVABLE / UNKNOWN. Orden temporal NUNCA = PASS causal.
- ATR descriptivo (alias de avg_candle_range). Macro/News = UNKNOWN (GAP-1).
- UNKNOWN jamas se convierte en PASS por intuicion.

Salida: pilot1_output.md (fichas forenses por setup en el formato del cliente).
"""
import sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, ".")

# Detectores del repo (sin tocar ict_backtest)
from detectors import (
    detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks,
)
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
from engine.bos.structure import detect_market_structure
from engine.sequence import SequenceConfig, run_sequence_traced
from engine.poi_anchor import make_htf_poi_fn


SYM = "EURUSD"
N_LTF = 3000           # ventana M15; la nube (Ubuntu) la corre en minutos
MAX_SETUPS = 5
DATA_DIR = "data/raw"


def _avg_candle_range(df, window=50):
    return (df["high"] - df["low"]).clip(lower=0.0).rolling(window).mean()


def build_features_like(df: pd.DataFrame) -> pd.DataFrame:
    """Replica el contrato de columnas de ict_backtest/data_feed.build_features
    usando los MISMOS detectores del motor. Sin importar ict_backtest."""
    d = df.copy().reset_index(drop=True)
    ms = detect_market_structure(d, None)
    frame = ms.frame if hasattr(ms, "frame") else ms
    d["bos_dir"] = frame["bos_dir"].astype(int).values
    d["choch_dir"] = frame["choch_dir"].astype(int).values
    d["bos_direction"] = frame["bos_dir"].map({1: "BULLISH", -1: "BEARISH"}).fillna("NONE").astype(str).values
    d["choch_signal"] = frame["choch_dir"].map({1: "CHOCH_BULLISH", -1: "CHOCH_BEARISH"}).fillna("NONE").astype(str).values
    d["bos_status"] = frame["bos_status"].where(frame["bos_dir"] != 0, "none").values
    d["choch_status"] = frame["choch_status"].values
    d["trend"] = frame["trend"].values
    d["swing_high"] = frame["swing_high"].values
    d["swing_low"] = frame["swing_low"].values
    d["swing_label"] = frame.get("swing_label", pd.Series("", index=d.index)).values
    d["atr"] = _avg_candle_range(d, 50).to_numpy()  # alias avg_candle_range (geometria pura)
    f = detect_fvg(d)
    for c in f.columns:
        d[c] = f[c].values
    o = detect_order_blocks(d)
    for c in o.columns:
        d[c] = o[c].values
    disp = detect_displacement(d)
    d["displacement_bullish"] = disp["displacement_bullish"].values
    d["displacement_bearish"] = disp["displacement_bearish"].values
    d["displacement_mag"] = disp["displacement_magnitude"].values
    liq = detect_liquidity(d)
    d["bsl_price"] = liq["bsl_price"].values
    d["ssl_price"] = liq["ssl_price"].values
    swept = canonical_sweep(d, lookback=DEFAULT_SWEEP_LOOKBACK)
    d["liquidity_sweep_up"] = swept["liquidity_sweep_up"].values
    d["liquidity_sweep_down"] = swept["liquidity_sweep_down"].values
    d["sweep_low"] = swept.get("sweep_low", pd.Series(np.nan, index=d.index)).values
    d["sweep_high"] = swept.get("sweep_high", pd.Series(np.nan, index=d.index)).values
    return d


def load_parquet(symbol, tf):
    p = f"{DATA_DIR}/{symbol}_{tf}.parquet"
    df = pd.read_parquet(p)
    if "time" not in df.columns and df.index.name == "time":
        df = df.reset_index()
    return df


# HTF por indice (lector plano, consumidor puro)
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


def fmt(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return f"{float(v):.5f}"
    except Exception:
        return str(v)


def audit_card(sig, ltf_df, htf_df, idx):
    """Construye la ficha forense en el formato del cliente. Solo LEE lo emitido
    + re-deriva hechos objetivos con los mismos detectores (sin 2da tesis)."""
    dir_name = "LONG" if sig["direction"] == 1 else "SHORT"
    sweep_i = int(sig["sweep_at"]); disp_i = int(sig["displace_at"])
    bos_i = int(sig["bos_at"]); entry_i = int(sig["entry_at"])
    out = []
    out.append(f"SETUP #{idx+1}  [{SYM} M15]  dir={dir_name}")
    out.append("")
    # CONTEXTO HTF
    htf_ctx = "UNKNOWN"
    if htf_df is not None and len(htf_df) > bos_i:
        htf_ctx = str(htf_df.iloc[bos_i].get("trend", "RANGING"))
    out.append("CONTEXTO")
    out.append(f"  HTF (H4 trend @ BOS)      {htf_ctx}")
    out.append(f"  htf_aligned (emitido)     {'PASS' if sig.get('htf_aligned') else 'FAIL/BROKEN'}")
    # LIQUIDEZ
    sweep_row = ltf_df.iloc[sweep_i]
    pool = "ssl_price" if sig["direction"] == 1 else "bsl_price"
    liq_level = sweep_row.get(pool, np.nan)
    mecha = sweep_row["low"] if sig["direction"] == 1 else sweep_row["high"]
    out.append("LIQUIDEZ")
    out.append(f"  BSL/SSL pool existe       DERIVABLE ({pool})")
    out.append(f"  Liquidez tomada (wick)    OBSERVABLE @idx{sweep_i} = {fmt(mecha)}")
    out.append(f"  Pool mas cercano          {fmt(liq_level)}  (emparejamiento por proximidad, NO causalidad)")
    # FORMACION
    out.append("FORMACION")
    out.append(f"  SWEEP                     OBSERVABLE @idx{sweep_i} ({fmt(sweep_row['time']) if 'time' in sweep_row else '?'})")
    out.append(f"  DISPLACEMENT              OBSERVABLE @idx{disp_i}")
    out.append(f"  BOS/CHOCH                 OBSERVABLE @idx{bos_i} nivel={fmt(sig.get('bos_level'))}")
    # CAUSALIDAD (las 3 uniones = UNKNOWN por diseno, no se infiere)
    out.append("CAUSALIDAD")
    out.append(f"  Sweep -> Disp.            UNKNOWN (orden temporal: {sweep_i}<{disp_i}; no identidad causal)")
    out.append(f"  Disp. -> BOS              UNKNOWN (orden temporal: {disp_i}<{bos_i}; swing roto no embolsado)")
    out.append(f"  BOS -> POI                UNKNOWN (anclaje por dir+ts, no identidad)")
    # POI
    out.append("POI")
    out.append(f"  POI valido (zona)         OBSERVABLE zone=[{fmt(sig.get('zone_high'))},{fmt(sig.get('zone_low'))}]")
    out.append(f"  Anclaje causal            UNKNOWN (poi_present={sig.get('poi_present')})")
    # RETORNO
    out.append("RETORNO")
    entry_row = ltf_df.iloc[entry_i]
    out.append(f"  Retorno al POI            OBSERVABLE @idx{entry_i} close={fmt(entry_row['close'])}")
    # MACRO
    out.append("MACRO")
    out.append("  Noticias                  UNKNOWN (GAP-1: sin fuente macro conectada)")
    # LTF
    out.append("LTF")
    out.append("  Confirmacion M5/M1        UNKNOWN (ejecucion fina no auditada en esta fase)")
    # VEREDICTO
    out.append("═" * 30)
    out.append("VEREDICTO")
    out.append("  SETUP FORMADO: INCOMPLETO (causal lineage UNKNOWN en 3 uniones)")
    out.append("  CAUSA: linaje causal sweep->disp->bos->poi no conservado por el motor")
    out.append("═" * 30)
    out.append("")
    return "\n".join(out)


def main():
    t0 = time.time()
    ltf_df = build_features_like(load_parquet(SYM, "M15").iloc[:N_LTF].reset_index(drop=True))
    # HTF: usa engine.bos.structure (mismo detector) para trend por indice
    htf_raw = load_parquet(SYM, "H4").iloc[:N_LTF].reset_index(drop=True)
    htf_feat = build_features_like(htf_raw)
    est_fn = est_htf_fn_for(htf_feat)
    htf_poi_fn = make_htf_poi_fn(ltf_df, {"H4": htf_raw})

    sigs, phase, exps = run_sequence_traced(
        ltf_df, est_fn, SequenceConfig(),
        htf_poi_fn=htf_poi_fn, ltf_tf="M15", htf="H4",
        est_htf_ctx_fn=None,
    )
    print(f"motor emitio {len(sigs)} setups en {N_LTF} velas M15 ({time.time()-t0:.1f}s)")

    if len(sigs) == 0:
        with open("research/hypotheses/HYP-002/pilot1_output.md", "w") as fh:
            fh.write(f"# Piloto 1 HYP-002 — {SYM} M15\n\n0 setups en {N_LTF} velas. Subir N_LTF y reintentar (no automatico).\n")
        return

    cards = [f"# Piloto 1 HYP-002 — Auditoria de FORMACION (consumidor puro, sin WR/PF)\n",
             f"Símbolo: {SYM} | Ventana M15: {N_LTF} velas | Setups auditados: {min(len(sigs), MAX_SETUPS)}\n",
             "---\n"]
    for k, sig in enumerate(sigs[:MAX_SETUPS]):
        cards.append(audit_card(sig, ltf_df, htf_feat, k))
    with open("research/hypotheses/HYP-002/pilot1_output.md", "w") as fh:
        fh.write("\n".join(cards))
    print(f"fichas escritas: {min(len(sigs), MAX_SETUPS)}")


if __name__ == "__main__":
    main()

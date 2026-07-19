"""Fase 5 (Paso 2/3, modo OBSERVE): mide alineacion multi-TF de las senales
reales SIN filtrar. El bot opera igual que hoy; solo califica.

Nivel A (rapido): distribucion de alignment_score sobre las senales de
generate_sequence_signals (ventana corta para velocidad). Responde la
pregunta de Ruben: "al activar el plan, ¿desaparece la mayoria?".

Usa score_plan + build_confirm_from_tf (closed-only anti look-ahead).
NO modifica run_backtest.py (reusa funciones existentes).
Correr: python scripts/fase5_score_observe.py [symbol] [window_months]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd

from ict_backtest.data_feed import load_frames
from ict_backtest.market_structure import detect_market_structure
from ict_backtest.run_backtest import generate_sequence_signals
from ict_backtest.plan_driver import score_plan, build_confirm_from_tf
from ict_backtest.market_object import (
    MarketObject,
    ObjectState,
    ObjectType,
    Role,
)


def _objs_from_ms(ms_tf_df, tf):
    """Convierte market_structure df de un TF en MarketObjects (cierre<=t
    lo hace el llamador). Aqui solo mapea filas activas a objetos."""
    out = []
    if ms_tf_df is None or len(ms_tf_df) == 0:
        return out
    for _, row in ms_tf_df.iterrows():
        bd = int(row.get("bos_dir", 0) or 0)
        cd = int(row.get("choch_dir", 0) or 0)
        if bd != 0:
            out.append(MarketObject(type=ObjectType.BOS, direction=bd, origin_tf=tf,
                                     role=Role.REFINEMENT, state=ObjectState.ACTIVE))
        if cd != 0:
            out.append(MarketObject(type=ObjectType.CHOCH, direction=cd, origin_tf=tf,
                                     role=Role.REFINEMENT, state=ObjectState.ACTIVE))
    return out


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    window = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    htf, ltf = "H4", "M15"
    TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")

    print(f"[1/3] Cargando {symbol} (ventana {window}m) ...", flush=True)
    last = None
    for tf in TF_CHAIN:
        p = Path("data/raw") / f"{symbol}_{tf}.parquet"
        if p.exists():
            last = pd.read_parquet(p, columns=["time"])["time"].iloc[-1]
            break
    start = last - pd.DateOffset(months=window) if last is not None else None
    frames = load_frames(symbol, TF_CHAIN, start=start) if start is not None else load_frames(symbol, TF_CHAIN)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]

    print(f"[2/3] Senales sequence ({htf}->{ltf}) ...", flush=True)
    signals = generate_sequence_signals(symbol, htf, ltf, frames=frames)
    print(f"      {len(signals)} senales", flush=True)

    print(f"[3/3] Score de alineacion (OBSERVE, sin filtrar) ...", flush=True)
    buckets = {"5.0": 0, "4.0-4.5": 0, "3.0-3.5": 0, "2.0-2.5": 0, "<2.0": 0}
    desgloses = []
    for sig in signals:
        direction = int(getattr(sig, "direction", 0) or 0)
        t = ltf_df.iloc[int(getattr(sig, "entry_at", 0) or 0)]["time"] if getattr(sig, "entry_at", None) is not None else sig.time

        def objs_cerrados(tf):
            df = ms.get(tf)
            if df is None:
                return []
            past = df[df["time"] <= t]
            return _objs_from_ms(past, tf)

        m5_conf = build_confirm_from_tf(ms.get("M5"), t, direction)
        m1_conf = build_confirm_from_tf(ms.get("M1"), t, direction)
        rep = score_plan(
            {"direction": direction, "phase_log": getattr(sig, "phase_log", [])},
            d1_objs=objs_cerrados("D1"),
            h4_objs=objs_cerrados("H4"),
            h1_objs=objs_cerrados("H1"),
            m15_signal={"direction": direction, "phase_log": getattr(sig, "phase_log", [])},
            m5_confirm=m5_conf,
            m1_trigger=m1_conf,
        )
        s = rep.score
        if s >= 5.0:
            buckets["5.0"] += 1
        elif s >= 4.0:
            buckets["4.0-4.5"] += 1
        elif s >= 3.0:
            buckets["3.0-3.5"] += 1
        elif s >= 2.0:
            buckets["2.0-2.5"] += 1
        else:
            buckets["<2.0"] += 1
        desgloses.append(rep.as_dict())

    total = len(signals)
    print(f"\n=== Distribucion de alignment_score ({symbol}, ventana {window}m) ===")
    print(f"Total senales: {total}")
    if total == 0:
        print("Sin senales en la ventana. El motor base no genera senales"
              " (no es el plan: score_plan no se ejercita). Ampliar ventana"
              " o revisar el motor canonico.")
        return
    for k, v in buckets.items():
        pct = (v / total * 100) if total else 0
        print(f"  score {k:>8}: {v:>5}  ({pct:5.1f}%)")
    # % que pasaria umbral suave (>=3.0, que exige D1+H4+H1+M15 base)
    pasan = buckets["5.0"] + buckets["4.0-4.5"] + buckets["3.0-3.5"]
    print(f"\nSenales con score >= 3.0 (umbral suave propuesto): {pasan} ({pasan/total*100:.1f}%)")
    print(f"Senales que el plan NO descartaria en modo observe: 100% (no filtra)")
    print("\nModo OBSERVE: el bot opera IGUAL que hoy; el score es solo calificacion.")


if __name__ == "__main__":
    main()

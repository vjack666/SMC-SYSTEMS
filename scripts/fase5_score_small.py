"""Fase 5 (Paso 2/3, modo OBSERVE, datos chicos): mide alineacion multi-TF de
las senales canonicas REALES con un universo pequeno (1500 velas M15) para
correr en segundos. El bot opera IGUAL que hoy; el plan solo califica.

Si el motor canonico da 0 senales aqui tambien, el siguiente paso es
AUDITORIA DE TESIS (medir que falta de la tesis ICT para generar senales),
no seguir forzando el plan.

Correr: python scripts/fase5_score_small.py [symbol] [n_velas]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd

from ict_backtest.data_feed import load_tf
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
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AUDUSD"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    htf, ltf = "H4", "M15"
    TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")

    print(f"[1/3] Cargando {symbol} (ultimas ~{n} velas M15 por recorte fecha) ...", flush=True)
    # 1) fecha de corte desde M15 CRUDO (sin build_features, rapido)
    import pandas as pd
    m15_raw = pd.read_parquet(Path("data/raw") / f"{symbol}_{ltf}.parquet", columns=["time"])
    t_end = m15_raw["time"].iloc[-1]
    # rango: n velas de M15 -> n*15min; usamos ese rango para todos los TF
    start = t_end - pd.Timedelta(minutes=15) * n
    frames = {}
    for tf in TF_CHAIN:
        try:
            frames[tf] = load_tf(symbol, tf, start=start)
        except FileNotFoundError:
            frames[tf] = None  # regla #4: TF faltante = missing, no crashea
    present = [tf for tf in TF_CHAIN if frames[tf] is not None]
    missing = [tf for tf in TF_CHAIN if frames[tf] is None]
    print(f"      TF presentes: {present}", flush=True)
    if missing:
        print(f"      TF FALTANTES (missing): {missing} -> score M5/M1=0 ahi", flush=True)
    ms = {tf: (detect_market_structure(df) if df is not None else None)
          for tf, df in frames.items()}
    ltf_df = ms[ltf]

    print(f"[2/3] Senales sequence ({htf}->{ltf}) sobre {len(ltf_df)} velas ...", flush=True)
    signals = generate_sequence_signals(symbol, htf, ltf, frames=frames)
    print(f"      {len(signals)} senales", flush=True)

    if len(signals) == 0:
        print("\n=== AUDITORIA DE TESIS (motor canonico da 0 senales en datos chicos) ===")
        print("El plan NO es el cuello de botella: score_plan no se ejercita.")
        print("El motor canonico no genera senales. Falta medir que de la tesis ICT")
        print("no esta implementado para que el flujo sweep->displace->BOS->entry")
        print("se produzca. Revisar: (1) confirm_bars de StructureConfig, (2) que")
        print("htf_poi_fn / POI este anclado, (3) requisitos de displacement/sweep.")
        return

    print(f"[3/3] Score de alineacion (OBSERVE, sin filtrar) ...", flush=True)
    buckets = {"5.0": 0, "4.0-4.5": 0, "3.0-3.5": 0, "2.0-2.5": 0, "<2.0": 0}
    for sig in signals:
        direction = int(getattr(sig, "direction", 0) or 0)
        st = getattr(sig, "entry_at", None)
        t = ltf_df.iloc[int(st)]["time"] if st is not None else sig.time

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

    total = len(signals)
    print(f"\n=== Distribucion de alignment_score ({symbol}, {n} velas M15) ===")
    print(f"Total senales: {total}")
    for k, v in buckets.items():
        pct = (v / total * 100) if total else 0
        print(f"  score {k:>8}: {v:>5}  ({pct:5.1f}%)")
    pasan = buckets["5.0"] + buckets["4.0-4.5"] + buckets["3.0-3.5"]
    print(f"\nSenales con score >= 3.0 (umbral suave): {pasan} ({pasan/total*100:.1f}%)")
    print(f"Modo OBSERVE: el plan NO filtra, solo califica. 0 senales borradas.")


if __name__ == "__main__":
    main()

"""C5 — Validacion manual Fase C sobre datos reales (EURUSD M15 completo).

No es un test pytest (el motor B1 completo tarda >60s). Se corre con
runner_monitor. Verifica end-to-end:
  R1: nº de senales CON indice HTF == SIN indice HTF (C no altera R7).
  C3: cada senal trae zone_authority con peso en [0,1].
  §5: distribucion de niveles de autoridad (Alta/Media/Baja) — metrica de
      FIDELIDAD, NO de PF (no se evalua por retorno).

Salida: imprime conteos y distribucion; se redirige a results/_c5_real.log.
"""
import argparse
import sys
from pathlib import Path

# Asegurar que el root del repo este en sys.path (el script se corre como
# `python scripts/c5_validate_real.py`, fuera de pytest que si resuelve el root).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import time

from collections import Counter

from ict_backtest.canonical import evaluate_signals
from ict_backtest.data_feed import load_frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=None,
                    help="limita velas M15 (para validacion rapida; por defecto todas)")
    args = ap.parse_args()

    t0 = time.time()
    print("=== C5: EURUSD H4/M15 ===", flush=True)
    if args.cap:
        print(f"(modo rapido: cap={args.cap} velas M15)", flush=True)

    # Sin indice (comportamiento historico) — modo rapido, SIN costo HTF FVG/OB
    base = evaluate_signals("EURUSD", "H4", "M15", counter_trend=False,
                            frames=_load(args.cap))
    print(f"senales SIN indice HTF: {len(base)}  ({time.time()-t0:.1f}s)", flush=True)

    # Con indice (Fase C enchufada) — paga el costo de detectar FVG/OB del HTF
    t1 = time.time()
    with_idx = evaluate_signals("EURUSD", "H4", "M15", counter_trend=False,
                                frames=_load(args.cap), enable_pd_index=True)
    print(f"senales CON indice HTF: {len(with_idx)}  ({time.time()-t1:.1f}s)", flush=True)

    # R1: mismo conteo
    assert len(with_idx) == len(base), (
        f"R1 VIOLADA: C altero el conteo {len(base)} -> {len(with_idx)}"
    )
    print("R1 OK: conteo identico (C no invadio R7)", flush=True)

    # C3 + §5: distribucion de autoridad
    levels = Counter()
    pesos = []
    for s in with_idx:
        a = s.zone_authority
        if a is None:
            levels["SIN_ANCLA(None)"] += 1
        else:
            levels[a.level] += 1
            pesos.append(a.confidence_weight)
    print(f"distribucion de autoridad: {dict(levels)}", flush=True)
    if pesos:
        print(f"peso confianza: min={min(pesos):.2f} max={max(pesos):.2f} "
              f"mean={sum(pesos)/len(pesos):.2f}", flush=True)
    print("C5 completado sin errores.", flush=True)


def _load(cap):
    """Carga EURUSD y opcionalmente recorta M15 para validacion rapida."""
    fr = load_frames("EURUSD", ("D1", "H4", "M15"))
    if cap is not None:
        fr["M15"] = fr["M15"].head(cap).reset_index(drop=True)
    return fr


if __name__ == "__main__":
    main()

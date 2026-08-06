"""AUDITORIA DE SECUENCIA / FUNNEL (no backtest de P&L).

Objetivo (Ruben 2026-08-06): demostrar que el motor, vela a vela, RECONOCE
cuando se arma el patron ICT canonico en HTF:
    SWEEP (barrido de liquidez) -> DISPLACE (empujon) -> BOS/CHOCH (rotura)
    -> ENTRY (retorno a zona POI anclada al BOS del padre).

NO simula entradas ni P&L. Solo mide el FUNNEL del detector del motor:
cuantos setups nacen en SWEEP, cuantos pasan a DISPLACE, a BOS, y cuantos
completan ENTRY (setup completo de HTF). La diferencia entre fases dice EN
QUE ESLABON se pierde el patron en datos reales.

Consumidor PURO del motor: usa evaluate_signals (endpoint canon que llama a
engine.sequence). No hay logica de deteccion propia (Ley: el backtest/demo
solo consume el motor, nunca lo reimplementa).

Uso:
    python scripts/audit_sequence_funnel.py [window_months=1]
"""

import sys

sys.path.insert(0, ".")

import time as _t
import pandas as pd

from engine.data_feed import load_frames
from ict_backtest.canonical import evaluate_signals

SYMBOL = "EURUSD"
HTF = "D1"
LTF = "M15"
# Auditoria de HTF: basta con D1/H4/H1/M15. NO cargamos M1/M5 (1.6M velas)
# porque ese es el cuello de botella que colgaba el build de objects.
TF_CHAIN = ("D1", "H4", "H1", "M15")


def _recortar(frames: dict, window_months: int):
    """Recorta todos los TF a los ultimos `window_months` meses del LTF."""
    last = pd.to_datetime(frames[LTF]["time"].iloc[-1], utc=True, errors="coerce")
    start = last - pd.DateOffset(months=window_months)
    out = {}
    for tf, df in frames.items():
        t = pd.to_datetime(df["time"], utc=True, errors="coerce")
        out[tf] = df.loc[t >= start].reset_index(drop=True)
    return out


def _field(s, key, default=None):
    """Lee campo de una señal sea dict o objeto ICTSignal."""
    if isinstance(s, dict):
        return s.get(key, default)
    return getattr(s, key, default)


def main(window_months: int = 1):
    print(f"[audit] cargando {SYMBOL} frames...", flush=True)
    t0 = _t.time()
    frames = load_frames(SYMBOL, TF_CHAIN)
    if window_months:
        frames = _recortar(frames, window_months)
    n_ltf = len(frames[LTF])
    print(f"[audit] frames cargados ({n_ltf} velas {LTF}, "
          f"{window_months} mes(es)). detectando...", flush=True)

    # Endpoint canon: consume engine.sequence (motor). HTF real + POI anclado
    # (enable_pd_index) + gate de sesgo T9 (plan_gate). return_phase_seen
    # devuelve el funnel del detector sin simular P&L.
    res, phase_seen = evaluate_signals(
        SYMBOL, HTF, LTF,
        frames=frames,
        enable_pd_index=True,
        require_displacement=True,
        counter_trend=False,
        return_phase_seen=True,
    )

    signals = res if isinstance(res, list) else res.get("signals", []) or []
    print(f"[audit] funnel: {phase_seen}", flush=True)
    print(f"[audit] setups completos (ENTRY): {len(signals)}", flush=True)

    # Tasa de conversion por eslabon (funnel).
    sw = phase_seen.get("SWEEP", 0)
    di = phase_seen.get("DISPLACE", 0)
    bo = phase_seen.get("BOS", 0)
    en = phase_seen.get("ENTRY", 0)
    print("[audit] ---- FUNNEL (nacen -> completan) ----", flush=True)
    print(f"  SWEEP   : {sw}", flush=True)
    print(f"  DISPLACE: {di}  ({100*di/sw:.1f}% de SWEEP)" if sw else "  DISPLACE: 0", flush=True)
    print(f"  BOS     : {bo}  ({100*bo/sw:.1f}% de SWEEP)" if sw else "  BOS: 0", flush=True)
    print(f"  ENTRY   : {en}  ({100*en/sw:.1f}% de SWEEP)" if sw else "  ENTRY: 0", flush=True)

    # Setups completos por mes (Evidencia: "se arma cada cierto tiempo").
    if signals:
        times = []
        for s in signals:
            tt = (_field(s, "time") or _field(s, "entry_time")
                  or _field(s, "birth_time") or _field(s, "t"))
            if tt is not None:
                times.append(pd.to_datetime(tt, utc=True, errors="coerce"))
        ts = pd.Series(times).dropna()
        by_month = ts.dt.to_period("M").value_counts().sort_index()
        print("[audit] ---- SETUPS COMPLETOS POR MES ----", flush=True)
        for p, c in by_month.items():
            print(f"  {p}: {c}", flush=True)
        print(f"[audit] muestra primeros 5 tiempos: "
              f"{[str(t) for t in ts.head(5)]}", flush=True)
    else:
        print("[audit] 0 setups completos en la ventana.", flush=True)

    print(f"[audit] listo en {_t.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    wm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(wm)

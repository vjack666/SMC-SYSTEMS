"""
Fase Wyckoff en M15 — usa el WyckoffAgent YA EXISTENTE del proyecto.

Carga EURUSD_M15 (data/raw), enriquece con las columnas que el agente necesita
(atr, swing_label, macro_direction, stoch_k/d; tick_volume ya viene) y reporta
la fase del ciclo de Wyckoff en la ultima vela cerrada.

Reusa:
  - agents/wyckoff_agent.py  -> WyckoffAgent (logica de fase del proyecto)
  - detectors/bos.py         -> detect_bos() pone swing_label
  - indicators.py            -> compute_stochastic(), add_atr()

Uso:
  C:\\Python314\\python.exe scripts\\fase_wyckoff_m15.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from agents.wyckoff_agent import WyckoffAgent  # noqa: E402
from detectors import BosConfig, detect_bos  # noqa: E402
from indicators import add_atr, add_stochastic  # noqa: E402
from detectors import TrendConfig, detect_trend  # noqa: E402

DATA_DIR = BASE / "data" / "raw"

_PHASE_ES = {
    "ACCUMULATION": "ACUMULACION",
    "ACCUMULATION_EARLY": "ACUMULACION (temprana)",
    "ACCUMULATION_LATE": "ACUMULACION (tardia)",
    "MARKUP": "MARKUP (subida)",
    "DISTRIBUTION": "DISTRIBUCION",
    "DISTRIBUTION_EARLY": "DISTRIBUCION (temprana)",
    "DISTRIBUTION_LATE": "DISTRIBUCION (tardia)",
    "MARKDOWN": "MARKDOWN (bajada)",
    "UNKNOWN": "INDEFINIDA",
}


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega las columnas que WyckoffAgent.analyze() requiere."""
    df = df.copy()
    df["atr"] = add_atr(df, 14)
    bos = detect_bos(df, BosConfig())
    df["swing_label"] = bos["swing_label"]
    trend = detect_trend(df, TrendConfig())
    t = str(trend["trend"].iloc[-1])
    df["macro_direction"] = t
    stoch = add_stochastic(df, k_period=14, d_period=3, smooth_k=3)
    df["stoch_k"] = stoch["stoch_k"]
    df["stoch_d"] = stoch["stoch_d"]
    return df


def fase_actual(symbol: str = "EURUSD", tf: str = "M15") -> dict:
    p = DATA_DIR / f"{symbol}_{tf}.parquet"
    if not p.exists():
        raise SystemExit(f"[!] No existe {p}")
    df = pd.read_parquet(p)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.sort_values("time").reset_index(drop=True)
    df = _enrich(df)
    agent = WyckoffAgent(lookback=min(40, len(df)))
    res = agent.analyze(df, len(df) - 1)
    ev = res.evidence
    return {
        "symbol": symbol,
        "tf": tf,
        "phase_raw": ev.get("phase", "UNKNOWN"),
        "phase_es": _PHASE_ES.get(ev.get("phase", "UNKNOWN"), "INDEFINIDA"),
        "bias": res.bias,
        "confidence": res.confidence,
        "eventos": [e["type"] for e in res.detected_events],
        "macro_direction": str(df["macro_direction"].iloc[-1]),
        "time": str(df["time"].iloc[-1]) if "time" in df else "-",
    }


def main() -> int:
    r = fase_actual()
    print("=" * 56)
    print(f"  FASE WYCKOFF {r['symbol']} {r['tf']}   (vela {r['time']})")
    print("=" * 56)
    print(f"  Fase del ciclo : {r['phase_es']}")
    print(f"  Sesgo Wyckoff  : {r['bias']}  (confianza {r['confidence']:.0%})")
    print(f"  Macro (trend)  : {r['macro_direction']}")
    if r["eventos"]:
        print(f"  Eventos        : {', '.join(r['eventos'])}")
    else:
        print("  Eventos        : ninguno claro")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

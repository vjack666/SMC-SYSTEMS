"""FASE G — Auditoria de equivalencia funcional legacy vs canonico.

Compara vela por vela los dos motores de estructura sobre datos REALES,
no solo nombres de columnas.

legacy  : detectors.bos.detect_bos + detectors.choch.detect_choch
canonico: ict_backtest.market_structure.detect_market_structure

Reporta:
  - n de BOS detectados por cada motor y barra de primer BOS
  - n de CHOCH detectados y barra de primer CHOCH
  - overlap exacto (misma vela) de bos_dir/choch_dir
  - desfase promedio (lag en velas) entre motores
  - concordancia de trend
NO modifica nada del repo. Solo lectura + reporte.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from detectors.bos import detect_bos, BosConfig
from detectors.choch import detect_choch
from ict_backtest.market_structure import detect_market_structure, StructureConfig


def _align(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """El canonico hace reset_index(drop=True); legacy conserva index del parquet.
    Alineamos por posicion (reset a 0..n-1) para comparar vela a vela."""
    out = df.reset_index(drop=True)
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    return out


def _first_idx(series: pd.Series) -> int:
    nz = np.flatnonzero(series.to_numpy() != 0)
    return int(nz[0]) if len(nz) else -1


def _diff_report(name: str, a: pd.Series, b: pd.Series) -> dict:
    a = a.to_numpy(dtype=float)
    b = b.to_numpy(dtype=float)
    same = int((np.sign(a) == np.sign(b)).sum())
    exact = int((a == b).sum())
    # lag: para cada vela con senal distinta, buscar match en ventana +/-3
    lag_sum = 0
    lag_n = 0
    for i in range(len(a)):
        if a[i] != 0 and a[i] != b[i]:
            for d in (1, -1, 2, -2, 3, -3):
                j = i + d
                if 0 <= j < len(b) and b[j] == a[i]:
                    lag_sum += abs(d)
                    lag_n += 1
                    break
    return {
        "motor_A_nonzero": int((a != 0).sum()),
        "motor_B_nonzero": int((b != 0).sum()),
        "mismo_signo": same,
        "exactas": exact,
        "total": len(a),
        "lag_promedio_velas": round(lag_sum / lag_n, 2) if lag_n else 0.0,
        "velas_con_desfase": lag_n,
    }


def main() -> None:
    symbol, tf = "EURUSD", "M15"
    print(f"=== EQUIVALENCIA FUNCIONAL: {symbol} {tf} (datos reales) ===\n")
    df = pd.read_parquet(ROOT / "data" / "raw" / f"{symbol}_{tf}.parquet")

    # --- LEGACY ---
    leg = detect_bos(df, BosConfig(followthrough_bars=18))
    leg = detect_choch(leg)
    from detectors.trend import detect_trend
    leg = detect_trend(leg)
    leg = _align(leg, ["bos_direction", "choch_signal", "bos_status", "choch_status", "trend"])

    # --- CANONICO ---
    cfg = StructureConfig(swing_lookback=5, confirm_bars=2, atr_period=14)
    can = detect_market_structure(df, cfg)
    can = _align(can, ["bos_dir", "choch_dir", "bos_status", "choch_status", "trend"])

    # vistas int para comparar.
    # legacy bos_direction es INT (1/-1/0); choch_signal es STRING.
    leg_bos = leg["bos_direction"].astype(int)
    leg_choch = leg["choch_signal"].map({"CHOCH_BULLISH": 1, "CHOCH_BEARISH": -1}).fillna(0).astype(int)
    can_bos = can["bos_dir"].astype(int)
    can_choch = can["choch_dir"].astype(int)

    print(">> BOS")
    print("  legacy   nonzeros:", int((leg_bos != 0).sum()), " | primer BOS en vela:", _first_idx(leg_bos))
    print("  canonico nonzeros:", int((can_bos != 0).sum()), " | primer BOS en vela:", _first_idx(can_bos))
    print("  diff:", _diff_report("bos", leg_bos, can_bos))
    print()
    print(">> CHOCH")
    print("  legacy   nonzeros:", int((leg_choch != 0).sum()), " | primer CHOCH en vela:", _first_idx(leg_choch))
    print("  canonico nonzeros:", int((can_choch != 0).sum()), " | primer CHOCH en vela:", _first_idx(can_choch))
    print("  diff:", _diff_report("choch", leg_choch, can_choch))
    print()
    print(">> TREND (HH/HL vs LH/LL)")
    print("  legacy trend vals:", leg["trend"].value_counts().to_dict())
    print("  canon  trend vals:", can["trend"].value_counts().to_dict())
    t_same = int((leg["trend"].to_numpy() == can["trend"].to_numpy()).sum())
    print(f"  trend igual en {t_same}/{len(can)} velas ({100*t_same/len(can):.1f}%)")
    print()
    print(">> STATUS (active vs invalidated)")
    print("  legacy bos_status:", leg["bos_status"].value_counts().to_dict())
    print("  canon  bos_status:", can["bos_status"].value_counts().to_dict())
    print("  legacy choch_status:", leg["choch_status"].value_counts().to_dict())
    print("  canon  choch_status:", can["choch_status"].value_counts().to_dict())
    bs_same = int((leg["bos_status"].to_numpy() == can["bos_status"].to_numpy()).sum())
    cs_same = int((leg["choch_status"].to_numpy() == can["choch_status"].to_numpy()).sum())
    print(f"  bos_status igual: {bs_same}/{len(can)} | choch_status igual: {cs_same}/{len(can)}")
    print()
    print("CONCLUSION: ver si las columnas 'exactas' son altas (>=95%) y lag bajo (<1.5).")


if __name__ == "__main__":
    main()

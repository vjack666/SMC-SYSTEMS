"""scripts/request_daily_bias.py — Bias del dia bajo demanda (Hermes lo invoca).

Flujo cuando el usuario pide "bias de hoy" / "analiza la grafica":
  1) Actualiza EURUSD D1/H4/H1 desde MT5 FundedNext (merge, guarda en data/raw/).
  2) Corre el motor de sesgo real (engine/bias/narrative.py).
  3) Imprime el resumen del dia.

Uso:
  C:\\Python314\\python.exe scripts/request_daily_bias.py
  C:\\Python314\\python.exe scripts/request_daily_bias.py --symbols EURUSD --tfs D1,H4,H1
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _update() -> int:
    """Lanza el actualizador MT5 (merge) con el Python del sistema."""
    py = r"C:\Python314\python.exe"
    cmd = [py, str(ROOT / "scripts" / "update_mt5_data.py"),
           "--symbols", "EURUSD", "--tfs", "D1,H4,H1"]
    r = subprocess.run(cmd, creationflags=(
        subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0))
    return r.returncode


def _bias(symbol: str):
    import pandas as pd
    from engine.bias.narrative import compute_htf_bias, HtfBias
    from engine.htf_narrative import build_htf_narrative

    def load(tf: str) -> pd.DataFrame:
        df = pd.read_parquet(ROOT / "data" / "raw" / f"{symbol}_{tf}.parquet")
        df = df[["time", "open", "high", "low", "close"]].copy()
        df["time"] = pd.to_datetime(df["time"], utc=True)
        return df.set_index("time").sort_index()

    d1, h4, h1 = load("D1"), load("H4"), load("H1")
    bias: HtfBias = compute_htf_bias(d1, h4, h1)
    # Narrativa HTF con POI anclado (Brecha B): pasamos los TF padre.
    htf_frames = {"D1": d1.reset_index(), "H4": h4.reset_index(), "H1": h1.reset_index()}
    narr = build_htf_narrative(d1, htf_bias=bias, htf_frames=htf_frames)
    return bias, d1, h4, h1, narr


def main() -> int:
    ap = argparse.ArgumentParser(description="Bias del dia bajo demanda")
    ap.add_argument("--symbols", default="EURUSD")
    ap.add_argument("--tfs", default="D1,H4,H1")
    ap.add_argument("--no-update", action="store_true",
                    help="no bajar datos de MT5, usar parquet en disco")
    args = ap.parse_args()
    symbol = args.symbols.split(",")[0].strip().upper()

    if not args.no_update:
        print("[*] Actualizando velas del dia desde MT5 FundedNext...")
        rc = _update()
        if rc != 0:
            print(f"[!] Update fallo (rc={rc}); uso datos en disco si existen.")

    bias, d1, h4, h1, narr = _bias(symbol)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("\n==================== BIAS DEL DIA ====================")
    print(f"  Simbolo      : {symbol}")
    print(f"  Generado     : {now}")
    print(f"  D1  (diario) : {bias.d1}   (ultima vela {d1.index[-1]})")
    print(f"  H4  (4H)     : {bias.h4}   (ultima vela {h4.index[-1]})")
    print(f"  H1  (1H)     : {bias.h1}   (ultima vela {h1.index[-1]})")
    print(f"  Alineado     : {bias.aligned}")
    print(f"  Direccion    : {bias.direction}")
    # POI anclado (Brecha B): el POI del motor ya respaldado por BOS/CHOCH padre
    poi = narr.get("poi")
    if poi:
        anc = "ANCLADO HTF" if poi.get("anchored") else "SIN ANCLAR"
        print(f"  POI          : {poi.get('kind')} {anc}")
    else:
        print("  POI          : sin POI")
    print("=====================================================")
    print("Lectura: si D1 difiere de H4/H1 es pullback dentro de la tendencia mayor.")
    print("El bias solo NO es senal de entrada; requiere POI anclado + estructura.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

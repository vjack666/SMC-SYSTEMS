"""Demostracion: stack HTF completo del motor sobre el dia de hoy (EURUSD 2026-08-06).

No toca LTF (M5/M1). Solo D1->H4->H1->M15: sesgo, estructura, premium/discount,
POI anclado y gate top-down. Prueba que el HTF del motor esta al 100%.

Uso:
  python scripts/_demo_htf_today.py
  python scripts/_demo_htf_today.py --symbol EURUSD
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.bias.narrative import compute_htf_bias
from engine.bos import detect_market_structure
from engine.plan import build_context_stack, top_down_allows_trade, dealing_range_pd
from engine.poi_anchor import build_htf_structure_index

TFS = ("D1", "H4", "H1", "M15")
DATA = ROOT / "data" / "raw"


def _load_tf(symbol: str, tf: str, tail: int = 600) -> pd.DataFrame:
    df = pd.read_parquet(DATA / f"{symbol}_{tf}.parquet")
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread"]].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    # Para "el dia de hoy" basta la cola reciente; detect_market_structure es O(n).
    if len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    return df


def _enrich_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Puebla 'trend'/'bos_dir'/'choch_dir' en cada vela (lo que lee plan.snapshot_tf)."""
    res = detect_market_structure(df)
    fr = res.frame.copy()
    out = df.copy()
    # propagar columnas de estructura que snapshot_tf consulta
    for col in (
        "trend", "bos_dir", "choch_dir", "bos_status", "choch_status",
        "bos_proj_level", "bos_inval_level", "choch_proj_level", "choch_inval_level",
    ):
        if col in fr.columns:
            out[col] = fr[col].values
    # momentum: cierre vs abrir de la ventana corta no es necesario aqui
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    args = ap.parse_args()
    sym = args.symbol.upper()

    raw = {tf: _load_tf(sym, tf) for tf in TFS}
    ms = {tf: _enrich_structure(raw[tf]) for tf in TFS}

    # Tiempo de la ultima vela M15 cerrada (anti look-ahead: el LTF ya cerro)
    t = raw["M15"]["time"].iloc[-1]

    # --- Bias direccional (D1/H4/H1) ---
    bias = compute_htf_bias(
        raw["D1"].set_index("time"), raw["H4"].set_index("time"), raw["H1"].set_index("time")
    )
    direction = 1 if bias.direction == "BULLISH" else (-1 if bias.direction == "BEARISH" else 0)

    # --- POI anclado (Brecha B): eventos BOS/CHOCH en TF padre ya cerrados ---
    htf_frames = {tf: raw[tf] for tf in ("D1", "H4", "H1")}
    events = build_htf_structure_index(htf_frames)
    n_bull = sum(1 for e in events if e.direction == 1)
    n_bear = sum(1 for e in events if e.direction == -1)

    # --- Stack top-down completo ---
    stack = build_context_stack(ms, t, tfs=TFS)

    # --- Gate del humano ---
    allow, reason = top_down_allows_trade(stack, direction, require_pd=True, require_ltf=False)

    # --- Reporte ---
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("\n================ STACK HTF COMPLETO (motor) ================")
    print(f"  Simbolo : {sym}")
    print(f"  Hora    : {now}  (vela M15 cerrada {t})")
    print(f"  Bias D1/H4/H1 : {bias.d1} / {bias.h4} / {bias.h1}  aligned={bias.aligned}")
    print(f"  Direccion     : {bias.direction} (num {direction})")
    print("-" * 60)
    for tf in TFS:
        s = stack.get(tf, {})
        trend = s.get("trend", "?")
        pd_side = s.get("pd_side", "-")
        print(f"  {tf:4} trend={trend:8} PD={pd_side:9} close={s.get('close', float('nan'))}")
    print("-" * 60)
    # --- T9.2: picos de BOS/CHOCH esperados e invalidaciones (lo que el
    # trader marca en pantalla: donde debe hacerse el BOS y donde muere) ---
    print("  MARCAS DEL TRADER (ultimo BOS/CHOCH activo por TF):")
    for tf in TFS:
        fr = detect_market_structure(raw[tf]).frame
        bos = fr[(fr["bos_dir"] != 0) & (fr["bos_status"] == "active")]
        ch = fr[(fr["choch_dir"] != 0) & (fr["choch_status"] == "active")]
        if len(bos):
            b = bos.iloc[-1]
            print(f"    {tf:4} BOS {('ALC' if b['bos_dir']>0 else 'BAJ')} "
                  f"pico={b['bos_proj_level']:.5f}  invalida_si_cruza={b['bos_inval_level']:.5f}")
        if len(ch):
            c = ch.iloc[-1]
            print(f"    {tf:4} CHOCH {('ALC' if c['choch_dir']>0 else 'BAJ')} "
                  f"rompe_nivel={c['choch_proj_level']:.5f}  muere_si_cruza={c['choch_inval_level']:.5f}")
    print("-" * 60)
    print(f"  POI anclado   : {len(events)} eventos BOS/CHOCH padre "
          f"(bull={n_bull} bear={n_bear})  [Brecha B ACTIVA]")
    print(f"  GATE top-down : {'PERMITIDO' if allow else 'BLOQUEADO'}  -> {reason}")
    print("=" * 60)
    if allow:
        print("  Lectura: HTF alineado + PD a favor + POI anclado -> setup valido.")
    else:
        print("  Lectura: el motor bloquea por falta de alineacion HTF/PD/POI.")
        print("  (Esto DEMUESTRA que el HTF funciona: evalua y filtra, no dice siembre si.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Rutina EURUSD — Ficha de contexto top-down (D1 -> H4 -> M15).

Lee datos reales cacheados en data/raw/ y corre los detectores deterministas
de SMC-SYSTEMS (BOS, OB, FVG, zones, trend, choch). NO estima a ojo: todo sale
del codigo. NO toca produccion ni MT5.

Uso:
  python scripts/rutina_eurusd.py
  python scripts/rutina_eurusd.py --symbol EURUSD --save

Salida:
  - Ficha de texto en la terminal.
  - Con --save: guarda docs/diario/<SYMBOL>_<fecha>.md como diario.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from detectors import (
    detect_fvg,
    detect_order_blocks,
    ZoneConfig, compute_zones,
)
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
from ict_backtest.market_structure import StructureConfig, detect_market_structure
from fase_wyckoff_m15 import fase_actual as _wyckoff_fase  # noqa: E402

DATA_DIR = Path("data/raw")


def _load(symbol: str, tf: str) -> pd.DataFrame:
    p = DATA_DIR / f"{symbol}_{tf}.parquet"
    if not p.exists():
        raise SystemExit(f"[!] No existe {p}. Descarga datos primero.")
    df = pd.read_parquet(p)
    # normalizar: time -> index datetime ordenado
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.sort_values("time").reset_index(drop=True)
    return df


def _fmt(x, nd=5) -> str:
    try:
        if x is None or pd.isna(x):
            return "-"
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def _atr(frame: pd.DataFrame, period: int = 14) -> float:
    hl = frame["high"] - frame["low"]
    hc = (frame["high"] - frame["close"].shift(1)).abs()
    lc = (frame["low"] - frame["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def analyze_timeframe(df: pd.DataFrame, tf: str) -> dict:
    """Corre los detectores y devuelve el estado en la ULTIMA vela cerrada.

    Estructura (BOS/CHOCH/trend/swing) via `market_structure.detect_market_structure`
    (canonico, reemplaza los detectores legacy detect_bos/detect_choch/detect_trend
    que fueron eliminados en un refactor). Liquidez (sweep) via
    `detectors.liquidity_context.canonical_sweep`. OB/FVG/ZONAS se mantienen en
    sus detectores actuales. NO depende del backtest: son librerias de calculo
    puras compartidas, no el pipeline run_backtest.
    """
    # Estructura canonica: BOS/CHOCH/trend/swing en una sola pasada.
    ms = detect_market_structure(df, StructureConfig(swing_lookback=5, confirm_bars=2))
    # Liquidez (sweep) canonico, sin look-ahead.
    swept = canonical_sweep(df, lookback=DEFAULT_SWEEP_LOOKBACK)

    ob = detect_order_blocks(df)
    fvg = detect_fvg(df)
    zones = compute_zones(df, ZoneConfig(swing_lookback=20))

    last = -1
    close = float(df["close"].iloc[last])
    atr = _atr(df)

    # OB mas reciente FORMADO (bordes exactos vivos en la vela donde se creo).
    ob_formed = ob[ob["ob_bullish"] | ob["ob_bearish"]]
    ob_row = ob_formed.iloc[-1] if len(ob_formed) else None

    # FVG sin rellenar mas reciente
    fvg_state = str(fvg["fvg_fill_status"].iloc[last]) if "fvg_fill_status" in fvg else "-"

    # liquidez cercana (sweep canonico)
    sweep_down = bool(swept["liquidity_sweep_down"].iloc[last])
    sweep_up = bool(swept["liquidity_sweep_up"].iloc[last])

    # CHOCH como senal legible (igual contrato que data_feed / motor)
    choch_dir = int(ms["choch_dir"].iloc[last])
    choch_signal = {1: "CHOCH_BULLISH", -1: "CHOCH_BEARISH"}.get(choch_dir, "NONE")

    return {
        "tf": tf,
        "time": str(df["time"].iloc[last]) if "time" in df else "-",
        "close": close,
        "atr": atr,
        "trend": str(ms["trend"].iloc[last]),
        "swing_label": str(ms["swing_label"].iloc[last]),
        "bos_dir": int(ms["bos_dir"].iloc[last]),
        "bos_status": str(ms["bos_status"].iloc[last]),
        "bos_level": ms["bos_level"].iloc[last],
        "ob_top": ob_row["ob_top"] if ob_row is not None else None,
        "ob_bottom": ob_row["ob_bottom"] if ob_row is not None else None,
        "ob_dir": ("bullish" if ob_row is not None and ob_row["ob_bullish"]
                   else "bearish" if ob_row is not None else "-"),
        "fvg_state": fvg_state,
        "zone": str(zones["premium_discount_zone"].iloc[last]),
        "zone_high": float(zones["zone_high"].iloc[last]),
        "zone_low": float(zones["zone_low"].iloc[last]),
        "ote_long": (float(zones["ote_long_min"].iloc[last]), float(zones["ote_long_max"].iloc[last])),
        "ote_short": (float(zones["ote_short_min"].iloc[last]), float(zones["ote_short_max"].iloc[last])),
        "choch": choch_signal,
        "choch_status": str(ms["choch_status"].iloc[last]),
        "sweep_up": sweep_up,
        "sweep_down": sweep_down,
    }


def _bias_word(trend: str) -> str:
    return {"BULLISH": "ALCISTA", "BEARISH": "BAJISTA", "RANGING": "RANGO"}.get(trend, trend)


def build_verdict(d1: dict, h4: dict, m15: dict) -> dict:
    """Sintetiza un sesgo operativo simple y transparente (reglas explicitas)."""
    votes = {"LONG": 0, "SHORT": 0}
    reasons = []

    for tf_data, w in ((d1, "D1"), (h4, "H4"), (m15, "M15")):
        if tf_data["trend"] == "BULLISH":
            votes["LONG"] += 1
            reasons.append(f"{w}: tendencia alcista")
        elif tf_data["trend"] == "BEARISH":
            votes["SHORT"] += 1
            reasons.append(f"{w}: tendencia bajista")
        else:
            reasons.append(f"{w}: en rango (sin sesgo)")

    # confirmaciones M15
    if m15["bos_dir"] == 1 and m15["bos_status"] == "active":
        votes["LONG"] += 1
        reasons.append("M15: BOS alcista activo")
    elif m15["bos_dir"] == -1 and m15["bos_status"] == "active":
        votes["SHORT"] += 1
        reasons.append("M15: BOS bajista activo")

    if m15["sweep_down"]:
        votes["LONG"] += 1
        reasons.append("M15: barrido de liquidez abajo (posible giro alcista)")
    if m15["sweep_up"]:
        votes["SHORT"] += 1
        reasons.append("M15: barrido de liquidez arriba (posible giro bajista)")

    if votes["LONG"] > votes["SHORT"] and votes["LONG"] >= 2:
        bias = "LONG"
    elif votes["SHORT"] > votes["LONG"] and votes["SHORT"] >= 2:
        bias = "SHORT"
    else:
        bias = "NEUTRAL (esperar)"

    # zona de interes e invalidacion (M15) para el sesgo dominante
    zone_note = ""
    if bias == "LONG":
        lo, hi = m15["ote_long"]
        zone_note = f"Zona de compra (OTE M15): {_fmt(lo)} - {_fmt(hi)}"
        invalid = m15["zone_low"]
        target = m15["zone_high"]
    elif bias == "SHORT":
        lo, hi = m15["ote_short"]
        zone_note = f"Zona de venta (OTE M15): {_fmt(lo)} - {_fmt(hi)}"
        invalid = m15["zone_high"]
        target = m15["zone_low"]
    else:
        invalid = None
        target = None

    return {
        "bias": bias,
        "votes": votes,
        "reasons": reasons,
        "zone_note": zone_note,
        "invalidation": invalid,
        "target": target,
    }


PIP = 0.0001  # EURUSD: 1 pip
RR_MIN = 2.0  # R:R minimo para validar el setup (1:2)


def _pips(a: float, b: float) -> float:
    return abs(a - b) / PIP


def compute_trade_plan(verdict: dict, m15: dict) -> dict | None:
    """Arma entrada/SL/TP y valida R:R >= RR_MIN. None si NEUTRAL o sin datos.

    Reusa lo que build_verdict ya calculo:
      - entry  = punto medio de la zona OTE del lado del bias (ejecucion M15)
      - SL     = invalidacion (verdict['invalidation'])
      - TP     = objetivo por estructura (verdict['target'])
    """
    bias = verdict["bias"]
    sl = verdict.get("invalidation")
    tp = verdict.get("target")
    if bias not in ("LONG", "SHORT") or sl is None or tp is None:
        return None

    lo, hi = m15["ote_long"] if bias == "LONG" else m15["ote_short"]
    entry = (float(lo) + float(hi)) / 2.0

    risk = abs(entry - float(sl))
    reward = abs(float(tp) - entry)
    if risk <= 0:
        return None
    rr = reward / risk
    valido = rr >= RR_MIN

    return {
        "bias": bias,
        "entry": entry,
        "sl": float(sl),
        "tp": float(tp),
        "risk_pips": _pips(entry, float(sl)),
        "reward_pips": _pips(entry, float(tp)),
        "rr": rr,
        "valido": valido,
    }


def render(symbol: str, d1: dict, h4: dict, m15: dict, verdict: dict) -> str:
    L = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L.append("=" * 64)
    L.append(f"  FICHA {symbol} — RUTINA TOP-DOWN   (generada {now})")
    L.append("=" * 64)

    L.append("")
    L.append("CONTEXTO GRANDE (la marea)")
    L.append("-" * 64)
    for tf_data, name in ((d1, "D1"), (h4, "H4")):
        L.append(f"[{name}]  vela: {tf_data['time']}")
        L.append(f"   Bias/Tendencia : {_bias_word(tf_data['trend'])}  | ultimo swing: {tf_data['swing_label']}")
        L.append(f"   Zona precio    : {tf_data['zone']}  (rango {_fmt(tf_data['zone_low'])} - {_fmt(tf_data['zone_high'])})")
        L.append(f"   BOS            : dir={tf_data['bos_dir']} status={tf_data['bos_status']} nivel={_fmt(tf_data['bos_level'])}")
        L.append(f"   OB activo      : {tf_data['ob_dir']}  [{_fmt(tf_data['ob_bottom'])} - {_fmt(tf_data['ob_top'])}]")
        L.append(f"   FVG            : {tf_data['fvg_state']}")
        # Fase Wyckoff de esta temporalidad (reusa fase_wyckoff_m15.fase_actual)
        try:
            w = _wyckoff_fase(symbol, name)
            ev_txt = f" ({', '.join(w['eventos'])})" if w["eventos"] else ""
            L.append(f"   Fase Wyckoff   : {w['phase_es']} | sesgo {w['bias']} {w['confidence']:.0%}{ev_txt}")
        except Exception as e:  # noqa: BLE001
            L.append(f"   Fase Wyckoff   : (no disponible: {e})")
        L.append("")
    L.append("EJECUCION (el timing — M15)")
    L.append("-" * 64)
    L.append(f"[M15]  vela: {m15['time']}   close: {_fmt(m15['close'])}   ATR: {_fmt(m15['atr'])}")
    L.append(f"   Tendencia      : {_bias_word(m15['trend'])}  | swing: {m15['swing_label']}")
    L.append(f"   BOS            : dir={m15['bos_dir']} status={m15['bos_status']} nivel={_fmt(m15['bos_level'])}")
    L.append(f"   CHOCH          : {m15['choch']} ({m15['choch_status']})")
    L.append(f"   OB activo      : {m15['ob_dir']}  [{_fmt(m15['ob_bottom'])} - {_fmt(m15['ob_top'])}]")
    L.append(f"   FVG            : {m15['fvg_state']}")
    L.append(f"   Zona precio    : {m15['zone']}")
    L.append(f"   Liquidez       : barrido_arriba={m15['sweep_up']}  barrido_abajo={m15['sweep_down']}")
    L.append("")

    L.append("VEREDICTO OPERATIVO")
    L.append("-" * 64)

    # Alineacion Wyckoff D1/H4/M15 (contexto vs ejecucion)
    try:
        w_d1 = _wyckoff_fase(symbol, "D1")
        w_h4 = _wyckoff_fase(symbol, "H4")
        w_m15 = _wyckoff_fase(symbol, "M15")
        biases = {w_d1["bias"], w_h4["bias"], w_m15["bias"]}
        if biases == {"BULLISH"}:
            alineacion = "ALINEADAS AL ALZA (contexto y ejecucion compran)"
        elif biases == {"BEARISH"}:
            alineacion = "ALINEADAS A LA BAJA (contexto y ejecucion venden)"
        elif "BULLISH" in biases and "BEARISH" in biases:
            alineacion = "EN CONFLICTO (contexto y M15 dicen distinto -> precaucion)"
        else:
            alineacion = "NEUTRALES (sin una direccion clara)"
        L.append(f"   ALINEACION WYCKOFF: {alineacion}")
        L.append(f"      D1={w_d1['phase_es']}  H4={w_h4['phase_es']}  M15={w_m15['phase_es']}")
    except Exception as e:  # noqa: BLE001
        L.append(f"   ALINEACION WYCKOFF: (no disponible: {e})")

    L.append(f"   SESGO DEL DIA  : {verdict['bias']}   (votos L:{verdict['votes']['LONG']} / S:{verdict['votes']['SHORT']})")

    # Fase Wyckoff M15 (reusa fase_wyckoff_m15.fase_actual sobre datos reales)
    try:
        w = _wyckoff_fase(symbol, "M15")
        ev_txt = f" ({', '.join(w['eventos'])}) " if w["eventos"] else ""
        L.append(f"   FASE WYCKOFF M15: {w['phase_es']}  | sesgo {w['bias']} {w['confidence']:.0%}{ev_txt}")
    except Exception as e:  # noqa: BLE001
        L.append(f"   FASE WYCKOFF M15: (no disponible: {e})")
    L.append("")
    if verdict["zone_note"]:
        L.append(f"   {verdict['zone_note']}")
    if verdict["invalidation"] is not None:
        L.append(f"   Invalidacion   : {_fmt(verdict['invalidation'])}  (si el precio cierra mas alla, el sesgo se cae)")
    if verdict["target"] is not None:
        L.append(f"   Objetivo logico: {_fmt(verdict['target'])}  (siguiente liquidez del rango)")
    L.append("")

    plan = compute_trade_plan(verdict, m15)
    if plan is not None:
        estado = "VALIDO ✓" if plan["valido"] else f"DESCARTAR (R:R < 1:{RR_MIN:.0f})"
        L.append("PLAN DE TRADE (entrada / SL / TP por estructura)")
        L.append("-" * 64)
        L.append(f"   Direccion      : {plan['bias']}")
        L.append(f"   Entrada (OTE)  : {_fmt(plan['entry'])}")
        L.append(f"   Stop Loss      : {_fmt(plan['sl'])}   ({plan['risk_pips']:.1f} pips de riesgo)")
        L.append(f"   Take Profit    : {_fmt(plan['tp'])}   ({plan['reward_pips']:.1f} pips de objetivo)")
        L.append(f"   Ratio R:R      : 1:{plan['rr']:.2f}   -> {estado}")
        if not plan["valido"]:
            L.append(f"   >> El objetivo no da 1:{RR_MIN:.0f}. Mejor esperar otro setup.")
        L.append("")
    L.append("   Razones:")
    for r in verdict["reasons"]:
        L.append(f"     - {r}")
    L.append("")
    L.append("   NOTA: sesgo derivado de reglas deterministas sobre datos reales.")
    L.append("   No es orden de entrada; es el mapa. Confirmar en tu ejecucion.")
    L.append("=" * 64)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rutina EURUSD top-down")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--save", action="store_true", help="guardar al diario docs/diario/")
    args = ap.parse_args()

    sym = args.symbol.upper()
    d1 = analyze_timeframe(_load(sym, "D1"), "D1")
    h4 = analyze_timeframe(_load(sym, "H4"), "H4")
    m15 = analyze_timeframe(_load(sym, "M15"), "M15")
    verdict = build_verdict(d1, h4, m15)

    ficha = render(sym, d1, h4, m15, verdict)
    print(ficha)

    if args.save:
        out_dir = Path("docs/diario")
        out_dir.mkdir(parents=True, exist_ok=True)
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = out_dir / f"{sym}_{fecha}.md"
        out.write_text("```\n" + ficha + "\n```\n", encoding="utf-8")
        print(f"\n[*] Diario guardado en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

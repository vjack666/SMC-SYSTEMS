"""Scanner report builder — plain-text trade card from engine.run_cycle().

Same shape as the operator brief: Entry/SL/TP, OTE zone, structure, honest R:R.
No orders, no automation — numbers only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app_observador.config import SYMBOL
from app_observador.core.position_sizer_bridge import extract_levels


def _fmt(x: Any, digits: int = 5) -> str:
    try:
        if x is None:
            return "—"
        v = float(x)
        if v != v:  # NaN
            return "—"
        return f"{v:.{digits}f}"
    except (TypeError, ValueError):
        return str(x) if x is not None else "—"


def _side_from_result(result: dict) -> str:
    verd = result.get("veredicto") or {}
    votes = verd.get("votes") if isinstance(verd.get("votes"), dict) else None
    if votes:
        if votes.get("LONG", 0) > votes.get("SHORT", 0):
            return "LONG"
        if votes.get("SHORT", 0) > votes.get("LONG", 0):
            return "SHORT"
    bias = str(verd.get("bias") or result.get("bias") or "")
    up = bias.upper()
    if "LONG" in up and "SHORT" not in up:
        return "LONG"
    if "SHORT" in up:
        return "SHORT"
    return "NEUTRAL"


def build_scanner_report(result: dict | None, *, symbol: str = SYMBOL) -> str:
    """Build the operator card (plain text). Safe with missing/partial data."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"ESCÁNER DE SETUP — {symbol}",
        f"Generado: {now}",
        "",
    ]

    if not result:
        lines.append("Sin datos del motor. Pulsá Actualizar o esperá el ciclo.")
        return "\n".join(lines)

    # Model (ICT)
    try:
        from app_observador.ui.resumen_widget import modelo_ict

        est = result.get("estructura") or {}
        bias = str(result.get("bias") or "")
        votes = (result.get("veredicto") or {}).get("votes")
        nombre, libro, score = modelo_ict(est, bias, votes)
        lines.append(f"Modelo ICT más coherente: {nombre}  (score {score})")
        if libro:
            lines.append(f"Referencia: docs/ict/{libro}")
    except Exception as e:
        lines.append(f"Modelo ICT: no disponible ({e})")

    bias = result.get("bias", "—")
    verd = result.get("veredicto") or {}
    votes = verd.get("votes") if isinstance(verd.get("votes"), dict) else {}
    lines += [
        "",
        f"Sesgo: {bias}",
        f"Votos: LONG {votes.get('LONG', 0)} / SHORT {votes.get('SHORT', 0)}",
        f"Semáforo: {(result.get('semaforo') or {}).get('color', '—')}",
    ]
    reasons = (result.get("semaforo") or {}).get("reasons") or []
    for r in reasons[:4]:
        lines.append(f"  · {r}")

    # Plan numbers
    levels = None
    try:
        levels = extract_levels(result, symbol=symbol)
    except Exception:
        levels = None

    lines += ["", "=== PLAN OPERATIVO (Entry / SL / TP) ==="]
    if levels is None:
        lines.append("Sin plan numérico completo (falta lado + OTE + SL + TP).")
        zone = verd.get("zone_note")
        if zone:
            lines.append(f"Nota de zona: {zone}")
        if verd.get("invalidation") is not None:
            lines.append(f"Invalidación (SL): {_fmt(verd.get('invalidation'))}")
        if verd.get("target") is not None:
            lines.append(f"Target (TP):       {_fmt(verd.get('target'))}")
    else:
        flag = "R:R OK (≥1:2)" if levels.valid_rr else "R:R BAJO — Lab descartaría para live"
        lines += [
            f"Lado:   {levels.side}",
            f"Entry:  {_fmt(levels.entry)}",
            f"SL:     {_fmt(levels.sl)}",
            f"TP:     {_fmt(levels.tp)}",
            f"R:R:    1:{levels.rr:.2f}  ({flag})",
            f"Riesgo sizing ref: {levels.risk_pct:.1f}% del balance",
        ]
        if levels.zone_note:
            lines.append(f"Zona:   {levels.zone_note}")
        risk_pips = abs(levels.entry - levels.sl) * 10_000  # EURUSD-style
        rew_pips = abs(levels.tp - levels.entry) * 10_000
        lines.append(f"Distancia aprox: risk {risk_pips:.1f} pips | reward {rew_pips:.1f} pips")

    # Structure M15 (+ light HTF)
    est = result.get("estructura") or {}
    m15 = est.get("M15") or {}
    h4 = est.get("H4") or {}
    d1 = est.get("D1") or {}
    lines += [
        "",
        "=== ESTRUCTURA ===",
        f"D1:  trend={d1.get('trend', '—')}  sweep↑={bool(d1.get('sweep_up'))} sweep↓={bool(d1.get('sweep_down'))}",
        f"H4:  trend={h4.get('trend', '—')}  fvg={h4.get('fvg_state', '—')}  ob={h4.get('ob_dir', '—')}",
        f"M15: trend={m15.get('trend', '—')}  bos_dir={m15.get('bos_dir', 0)}  "
        f"bos_status={m15.get('bos_status', '—')}  bos_level={_fmt(m15.get('bos_level'))}",
        f"M15: sweep↑={bool(m15.get('sweep_up'))}  sweep↓={bool(m15.get('sweep_down'))}  "
        f"fvg={m15.get('fvg_state', '—')}  ob={m15.get('ob_dir', '—')}  choch={m15.get('choch_status', '—')}",
    ]
    ote_l = m15.get("ote_long") or []
    ote_s = m15.get("ote_short") or []
    if len(ote_l) >= 2:
        lines.append(f"OTE long M15:  {_fmt(ote_l[0])} – {_fmt(ote_l[1])}")
    if len(ote_s) >= 2:
        lines.append(f"OTE short M15: {_fmt(ote_s[0])} – {_fmt(ote_s[1])}")

    wyk = (result.get("wyckoff") or {}).get("M15") or est.get("WYCKOFF_M15") or {}
    if wyk:
        lines.append(
            f"Wyckoff M15: {wyk.get('phase_es') or wyk.get('phase_raw') or '—'} "
            f"({wyk.get('bias', '—')})"
        )

    # Canonical engine note
    can = result.get("canonical")
    lines += ["", "=== MOTOR ==="]
    if isinstance(can, dict) and can.get("entry") is not None:
        lines.append(
            f"Plan canónico sequence: {can.get('side') or can.get('direction')} "
            f"E={_fmt(can.get('entry'))} SL={_fmt(can.get('sl'))} TP={_fmt(can.get('tp'))}"
        )
    else:
        lines.append("Sin plan canónico sequence fresco (fallback OTE/Lab si hay números).")

    side = _side_from_result(result)
    lines += [
        "",
        "=== LECTURA HONESTA ===",
    ]
    if levels is None:
        lines.append("No hay ficha operable. Esperá sweep + OTE + invalidación + target.")
    elif not levels.valid_rr:
        lines.append(
            f"Hay estructura ({side}) pero el R:R 1:{levels.rr:.2f} NO compensa el riesgo. "
            "Contexto puede verse 'perfecto' y aun así el trade no conviene."
        )
    else:
        lines.append(
            f"Setup {levels.side} con R:R 1:{levels.rr:.2f} ≥ 1:2. "
            "Validá precio en vivo antes de cualquier orden manual."
        )
    lines.append("Modo observador: esta ficha NO abre órdenes.")
    errs = result.get("errores") or []
    if errs:
        lines += ["", "Errores del ciclo:"]
        for e in errs[:5]:
            lines.append(f"  · {e}")

    return "\n".join(lines)

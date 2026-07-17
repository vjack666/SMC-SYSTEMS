"""Contexto completo de la app para el chat del MODELO.

El usuario no tiene que generar ni adjuntar fichas a mano: el chat arma el
contexto desde el último ciclo del motor (memoria / cache) + noticias +
plan canónico.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_observador.config import ROOT, SYMBOL
from app_observador.core.engine import CACHE_PATH, load_cached
from app_observador.core.scanner_report import build_scanner_report


def _news_block(result: dict | None) -> str:
    lines: list[str] = ["## Noticias / calendario (app)"]
    events = []
    if result and isinstance(result.get("noticias"), list):
        events = result["noticias"]
    if not events:
        # Fallback cache de noticias del proyecto
        cache = ROOT / "data" / "news_cache.json"
        try:
            if cache.exists():
                raw = json.loads(cache.read_text(encoding="utf-8"))
                events = raw.get("events") or raw.get("items") or []
                if raw.get("date"):
                    lines.append(f"Cache date: {raw.get('date')}")
        except Exception:
            pass
    if not events:
        lines.append(
            "SIN EVENTOS en el calendario/cache de la app para esta ventana. "
            "Decile al usuario exactamente eso. PROHIBIDO inventar macro, "
            "NFP, FOMC, CPI u otras news 'externas' no listadas aquí."
        )
        return "\n".join(lines)

    for i, ev in enumerate(events[:25], 1):
        if isinstance(ev, dict):
            title = ev.get("title") or ev.get("name") or ev.get("event") or str(ev)
            impact = ev.get("impact") or ev.get("importance") or ""
            when = ev.get("time") or ev.get("datetime") or ev.get("date") or ""
            cur = ev.get("currency") or ev.get("country") or ""
            lines.append(f"{i}. [{impact}] {when} {cur} — {title}".strip())
        else:
            lines.append(f"{i}. {ev}")
    return "\n".join(lines)


def _structure_block(result: dict) -> str:
    lines = ["## Estructura / sesgo (motor)"]
    lines.append(f"Símbolo: {result.get('symbol') or SYMBOL}")
    lines.append(f"Sesgo: {result.get('bias', '—')}")
    verd = result.get("veredicto") or {}
    if verd:
        lines.append(f"Veredicto keys: {', '.join(sorted(str(k) for k in list(verd.keys())[:20]))}")
        if verd.get("canonical_entry") is not None:
            lines.append(
                f"Canonical: side={verd.get('canonical_side')} "
                f"entry={verd.get('canonical_entry')} "
                f"SL={verd.get('invalidation')} TP={verd.get('target')} "
                f"RR={verd.get('canonical_rr')}"
            )
    can = result.get("canonical")
    if isinstance(can, dict) and can.get("entry") is not None:
        lines.append(
            f"Plan canónico: {can.get('side')} E={can.get('entry')} "
            f"SL={can.get('sl')} TP={can.get('tp')} RR={can.get('rr')} "
            f"engine={can.get('engine')}"
        )
    wyk = result.get("wyckoff") or {}
    if wyk:
        m15 = wyk.get("M15") if isinstance(wyk, dict) else None
        if isinstance(m15, dict):
            lines.append(
                f"Wyckoff M15: fase={m15.get('phase_es') or m15.get('phase')} "
                f"sesgo={m15.get('bias')}"
            )
    sem = result.get("semaforo") or {}
    if sem:
        lines.append(f"Semáforo: {sem.get('color')} — {sem.get('reasons')}")
    errs = result.get("errores") or []
    if errs:
        lines.append("Errores del ciclo: " + "; ".join(str(e) for e in errs[:8]))
    return "\n".join(lines)


def resolve_cycle_result(last_result: dict | None) -> dict | None:
    """Prefer live UI result; fall back to last_cycle.json cache."""
    if last_result and isinstance(last_result, dict) and last_result.get("bias"):
        return last_result
    try:
        cached = load_cached()
        if cached and isinstance(cached, dict):
            return cached
    except Exception:
        pass
    if last_result and isinstance(last_result, dict):
        return last_result
    return None


def build_chat_context(
    last_result: dict | None = None,
    *,
    scanner_text: str | None = None,
) -> str:
    """Full context string injected as system message for the MODELO chat."""
    result = resolve_cycle_result(last_result)
    parts: list[str] = [
        "# CONTEXTO VIVO DE LA APP OBSERVADOR (inyectado automáticamente)",
        "Usá ESTE bloque como fuente de verdad de precios y setup.",
        "PROHIBIDO pedirle al usuario que abra el Escáner o 'Genere ficha'.",
        "Si faltan datos, respondé con lo que hay y decí qué falta del motor,",
        "pero NO mandes al usuario a hacer clicks.",
        "",
    ]

    # 1) Ficha de precios (misma del escáner)
    card = (scanner_text or "").strip()
    if not card:
        card = build_scanner_report(result)
    parts.append("## Ficha de precios / setup")
    parts.append(card)
    parts.append("")

    # 2) Estructura + canónico
    if result:
        parts.append(_structure_block(result))
        parts.append("")
    else:
        parts.append("## Estructura / sesgo")
        parts.append("Sin ciclo del motor en memoria ni en last_cycle.json.")
        parts.append("")

    # 3) Noticias de la app
    parts.append(_news_block(result))
    parts.append("")

    parts.append("## Instrucción de respuesta (calidad modelo completo)")
    parts.append(
        "Respondé al nivel Claude/GPT/Grok: denso, estructurado, con criterio.\n"
        "- Resumen de mercado: sesgo + modelo ICT + estructura multi-TF + plan "
        "(Entry/SL/TP SOLO si están arriba) + noticias reales + lectura honesta R:R.\n"
        "- Si piden 'repaso/profundizar': NO copies el resumen anterior; profundizá "
        "lógica ICT, invalidación, escenarios A/B, pips de risk/reward, qué haría "
        "un operador disciplinado ahora.\n"
        "- Noticias: solo las de este bloque. Si dice SIN EVENTOS, no inventes macro.\n"
        "- Español rioplatense. Sin mandar al usuario a generar fichas ni clicks.\n"
        "- Si R:R < 1:2: diga claro que no conviene para live."
    )
    return "\n".join(parts)

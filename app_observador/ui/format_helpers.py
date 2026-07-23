"""Funciones PURAS de formato para los widgets del observador (Fase 5 UI).

Se extraen aquí para poder testearlas SIN importar PySide6 (los widgets
QWidget no corren en pytest headless). Los widgets solo llaman estas
funciones y setean el texto/estilo de sus QLabel.

Reglas honestas del SDD:
  - Campo del motor ausente  → "EN CONSTRUCCIÓN" (nunca inventar).
  - canonical tiene 3 estados: dict (plan) / "EN CONSTRUCCIÓN" (str) / None.

Este módulo importa SOLO constantes de color de theme.py (strings planos),
no PySide6, por lo que es 100% testeable en headless.
"""
from __future__ import annotations

from app_observador.ui.theme import TEXT_DIM, TEXT_MUTED, GREEN, YELLOW, RED

EN_CONSTRUCCION = "EN CONSTRUCCIÓN"

# Mapa de la máquina de estados del trigger → texto legible en español.
_TRIGGER_MAP = {
    "PENDING": "esperando",
    "STRUCTURE_READY": "estructura lista",
    "WAITING_PULLBACK": "esperando retroceso",
    "TRIGGER_READY": "✅ LISTO (en killzone)",
    "TRIGGER_READY_OFF_SESSION": "⏳ listo fuera de killzone",
}


def _fmt_price(x) -> str:
    try:
        return f"{float(x):.5f}"
    except Exception:
        return "—"


def format_poi(ca: dict | None) -> str:
    """POI enriquecido: `POI: <tier> [anclado] [apilado] (+bonus)`.

    Si no hay `poi_tier` en el context_alignment → "POI: EN CONSTRUCCIÓN".
    """
    ca = ca or {}
    tier = ca.get("poi_tier")
    if not tier:
        return f"POI: {EN_CONSTRUCCION}"

    parts = [str(tier)]
    if ca.get("poi_anchored"):
        parts.append("anclado")
    if ca.get("poi_stacked"):
        parts.append("apilado")

    tier_note = ca.get("poi_tier_note") or ca.get("tier_note")
    if str(tier).upper() == "SKIP" and tier_note:
        # ej. "SKIP wrong-side" — mostrar el diagnóstico honesto.
        note = str(tier_note).replace("SKIP", "").strip()
        if note:
            parts.append(note)

    bonus = ca.get("poi_quality_bonus", 0)
    try:
        bonus = int(bonus)
    except Exception:
        bonus = 0
    return f"POI: {' '.join(parts)} (+{bonus})"


def format_trigger(machine_state: str | None) -> str:
    """Trigger como máquina de estados legible: `TRIGGER: <estado español>`.

    Si `machine_state` es None/ausente/desconocido → "TRIGGER: EN CONSTRUCCIÓN".
    """
    if not machine_state:
        return f"TRIGGER: {EN_CONSTRUCCION}"
    legible = _TRIGGER_MAP.get(str(machine_state))
    if legible is None:
        return f"TRIGGER: {EN_CONSTRUCCION}"
    return f"TRIGGER: {legible}"


def canonical_is_ready(canonical) -> bool:
    """True solo si canonical es un plan vigente (dict con entry).

    "EN CONSTRUCCIÓN" (str) → False (calculando/colgado).
    None → False (corrió limpio, sin señal).
    """
    return isinstance(canonical, dict) and canonical.get("entry") is not None


def format_canonical(canonical) -> tuple[str, str]:
    """Formatea el canonical a (texto, color) para el chip de plan.

    3 estados honestos del SDD:
      - dict poblado  → (texto con side/plan, color verde)
      - "EN CONSTRUCCIÓN" → ("⏳ calculando plan…", color gris)
      - None → ("sin plan vigente", color dim)
    """
    if canonical_is_ready(canonical):
        side = str(canonical.get("side") or "—")
        entry = _fmt_price(canonical.get("entry"))
        sl = _fmt_price(canonical.get("sl"))
        tp = _fmt_price(canonical.get("tp"))
        texto = f"{side} · E {entry} · SL {sl} · TP {tp}"
        return texto, GREEN

    if canonical == EN_CONSTRUCCION:
        return "⏳ calculando plan…", TEXT_MUTED

    # None (o cualquier otro caso no-plan): corrió limpio, sin señal.
    return "sin plan vigente", TEXT_DIM

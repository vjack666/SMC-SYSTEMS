"""LLM client for the observador Chat tab.

Priority:
  1) Hermes Agent live config (Nous Portal OAuth + model from config.yaml)
  2) XAI_API_KEY / OPENAI_API_KEY fallback (SpaceXAI / custom OpenAI-compatible)

No hard dependency on the `openai` package — uses `requests`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from app_observador.config import ROOT
from app_observador.core.hermes_config import (
    hermes_model_settings,
    hermes_status_line,
    resolve_hermes_credentials,
)

# Senior-analyst system prompt: quality bar = Claude / GPT / Grok desk brief.
# (No tools; live market data arrives via injected system context every turn.)
HERMES_SYSTEM = """Sos Hermes ICT: analista senior de Smart Money Concepts (ICT + Wyckoff)
embebido en la app SMC-SYSTEMS (modo OBSERVADOR — no abre órdenes; decide el humano).

Nivel de respuesta: igual que un modelo completo (Claude / GPT / Grok). NO respondas
como bot corto ni como checklist genérico. Escribí en español rioplatense, claro,
profesional y con criterio.

## Fuente de verdad
Cada mensaje trae un bloque de CONTEXTO VIVO de la app (ficha, estructura, noticias).
- Usá SOLO esos números para Entry/SL/TP/zonas.
- NUNCA inventes precios, noticias, horarios de eventos ni “macro general” no listado.
- Si no hay noticias en contexto: decí “sin eventos en el calendario de la app” y listo.
  No rellenes con “contexto externo” inventado.
- NUNCA pidas al usuario que abra Escáner, genere ficha o adjunte nada.

## Formato de un resumen de mercado (primera respuesta o “dame contexto”)
Estructura OBLIGATORIA (podés usar tablas markdown o listas densas):

1) **Sesgo y modelo ICT** — sesgo, votos, modelo + score, semáforo y por qué.
2) **Estructura multi-TF** — D1 / H4 / M15 (trend, BOS, sweep, FVG, OB, CHOCH, Wyckoff).
3) **Plan operativo** — lado, zona OTE, Entry, SL, TP, R:R, pips aprox de risk/reward,
   sizing ref y límites challenge si están.
4) **Noticias** — lista real del contexto, o “sin eventos en app”.
5) **Lectura operativa honesta** — qué confirma el setup, qué lo invalida, si conviene
   o no (R:R ≥ 1:2), y qué esperar (no forzar trade).

## Si el usuario dice “repasalo / profundizá / detallá”
NO repitas el mismo resumen con otras palabras.
Subí de nivel: explicá la lógica ICT del Silver Bullet / Turtle / PO3 con ESTOS niveles;
condiciones de invalidación; escenarios A/B (si respeta OTE vs si rompe SL); killzone
si aplica; por qué el R:R es bueno o malo en pips; qué haría un operador disciplinado
ahora (esperar / no operar / vigilar nivel X). Máximo 1 pregunta al final, y solo si suma.

## Reglas de riesgo
- R:R < 1:2 → setup NO conviene para live (decilo sin suavizar).
- Prop firm: no incentivar forzar trades en semáforo AMARILLO/ROJO.
- Admití incertidumbre: “el motor no trae X” es mejor que inventar.

## Estilo
- Densidad alta, sin relleno, sin “¡Claro!” ni frases vacías.
- Números con 5 decimales en FX cuando existan.
- Tono de mentor senior que enseña el porqué, no un teleprompter.
"""

DEFAULT_SYSTEM = HERMES_SYSTEM

XAI_SYSTEM = HERMES_SYSTEM


def list_chat_models() -> list[tuple[str, str, str, str]]:
    """UI models: (display_name, api_model_id, system_prompt, provider_tag).

    provider_tag: 'hermes' | 'xai' | 'openai'
    """
    ms = hermes_model_settings()
    models: list[tuple[str, str, str, str]] = [
        (
            "Hermes ICT",
            ms.model_id,
            HERMES_SYSTEM,
            "hermes",
        ),
        ("Grok 4.5 (xAI)", "grok-4.5", XAI_SYSTEM, "xai"),
        ("Grok 3 mini (xAI)", "grok-3-mini", XAI_SYSTEM, "xai"),
    ]
    return models


# Back-compat for imports that expect CHAT_MODELS as 3-tuples
CHAT_MODELS: list[tuple[str, str, str]] = [
    (label, mid, sys) for label, mid, sys, _prov in list_chat_models()
]


@dataclass(frozen=True)
class ChatConfig:
    api_key: str
    base_url: str
    model: str
    provider: str = "unknown"


def _load_dotenv_once() -> None:
    try:
        from dotenv import load_dotenv

        env_path = ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
        else:
            load_dotenv(override=False)
    except Exception:
        pass


def resolve_chat_config(
    model_id: str | None = None,
    *,
    provider_tag: str | None = None,
) -> ChatConfig | None:
    """Resolve API credentials for the selected model/provider."""
    _load_dotenv_once()
    ms = hermes_model_settings()
    mid = (model_id or ms.model_id).strip()
    tag = (provider_tag or "").strip().lower()

    # Infer provider from model id if not tagged
    if not tag:
        if mid.startswith("grok-") or mid.startswith("grok"):
            tag = "xai"
        else:
            tag = "hermes"

    if tag == "hermes":
        creds = resolve_hermes_credentials()
        if creds and creds.get("api_key"):
            return ChatConfig(
                api_key=str(creds["api_key"]),
                base_url=str(creds.get("base_url") or ms.base_url).rstrip("/"),
                model=mid,
                provider=str(creds.get("provider") or ms.provider),
            )
        # fall through to env if Hermes session missing

    if tag in ("xai", "openai") or tag == "hermes":
        key = (
            os.environ.get("XAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        if key:
            if tag == "xai" or mid.startswith("grok"):
                base = (
                    os.environ.get("XAI_BASE_URL")
                    or "https://api.x.ai/v1"
                ).rstrip("/")
                prov = "xai"
            else:
                base = (
                    os.environ.get("OPENAI_BASE_URL")
                    or os.environ.get("XAI_BASE_URL")
                    or "https://api.x.ai/v1"
                ).rstrip("/")
                prov = "openai"
            return ChatConfig(api_key=key, base_url=base, model=mid, provider=prov)

    return None


def status_line() -> str:
    """UI status: Hermes first, then env keys."""
    try:
        h = hermes_status_line()
    except Exception as e:
        h = f"Hermes status error: {e}"
    _load_dotenv_once()
    has_xai = bool((os.environ.get("XAI_API_KEY") or "").strip())
    has_oai = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    extra = []
    if has_xai:
        extra.append("XAI_API_KEY ok")
    if has_oai:
        extra.append("OPENAI_API_KEY ok")
    if extra:
        return h + " · " + " · ".join(extra)
    return h


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model_id: str | None = None,
    provider_tag: str | None = None,
    temperature: float = 0.4,
    timeout_s: float = 120.0,
) -> str:
    """POST /chat/completions. Raises RuntimeError with a clear message on failure."""
    ms = hermes_model_settings()
    mid = model_id or ms.model_id
    cfg = resolve_chat_config(mid, provider_tag=provider_tag)
    if cfg is None:
        raise RuntimeError(
            "Sin credenciales. Hermes (Nous OAuth) no resolvió token y tampoco hay "
            "XAI_API_KEY / OPENAI_API_KEY. Abrí Hermes o corré `hermes auth`."
        )

    url = f"{cfg.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
    }
    # Some free/Nous models ignore or reject temperature — send only if not hermes free path issues
    if cfg.provider != "nous":
        body["temperature"] = temperature

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout_s)
    except requests.RequestException as e:
        raise RuntimeError(f"Error de red al llamar al modelo: {e}") from e

    # One retry on 401 with forced Hermes refresh
    if resp.status_code == 401 and (provider_tag or "hermes") == "hermes":
        resolve_hermes_credentials(force_refresh=True)
        cfg2 = resolve_chat_config(mid, provider_tag="hermes")
        if cfg2:
            headers["Authorization"] = f"Bearer {cfg2.api_key}"
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=timeout_s)
            except requests.RequestException as e:
                raise RuntimeError(f"Error de red al reintentar: {e}") from e

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(
            f"API {resp.status_code} [{cfg.provider} {cfg.model} @ {cfg.base_url}]: {detail}"
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            # some providers return content parts
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append(str(p.get("text") or ""))
                else:
                    parts.append(str(p))
            return "\n".join(parts).strip()
        return str(content).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Respuesta inesperada del modelo: {data!r}") from e

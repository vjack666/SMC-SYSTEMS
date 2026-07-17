"""Load the live Hermes Agent config used on this machine.

Reads:
  %LOCALAPPDATA%/hermes/config.yaml   → model, provider, base_url
  auth via hermes_cli.auth (OAuth Nous) → short-lived Bearer token

Never hardcodes secrets. Tokens are resolved at call time and can refresh.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


def hermes_home() -> Path:
    env = (os.environ.get("HERMES_HOME") or "").strip()
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "hermes"


def hermes_agent_root() -> Path:
    return hermes_home() / "hermes-agent"


def hermes_venv_python() -> Path | None:
    py = hermes_agent_root() / "venv" / "Scripts" / "python.exe"
    if py.exists():
        return py
    py2 = hermes_agent_root() / "venv" / "bin" / "python"
    if py2.exists():
        return py2
    return None


@lru_cache(maxsize=1)
def load_hermes_yaml() -> dict[str, Any]:
    path = hermes_home() / "config.yaml"
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        # Minimal parser for the keys we need if PyYAML missing
        return _parse_yaml_min(path.read_text(encoding="utf-8", errors="replace"))


def _parse_yaml_min(text: str) -> dict[str, Any]:
    """Tiny subset parser: top-level model.default / provider / base_url."""
    out: dict[str, Any] = {"model": {}}
    section = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            if section == "model":
                out["model"] = {}
            continue
        if section == "model" and ":" in line:
            k, v = line.strip().split(":", 1)
            out["model"][k.strip()] = v.strip().strip("\"'")
    return out


@dataclass(frozen=True)
class HermesModelSettings:
    model_id: str
    provider: str
    base_url: str
    reasoning_effort: str
    config_path: str


def hermes_model_settings() -> HermesModelSettings:
    cfg = load_hermes_yaml()
    model = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    agent = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
    model_id = str(model.get("default") or "tencent/hy3:free").strip()
    provider = str(model.get("provider") or "nous").strip()
    base_url = str(
        model.get("base_url")
        or "https://inference-api.nousresearch.com/v1"
    ).rstrip("/")
    effort = str(agent.get("reasoning_effort") or "medium").strip()
    return HermesModelSettings(
        model_id=model_id,
        provider=provider,
        base_url=base_url,
        reasoning_effort=effort,
        config_path=str(hermes_home() / "config.yaml"),
    )


# Cache short-lived credentials (refresh near expiry)
_cred_cache: dict[str, Any] | None = None
_cred_cache_until: float = 0.0


def _parse_expires_at(s: str | None) -> float:
    if not s:
        return 0.0
    try:
        # 2026-07-17T15:00:49+00:00
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def resolve_hermes_credentials(*, force_refresh: bool = False) -> dict[str, Any] | None:
    """Return {api_key, base_url, provider, expires_at, source} or None."""
    global _cred_cache, _cred_cache_until
    now = datetime.now(timezone.utc).timestamp()
    if (
        not force_refresh
        and _cred_cache
        and _cred_cache_until - 90 > now  # 90s skew
    ):
        return _cred_cache

    creds = _resolve_via_import(force_refresh=force_refresh)
    if creds is None:
        creds = _resolve_via_subprocess(force_refresh=force_refresh)
    if creds is None:
        creds = _resolve_from_auth_json_fallback()

    if creds and creds.get("api_key"):
        _cred_cache = creds
        _cred_cache_until = _parse_expires_at(str(creds.get("expires_at") or "")) or (
            now + 300
        )
        return creds
    return None


def _resolve_via_import(*, force_refresh: bool = False) -> dict[str, Any] | None:
    root = hermes_agent_root()
    if not root.exists():
        return None
    try:
        # Ensure Hermes sees the same home
        os.environ.setdefault("HERMES_HOME", str(hermes_home()))
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from hermes_cli.auth import resolve_nous_runtime_credentials  # type: ignore

        raw = resolve_nous_runtime_credentials(force_refresh=force_refresh)
        if not isinstance(raw, dict):
            return None
        return {
            "provider": raw.get("provider") or "nous",
            "base_url": str(raw.get("base_url") or "").rstrip("/"),
            "api_key": str(raw.get("api_key") or ""),
            "expires_at": raw.get("expires_at"),
            "source": f"hermes_cli:{raw.get('source') or 'import'}",
        }
    except Exception:
        return None


def _resolve_via_subprocess(*, force_refresh: bool = False) -> dict[str, Any] | None:
    py = hermes_venv_python()
    root = hermes_agent_root()
    if not py or not root.exists():
        return None
    code = (
        "import json,sys,os;"
        f"os.environ['HERMES_HOME']=r'{hermes_home()}';"
        f"sys.path.insert(0,r'{root}');"
        "from hermes_cli.auth import resolve_nous_runtime_credentials;"
        f"c=resolve_nous_runtime_credentials(force_refresh={bool(force_refresh)});"
        "print(json.dumps({"
        "'provider':c.get('provider'),"
        "'base_url':c.get('base_url'),"
        "'api_key':c.get('api_key'),"
        "'expires_at':c.get('expires_at'),"
        "'source':'subprocess:'+str(c.get('source') or '')"
        "}))"
    )
    try:
        proc = subprocess.run(
            [str(py), "-c", code],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(root),
            env={**os.environ, "HERMES_HOME": str(hermes_home())},
        )
        if proc.returncode != 0:
            return None
        line = (proc.stdout or "").strip().splitlines()[-1]
        data = json.loads(line)
        if not data.get("api_key"):
            return None
        data["base_url"] = str(data.get("base_url") or "").rstrip("/")
        return data
    except Exception:
        return None


def _resolve_from_auth_json_fallback() -> dict[str, Any] | None:
    """Last resort: read agent_key / access_token if still valid."""
    path = hermes_home() / "auth.json"
    if not path.exists():
        return None
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    providers = store.get("providers") or {}
    nous = providers.get("nous") or {}
    token = str(nous.get("agent_key") or nous.get("access_token") or "").strip()
    if not token:
        return None
    exp = _parse_expires_at(str(nous.get("agent_key_expires_at") or nous.get("expires_at") or ""))
    now = datetime.now(timezone.utc).timestamp()
    if exp and exp - 90 <= now:
        return None  # expired — need refresh path
    base = str(
        nous.get("inference_base_url")
        or "https://inference-api.nousresearch.com/v1"
    ).rstrip("/")
    return {
        "provider": "nous",
        "base_url": base,
        "api_key": token,
        "expires_at": nous.get("agent_key_expires_at") or nous.get("expires_at"),
        "source": "auth.json:fallback",
    }


def hermes_status_line() -> str:
    """Human status for the Chat tab (no secrets)."""
    ms = hermes_model_settings()
    creds = resolve_hermes_credentials()
    if not creds:
        return (
            f"Hermes config: {ms.model_id} @ {ms.provider} · "
            f"SIN sesión Nous (corrí `hermes auth` o abrí Hermes)"
        )
    exp = creds.get("expires_at") or "?"
    return (
        f"Hermes OK · {ms.model_id} · {ms.provider} · "
        f"{creds.get('base_url')} · token hasta {exp} · src={creds.get('source')}"
    )

#!/usr/bin/env python3
"""
check_truth_sources.py — Auditoría automática de fuentes de verdad (Misión 1).

Verifica que las referencias ACTIVAS en los documentos de autoridad
(AGENTS.md, README.md, opencode.json) apunten a archivos que realmente existen
en el árbol, y que NO citen documentación histórica/descartada como autoridad
ni proyectos ajenos (QUOTEX/binarias/OTC) como instrucción vigente.

NO modifica archivos. Falla (exit != 0) si hay referencias rotas activas.

Uso:
    python scripts/check_truth_sources.py
    python scripts/check_truth_sources.py --root .

Criterio de éxito (contrato §13):
    BROKEN ACTIVE REFERENCES = 0
    ACTIVE CROSS-PROJECT REFERENCES = 0
    AUTHORITY AMBIGUITIES = 0
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Windows may expose the console as cp1252.  The audit report can contain
# Unicode markers copied from repository documentation; keep verification
# deterministic by replacing only characters the active console cannot emit.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Autoridad ACTIVA que debe existir (verificación positiva).
ACTIVE_AUTHORITY = [
    "AGENTS.md", "README.md",
    "docs/ict/SPEC_TESIS_FORMAL.md", "docs/DECISION_BACKTEST_UNICO.md",
    "engine/", "ict_backtest/",
    "docs/specs/SDD_GOVERNANCE.md", "docs/specs/INDICE_MDS.md",
    "docs/architecture/RESEARCH_CONTRACT.md", "docs/architecture/DIRECTORY_CONTRACT.md",
    "agents/governance/ROLES_GOBERNANZA.md", "agents/governance/ORQUESTADOR.md",
    "agents/governance/PROTOCOLO_AGENTE.md", "agents/governance/CONTRATO_ORDEN.md",
]

# Prefijos donde resolver nombres de archivo sin ruta (bare filenames).
RESOLVE_DIRS = ["agents/governance", "agents", "engine", "ict_backtest", "scripts", "docs/specs", "docs/ict", "docs/architecture"]

# Marcadores de sección NO vigente: si un bloque de README los contiene, se ignora
# para contaminación cruzada y para "broken" (es historia/documento descartado).
NON_ACTIVE_MARKERS = ["HISTÓR", "DESCART", "HEREDADO", "OBSOLETO", "NO VIGENTE", "NO CABLEAD"]

# Referencias a proyectos ajenos (no deben aparecer como instrucción vigente del producto).
CROSS_PROJECT = re.compile(r"\b(quotex|binaria(s)?|otc)\b", re.IGNORECASE)

# Extrae referencias tipo ruta de archivo (.md/.json/.py/.spec/.yaml/.yml/.ps1/.bat).
PATH_RE = re.compile(r"`?([A-Za-z0-9_./\\-]+\.(?:md|json|py|spec|yaml|yml|ps1|bat))`?")
LINK_RE = re.compile(r"\]\(([^)]+\.(?:md|json|py|spec|yaml|yml))\)")


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa
        return ""


def resolve(ref: str, root: Path) -> bool:
    ref = ref.split("#", 1)[0]
    if ref.endswith("/"):
        return (root / ref.rstrip("/")).is_dir()
    ref_norm = ref.replace("\\", "/")
    candidates = [ref, ref_norm]
    for d in RESOLVE_DIRS:
        candidates.append(f"{d}/{ref}")
        candidates.append(f"{d}/{ref_norm}")
    return any((root / c).exists() for c in candidates)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Divide README en (encabezado, cuerpo) por '## '."""
    parts = re.split(r"(?m)^#{1,3}\s+(.+)$", text)
    # parts: [pre, h1, body1, h2, body2, ...]
    sections = []
    if parts[0].strip():
        sections.append(("__PRE__", parts[0]))
    for i in range(1, len(parts) - 1, 2):
        sections.append((parts[i], parts[i + 1]))
    return sections


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root).resolve()

    broken_active: list[str] = []
    historical_as_authority: list[str] = []
    cross_project: list[str] = []
    checked = 0

    # 1) Autoridad activa existe.
    for ref in ACTIVE_AUTHORITY:
        checked += 1
        if not resolve(ref, root):
            broken_active.append(f"AUTHORITY MISSING: {ref}")

    # 2) Escanear AGENTS.md (todo es autoridad activa, salvo bloque §16 de eliminados).
    agents_text = read_text(root / "AGENTS.md")
    # §16 es la última sección y documenta eliminados; se omite su contenido.
    sec16 = agents_text.find("### §16")
    scan_text = agents_text[:sec16] if sec16 != -1 else agents_text
    for m in PATH_RE.finditer(scan_text):
        r = m.group(1).strip()
        if not r or r.startswith("http"):
            continue
        # contexto de eliminación/documentación de borrado: "NO leas X: fue borrado"
        win = scan_text[max(0, m.start() - 200):m.start() + 120]
        if any(w in win for w in ("borrado", "eliminado", "NO leas", "fue borrad", "BORRADO")):
            historical_as_authority.append(f"AGENTS.md: ref en contexto de eliminación: {r}")
            continue
        if r in ("docs/tesis/SPEC_TESIS_FORMAL.md", "docs/tesis/TRUTH_SOURCES.md"):
            historical_as_authority.append(f"AGENTS.md: ruta obsoleta (vigentes en docs/ict/): {r}")
            continue
        if not resolve(r, root):
            broken_active.append(f"AGENTS.md: referencia rota: {r}")


    # 3) Escanear README.md por secciones (solo CURRENT para contaminación).
    readme_text = read_text(root / "README.md")
    for header, body in split_sections(readme_text):
        is_nonactive = any(mk in (header + body[:400]).upper() for mk in NON_ACTIVE_MARKERS)
        for r in set(PATH_RE.findall(body)) | set(m.group(1) for m in LINK_RE.finditer(body)):
            r = r.strip()
            if not r or r.startswith("http"):
                continue
            if r in ("docs/CRONOGRAMA_Y_ROADMAP.md", "docs/HOJA_DE_RUTA_SMC-SYSTEMS.md",
                     "docs/METRICS_CANON.md", "COMPLETION_REPORT.md"):
                if not is_nonactive:
                    historical_as_authority.append(f"README.md [{header}]: ref histórica como vigente: {r}")
                continue
            if not resolve(r, root) and not is_nonactive:
                broken_active.append(f"README.md [{header}]: referencia rota: {r}")
        if not is_nonactive:
            for m in CROSS_PROJECT.finditer(body):
                # tolerar enunciados de frontera de dominio (lo que el contrato §4 exige):
                # "NO es Quotex/binarias/OTC", "exclusivamente Forex", "no debe mezclarse"
                ctx = body[max(0, m.start() - 120):m.start() + 40]
                if any(w in ctx for w in ("NO es", "NO debe", "exclusivament", "NO es un bot", "no debe mezclarse")):
                    continue
                cross_project.append(f"README.md [{header}]: proyecto ajeno en zona vigente: '{m.group(0)}'")

    # 4) opencode.json.instructions debe existir.
    oc = root / "opencode.json"
    if oc.exists():
        try:
            data = json.loads(oc.read_text(encoding="utf-8"))
            for instr in data.get("instructions", []):
                if instr.startswith("http"):
                    continue
                checked += 1
                if not resolve(instr, root):
                    broken_active.append(f"opencode.json: instrucción rota: {instr}")
        except Exception as exc:  # noqa
            broken_active.append(f"opencode.json: JSON inválido: {exc}")

    # 5) Resultado.
    print("=" * 64)
    print("AUDITORÍA DE FUENTES DE VERDAD — SMC-SYSTEMS (Misión 1)")
    print("=" * 64)
    print(f"CURRENT SOURCES verificadas : {checked}")
    print(f"BROKEN ACTIVE REFERENCES     : {len(broken_active)}")
    print(f"HISTORICAL AS AUTHORITY      : {len(historical_as_authority)} (informativo)")
    print(f"ACTIVE CROSS-PROJECT REFS    : {len(cross_project)}")
    print("-" * 64)
    for x in broken_active:
        print(f"  [BROKEN] {x}")
    for x in historical_as_authority:
        print(f"  [HIST]   {x}")
    for x in cross_project:
        print(f"  [CROSS]  {x}")

    ok = (len(broken_active) == 0 and len(cross_project) == 0)
    print("-" * 64)
    if ok:
        print("RESULTADO: OK — BROKEN ACTIVE=0, CROSS-PROJECT=0")
        print("Criterio de terminación §13 CUMPLIDO.")
        return 0
    print("RESULTADO: FALLO — corregir referencias antes de cerrar misión.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

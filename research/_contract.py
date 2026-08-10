"""Validador del contrato de `research/` (FASE 3B).

NO es código de experimento: es un *guardián del contrato*. Impide que un EXP-NNN
incompleto se promueva o se considere válido.

Uso:
    python research/_contract.py skeleton          # verifica que research/ tiene la estructura contractual
    python research/_contract.py check <path/EXP-NNN>   # verifica un experimento

Reglas implementadas (de docs/architecture/RESEARCH_CONTRACT.md):
- §3 archivos obligatorios de EXP-NNN
- §9 inmutabilidad: verdict.yaml debe incluir hash de results/ cuando existe
- §6 research/experiments/EXP-NNN = fuente primaria

No crea, mueve ni repara nada. Solo valida.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

RESEARCH_ROOT = Path(__file__).resolve().parent

REQUIRED_EXP_FILES = [
    "experiment.md",
    "protocol.yaml",
    "config.yaml",
    "data_manifest.json",
    "verdict.yaml",
]
REQUIRED_EXP_DIRS = ["code", "run", "results", "evidence"]

REQUIRED_SKELETON_DIRS = ["hypotheses", "experiments", "protocols", "validation"]


def _err(msg: str) -> None:
    print(f"FAIL: {msg}")


def check_skeleton(root: Path = RESEARCH_ROOT) -> bool:
    """Verifica que research/ tenga las 4 carpetas contractuales."""
    ok = True
    for d in REQUIRED_SKELETON_DIRS:
        p = root / d
        if not p.is_dir():
            _err(f"falta carpeta contractual: research/{d}/")
            ok = False
    if ok:
        print("OK skeleton: research/ tiene hypotheses/experiments/protocols/validation")
    return ok


def _hash_dir(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


def check_experiment(exp_path: Path) -> bool:
    """Valida un EXP-NNN contra el contrato. Devuelve True si cumple."""
    ok = True
    if not exp_path.is_dir():
        _err(f"no es directorio: {exp_path}")
        return False

    # §3 archivos obligatorios
    for f in REQUIRED_EXP_FILES:
        if not (exp_path / f).is_file():
            _err(f"EXP {exp_path.name}: falta archivo obligatorio {f}")
            ok = False
    # §3 carpetas obligatorias
    for d in REQUIRED_EXP_DIRS:
        if not (exp_path / d).is_dir():
            _err(f"EXP {exp_path.name}: falta carpeta obligatoria {d}/")
            ok = False

    # §9 inmutabilidad: si results/ existe y hay verdict.yaml, debe referenciar su hash
    results_dir = exp_path / "results"
    verdict = exp_path / "verdict.yaml"
    if results_dir.is_dir() and verdict.is_file():
        txt = verdict.read_text(encoding="utf-8")
        if "results_hash:" not in txt:
            _err(f"EXP {exp_path.name}: verdict.yaml no incluye results_hash (§9 inmutabilidad)")
            ok = False

    if ok:
        print(f"OK EXP {exp_path.name}: cumple contrato (fuente primaria válida)")
    return ok


def main(argv: list[str]) -> int:
    if not argv:
        _err("uso: _contract.py skeleton | check <EXP-NNN-path>")
        return 2
    cmd = argv[0]
    if cmd == "skeleton":
        return 0 if check_skeleton() else 1
    if cmd == "check":
        if len(argv) < 2:
            _err("check requiere <path/EXP-NNN>")
            return 2
        return 0 if check_experiment(Path(argv[1])) else 1
    _err(f"comando desconocido: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

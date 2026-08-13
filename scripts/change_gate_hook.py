#!/usr/bin/env python3
"""Pre-commit hook: Change Gate Enforcement (Opción C del CEO).

Este script es invocado por Git AUTOMATICAMENTE antes de cada commit.
Si el validador detecta un cambio no autorizado sobre un path protegido,
el commit se CANCELA (exit 1). Esto cierra la frontera de cambio:
ya no se puede "entrar por la ventana" escribiendo y haciendo commit por fuera.

Opción C: engine/ es única fuente de decisión y permanece IGNORANTE del gate.
Este hook vive en la frontera de promoción del repo, NO dentro del motor.

Autoridades:
- SDD_GOVERNANCE.md (DoR, estados, verificación)
- PROTOCOLO_AGENTE.md (estados operacionales)
- auditor_independiente.md (veto, independencia)
- AGENTS.md (Ley Fundamental: engine≠backtest, I1 hipótesis no promovida)

Uso:
  Se instala como .git/hooks/pre-commit (o vía core.hooksPath).
  No requiere argumentos.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Asegurar que el repo esté en sys.path para importar gate/
def _find_repo_root(start: Path) -> Path:
    """Sube hasta encontrar .git/."""
    cur = start.resolve()
    for _ in range(6):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve().parent.parent  # fallback: dos niveles


REPO_ROOT = _find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT))

from gate import GateConfig
from gate.change_validator import ChangeGateValidator, DiffEntry, TaskContext


def _git(*args: str) -> str:
    """Ejecuta un comando git y devuelve stdout (strip)."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Si git falla (ej. no repo), devolver vacío para no bloquear ciegamente
        return ""


def _changed_paths() -> list[str]:
    """Archivos en el staging area (git diff --cached --name-only)."""
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if not out:
        return []
    return [p for p in out.splitlines() if p.strip()]


def _current_branch() -> str:
    return _git("branch", "--show-current")


def _derive_task_id(branch: str) -> str:
    """Deriva task_id del nombre de branch.

    Formatos aceptados:
      feature/TASK-123, feature/backtest-ict, TASK-456, hotfix/xxx-TASK-7
    Si no hay TASK-xxx, usa el branch tal cual (puede no estar promovido).
    """
    import re
    m = re.search(r"TASK-(\w+)", branch, re.IGNORECASE)
    if m:
        return f"TASK-{m.group(1).upper()}"
    return branch or "NO-BRANCH"


def _load_task_context(task_id: str) -> TaskContext:
    """Carga el contexto de la tarea desde el registry de tareas.

    En integración real esto vendría de un registry persistente. Por ahora
    leemos gate/task_registry.json si existe; si no, el contexto es
    "no promovido / sin DoR" -> cualquier cambio protegido será BLOCK.
    Esto es correcto: sin evidencia de promoción, el cambio se rechaza.
    """
    registry_path = REPO_ROOT / "gate" / "task_registry.json"
    default = TaskContext(
        task_id=task_id,
        state="DISCOVERED",
        promoted=False,
        dor_passed=False,
        creator="",
        auditor="",
        has_evidence=False,
    )
    if not registry_path.exists():
        return default

    try:
        registry = json.loads(registry_path.read_text())
    except json.JSONDecodeError:
        return default

    entry = registry.get(task_id)
    if not entry:
        return default

    return TaskContext(
        task_id=task_id,
        state=entry.get("state", "DISCOVERED"),
        promoted=bool(entry.get("promoted", False)),
        dor_passed=bool(entry.get("dor_passed", False)),
        creator=entry.get("creator", ""),
        auditor=entry.get("auditor", ""),
        has_evidence=bool(entry.get("has_evidence", False)),
    )


def main() -> int:
    changed = _changed_paths()
    if not changed:
        # Nada en staging: no hay nada que validar
        return 0

    branch = _current_branch()
    task_id = _derive_task_id(branch)
    ctx = _load_task_context(task_id)

    diff = [DiffEntry(path=p, action="modify") for p in changed]

    config = GateConfig(mode="enforcement")
    validator = ChangeGateValidator(config=config)
    result = validator.validate_diff(diff, ctx)
    validator.log_validation(diff, ctx, result)

    if not result.allowed:
        print("=" * 60)
        print("CHANGE GATE: COMMIT RECHAZADO")
        print("=" * 60)
        print(f"Razón: {result.reason}")
        if result.blocked_paths:
            print("Archivos bloqueados:")
            for p in result.blocked_paths:
                print(f"  - {p}")
        print(f"Task: {task_id} | Branch: {branch}")
        print("-" * 60)
        print("Para autorizar: promueve la hipótesis, completa DoR,")
        print("asigna auditor independiente y asegura ausencia de veto.")
        print("Detalles en results/change_gate_log.json")
        print("=" * 60)
        return 1  # Git cancela el commit

    # Cambio permitido
    return 0


if __name__ == "__main__":
    sys.exit(main())

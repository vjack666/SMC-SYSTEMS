"""Tests de integración del Change Gate Hook (ENFORCEMENT real).

Estos tests verifican que el hook de pre-commit RECHAZA commits sobre paths
protegidos cuando la tarea no está promovida/validada, y PERMITE los legítimos.

No dependen del repo real: inyectan los paths y el contexto en el hook para
simular el diff de git y el registry de tareas.

Diferencia con G-K: aquí probamos el hook completo (main()), no solo el
validador suelto. Esto demuestra que la frontera de commit está cerrada.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.change_gate_hook as hook
from gate.change_validator import TaskContext


def test_hook_rechaza_commit_engine_sin_promocion():
    """Hook debe salir con exit 1 si se intenta commit de engine/ sin promoción."""
    paths = ["engine/sequence.py"]
    ctx = TaskContext(
        task_id="TASK-X1", state="DISCOVERED", promoted=False,
        dor_passed=False, creator="ingeniero_A", auditor="auditor_X",
    )
    with mock.patch.object(hook, "_changed_paths", return_value=paths), \
         mock.patch.object(hook, "_load_task_context", return_value=ctx), \
         mock.patch.object(hook, "_current_branch", return_value="feature/TASK-X1"):
        code = hook.main()
    assert code == 1, f"Hook debió rechazar commit (exit 1), salió {code}"
    print("✅ HOOK: commit engine/ sin promoción → exit 1 (RECHAZADO)")


def test_hook_rechaza_commit_engine_con_veto():
    """Hook debe salir con exit 1 si hay veto activo."""
    paths = ["engine/plan.py"]
    ctx = TaskContext(
        task_id="TASK-X2", state="READY", promoted=True, dor_passed=True,
        creator="ingeniero_A", auditor="auditor_B",
    )
    with mock.patch.object(hook, "_changed_paths", return_value=paths), \
         mock.patch.object(hook, "_load_task_context", return_value=ctx), \
         mock.patch.object(hook, "_current_branch", return_value="feature/TASK-X2"), \
         mock.patch("gate.veto_registry.VetoRegistry.has_active_veto", return_value=True):
        code = hook.main()
    assert code == 1, f"Hook debió rechazar por veto (exit 1), salió {code}"
    print("✅ HOOK: commit engine/ con veto → exit 1 (RECHAZADO)")


def_hook_permitido = None

def test_hook_permite_commit_results_sin_gate():
    """Hook debe salir con exit 0 para results/ (no protegido)."""
    paths = ["results/exp071.json"]
    ctx = TaskContext(
        task_id="TASK-X3", state="DISCOVERED", promoted=False,
        dor_passed=False, creator="", auditor="",
    )
    with mock.patch.object(hook, "_changed_paths", return_value=paths), \
         mock.patch.object(hook, "_load_task_context", return_value=ctx), \
         mock.patch.object(hook, "_current_branch", return_value="feature/TASK-X3"):
        code = hook.main()
    assert code == 0, f"Hook debió permitir results/ (exit 0), salió {code}"
    print("✅ HOOK: commit results/ → exit 0 (PERMITIDO)")


def test_hook_permite_commit_engine_legitimo():
    """Hook debe salir con exit 0 para engine/ con todo en orden."""
    paths = ["engine/sequence.py"]
    ctx = TaskContext(
        task_id="TASK-X4", state="READY", promoted=True, dor_passed=True,
        creator="ingeniero_A", auditor="auditor_B",
    )
    with mock.patch.object(hook, "_changed_paths", return_value=paths), \
         mock.patch.object(hook, "_load_task_context", return_value=ctx), \
         mock.patch.object(hook, "_current_branch", return_value="feature/TASK-X4"), \
         mock.patch("gate.veto_registry.VetoRegistry.has_active_veto", return_value=False):
        code = hook.main()
    assert code == 0, f"Hook debió permitir commit legítimo (exit 0), salió {code}"
    print("✅ HOOK: commit engine/ legítimo → exit 0 (PERMITIDO)")


def test_hook_sin_staging_no_bloquea():
    """Si no hay nada en staging, hook sale 0 (nada que validar)."""
    with mock.patch.object(hook, "_changed_paths", return_value=[]):
        code = hook.main()
    assert code == 0, f"Sin staging debió salir 0, salió {code}"
    print("✅ HOOK: sin staging → exit 0 (nada que validar)")


if __name__ == "__main__":
    test_hook_rechaza_commit_engine_sin_promocion()
    test_hook_rechaza_commit_engine_con_veto()
    test_hook_permite_commit_results_sin_gate()
    test_hook_permite_commit_engine_legitimo()
    test_hook_sin_staging_no_bloquea()
    print("\n✅ INTEGRACIÓN HOOK: frontera de commit cerrada (exit codes correctos)")

"""Tests de bypass del Change Gate (FASE 7.x, Opción C del CEO).

Diferencia con test_gate_adversarial.py (ataques A-F):
- A-F llaman gate.request_change() -> prueban la API del gate.
- G-K construyen un DIFF y lo pasan a ChangeGateValidator.validate_diff().
  Nadie llama request_change(). Esto simula "entrar por la ventana":
  el agente escribe directo sin pedir permiso, y el validador de la
  frontera de cambio debe cazarlo.

Cada test debe demostrar BLOCK (o ALLOW correcto en K) SOBRE EL DIFF.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.change_validator import ChangeGateValidator, DiffEntry, TaskContext
from gate import GateConfig


def test_attack_g_modificacion_directa_engine_sin_promocion():
    """G: write directo a engine/ SIN pasar por API del gate, sin promoción -> BLOCK.
    
    Esto es el bypass real: el agente no llama request_change().
    """
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    # Agente escribe directo (NO llama request_change)
    diff = [DiffEntry(path="engine/sequence.py", action="modify")]
    
    # Contexto de tarea: hipótesis NO promovida (I1)
    ctx = TaskContext(
        task_id="TASK-G1",
        state="DISCOVERED",
        promoted=False,
        dor_passed=False,
        creator="ingeniero_A",
        auditor="auditor_X",
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == False, f"ATAQUE G FALLÓ: engine modificado sin promoción. Reason: {result.reason}"
    assert "I1" in result.reason, f"Razón debe mencionar I1: {result.reason}"
    assert "engine/sequence.py" in result.blocked_paths
    print("✅ ATAQUE G: write directo engine/ sin promoción → BLOCK (sobre diff)")


def test_attack_h_modificacion_directa_dor_falso():
    """H: write directo a engine/ con DoR falso/inexistente -> BLOCK en diff."""
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    diff = [DiffEntry(path="engine/plan.py", action="modify")]
    
    ctx = TaskContext(
        task_id="TASK-H1",
        state="READY",
        promoted=True,         # promovida, pero...
        dor_passed=False,       # ...DoR NO validado
        creator="ingeniero_A",
        auditor="auditor_X",
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == False, f"ATAQUE H FALLÓ: modificación sin DoR permitida. Reason: {result.reason}"
    assert "DoR" in result.reason, f"Razón debe mencionar DoR: {result.reason}"
    print("✅ ATAQUE H: write directo engine/ con DoR falso → BLOCK (sobre diff)")


def test_attack_i_modificacion_estado_invalido():
    """I: write directo a engine/ con estado inválido (DISCOVERED) -> BLOCK en diff."""
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    diff = [DiffEntry(path="engine/htf_narrative.py", action="modify")]
    
    ctx = TaskContext(
        task_id="TASK-I1",
        state="DISCOVERED",    # estado inválido para modificar (no READY/IMPLEMENTING)
        promoted=True,
        dor_passed=True,
        creator="ingeniero_A",
        auditor="auditor_X",
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == False, f"ATAQUE I FALLÓ: estado inválido permitido. Reason: {result.reason}"
    print("✅ ATAQUE I: write directo engine/ con estado inválido → BLOCK (sobre diff)")


def test_attack_j_modificacion_con_veto():
    """J: write directo a engine/ con veto activo -> BLOCK en diff."""
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    # Emitir veto primero
    validator._enforcer.veto_registry.emit_veto(
        task_id="TASK-J1",
        auditor_id="auditor_X",
        reason="Evidencia no reproducible",
    )
    
    diff = [DiffEntry(path="engine/dealing_range.py", action="modify")]
    
    ctx = TaskContext(
        task_id="TASK-J1",
        state="READY",
        promoted=True,
        dor_passed=True,
        creator="ingeniero_A",
        auditor="auditor_X",
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == False, f"ATAQUE J FALLÓ: promoción con veto permitida. Reason: {result.reason}"
    assert "veto" in result.reason.lower(), f"Razón debe mencionar veto: {result.reason}"
    print("✅ ATAQUE J: write directo engine/ con veto activo → BLOCK (sobre diff)")


def test_attack_k_cambio_results_sin_gate():
    """K: write a results/ (NO protegido) -> ALLOW sin burocracia, sin importar ctx."""
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    # Agente escribe directo a results/ sin promoción ni DoR
    diff = [DiffEntry(path="results/exp071.json", action="create")]
    
    ctx = TaskContext(
        task_id="TASK-K1",
        state="DISCOVERED",
        promoted=False,
        dor_passed=False,
        creator="ingeniero_A",
        auditor="",
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == True, f"ATAQUE K FALLÓ: results/ bloqueado injustamente. Reason: {result.reason}"
    assert "Sin paths protegidos" in result.reason, f"Razón debe indicar libre: {result.reason}"
    print("✅ ATAQUE K: write directo results/ sin gate → ALLOW (sin burocracia)")


def test_change_legitimo_pasa():
    """Caso positivo: cambio legítimo sobre engine/ con todo en orden -> ALLOW."""
    validator = ChangeGateValidator(GateConfig(mode="enforcement"))
    
    diff = [DiffEntry(path="engine/sequence.py", action="modify")]
    
    ctx = TaskContext(
        task_id="TASK-OK1",
        state="READY",
        promoted=True,
        dor_passed=True,
        creator="ingeniero_A",
        auditor="auditor_B",   # independiente
    )
    
    result = validator.validate_diff(diff, ctx)
    assert result.allowed == True, f"Cambio legítimo bloqueado: {result.reason}"
    print("✅ CASO POSITIVO: cambio legítimo engine/ → ALLOW")


if __name__ == "__main__":
    test_attack_g_modificacion_directa_engine_sin_promocion()
    test_attack_h_modificacion_directa_dor_falso()
    test_attack_i_modificacion_estado_invalido()
    test_attack_j_modificacion_con_veto()
    test_attack_k_cambio_results_sin_gate()
    test_change_legitimo_pasa()
    print("\n✅ FASE 7.x: validador de diff caza bypass (G-K) y permite lo legítimo")
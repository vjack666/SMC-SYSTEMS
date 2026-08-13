"""Tests adversariales del gate de gobernanza (Opción C: Gate de Cambio).

Estos tests INTENTAN ROMPER el gate y deben demostrar BLOQUEO REAL.

Cada test simula una violación de autoridad y verifica que el gate la detiene.

Autoridad: SDD_GOVERNANCE.md, PROTOCOLO_AGENTE.md, auditor_independiente.md, AGENTS.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate import (
    GateOrchestratorEnforcer,
    AuditIsolationService,
    VetoRegistry,
    VetoStatus,
    TaskState,
    GateConfig,
)
from gate.orchestrator_enforcer import ChangeRequest


def test_attack_a_modificar_engine_sin_dor():
    """ATAQUE A: Modificar engine/sequence.py sin DoR → debe BLOCK."""
    enforcer = GateOrchestratorEnforcer(GateConfig(mode="enforcement"))
    
    req = ChangeRequest(
        task_id="TASK-A1",
        agent_id="ingeniero",
        file_path="engine/sequence.py",
        action="modify",
        from_state=TaskState.READY,
        to_state=TaskState.IMPLEMENTING,
    )
    
    allowed, reason = enforcer.request_change(req)
    assert allowed == False, f"ATEQUE A FALLÓ: engine modificado sin DoR. Reason: {reason}"
    assert "DoR" in reason, f"Razón debe mencionar DoR: {reason}"
    print("✅ ATAQUE A: engine/ modificado sin DoR → BLOCK")


def test_attack_b_modificar_engine_con_dor_sin_autorizacion():
    """ATAQUE B: Modificar engine/ con DoR pero sin autorización → debe BLOCK."""
    enforcer = GateOrchestratorEnforcer(GateConfig(mode="enforcement"))
    
    # Simular que el task no tiene estado válido
    req = ChangeRequest(
        task_id="TASK-B1",
        agent_id="ingeniero",
        file_path="engine/sequence.py",
        action="modify",
        from_state=TaskState.DISCOVERED,  # Estado inválido para modificar
        to_state=TaskState.IMPLEMENTING,
    )
    
    allowed, reason = enforcer.request_change(req)
    assert allowed == False, f"ATAQUE B FALLÓ: modificación sin autorización permitida. Reason: {reason}"
    print("✅ ATAQUE B: engine/ modificado sin autorización → BLOCK")


def test_attack_c_ingeniero_autoaprueba():
    """ATAQUE C: Ingeniero produce y aprueba su propio trabajo → debe BLOCK."""
    audit = AuditIsolationService()
    
    # Intentar auto-asignación
    try:
        audit.assign_auditor(task_id="TASK-C1", creator="ingeniero_A", auditor="ingeniero_A")
        assert False, "ATAQUE C FALLÓ: auto-asignación permitida"
    except ValueError as e:
        assert "auto" in str(e).lower() or "mismo" in str(e).lower(), f"Mensaje debe indicar auto-audit: {e}"
        print("✅ ATAQUE C: Ingeniero auto-aprueba → BLOCK")


def test_attack_d_auditor_audita_su_trabajo():
    """ATAQUE D: Auditor audita trabajo del Auditor → debe BLOCK."""
    audit = AuditIsolationService()
    
    try:
        audit.assign_auditor(task_id="TASK-D1", creator="auditor_A", auditor="auditor_A")
        assert False, "ATAQUE D FALLÓ: auditor auto-audita"
    except ValueError as e:
        assert "auto" in str(e).lower(), f"Mensaje debe indicar auto-audit: {e}"
        print("✅ ATAQUE D: Auditor audita su trabajo → BLOCK")


def test_attack_e_veto_activo_promocion():
    """ATAQUE E: AUDITED→ACCEPTED con veto activo → debe BLOCK."""
    enforcer = GateOrchestratorEnforcer(GateConfig(mode="enforcement"))
    
    # Emitir veto
    enforcer.veto_registry.emit_veto(
        task_id="TASK-E1",
        auditor_id="auditor_X",
        reason="Resultados no reproducibles"
    )
    
    req = ChangeRequest(
        task_id="TASK-E1",
        agent_id="ingeniero",
        file_path="engine/plan.py",
        action="modify",
        from_state=TaskState.AUDITED,
        to_state=TaskState.ACCEPTED,
    )
    
    allowed, reason = enforcer.request_change(req)
    assert allowed == False, f"ATAQUE E FALLÓ: promoción con veto permitida. Reason: {reason}"
    assert "veto" in reason.lower(), f"Razón debe mencionar veto: {reason}"
    print("✅ ATAQUE E: Veto activo → promoción BLOCK")


def test_attack_f_archivo_no_sensible_permitido():
    """ATAQUE F: Cambiar archivo NO sensible (results/) → debe ALLOW."""
    enforcer = GateOrchestratorEnforcer(GateConfig(mode="enforcement"))
    
    req = ChangeRequest(
        task_id="TASK-F1",
        agent_id="ingeniero",
        file_path="results/exp071.json",
        action="create",
        from_state=TaskState.READY,
        to_state=TaskState.IMPLEMENTING,
    )
    
    allowed, reason = enforcer.request_change(req)
    assert allowed == True, f"ATAQUE F FALLÓ: archivo no sensible bloqueado. Reason: {reason}"
    assert "no es sensible" in reason, f"Razón debe indicar no sensible: {reason}"
    print("✅ ATAQUE F: Archivo no sensible → ALLOW (sin burocracia)")


def test_perimeter_isolation():
    """Verifica que engine/ está protegido pero docs/ no."""
    enforcer = GateOrchestratorEnforcer()
    
    assert enforcer.is_protected_path("engine/sequence.py") == True
    assert enforcer.is_protected_path("engine/plan.py") == True
    assert enforcer.is_protected_path("docs/specs/SDD_GOVERNANCE.md") == True
    assert enforcer.is_protected_path("ict_backtest/run_backtest.py") == True
    assert enforcer.is_protected_path("results/exp071.json") == False
    assert enforcer.is_protected_path("docs/bitacora/bitacora_trabajo.md") == False
    print("✅ Perímetro: engine/ protegido, results/ libre")


if __name__ == "__main__":
    test_attack_a_modificar_engine_sin_dor()
    test_attack_b_modificar_engine_con_dor_sin_autorizacion()
    test_attack_c_ingeniero_autoaprueba()
    test_attack_d_auditor_audita_su_trabajo()
    test_attack_e_veto_activo_promocion()
    test_attack_f_archivo_no_sensible_permitido()
    test_perimeter_isolation()
    print("\n✅ TODOS LOS ATAQUES DEMUESTRAN BLOQUEO REAL (o ALLOW correcto)")
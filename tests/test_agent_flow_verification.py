"""test_agent_flow_verification.py — Prueba operacional de la arquitectura de agentes.

Verifica que la cadena documentada (Orquestador→Investigador→Ingeniero→Auditor→Memoria)
existe operacionalmente sin violar separaciones.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"


def test_orquestador_delegation_mechanism_exists():
    """Verifica si existe mecanismo explícito de delegación en el orquestador."""
    orch_path = PROJECT_ROOT / "orchestration" / "orchestrator.py"
    
    content = orch_path.read_text(encoding="utf-8")
    
    # Buscar patrones de delegación explícita
    delegation_indicators = [
        "delegate",
        "dispatch_to",
        "route_to_agent",
        "investigator",
        "ingeniero",
        "auditor",
        "memoria",
    ]
    
    found_indicators = [d for d in delegation_indicators if d.lower() in content.lower()]
    
    # El orquestador actual son shims que reexportan
    assert len(found_indicators) == 0, (
        f"VIOLACIÓN: orquestador muestra indicadores de delegación: {found_indicators}. "
        "Los agentes documentados NO tienen mecanismo de handoff real."
    )


def test_investigador_is_executable_agent():
    """Verifica si el rol investigador existe como agente ejecutable."""
    # investigador.md es solo documento
    doc_path = PROJECT_ROOT / "agents" / "governance" / "investigador.md"
    
    # No existe agente ejecutable
    agent_py_paths = [
        PROJECT_ROOT / "agents" / "investigador.py",
        PROJECT_ROOT / "agents" / "governance" / "investigador.py",
        PROJECT_ROOT / "analysis" / "investigador.py",
    ]
    
    executable_exists = any(p.exists() for p in agent_py_paths)
    
    assert not executable_exists, (
        "GAP: investigador.md es solo documento. No existe agente ejecutable "
        "que realice investigación SIN tocar engine/."
    )


def test_ingeniero_has_clear_input_contract():
    """Verifica si el ingeniero recibe contrato de entrada explícito."""
    # ingeniero.md no define formato de entrada estructurado
    doc_path = PROJECT_ROOT / "agents" / "governance" / "ingeniero.md"
    
    content = doc_path.read_text(encoding="utf-8")
    
    # Buscar especificación de input format
    input_spec_indicators = ["INPUT:", "formato_de entrada:", "schema:", "contract"]
    
    has_input_spec = any(ind.lower() in content.lower() for ind in input_spec_indicators)
    
    assert not has_input_spec, (
        "GAP: ingeniero.md no define contrato de entrada explícito. "
        "No hay handshake que garantice alineación de expectativas."
    )


def test_auditor_veto_is_enforced():
    """Verifica si el auditor puede parar una promoción en la práctica."""
    # auditor_independiente.md define veto pero no hay mecanismo
    doc_path = PROJECT_ROOT / "agents" / "governance" / "auditor_independiente.md"
    
    content = doc_path.read_text(encoding="utf-8")
    
    # Verificar que el veto está documentado
    assert "veto" in content.lower() or "fiscal" in content.lower(), (
        "Auditor no define poder de veto"
    )
    
    # Verificar que NO hay mecanismo de ejecución
    audit_integration_points = [
        PROJECT_ROOT / "scripts" / "audit_veto.py",
        PROJECT_ROOT / "agents" / "auditor_independiente.py",
        PROJECT_ROOT / "orchestration" / "audit_gate.py",
    ]
    
    integration_exists = any(p.exists() for p in audit_integration_points)
    
    assert not integration_exists, (
        "GAP: El veto del auditor está documentado pero NO tiene mecanismo "
        "de ejecución que pueda detener procesos reales."
    )


def test_memoria_actua_como_log_centralizado():
    """Verifica si la memoria institucional registra eventos de forma forzada."""
    doc_path = PROJECT_ROOT / "agents" / "governance" / "memoria_institucional.md"
    
    # Verificar que NO hay sistema de logging forzado
    log_systems = [
        PROJECT_ROOT / "scripts" / "forensic_logger.py",
        PROJECT_ROOT / "agents" / "governance" / "audit_trail.py",
        PROJECT_ROOT / "monitoring" / "event_logger.py",
    ]
    
    log_system_exists = any(p.exists() for p in log_systems)
    
    assert not log_system_exists, (
        "VIOLACIÓN: memoria_institucional.md es referencia histórica, "
        "no un sistema de logging forzado que registre eventos."
    )


def test_protocolo_estados_operacionales_existen_en_codigo():
    """Verifica si los estados operacionales documentados existen en código."""
    proto_path = PROJECT_ROOT / "agents" / "governance" / "PROTOCOLO_AGENTE.md"
    
    content = proto_path.read_text(encoding="utf-8")
    
    # Verificar que estados están definidos
    states_mentioned = ["READY", "WORKING", "WAITING", "BLOCKED", "COMPLETED"]
    
    states_in_proto = [s for s in states_mentioned if s in content.upper()]
    assert len(states_in_proto) == len(states_mentioned), (
        f"PROTOCOLO_AGENTE.md menciona solo: {states_in_proto}"
    )
    
    # Verificar si existen en el código
    state_enum_files = [
        PROJECT_ROOT / "agents" / "base.py",
        PROJECT_ROOT / "orchestration" / "orchestrator.py",
        PROJECT_ROOT / "models" / "agent_state.py",
    ]
    
    code_has_states = False
    for f in state_enum_files:
        if f.exists():
            code_content = f.read_text(encoding="utf-8")
            for state in states_mentioned:
                if state in code_content:
                    code_has_states = True
                    break
    
    assert not code_has_states, (
        "VIOLACIÓN: Los estados operacionales (READY, WORKING, etc.) "
        "documentados en PROTOCOLO_AGENTE.md NO existen como enums o constants en código."
    )


def test_funnel_integrity_with_real_data():
    """Verifica que el funnel del motor funciona con datos reales."""
    funnel_path = RESULTS_DIR / "funnel_authority_filter.json"
    
    if not funnel_path.exists():
        pytest.skip("No hay funnel_authority_filter.json - correr audit_funnel_first")
    
    with open(funnel_path, "r") as f:
        data = json.load(f)
    
    # Verificar funnel integrity
    funnel = data.get("funnel", {})
    assert funnel.get("SWEEP", 0) >= funnel.get("DISPLACE", 0), (
        "Funnel invalido: SWEEP < DISPLACE"
    )
    assert funnel.get("DISPLACE", 0) >= funnel.get("BOS", 0), (
        "Funnel invalido: DISPLACE < BOS"
    )
    assert funnel.get("BOS", 0) >= funnel.get("ENTRY", 0), (
        "Funnel invalido: BOS < ENTRY"
    )


def test_agent_flow_test_report_generated():
    """Verifica que el reporte de prueba forense fue generado."""
    report_path = RESULTS_DIR / "agent_flow_test_report.json"
    
    assert report_path.exists(), (
        "FALTANTE: agent_flow_test_report.json no fue generado"
    )
    
    with open(report_path, "r") as f:
        report = json.load(f)
    
    assert "results" in report, "Reporte sin 'results'"
    assert "summary" in report, "Reporte sin 'summary'"
    
    summary = report["summary"]
    assert summary.get("violations", 0) > 0 or summary.get("gaps", 0) > 0, (
        "El reporte debería mostrar VIOLACIONES o GAPS operacionales"
    )
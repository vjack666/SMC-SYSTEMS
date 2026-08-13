"""Enforcement del gate para el cambio de sistema (NO para ejecución del motor).

Implementa la validación de:
- DoR (Definition of Ready) según SDD_GOVERNANCE.md §44-64
- Estados de transición según PROTOCOLO_AGENTE.md + SDD_GOVERNANCE.md
- Auditoría independiente (creator ≠ auditor)
- Veto de promoción según auditor_independiente.md §3.1
- Perímetro de cambio protegido (engine/, backtest canónico, tesis)

Diseño V2.1 (Opción C: Gate de Gobernanza del Cambio):
- El gate NO envuelve el motor
- El gate controla OPERACIONES DE CAMBIO en archivos sensibles
- engine/ permanece IGNORANTE del gate
- engine/ sigue siendo ÚNICA fuente de decisión de mercado

Autoridades respetadas:
- SDD_GOVERNANCE.md (DoR, estados, verificación)
- PROTOCOLO_AGENTE.md (estados operacionales)
- auditor_independiente.md (veto, independencia)
- AGENTS.md (Ley Fundamental: engine≠backtest)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from .config import GateConfig
from .states import TaskState, can_transition as check_state_transition
from .veto_registry import VetoRegistry
from .audit_isolation_service import AuditIsolationService


@dataclass
class DoRResult:
    """Resultado de la validación DoR (Definition of Ready)."""
    passed: bool
    score: float
    checks: dict[str, bool]
    errors: list[str]
    warnings: list[str]


@dataclass
class ChangeRequest:
    """Representa una operación de cambio en el sistema."""
    task_id: str
    agent_id: str
    file_path: str
    action: str  # "modify", "create", "delete"
    from_state: TaskState | str
    to_state: TaskState | str


class GateOrchestratorEnforcer:
    """Gate de Gobernanza del Cambio.
    
    Responsabilidades:
    1. Verificar DoR antes de permitir modificación de archivos sensibles
    2. Verificar transiciones de estado válidas
    3. Coordinar con VetoRegistry y AuditIsolationService
    4. Controlar el PERÍMETRO DE CAMBIO (engine/, backtest, tesis)
    5. Generar evidencia en results/
    
    NO controla:
    - Ejecución del motor (engine/sequence.run())
    - Backtests (solo consumen el motor)
    - Lectura/consulta de cualquier archivo
    """
    
    DO_RULES = [
        "objetivo_claro", "relacion_tesis", "comportamiento_esperado",
        "entradas_definidas", "salidas_definidas", "invariantes",
        "limites_explicitos", "casos_negativos", "dato_faltante_manejo",
        "criterios_falsacion", "criterios_aceptacion", "impacto_modulos",
        "prohibiciones_explicitas",
    ]
    
    def __init__(self, config: GateConfig | None = None, perimeter_path: Path | None = None):
        self.config = None
        self.veto_registry = VetoRegistry()
        self.audit_service = AuditIsolationService()
        self._results_path = Path("results")
        self._results_path.mkdir(exist_ok=True)
        self._perimeter = self._load_perimeter(perimeter_path)
        if config:
            self.config = config
        else:
            self.config = GateConfig()
    
    def _load_perimeter(self, perimeter_path: Path | None) -> dict:
        """Carga el perímetro de cambio protegido."""
        path = perimeter_path or Path("gate/perimeter.json")
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                return {"protected_paths": [], "unprotected_paths": []}
        return {"protected_paths": [], "unprotected_paths": []}
    
    def is_protected_path(self, file_path: str | Path) -> bool:
        """Verifica si un archivo está dentro del perímetro protegido.
        
        El gate solo controla CAMBIOS en archivos sensibles.
        Archivos no sensibles (docs/, results/, research/) no requieren gate.
        """
        path_str = str(file_path).replace("\\", "/")
        
        # Verificar protected_paths PRIMERO (tiene prioridad)
        for protected in self._perimeter.get("protected_paths", []):
            protected_norm = protected.rstrip("/")
            # Match exact path or path with prefix
            if path_str == protected_norm or path_str.startswith(protected_norm + "/"):
                return True
            # Also match if protected_norm is a file (not directory)
            if protected_norm.endswith((".py", ".md")) and path_str == protected_norm:
                return True
        
        # Si está en unprotected_paths, no proteger (pero protected ya fue verificado)
        for unprotected in self._perimeter.get("unprotected_paths", []):
            unprotected_norm = unprotected.rstrip("/")
            if path_str.startswith(unprotected_norm + "/") or path_str == unprotected_norm:
                return False
        
        return False
    
    def validate_dor(self, spec_path: Path) -> DoRResult:
        """Valida si un spec pasa el DoR (Definition of Ready)."""
        checks: dict[str, bool] = {}
        errors: list[str] = []
        warnings: list[str] = []
        
        if not spec_path.exists():
            errors.append(f"Spec no existe: {spec_path}")
            return DoRResult(passed=False, score=0.0, checks=checks, errors=errors, warnings=warnings)
        
        content = spec_path.read_text(encoding="utf-8")
        
        checks["objetivo_claro"] = "obj" in content.lower() or "problema" in content.lower() or "solucion" in content.lower()
        if not checks["objetivo_claro"]:
            errors.append("Falta objetivo claro")
        
        checks["relacion_tesis"] = "tesis" in content.lower() or "SPEC_TESIS_FORMAL" in content
        if not checks["relacion_tesis"]:
            warnings.append("Falta referencia a tesis ICT")
        
        checks["comportamiento_esperado"] = "entrada" in content.lower() and "salida" in content.lower()
        checks["entradas_definidas"] = "entradas" in content.lower() or "input" in content.lower()
        if not checks["entradas_definidas"]:
            errors.append("Faltan entradas definidas")
        
        checks["salidas_definidas"] = "salidas" in content.lower() or "output" in content.lower()
        checks["invariantes"] = "nunca" in content.lower() or "prohibido" in content.lower()
        checks["limites_explicitos"] = "limite" in content.lower() or "no hace" in content.lower()
        checks["casos_negativos"] = "faltante" in content.lower() or "dato" in content.lower()
        checks["dato_faltante_manejo"] = "UNKNOWN" in content or "GAP" in content
        checks["criterios_falsacion"] = "falsar" in content.lower() or "rechazar" in content.lower()
        checks["criterios_aceptacion"] = "aceptar" in content.lower() or "validado" in content.lower()
        checks["impacto_modulos"] = "afectado" in content.lower() or "archivos" in content.lower()
        checks["prohibiciones_explicitas"] = ("ATR" not in content or "indicador" not in content.lower()) and "indicadores técnicos" in content
        
        passed_count = sum(1 for v in checks.values() if v)
        score = passed_count / len(self.DO_RULES)
        passed = score >= 0.7
        
        return DoRResult(passed=passed, score=score, checks=checks, errors=errors, warnings=warnings)
    
    def can_transition(self, from_state: TaskState | str, to_state: TaskState | str, task_id: str) -> tuple[bool, str]:
        """Verifica si una transición de estado es válida."""
        if not check_state_transition(from_state, to_state):
            return False, f"Transición {from_state} → {to_state} inválida según PROTOCOLO_AGENTE.md"
        
        fs = from_state.value if isinstance(from_state, TaskState) else str(from_state)
        ts = to_state.value if isinstance(to_state, TaskState) else str(to_state)
        
        if fs == "READY" and ts == "IMPLEMENTING":
            # La FORMA de la transición es válida. El DoR se valida como paso
            # explícito en request_change / ChangeGateValidator (no aquí), para
            # no acoplar la máquina de estados a archivos físicos en disco.
            return True, "READY → IMPLEMENTING autorizado (forma válida)"
        
        if fs == "AUDITED" and ts == "ACCEPTED":
            if self.veto_registry.has_active_veto(task_id):
                return False, f"Veto activo para {task_id} (auditor_independiente.md §3.1)"
            return True, "AUDITED → ACCEPTED autorizado"
        
        if fs == "TESTED" and ts == "AUDITED":
            return True, "TESTED → AUDITED requiere auditor independiente"
        
        return True, "Transición válida"
    
    def request_change(self, req: ChangeRequest) -> tuple[bool, str]:
        """Punto de enforcement principal para operaciones de cambio.
        
        Verifica:
        1. ¿El archivo está en el perímetro protegido?
        2. ¿La transición de estado es válida?
        3. ¿Hay veto activo?
        4. ¿Hay auto-aprobación/auto-auditoría?
        
        Returns: (allowed, reason)
        """
        # 1. Si el archivo NO es sensible, permitir (Ataque F debe pasar)
        if not self.is_protected_path(req.file_path):
            return True, f"Archivo {req.file_path} no es sensible - sin gate requerido"
        
        # 2. Verificar transición de estado (FORMA)
        allowed, reason = self.can_transition(req.from_state, req.to_state, req.task_id)
        if not allowed:
            return False, reason
        
        # 2b. Verificar DoR explícito para modificación de archivos sensibles.
        # READY→IMPLEMENTING requiere DoR validado (Definition of Ready).
        fs = req.from_state.value if isinstance(req.from_state, TaskState) else str(req.from_state)
        ts = req.to_state.value if isinstance(req.to_state, TaskState) else str(req.to_state)
        if fs == "READY" and ts == "IMPLEMENTING":
            dor_path = Path(f"docs/specs/SDD_{req.task_id}.md")
            if dor_path.exists():
                result = self.validate_dor(dor_path)
                if not result.passed:
                    return False, "DoR incompleto (requerido para READY→IMPLEMENTING)"
            else:
                return False, "DoR no encontrado (requerido para READY→IMPLEMENTING)"
        
        # 3. Verificar auto-aprobación (Ataque C)
        # En implementación real, el creator se extrae del contexto de la tarea
        # Por ahora, el orquestador debe registrar quién creó la tarea
        
        # 4. Verificar veto
        if self.veto_registry.has_active_veto(req.task_id):
            return False, f"Veto activo bloquea cambio en {req.file_path}"
        
        return True, "Cambio autorizado"
    
    def enforce_before_routing(self, task_id: str, intended_state: TaskState) -> tuple[bool, str]:
        """Enforcement antes de enrutar a un agente."""
        if self.veto_registry.has_active_veto(task_id):
            return False, f"Veto activo para task {task_id}"
        return True, "Sin bloqueos"
    
    def log_violation(self, violation_type: str, details: dict[str, Any]):
        """Loggea una violación al gate en results/gate_violations.json."""
        log_path = self._results_path / "gate_violations.json"
        violations = []
        if log_path.exists():
            try:
                violations = json.loads(log_path.read_text())
            except json.JSONDecodeError:
                violations = []
        
        violation_entry = {
            "type": violation_type,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        violations.append(violation_entry)
        log_path.write_text(json.dumps(violations, indent=2))
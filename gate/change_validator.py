"""Change Gate Validator — frontera de cambio del repositorio.

Este módulo NO es un nuevo órgano de gobernanza. Es la MISMA lógica de reglas
ya definida (DoR, estado, auditor, veto, perímetro) aplicada en el punto
correcto: SOBRE el diff resultante, no sobre la petición del agente.

Diferencia clave con orchestrator_enforcer.request_change():
- request_change(): el agente PIDE permiso y luego escribe. Depende de que
  el agente "sea bueno" y llame al gate.
- ChangeGateValidator.validate_diff(): se aplica SOBRE lo que efectivamente
  cambió. No importa si el agente llamó al gate o escribió por la ventana.

Esto cierra el bypass principal: un cambio sobre path protegido no puede ser
aceptado/promovido si no cumple las condiciones del gate.

Opción C (CEO): engine/ es única fuente de decisión y permanece IGNORANTE del
gate. Este validador vive en la frontera de cambio/promoción, no dentro del
motor. NO se importa desde engine/.

Autoridades respetadas:
- SDD_GOVERNANCE.md (DoR, estados, verificación)
- PROTOCOLO_AGENTE.md (estados operacionales)
- auditor_independiente.md (veto, independencia)
- AGENTS.md (Ley Fundamental: engine≠backtest, I1 hipótesis no promovida)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import GateConfig
from .states import TaskState
from .veto_registry import VetoRegistry
from .audit_isolation_service import AuditIsolationService
from .orchestrator_enforcer import GateOrchestratorEnforcer, DoRResult


@dataclass
class DiffEntry:
    """Una entrada de diff: un archivo modificado/creado/borrado."""
    path: str
    action: str = "modify"  # "modify", "create", "delete"


@dataclass
class TaskContext:
    """Contexto de la tarea que origina el cambio.
    
    En integración real esto vendría del registry de tareas / git notes.
    Aquí es un dict plano para que el validador sea testeable sin infra.
    """
    task_id: str
    state: str
    promoted: bool = False          # I1: hipótesis promovida antes de tocar engine/
    dor_passed: bool = False         # DoR validado
    creator: str = ""               # quien implementó
    auditor: str = ""               # quien audita (debe != creator)
    has_evidence: bool = False      # resultados medibles


@dataclass
class ValidationResult:
    allowed: bool
    reason: str
    blocked_paths: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class ChangeGateValidator:
    """Valida un diff completo contra las reglas de gobernanza.
    
    Punto de enforcement: frontera de cambio del repo (pre-commit / promoción).
    No depende de que el agente haya llamado request_change().
    """
    
    def __init__(self, config: GateConfig | None = None, perimeter_path: Path | None = None):
        self.config = config or GateConfig()
        self._enforcer = GateOrchestratorEnforcer(config=self.config, perimeter_path=perimeter_path)
        self._results_path = Path("results")
        self._results_path.mkdir(exist_ok=True)
    
    def validate_diff(self, diff: list[DiffEntry], ctx: TaskContext) -> ValidationResult:
        """Valida un diff (cambios reales) contra el gate.
        
        Reglas aplicadas por path protegido:
        1. I1: debe estar promovida (promoted=True) antes de tocar engine/backtest/tesis
        2. DoR: dor_passed=True para modificar archivos sensibles
        3. Estado: la transición de estado debe ser válida y autorizada
        4. Auditor: creator != auditor (aislamiento)
        5. Veto: no hay veto activo para la tarea
        
        Paths NO protegidos: se permiten sin estas condiciones (Ataque K).
        """
        blocked_paths: list[str] = []
        errors: list[str] = []
        
        protected_entries = [e for e in diff if self._enforcer.is_protected_path(e.path)]
        
        # Si no hay paths protegidos, el diff es libre (Ataque K)
        if not protected_entries:
            return ValidationResult(
                allowed=True,
                reason="Sin paths protegidos - sin gate requerido",
                blocked_paths=[],
                details={"protected_count": 0},
            )
        
        # Regla 1: I1 — promoción formal antes de tocar engine/backtest/tesis
        if not ctx.promoted:
            for e in protected_entries:
                blocked_paths.append(e.path)
            errors.append(
                f"I1 violada: cambio sobre path protegido sin promoción formal "
                f"(task {ctx.task_id} promoted={ctx.promoted})"
            )
            return ValidationResult(
                allowed=False,
                reason="I1: hipótesis no promovida no puede modificar engine/backtest/tesis",
                blocked_paths=blocked_paths,
                details={"rule": "I1", "task_id": ctx.task_id},
            )
        
        # Regla 2: DoR
        if not ctx.dor_passed:
            for e in protected_entries:
                blocked_paths.append(e.path)
            errors.append(f"DoR no validado para task {ctx.task_id}")
            return ValidationResult(
                allowed=False,
                reason="DoR incompleto (requerido para modificar path protegido)",
                blocked_paths=blocked_paths,
                details={"rule": "DoR", "task_id": ctx.task_id},
            )
        
        # Regla 3: transición de estado válida (FORMA únicamente).
        # El DoR ya se validó en Regla 2 (ctx.dor_passed). Aquí solo comprobamos
        # que la transición esté en la tabla documental (PROTOCOLO_AGENTE.md /
        # SDD_GOVERNANZA.md). No re-exigimos el archivo físico: el validador es
        # la fuente de verdad del contexto de la tarea.
        from_state = TaskState(ctx.state) if ctx.state in TaskState.__members__ else ctx.state
        to_state = TaskState.IMPLEMENTING
        from .states import can_transition as check_form
        if not check_form(from_state, to_state):
            for e in protected_entries:
                blocked_paths.append(e.path)
            return ValidationResult(
                allowed=False,
                reason=f"Transición {ctx.state} → IMPLEMENTING inválida según PROTOCOLO_AGENTE.md",
                blocked_paths=blocked_paths,
                details={"rule": "state", "task_id": ctx.task_id},
            )
        
        # Regla 4: auditoría independiente (creator != auditor)
        if ctx.creator and ctx.auditor and ctx.creator == ctx.auditor:
            for e in protected_entries:
                blocked_paths.append(e.path)
            return ValidationResult(
                allowed=False,
                reason="Auditoría no independiente: creator == auditor",
                blocked_paths=blocked_paths,
                details={"rule": "audit_isolation", "task_id": ctx.task_id},
            )
        
        # Regla 5: veto activo
        if self._enforcer.veto_registry.has_active_veto(ctx.task_id):
            for e in protected_entries:
                blocked_paths.append(e.path)
            return ValidationResult(
                allowed=False,
                reason=f"Veto activo bloquea cambio (task {ctx.task_id})",
                blocked_paths=blocked_paths,
                details={"rule": "veto", "task_id": ctx.task_id},
            )
        
        # Todas las reglas pasan
        return ValidationResult(
            allowed=True,
            reason="Cambio sobre paths protegidos autorizado por gate",
            blocked_paths=[],
            details={
                "rule": "all_pass",
                "task_id": ctx.task_id,
                "paths": [e.path for e in protected_entries],
            },
        )
    
    def log_validation(self, diff: list[DiffEntry], ctx: TaskContext, result: ValidationResult):
        """Registra la validación en results/change_gate_log.json."""
        log_path = self._results_path / "change_gate_log.json"
        entries = []
        if log_path.exists():
            try:
                entries = json.loads(log_path.read_text())
            except json.JSONDecodeError:
                entries = []
        
        entry = {
            "task_id": ctx.task_id,
            "allowed": result.allowed,
            "reason": result.reason,
            "blocked_paths": result.blocked_paths,
            "diff_paths": [e.path for e in diff],
        }
        entries.append(entry)
        log_path.write_text(json.dumps(entries, indent=2))
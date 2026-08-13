"""Servicio de aislamiento de auditoría.

Implementa el principio de independencia según auditor_independiente.md §3.4.
El Auditor NO puede auditar trabajo producido por él mismo.

Autoridad:
- auditor_independiente.md §3: Responsabilidades del Auditor
- auditor_independiente.md §5: Límites (No auditar trabajo suyo)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class AuditAssignment:
    """Asignación de auditoría a una tarea.
    
    Regla institucional (auditor_independiente.md §5):
    "El Auditor NO puede auditar trabajo producido por él mismo."
    """
    
    task_id: str
    creator: str      # quién creó/implementó la tarea
    auditor: str      # quién la auditó (debe ser diferente)
    assigned_at: str
    audit_result: Optional[str] = None  # PASS, VETO, FAIL
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "creator": self.creator,
            "auditor": self.auditor,
            "assigned_at": self.assigned_at,
            "audit_result": self.audit_result,
        }


class AuditIsolationService:
    """Servicio para garantizar independencia del auditor.
    
    Implementa la regla: creator(agent) != auditor(agent)
    
    Esta es una INFRAESTRUCTURA, no una nueva autoridad.
    """
    
    def __init__(self, assignments_path: Path | None = None):
        self.assignments_path = assignments_path or Path("gate/audit_assignments.json")
        self._assignments: dict[str, AuditAssignment] = {}
        self._load()
    
    def _load(self):
        """Carga las asignaciones desde disco."""
        if self.assignments_path.exists():
            try:
                data = json.loads(self.assignments_path.read_text())
                for item in data:
                    assignment = AuditAssignment(
                        task_id=item["task_id"],
                        creator=item["creator"],
                        auditor=item["auditor"],
                        assigned_at=item["assigned_at"],
                        audit_result=item.get("audit_result"),
                    )
                    self._assignments[assignment.task_id] = assignment
            except (json.JSONDecodeError, KeyError):
                self._assignments = {}
    
    def _save(self):
        """Guarda las asignaciones en disco."""
        self.assignments_path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self._assignments.values()]
        self.assignments_path.write_text(json.dumps(data, indent=2))
    
    def assign_auditor(self, task_id: str, creator: str, auditor: str) -> AuditAssignment:
        """Asigna un auditor a una tarea.
        
        PRE: auditor != creator (se lanza ValueError si no)
        PRE: task_id no puede tener auditor asignado ya
        POST: asignación registrada con timestamp
        """
        if creator == auditor:
            raise ValueError(
                f"Violación de autoridad: auditor '{auditor}' NO puede auditar su propio trabajo. "
                f"(creator == auditor)"
            )
        
        if task_id in self._assignments:
            existing = self._assignments[task_id]
            if existing.auditor == creator:
                # ya existe auto-audit, lanzar error
                raise ValueError(f"Auto-audit detectado para task {task_id}")
        
        import datetime
        assignment = AuditAssignment(
            task_id=task_id,
            creator=creator,
            auditor=auditor,
            assigned_at=datetime.datetime.now().isoformat(),
        )
        self._assignments[task_id] = assignment
        self._save()
        return assignment
    
    def is_valid_assignment(self, task_id: str, creator: str, auditor: str) -> bool:
        """Verifica si una asignación es válida (independencia)."""
        if creator == auditor:
            return False
        
        existing = self._assignments.get(task_id)
        if existing:
            return existing.auditor != creator  # no era auto-audit
        return True
    
    def get_assignment(self, task_id: str) -> Optional[AuditAssignment]:
        """Obtiene la asignación para una tarea."""
        return self._assignments.get(task_id)
    
    def record_audit_result(self, task_id: str, result: str):
        """Registra el resultado de la auditoría."""
        if task_id in self._assignments:
            self._assignments[task_id].audit_result = result
            self._save()
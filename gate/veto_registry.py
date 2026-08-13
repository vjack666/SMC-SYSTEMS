"""Registry de vetos para el gate de gobernanza.

Implementa el concepto de "VETO" según auditor_independiente.md §3.1, §19.
No crea nueva autoridad - implementa lo documentado.

Autoridad:
- auditor_independiente.md §3.1: "veto de PROMOCIÓN (no de exploración)"
- auditor_independiente.md §19: "Veto vinculante sobre PROMOCIÓN a operación"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class VetoStatus(Enum):
    """Estado del veto según auditor_independiente.md."""
    
    NONE = "NONE"       # No hay veto
    PENDING = "PENDING" # Veto emitido, en revisión
    ACTIVE = "ACTIVE"   # Veto vigente (no se puede promover)
    RESOVED = "RESOVED" # Veto retirado/resuelto


@dataclass
class Veto:
    """Representa un veto emitido por el Auditor.
    
    Según auditor_independiente.md:
    - El Auditor es Fiscal de Falsación
    - El veto es sobre PROMOCIÓN a operación (piso 6→7)
    - El Director puede resolver vetos
    - El Ingeniero NO puede invocar un veto
    """
    
    task_id: str
    auditor_id: str  # quién emitió el veto
    reason: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: VetoStatus = VetoStatus.ACTIVE
    resolution: Optional[str] = None  # quién y cómo se resolvió
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "auditor_id": self.auditor_id,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "resolution": self.resolution,
        }


class VetoRegistry:
    """Registry de vetos según auditor_independiente.md.
    
    Esta clase IMPLEMENTA el concepto documentado, no crea una nueva autoridad.
    
    Responsabilidades:
    1. Almacenar vetos emitidos por auditors
    2. Verificar si un task tiene veto activo
    3. Permitir que Director resuelva vetos
    4. Generar alertas cuando se intenta promover con veto
    """
    
    def __init__(self, registry_path: Path | None = None):
        self.registry_path = registry_path or Path("gate/veto_registry.json")
        self._vetoes: dict[str, Veto] = {}  # task_id -> Veto
        self._load()
    
    def _load(self):
        """Carga el registry desde disco (opcional)."""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text())
                for item in data:
                    veto = Veto(
                        task_id=item["task_id"],
                        auditor_id=item["auditor_id"],
                        reason=item["reason"],
                        created_at=datetime.fromisoformat(item["created_at"]),
                        expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                        status=VetoStatus(item.get("status", "ACTIVE")),
                        resolution=item.get("resolution"),
                    )
                    self._vetoes[veto.task_id] = veto
            except (json.JSONDecodeError, KeyError, ValueError):
                self._vetoes = {}  # corrupt file, start fresh
    
    def _save(self):
        """Guarda el registry en disco."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = [v.to_dict() for v in self._vetoes.values()]
        self.registry_path.write_text(json.dumps(data, indent=2))
    
    def emit_veto(
        self, 
        task_id: str, 
        auditor_id: str, 
        reason: str,
        expires_at: Optional[datetime] = None
    ) -> Veto:
        """Emite un nuevo veto sobre una tarea.
        
        Pre: auditor_id es un auditor válido
        Pre: task_id existe y está en estado AUDITED
        Post: veto queda registrado con status ACTIVE
        """
        veto = Veto(
            task_id=task_id,
            auditor_id=auditor_id,
            reason=reason,
            created_at=datetime.now(),
            expires_at=expires_at,
            status=VetoStatus.ACTIVE,
        )
        self._vetoes[task_id] = veto
        self._save()
        return veto
    
    def has_active_veto(self, task_id: str) -> bool:
        """Verifica si existe veto activo para una tarea.
        
        Esta es la verificación que PROHÍBE la promoción según
        auditor_independiente.md §3.1.
        """
        veto = self._vetoes.get(task_id)
        if not veto:
            return False
        if veto.status != VetoStatus.ACTIVE:
            return False
        if veto.expires_at and veto.expires_at < datetime.now():
            return False
        return True
    
    def resolve_veto(self, task_id: str, resolver_id: str, resolution: str) -> Optional[Veto]:
        """Resuelve un veto (solo Director o autoridad superior).
        
        El Ingeniero NO puede resolver vetos - solo Director.
        """
        veto = self._vetoes.get(task_id)
        if not veto:
            return None
        
        veto.status = VetoStatus.RESOVED
        veto.resolution = f"{resolver_id}: {resolution}"
        self._save()
        return veto
    
    def get_veto(self, task_id: str) -> Optional[Veto]:
        """Obtiene el veto para una tarea."""
        return self._vetoes.get(task_id)
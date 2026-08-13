"""Estados operacionales del gate.

Estados basados en PROTOCOLO_AGENTE.md §0 y SDD_GOVERNANCE.md §91-122.
NO es una nueva autoridad - es una representación ejecutable de documentos existentes.

Autoridades:
- PROTOCOLO_AGENTE.md §0 (formato de reporte)
- SDD_GOVERNANCE.md §91-122 (máquina de estados)
"""

from enum import Enum
from typing import Dict, List


class TaskState(str, Enum):
    """Estados de ciclo de vida de una tarea.
    
    Referencia: PROTOCOLO_AGENTE.md §0 + SDD_GOVERNANCE.md §91-122
    """
    
    # Estado inicial - hipótesis documentada
    DISCOVERED = "DISCOVERED"
    """Hipótesis formalizada, lista para investigación."""
    
    # Estado de investigación
    HYPOTHESIS = "HYPOTHESIS"  
    """Hipótesis en fase de investigación/experimentos."""
    
    # Promoción formal requerida
    PROMOTED = "PROMOTED"
    """Hipótesis promovida formalmente (requiere evidence de promoción)."""
    
    # Estados de implementación (SDD_GOVERNANCE.md §91-108)
    READY = "READY"
    """Listo para implementación (DoR cumplido, SDD especificado)."""
    
    IMPLEMENTING = "IMPLEMENTING"
    """Código en curso."""
    
    TESTED = "TESTED"
    """Tests pasan."""
    
    EVIDENCE_READY = "EVIDENCE_READY"
    """Resultados medibles disponibles."""
    
    # Estado de auditoría (auditor_independiente.md)
    AUDITED = "AUDITED"
    """Auditor (diferente al creador) revisó y soldó."""
    
    # Estados finales (SDD_GOVERNANCE.md §110-122)
    ACCEPTED = "ACCEPTED"
    """Aprobado por Director, puede ir a producción."""
    
    REJECTED = "REJECTED"
    """Cai la tesis (auditor o Director)."""
    
    BLOCKED = "BLOCKED"
    """Falta SDD/autoridad - marcado en PROTOCOLO_AGENTE.md §9."""
    
    ESCALATED = "ESCALATED" 
    """Subido al Director por riesgo/falta de autoridad (PROTOCOLO_AGENTE.md §18)."""
    
    # Estados administrativos
    IN_PROGRESS = "IN_PROGRESS"
    """Trabajo en curso (alias IMPLEMENTING para compatibilidad)."""


# Transiciones válidas según autoridad documental
# Estados son strings que coinciden con PROTOCOLO_AGENTE.md + SDD_GOVERNANCE.md
_VALID_TRANSITIONS: Dict[str, List[str]] = {
    "DISCOVERED": ["HYPOTHESIS", "BLOCKED"],
    "HYPOTHESIS": ["PROMOTED", "BLOCKED", "REJECTED"],
    "PROMOTED": ["READY", "BLOCKED"],
    "READY": ["IMPLEMENTING", "BLOCKED"],
    "IMPLEMENTING": ["TESTED", "BLOCKED"],
    "TESTED": ["AUDITED", "BLOCKED"],
    "EVIDENCE_READY": ["AUDITED", "BLOCKED"],
    "AUDITED": ["ACCEPTED", "REJECTED", "BLOCKED"],
    "ACCEPTED": [],
    "REJECTED": [],
    "BLOCKED": ["READY", "PROMOTED"],  # puede desbloquearse
    "ESCALATED": ["READY", "ACCEPTED", "REJECTED"],  # Director resuelve
    "IN_PROGRESS": ["IMPLEMENTING", "BLOCKED"],
}


def can_transition(from_state: TaskState | str, to_state: TaskState | str) -> bool:
    """Verifica si una transición es válida según autoridad documental.
    
    Los estados son definiciones documentales, no creaciones nuevas.
    
    Autoridades:
    - PROTOCOLO_AGENTE.md §0 (estados operacionales)
    - SDD_GOVERNANCE.md §91-122 (máquina de estados)
    """
    from_str = from_state.value if isinstance(from_state, TaskState) else str(from_state)
    to_str = to_state.value if isinstance(to_state, TaskState) else str(to_state)
    
    valid_targets = _VALID_TRANSITIONS.get(from_str, [])
    return to_str in valid_targets
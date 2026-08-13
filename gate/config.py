"""Configuración del Gate de Gobernanza.

Define el modo de operación del gate según SDD_GOVERNANCE.md.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class GateConfig:
    """Configuración mínima del gate de gobernanza.
    
    Los estados/validaciones se definen en:
    - PROTOCOLO_AGENTE.md §0 (estados operacionales)
    - SDD_GOVERNANCE.md §44-64 (DoR)
    - auditor_independiente.md §3.1 (veto), §5 (independencia)
    """
    
    mode: Literal["advisory", "enforcement"] = "enforcement"
    """Modo de operación:
    - advisory: emitir alerts en results/, no bloquear flow
    - enforcement: bloquear transiciones inválidas (ACTIVO desde FASE 7.x + hook)
    """
    
    doR_checks: int = 13
    """Número de checks DoR requeridos (SDD_GOVERNANCE.md §44-64)"""
    
    min_confidence: float = 0.55
    """Confianza mínima para promoción (ver decision_agent.py)"""
    
    def __post_init__(self):
        # Validar valores dentro de rango
        if self.mode not in ("advisory", "enforcement"):
            raise ValueError(f"mode must be 'advisory' or 'enforcement', got {self.mode}")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError(f"min_confidence must be 0-1, got {self.min_confidence}")
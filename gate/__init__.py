"""Gate de Gobernanza de Agentes — Implementación mínima.

Este módulo implementa los controles necesarios para que las reglas
institucionales documentadas sean invariantes verificables.

Autoridades respetadas:
- SDD_GOVERNANCE.md (DoR, estados, vetos)
- PROTOCOLO_AGENTE.md (estados operacionales)
- auditor_independiente.md (veto de promoción, independencia)
- AGENTS.md (Ley Fundamental: engine≠backtest)
"""

from .orchestrator_enforcer import GateOrchestratorEnforcer
from .audit_isolation_service import AuditIsolationService
from .veto_registry import VetoRegistry, VetoStatus
from .states import TaskState, can_transition
from .config import GateConfig

__all__ = [
    "GateOrchestratorEnforcer",
    "AuditIsolationService", 
    "VetoRegistry",
    "VetoStatus",
    "TaskState",
    "can_transition",
    "GateConfig",
]
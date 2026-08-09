# MICRO_AUDIT_AGENTS.md — Auditoría de `agents/` (FASE 3A-1, solo lectura)

> **Auditoría pura (2026-08-09).** FASE 3A-1 = auditoría de `agents/`. CERO movimientos,
> CERO borrado, CERO renombrado, CERO Python, CERO commit. `legacy_smc_backup` intacto.
> Objetivo: matriz de evidencia por elemento antes de cualquier migración.

## Estructura actual

```
agents/
├── __init__.py            # FACADE: re-exporta todo
├── base.py                # AnalysisResult, AgentProtocol
├── ict_agent.py           # ICTAgent
├── structure_agent.py     # StructureAgent
├── wyckoff_agent.py       # WyckoffAgent
├── decision_agent.py      # DecisionAgent, DecisionConfig, DecisionRecord
├── orchestrator.py        # AgentOrchestrator (instancia los 4 agents)
└── governance/            # 10 .md de gobernanza institucional
    ├── ROLES_GOBERNANZA.md  ORQUESTADOR.md  PROTOCOLO_AGENTE.md
    ├── investigador.md  ingeniero.md  auditor_independiente.md
    ├── memoria_institucional.md  cumplimiento_operativo.md
    └── alertas_tempranas.md  CONTRATO_ORDEN.md
```

## Consumidores vivos (hallazgo crítico)

`agents/` NO es código muerto. Es infraestructura de trading VIVA, consumida por:

| Consumidor | Importa | Tipo |
|------------|---------|------|
| `signals/pipeline.py:10` | `agents.orchestrator.AgentOrchestrator` | pipeline de señales (vivo) |
| `adapters/wyckoff_adapter.py:8` | `agents.wyckoff_agent.WyckoffAgent` | adapter (vivo) |
| `ml/dataset_builder.py:13,206` | `agents.orchestrator.AGENT_COLUMNS, AgentOrchestrator` | ML (vivo) |
| `ml/inference.py:10` | `agents.orchestrator.AGENT_COLUMNS` | ML (vivo) |
| `ml/validator.py:9` | `agents.orchestrator.AGENT_COLUMNS` | ML (vivo) |
| `paper_trading/runner.py:21,115,118` | `agents.orchestrator.AgentOrchestrator` | paper trading (vivo) |
| `tests/test_agents.py` | `from agents import (...)` | test (vivo) |
| `tests/test_decision_agent.py` | `agents.base`, `agents.decision_agent` | test (vivo) |
| internos | `agents/orchestrator.py` → `from agents.ict_agent/...` | intra-paquete |

- NO hay entry point CLI que instancie AgentOrchestrator (los `__main__` en el repo son de `app_observador/`, `ict_backtest/`, etc.).
- `agents/governance/` (10 .md): NO importado por código (grep vacío). Consumidor = humano/operacional (gobernanza del proyecto, citada por `AGENTS.md`). Estado: VIVO-DOCUMENTAL.

## Matriz por elemento (12 dimensiones)

| Elemento | Import dir | Dinámico | Entry point | Launcher | Orquestación | Tests | Config | Doc op. | Uso humano | Cadena ind. | Sustituible | Estado |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|--------|
| `base.py` | sí (5 módulos+tests) | no | no | no | base | sí | no | no | no | sí | no | **VIVO** |
| `ict_agent.py` | sí (orchestrator, __init__) | no | no | no | vía orch | sí | no | no | no | sí | no | **VIVO** |
| `structure_agent.py` | sí (orchestrator, tests_legacy) | no | no | no | vía orch | sí | no | no | no | sí | no | **VIVO** |
| `wyckoff_agent.py` | sí (orchestrator, adapters) | no | no | no | vía orch | sí | no | no | no | sí | no | **VIVO** |
| `decision_agent.py` | sí (orchestrator, __init__, tests) | no | no | no | vía orch | sí | no | no | no | sí | no | **VIVO** |
| `orchestrator.py` | sí (8 sites vivos) | no | no | no | SÍ (núcleo) | sí | no | no | no | sí | no | **VIVO** |
| `governance/*.md` (10) | no (no código) | no | no | no | no | no | no | sí (AGENTS.md) | sí | sí (MD→MD) | no | **VIVO-DOC** |
| `__init__.py` | facade | no | no | no | re-export | no | no | no | no | sí | reconstruir | **VIVO** |

## Veredicto de migración (FASE 3A-1)

El plan del Director (separar en `analysis/` + `orchestration/` + `governance/`) es
**SEMÁNTICAMENTE CORRECTO** según la evidencia:

- `analysis/` ← `base.py`, `ict_agent.py`, `structure_agent.py`, `wyckoff_agent.py`, `decision_agent.py`
- `orchestration/` ← `orchestrator.py`
- `governance/` ← (ya existe, 10 .md)

PERO la migración NO es cosmética. Requiere:

1. Crear `analysis/`, `orchestration/` (governance ya existe).
2. Mover los `.py`.
3. **Actualizar 8+ import sites**: `signals/pipeline.py`, `adapters/wyckoff_adapter.py`,
   `ml/dataset_builder.py`, `ml/inference.py`, `ml/validator.py`, `paper_trading/runner.py`,
   `tests/test_agents.py`, `tests/test_decision_agent.py` (y `scripts/_legacy/*`).
4. **Reconstruir `agents/__init__.py`** (facade) o decidir si `agents/` desaparece y los
   consumidores apuntan a `analysis`/`orchestration`.
5. Tests verdes.

INCIERTO (decisión del Director, no bloquea la auditoría):
- ¿`agents/` queda como FACADE que re-exporta desde `analysis`/`orchestration` (mínimo
  impacto en consumidores), o se elimina y se actualizan los 8 import sites? La facade es
  menos riesgo; eliminarlo es más limpio pero toca más archivos.

## Conclusión

Todos los elementos de `agents/` están VIVOS. La separación proposal es válida y mejora la
arquitectura (aisla análisis de orquestación), pero debe ejecutarse como migración
controlada: mover + actualizar 8 import sites + reconstruir facade + tests, en UN commit
aislado con verificación. NO es movimiento por patrón de nombres.

Nada se movió. Matriz lista para revisión del Director antes de migrar.

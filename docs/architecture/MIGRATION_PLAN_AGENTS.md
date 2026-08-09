# MIGRATION_PLAN_AGENTS.md — Diseño de migración `agents/` (FASE 3A-1)

> **Solo diseño (2026-08-09).** CERO movimientos, CERO Python, CERO commit. Plan para
> revisión del Director antes de ejecutar. Decision del Director: `agents/` queda como
> FACHADA de compatibilidad; no se elimina.

## 1. Símbolos exportados actualmente por `agents/__init__.py`

Re-exporta (API PÚBLICA a conservar):
- `AnalysisResult`, `AgentProtocol` ← `agents.base`
- `DecisionAgent`, `DecisionConfig`, `DecisionRecord` ← `agents.decision_agent`
- `ICTAgent` ← `agents.ict_agent`
- `StructureAgent` ← `agents.structure_agent`
- `WyckoffAgent` ← `agents.wyckoff_agent`
- `AgentOrchestrator` ← `agents.orchestrator`

Atributo de módulo usado externamente (vía `from agents.orchestrator import AGENT_COLUMNS`):
- `AGENT_COLUMNS` ← `agents.orchestrator`

## 2. Símbolos realmente utilizados externamente

| Símbolo | Quién lo usa (externo a agents/) |
|---------|----------------------------------|
| `AgentOrchestrator` | signals/pipeline.py, ml/dataset_builder.py, paper_trading/runner.py, tests/test_pipeline_integration.py |
| `AGENT_COLUMNS` | ml/dataset_builder.py, ml/inference.py, ml/validator.py, tests/test_ml_dataset.py, scripts/_legacy/_smc_measure_ml_gate.py |
| `WyckoffAgent` | adapters/wyckoff_adapter.py, tests/test_stochastic_exhaustion.py |
| `ICTAgent` | tests/test_r7_single_source.py |
| `DecisionAgent`/`AnalysisResult` | tests/test_decision_agent.py |

## 3. Imports internos de `orchestrator.py` (líneas 8-12)

```
from agents.base import AnalysisResult
from agents.decision_agent import DecisionAgent, DecisionConfig
from agents.ict_agent import ICTAgent
from agents.structure_agent import StructureAgent
from agents.wyckoff_agent import WyckoffAgent
```
Tras mover a `orchestration/orchestrator.py`, pasan a `from analysis.X import ...`.

## 4. `scripts/_legacy/*` — consumidores vivos o históricos

7 scripts en `scripts/_legacy/` importan `agents.*` (ablation_real, ablation_study,
build_real_dataset, fase_wyckoff_m15, generate_large_synthetic, gen_synth_ml,
_smc_measure_ml_gate). Son HISTÓRICOS (subcarpeta `_legacy`). **No se tocan.**
Como usan `from agents.X`, la fachada los sigue resolviendo → no se rompen.

## 5. API pública a conservar en la fachada

`agents/__init__.py` debe seguir exponiendo EXACTAMENTE los 7 símbolos + `AGENT_COLUMNS`
(vía `agents.orchestrator`). Además deben seguir funcionando los accesos por submódulo:
`from agents.orchestrator import AGENT_COLUMNS`, `from agents.wyckoff_agent import WyckoffAgent`.

## 6. Imports que CAMBIAN vs los que NO (gracias a la fachada)

**NO cambian (0 consumidores externos):** signals/pipeline.py, adapters/wyckoff_adapter.py,
ml/*, paper_trading/runner.py, tests/*, scripts/_legacy/* — todos usan `from agents.X`,
que la fachada redirige.

**SÍ cambian (solo dentro de agents/, inevitable al mover):**
- `analysis/base.py`, `ict_agent.py`, `structure_agent.py`, `wyckoff_agent.py`,
  `decision_agent.py`: `from agents.base import ...` → `from .base import ...` (relativo).
- `orchestration/orchestrator.py`: `from agents.X import ...` → `from analysis.X import ...`.

## 7. Ciclos potenciales

`orchestration` → `analysis` (uno sentido). `analysis` NO importa `orchestration` ni
`agents`. `agents` (fachada) → `analysis` + `orchestration`. **Sin ciclos.** ✅

## 8. Tests que demuestran "comportamiento no cambió"

Corrida ANTES y DESPUÉS debe dar idéntico conteo:
- `tests/test_agents.py` (fachada `from agents import (...)`)
- `tests/test_decision_agent.py`
- `tests/test_ml_dataset.py` (`AGENT_COLUMNS`)
- `tests/test_pipeline_integration.py` (`AgentOrchestrator` vía signals)
- `tests/test_r7_single_source.py` (`ICTAgent`)
- `tests/test_stochastic_exhaustion.py` (`WyckoffAgent`)
- smoke: `AgentOrchestrator().analyze_bar(...)` sigue devolviendo `AnalysisResult`.

## ESTRATEGIA DE MÍNIMA SUPERFICIE (fachada)

1. Crear `analysis/` con `base.py`, `ict_agent.py`, `structure_agent.py`,
   `wyckoff_agent.py`, `decision_agent.py` + `__init__.py` (re-exporta lo propio).
   Imports relativos (`from .base import ...`).
2. Crear `orchestration/orchestrator.py` (imports → `from analysis.X`).
3. Convertir los 6 archivos originales de `agents/` en **STUBS** que re-exportan:
   - `agents/base.py` → `from analysis.base import *`
   - `agents/ict_agent.py` → `from analysis.ict_agent import *`
   - `agents/structure_agent.py` → `from analysis.structure_agent import *`
   - `agents/wyckoff_agent.py` → `from analysis.wyckoff_agent import *`
   - `agents/decision_agent.py` → `from analysis.decision_agent import *`
   - `agents/orchestrator.py` → `from orchestration.orchestrator import *`
   (así `from agents.orchestrator import AGENT_COLUMNS` sigue funcionando)
4. `agents/__init__.py` queda igual (ya re-exporta; ahora los símbolos vienen de los stubs
   que apuntan a analysis/orchestration).
5. `agents/governance/` (10 .md) NO se toca — documentación.

Radio de cambio: **0 consumidores externos modificados**. Solo se crean `analysis/`,
`orchestration/` y se reescriben 6 stubs en `agents/`.

## Riesgos

- R1: consumidor que use `import agents.ict_agent` como submódulo directo fuera de los
  listados → cubierto por stub `agents/ict_agent.py`. ✅
- R2: `AGENT_COLUMNS` accedido como atributo de `agents.orchestrator` → cubierto por stub
  `agents/orchestrator.py`. ✅
- R3: import circular en arranque si `agents/__init__.py` importa `analysis` que a su vez
  intenta importar `agents` → no ocurre: `analysis` no importa `agents`. ✅
- R4: herramientas que hagan `isinstance(x, agents.ICTAgent)` comparando identidad de
  clase → sigue siendo la misma clase (re-exportada), idéntica. ✅

## Plan de ejecución (cuando se autorice)

1. Crear `analysis/` + `orchestration/` con los módulos movidos (imports relativos).
2. Reescribir 6 stubs en `agents/`.
3. `agents/governance/` intacto.
4. Correr los 7 tests ANTES/DESPUÉS → mismo conteo.
5. Commit aislado: `refactor: split agents into analysis/ and orchestration/ (agents stays facade)`.

Nada se movió aún. Diseño listo para revisión del Director.

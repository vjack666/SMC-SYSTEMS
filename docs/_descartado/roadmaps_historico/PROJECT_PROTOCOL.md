> ⚠️ **DOCUMENTO HISTÓRICO (recuperado 2026-08-05 del commit d0a5f20).**
>
> NO es fuente de verdad. La fuente de verdad viviente es:
> `AGENTS.md` + `docs/tesis/` (tesis del trader humano) + `engine/` (motor permanente)
> + `docs/bitacora/bitacora_trabajo.md` (estado real verificado).
>
> Este roadmap describe el estado al 2026-07-21, cuando el trabajo estaba medido
> en el **backtest** (`ict_backtest/`). El motor (`engine/`) se construyó DESPUÉS
> y está en otro punto. Ver `docs/planificacion/INDICE_PLANES.md` y el diff en
> `docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.
>
> Recuperado selectivamente (solo hitos/fases/decisiones, SIN código de backtest
> ni libro 13) por petición del trader humano para ubicar el punto actual.

# PROJECT_PROTOCOL — Protocolo de documentación y cambios

Protocolo de arranque para cualquier agente IA o desarrollador que toque
SMC-SYSTEMS. Sustituye la necesidad de un "prompt gigante" o de recordar
conversaciones previas: lee los documentos de la cadena y ejecuta solo lo que
dice el RFC activo.

## Antes de cualquier cambio
1. Lee **VISION** (`docs/plan/VISION.md`) — ¿por qué existe el proyecto?
2. Lee **PRD** (`docs/plan/PRD.md`) — ¿qué debe hacer?
3. Lee **SRS** (`docs/plan/SRS.md`) — ¿qué requisitos tiene?
4. Lee **SAD** (`docs/plan/SAD.md`) — ¿cómo está organizada la arquitectura?
5. Lee los **ADR** relevantes (`docs/plan/ADR-*.md`) — ¿por qué se tomó cada
   decisión técnica?
6. Lee el **RFC activo** (`docs/plan/RFC-*.md`) — ¿qué cambio se propone y por
   qué?

## Reglas de ejecución
- Implementa **SOLO** lo descrito en el RFC activo.
- Actualiza el **SDD** si la implementación cambia.
- Crea un **ADR** si la decisión afecta la arquitectura.
- **NO hagas commit** sin revisión de Ruben (dejar sin commitear para su
  revisión, según convención del proyecto).

## Espejo de memoria (Engram) — ahorro de contexto
- El estándar completo (RFC+ADR+SDD, filosofía ICT) se guarda como observación en
  **Engram** con `topic_key='doc_protocol'` (proyecto `smc-systems`). Engram es
  el espejo pesado y buscable; NO se inyecta en cada turno.
- La memoria del asistente NO contiene las reglas: solo un PUNTERO que dice
  "al iniciar tarea SMC-SYSTEMS lee PROJECT_PROTOCOL.md y mem_search Engram
  topic_key='doc_protocol'". Esto ahorra espacio de contexto.
- **Cualquier agente IA** (Hermes, ChatGPT, auditor) recupera el estándar con:
  `mem_search(query="doc_protocol", topic_key="doc_protocol", project="smc-systems")`.
- Fuente de verdad sigue siendo el **repo (git)**: `docs/plan/PROJECT_PROTOCOL.md`,
  `RFC-001`, `ADR-021`. Engram es respaldo recuperable, no reemplaza al repo.

## Jerarquía de documentos
```
VISION
  ├── PRD
  ├── SRS
  ├── SAD
  ├── ADR      ↑ Explica POR QUÉ cambió algo
  ├── RFC      ↑ Explica QUÉ se quiere cambiar y por qué
  ├── SDD      ↑ Explica CÓMO queda implementado
  └── Código   (implementación final)
```

| Documento | Responde                              |
| ---------- | ------------------------------------- |
| VISION     | ¿Por qué existe el proyecto?          |
| PRD        | ¿Qué debe hacer?                      |
| SRS        | ¿Qué requisitos tiene?                |
| SAD        | ¿Cómo está organizada la arquitectura?|
| ADR        | ¿Por qué se tomó esta decisión?       |
| RFC        | ¿Qué cambio se propone y por qué?     |
| SDD        | ¿Cómo se implementa ese cambio?       |
| Código     | Implementación final.                 |

## Para la biblioteca ICT
El RFC activo es **RFC-001** (`docs/plan/RFC-001_actualizacion_biblioteca_ict.md`).
La filosofía vinculante es **ADR-021** (`docs/plan/ADR-021_filosofia_documentacion_ict.md`).

## Convenciones del proyecto (de AGENTS.md)
- Leer README.md y COMPLETION_REPORT.md antes de decisiones técnicas.
- Fuente de verdad de hitos/roadmap: `docs/plan/CRONOGRAMA_Y_ROADMAP.md`.
- No reescribir AGENTS.md.
- Proyectos NO se mezclan: SMC-SYSTEMS (docs/ict/) es aparte de QUOTEX
  (boblioteca/).
- Tests/backtests usan TODOS los núcleos por defecto, sin tocar config global
  de la laptop ni el loop MT5 en vivo.

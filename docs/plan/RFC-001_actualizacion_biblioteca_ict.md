# RFC-001 — Modernización de la Biblioteca ICT

**Status:** Approved
**Date:** 2026-07-12
**Owner:** SMC-SYSTEMS (Ruben + agentes IA)
**Refiere a:** ADR-021 (Filosofía de Documentación ICT)

## Razón (Reason)
Los libros ICT actuales (`docs/ict/`) explican teoría resumida de fuentes
públicas, pero no reflejan:
- el flujo real de los traders (entrada, gestión, sesiones, multi-TF),
- cómo lo calculan las aplicaciones automáticas (MQL5 / nuestro propio código),
- consideraciones de MetaTrader 5 (Chart Shift, profundidad de histórico),
- los hallazgos de la auditoría 2026-07-11 (look-ahead #1, CHOCH=BOS #2) y su
  impacto medido (PF 2.003 → 1.548).

Esto genera divergencia entre documentación, implementación y backtests.

## Objetivo (Objective)
Elevar cada documento ICT a una cadena trazable y reutilizable:

```
Teoría
  ↓
Práctica de trading (traders reales)
  ↓
Algoritmo (detección automática)
  ↓
Implementación (código SMC-SYSTEMS)
  ↓
Auditoría (hallazgos internos)
  ↓
Resultados medidos (números reales)
```

## Alcance (Scope)
Documentos afectados (recorrido en orden):
- `03_FVG.md`
- `04_ORDER_BLOCKS.md`
- `05_LIQUIDEZ.md`
- `06_TURTLE_SOUP.md`
- `07_SILVER_BULLET.md`
- `08_POWER_OF_THREE.md`

`02_MSS_CHOCH.md` ya fue reescrito como referencia/prototipo de la tesis.

Fuera de alcance (Out of scope):
- Búsqueda en internet / investigación externa nueva.
- Nuevos conceptos ICT.
- Nuevos indicadores.
- Cambios de código (solo documentación).

## Reglas de implementación (Implementation Rules)
Usar SOLO:
- código fuente del repositorio (`detectors/`, `ict_backtest/`, `ml/`),
- documentación existente (`docs/ict/`, `docs/avances/`),
- auditorías (`docs/ict/10_AUDITORIA_REFACCION/`),
- backtests (`results/`, `docs/avances/AVANCES_ICT_BACKTEST_*`),
- resultados medidos internos.

## Flujo esperado (Expected workflow)
1. Leer documento actual.
2. Leer implementación (código que lo materializa).
3. Leer auditoría correspondiente.
4. Identificar huecos.
5. Reescribir con la tesis.
6. Actualizar `docs/ict/00_INDICE.md`.
7. Esperar revisión (NO commit).

## Criterios de aceptación (Acceptance Criteria)
Cada capítulo debe explicar:
- Cómo lo usan los traders en la práctica.
- Cómo los algoritmos lo detectan.
- Cómo lo implementa SMC-SYSTEMS (código real, con rutas de archivo).
- Cómo las auditorías afectaron la implementación.
- Impacto medido (números reales, no de oídas).

**Sin commit.** Para revisión de Ruben.

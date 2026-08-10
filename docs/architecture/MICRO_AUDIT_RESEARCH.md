# MICRO_AUDIT_RESEARCH.md — Auditoría de `research/` (FASE 3B, solo lectura)

> **Auditoría pura (2026-08-10).** FASE 3B = crear/consolidar `research/`. CERO movimientos,
> CERO borrado, CERO renombrado, CERO modificación de código, CERO commit. Solo mapeo de
> consumidores según el ciclo acordado: auditar → demostrar consumidores → diseñar →
> autorizar → ejecutar.

## 1. Estado de partida

`research/` **NO existe** en el repo hoy. La constitución ya lo define (ARCHITECTURE.md §4):

```
research/
├── hypotheses/      ← preguntas formuladas como hipótesis comprobables
├── experiments/     ← EXP-NNN/ (unidad autónoma reproducible)
├── protocols/       ← protocolos de experimentación
└── validation/      ← validación independiente
```

REGLA DE TRÁNSITO (constitución): una investigación que demuestra mérito pasa a
`results/experiments/EXP-NNN/` y luego a `engine/`; el experimento NO desaparece (trazabilidad).

## 2. Candidatos dispersos hoy (qué vive "fuera de producto")

| Elemento | Tipo | Estado físico | Consumidores de CÓDIGO | Consumidor humano/doc |
|----------|------|--------------|------------------------|----------------------|
| `geometry_lab/` (1 archivo: `run_experiment.py`, 13 KB) | código | **ROTO** | 0 | no |
| `docs/lab/LABORATORIO_ICT_SMC.md` | doc | vivo | 0 (no importado) | sí |
| `knowledge/research/completed/` (2 MD: multi-symbol-expectancy, wyckoff-smc-integration) | doc | vivo | 0 | sí |
| `knowledge/` (resto: architecture, learnings, references, summaries, theories) | doc | vivo | 0 (documental) | sí |
| `ict_backtest/diagnostics/` (`hypothesis_engine.py`, `statistics_engine.py`, `correlation_engine.py`, `diagnosis_report.py`, etc.) | código | vivo | **SÍ** (consumido internamente por `ict_backtest/diagnostics`) | — |

## 3. Hallazgos críticos

### 3.1 `geometry_lab/` está ROTO
`run_experiment.py` (auto-descrito "D3 - Experimento real: invarianza de escala de la
geometría del precio") hace:
```python
from .core import (Point, angle_cosine, menger_curvature, proportion_ratio,
                   segment_efficiency, signed_turn)
from .null_test import permutation_pvalue
```
Pero **`geometry_lab/core.py` y `geometry_lab/null_test.py NO EXISTEN** en disco.
Prueba de vida: `python -c "import geometry_lab.run_experiment"` →
`ModuleNotFoundError: No module named 'geometry_lab.core'`.

→ Moverlo tal cual a `research/` propagaría el defecto. Requiere decisión: ¿reparar y
  promover, o dejar como histórico? La auditoría NO lo repara (fuera de alcance de auditoría).

### 3.2 `ict_backtest/diagnostics/` NO es `research/`
Aunque contiene `hypothesis_engine`/`statistics_engine`, es **diagnóstico de backtest**
(vivo, consumido internamente por `ict_backtest/diagnostics/*`). La constitución lo sitúa
en el mundo BACKTEST, no en el mundo CIENCIA (`research/`). Moverlo a `research/` violaría
la separación epistemológica (research propone, backtest manda sobre sí mismo). **Excluido.**

### 3.3 Documentación es humana, no de código
`docs/lab/`, `knowledge/**` NO son importados por ningún `.py` (grep vacío). Son
conocimiento documental. Su reubicación es de baja superficie de riesgo (solo enlaces
rotos si los MD se referencian entre sí — verificar en fase de diseño).

## 4. Matriz de consumidores (12 dimensiones, resumen)

| Dimensión | `geometry_lab/` | `docs/lab/` | `knowledge/research/` | `ict_backtest/diagnostics/` |
|-----------|-----------------|-------------|----------------------|----------------------------|
| Importación directa | 0 | 0 | 0 | SÍ (interna ict_backtest) |
| Carga dinámica | 0 | 0 | 0 | 0 |
| Entry points | 0 | 0 | 0 | SÍ (`diagnosis_report.compute`) |
| Launchers .bat/.vbs/.ps1 | 0 | 0 | 0 | 0 |
| Orquestación | 0 | 0 | 0 | SÍ (usado por backtest) |
| Tests | 0 | n/a | n/a | SÍ (test_r10c_adapter etc.) |
| Config YAML/JSON/TOML | 0 | 0 | `index.json` (doc) | SÍ |
| Doc operacional | 0 | sí (humano) | sí (humano) | no |
| Uso humano | no | sí | sí | no |
| Cadena indirecta | 0 | 0 | 0 | SÍ |
| Sustituibilidad | roto | alta | alta | BAJA (acoplado a backtest) |
| Estado | ROTO | vivo-doc | vivo-doc | vivo-código |

## 5. Veredicto de auditoría

- `research/` **no existe** → 3B es **creación + consolidación**, no reordenamiento.
- Candidatos seguros a mover (documentales, 0 riesgo de ruptura de código):
  `docs/lab/LABORATORIO_ICT_SMC.md` → `research/hypotheses/` o `research/protocols/`.
  `knowledge/research/completed/*` → `research/experiments/EXP-<id>/` (o `archive/`).
  `knowledge/` resto → queda (es conocimiento general, no experimento).
- `geometry_lab/`: **ROTO**. Decisión del Director: ¿reparar+promover a `research/experiments/EXP-D3/`,
  o dejar en `legacy_smc_backup` / no tocar? La auditoría recomienda NO moverlo roto.
- `ict_backtest/diagnostics/`: **EXCLUIDO** de `research/` (es backtest, no ciencia).

## 6. Diseño propuesto (para autorización, NO ejecutado)

```
research/
├── hypotheses/          ← docs/lab/LABORATORIO_ICT_SMC.md + hipótesis formales
├── experiments/
│   ├── EXP-D3/           ← SOLO si el Director autoriza reparar geometry_lab
│   │   ├── hypothesis.md
│   │   ├── protocol.md
│   │   ├── code/         ← geometry_lab/ reparado
│   │   └── verdict.md
│   └── archive/          ← knowledge/research/completed/* (investigación cerrada)
├── protocols/            ← protocolos de experimentación
└── validation/           ← validación independiente (vacío al inicio)
```

Superficie mínima: crear `research/` + mover 3 MD documentales. `geometry_lab/` y
`ict_backtest/diagnostics/` requieren decisión explícita del Director (no se mueven en
esta auditoría).

## 7. Riesgos y deuda

- R1: `geometry_lab/` roto — si se promueve sin reparar, `research/experiments/EXP-D3/code/`
  hereda el `ModuleNotFoundError`.
- R2: enlaces relativos en MD (knowledge/ → docs/) podrían romperse al mover; verificar en
  diseño.
- R3: `ict_backtest/diagnostics/` tentador de "limpiar" hacia research — NO hacer (acoplado).
- DEUDA: `geometry_lab/` roto se registra; no se arregla en 3B sin autorización explícita.

---
*Auditoría pura. Pendiente de autorización del Director para diseño/ejecución de FASE 3B.*

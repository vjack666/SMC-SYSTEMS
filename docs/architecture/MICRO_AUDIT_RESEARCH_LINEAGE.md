# MICRO_AUDIT_RESEARCH_LINEAGE.md — Linaje de experimentos (FASE 3B, 2ª pasada)

> **Auditoría pura (2026-08-10).** Segunda pasada de FASE 3B: encontrar dónde vive actualmente
> la cadena completa de evidencia de un experimento (hipótesis → protocolo → código → datos →
> ejecución → resultados → evidencia → veredicto). CERO modificaciones. Solo mapeo.

## 1. Pregunta de la auditoría

> ¿Dónde está actualmente la cadena completa de evidencia de EXP-069, EXP-071 y los
> experimentos recientes? ¿Qué debería convertirse en la unidad `research/experiments/EXP-NNN/`?

## 2. Hallazgo central

**La cadena de evidencia de experimentos NO existe hoy como unidad física.**

Los IDs `EXP-069` y `EXP-071` **NO son experimentos reales ejecutados en el repo**. Solo
aparecen en la constitución arquitectónica como **ejemplos de la convención de nombres**
que se quiere imponer:

- `docs/architecture/ARCHITECTURE.md:108` → `research/experiments/EXP-071/`
- `docs/architecture/ARCHITECTURE.md:110` → `results/experiments/EXP-071/`
- `docs/architecture/ARCHITECTURE_MAP.md:89` → "uniforme `EXP-NNN/` (tu propuesta de
  `research/experiments/EXP-071/...`)"
- `docs/architecture/DIRECTORY_CONTRACT.md:52` → regla de IDs (`EXP-071`, `BT-2026-001`)

O sea: EXP-069/071 son **diseño/convención**, no ejecución. Su linaje no es recuperable
porque nunca se materializaron como artefactos.

## 3. Dónde vive cada eslabón HOY (disperso)

| Eslabón | Ubicación actual | Estado |
|---------|-----------------|--------|
| **Hipótesis** | `docs/specs/` (MDS_*, 12_ESTRATEGIAS_COMPLETAS.md), `docs/ict/` | documental, vivo |
| **Protocolo** | `docs/architecture/*.md`, `agents/governance/PROTOCOLO_AGENTE.md` | documental, vivo |
| **Código de experimento** | `scripts/_legacy/fase*_demo_plan.py`, `fase_e_demo_e1.py`, `audit_experiment_f_structural.py`, `geometry_lab/run_experiment.py` (ROTO) | HISTÓRICO / roto |
| **Datos** | `data/raw/`, `data/` (conectores) | vivos (no etiquetados por EXP) |
| **Ejecución** | `scripts/_legacy/*.py` (hand-run), `geometry_lab/` (roto) | histórico/roto |
| **Resultados** | `results/_archive/bt_v2/.../run_summary.json`, `coverage_report.json` | resultados de BACKTEST (no experimento) |
| **Evidencia** | `results/_archive/bt_v2/.../explanations.jsonl`, `tests_artifacts/`, `tv/` | parcial, backtest |
| **Veredicto / tribunal / FDR** | `agents/governance/investigador.md`, `PROTOCOLO_AGENTE.md`, `docs/_archivo/auditorias/AUDITORIA_COMITE_TECNICO_2026-07-17.md`, `ict_backtest/diagnostics/statistics_engine.py` (FDR/Bonferroni) | documental/código, vivo |
| **Validación independiente** | `scripts/measure_motor_veltick.py`, `scripts/validate_structural_sl_fix.py` (activos, no legacy) | validación de MOTOR, no exp. investigación |

## 4. Resultados de la búsqueda (resumen de grep)

- `grep -rln "EXP-069|EXP-071"` → solo `docs/architecture/*` y `agents/governance/ROLES_GOBERNANZA.md`
  (convención, no artefacto).
- `find results -iname "*exp*"` (vivo, no _archive) → 0 resultados.
- `results/` top-level vivo = `tests_artifacts/`, `tv/`. Nada de experimentos.
- Scripts de experimento ACTIVOS (no _legacy) = solo validación de motor
  (`measure_motor_veltick.py`, `validate_structural_sl_fix.py`).

## 5. Implicación para el diseño de `research/`

1. `research/` debe construirse como **frontera científica nueva** que adopte la convención
   `EXP-NNN/` de la constitución — pero arranca VACÍO o con las unidades que el Director
   autorice promover.
2. El linaje REAL recuperable son los **scripts en `scripts/_legacy/`** (fase1-4, fase_e,
   audit_*) y `geometry_lab/` (roto). Esos son candidatos a `research/experiments/EXP-XXX/code/`
   — pero requieren decisión del Director (no se mueven en esta auditoría).
3. EXP-069/071 son irreales (convención). NO se inventan carpetas vacías con esos IDs.
4. La segunda fase del tránsito epistemológico (`results/experiments/EXP-NNN/`) tampoco existe;
   los resultados hoy son de backtest en `results/_archive/`.

## 6. Veredicto de la 2ª pasada

- No hay una "cadena de evidencia de experimento" poblada que migrar tal cual.
- `research/` se crea por **diseño de frontera**, no por reubicación masiva.
- Candidatos a futuras unidades `EXP-NNN/` (cuando el Director autorice): `scripts/_legacy/fase*`,
  `geometry_lab/` (tras reparar), `audit_experiment_f_structural.py`.
- `ict_backtest/diagnostics/` (FDR/Bonferroni/veredictos) queda en backtest (separación
  epistemológica: research propone, backtest evalúa).

## 7. Recomendación para el diseño (NO ejecutado)

Cuando el Director autorice el diseño de `research/`, propongo:

```
research/
├── hypotheses/          ← HYP-NNN/ (de docs/specs, promovidas como unidades)
├── experiments/         ← EXP-NNN/ SOLO para experimentos reales que se autoricen
│                          (arranca vacío; no inventar EXP-069/071)
├── protocols/           ← protocolos versionados
└── validation/          ← validación independiente (vacío al inicio)
```

Y registrar `geometry_lab/` y `scripts/_legacy/*` como **experimentos huérfanos pendientes
de clasificación** (no tocar hoy).

---
*Auditoría pura (2ª pasada). Pendiente de autorización del Director para diseño/ejecución de FASE 3B.*

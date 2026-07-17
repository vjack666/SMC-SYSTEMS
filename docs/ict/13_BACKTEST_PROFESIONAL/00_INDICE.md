# Libro 13 — Backtest profesional (pasado / presente / futuro)

| Campo | Valor |
|-------|-------|
| **ID** | `13_BACKTEST_PROFESIONAL/` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estándar** | ADR-021 / RFC-001 · plantilla de biblioteca |
| **Estado** | Stable (docs) · Needs-code (gaps §06) |
| **Métricas** | [METRICS_CANON](../../METRICS_CANON.md) — no duplicar cifras aquí |
| **Plan de aplicación** | [PLAN_BACKTEST_PROFESIONAL](../../plan/PLAN_BACKTEST_PROFESIONAL.md) · R6 en roadmap |

> **Propósito:** checklist de un backtest **profesional** (no “script que mira el chart con hindsight”), mapeado a SMC-SYSTEMS y a lo que aún falta.  
> **Fuente de verdad:** código + auditorías del repo. Fuentes externas = respaldo verificable.

---

## Respuesta en una frase

Un backtest profesional **reconstruye el reloj del mercado**: en cada instante solo existe el pasado conocido, la barra presente (si ya cerró) y **nunca** el futuro — incluyendo multi-TF, fills, costos, y validación anti-overfit.

---

## Temas de este libro

| # | Tema | Qué cubre |
|---|------|-----------|
| 01 | [Checklist profesional](01_CHECKLIST_PROFESIONAL.md) | Lista completa de puntos que un quant / prop shop exige |
| 02 | [Modelo de tiempo y multi-TF](02_MODELO_TIEMPO_Y_MTF.md) | Pasado/presente/futuro; HTF solo cerradas |
| 03 | [Ejecución, fill y costos](03_EJECUCION_FILL_COSTOS.md) | Next-bar open, spread, swap, gaps, path OHLC |
| 04 | [Validación OOS y overfit](04_VALIDACION_OOS_OVERFIT.md) | Walk-forward, purge/embargo, PBO, N mínimo |
| 05 | [Datos, régimen y portafolio](05_DATOS_REGIMEN_PORTAFOLIO.md) | Calidad de data, regímenes, multi-símbolo |
| 06 | [Gap SMC-SYSTEMS](06_GAP_SMC_SYSTEMS.md) | Qué ya cumple el repo vs qué se escapa |
| 07 | [Fuentes](07_FUENTES.md) | Referencias web / literatura |

---

## Relación con el pack ICT

| Documento | Relación |
|-----------|----------|
| `10_AUDITORIA_REFACCION/` | Hallazgos #1–#7 ya cerrados en código (swing, CHOCH, costos, WF…) |
| `09_OPTIMIZADOR_BAYESIANO.md` | Optuna + WF; este libro fija **gates antes** de optimizar |
| `08_POWER_OF_THREE.md` | Narrativa A/M/D; el backtest debe respetar el **tiempo** del ciclo |
| `SDD_ICT_BACKTEST.md` / `SDD_REFACCION_*` | Diseño de capas; este libro es el **estándar de veracidad** |

---

## Orden de lectura

1. **01** (checklist) — panorama  
2. **02 + 03** — reloj y dinero (donde más se miente el PF)  
3. **04 + 05** — si el edge es real y estable  
4. **06** — gap del sistema + prioridades  
5. **Plan** → código (R6)

---

## Contrato operativo del libro (§0 global)

| # | Condición medible | Obligatorio |
|---|-------------------|:-----------:|
| 1 | El reloj es el LTF; no se usa OHLC futuro de ninguna TF | Sí |
| 2 | HTF solo si `close_time_HTF <= now` | Sí |
| 3 | Señal en close de barra LTF → fill en open de `i+1` (o documentar excepción) | Sí |
| 4 | Toda métrica de producción se reporta **con costos** | Sí |
| 5 | Edge se declara solo con OOS multi-fold + N suficiente (ver METRICS_CANON gates) | Sí |
| 6 | Misma función de evaluación en vivo y backtest (sin copias divergentes) | Sí |

**Backtest profesional** = todas las filas “Sí” en verdadero.  
**Backtest de investigación** = puede relajar 3–4 con flag explícito (`theory_mode`), nunca confundir con edge de producción.

---

*Creado 2026-07-13 tras auditoría de reloj multi-TF y revisión de prácticas profesionales de backtesting.*

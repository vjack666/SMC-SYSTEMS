# Biblioteca ICT — Índice (v2 · estándar 10/10)

Colección de reglas ICT (Inner Circle Trader) **operativas y trazables** para SMC-SYSTEMS.  
Cada archivo es un “libro”. La app y los agentes deben poder **citar el contrato §0** y el código.

> **Fuentes externas** (innercircletrader.net, fluxcharts, MQL5, alchemy, etc.) son respaldo.  
> **Fuente de verdad:** código del repo + auditorías + [METRICS_CANON](../METRICS_CANON.md).  
> No sustituyen el ICT Mentorship de pago.

**Estándar de escritura:** [ADR-021](../plan/ADR-021_filosofia_documentacion_ict.md) · plantilla [`_PLANTILLA_LIBRO.md`](_PLANTILLA_LIBRO.md).  
**Aplicación al sistema:** [ROADMAP_BIBLIOTECA_Y_APLICACION](../plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md).

---

## Libros de setup (ICT)

| ID | Libro | Contrato clave | Estado docs |
|----|-------|----------------|-------------|
| 01 | [Killzones](01_KILLZONES.md) | Ventana horaria unificada | ✅ 2.0 · Needs-code TZ |
| 02 | [MSS / CHoCH / BOS](02_MSS_CHOCH.md) | Secuencia BOS→CHOCH→BOS | ✅ 2.0 |
| 03 | [FVG](03_FVG.md) | 3 velas + unfilled | ✅ 2.0 |
| 04 | [Order Blocks](04_ORDER_BLOCKS.md) | Huella + followthrough post-cierre | ✅ 2.0 |
| 05 | [Liquidez / Sweep](05_LIQUIDEZ.md) | Sweep = filtro; unificar fuente | ✅ 2.0 · Needs-code |
| 06 | [Turtle Soup](06_TURTLE_SOUP.md) | Contratrend + sweep + giro | ✅ 2.0 · Needs model split |
| 07 | [Silver Bullet](07_SILVER_BULLET.md) | KZ + sweep + FVG + sesgo | ✅ 2.0 |
| 08 | [**Power of Three (pasado/presente/futuro)**](08_POWER_OF_THREE.md) | **A+M+D complete** | ✅ 2.0 · **Prioridad R1** |

## Libros de integración / validación

| ID | Libro | Notas |
|----|-------|-------|
| 09 | [Optimizador bayesiano](09_OPTIMIZADOR_BAYESIANO.md) | **Anexo** de validación, no setup ICT |
| 10 | [Sweep + OTE filtros](10_SWEEP_OTE_FILTRO.md) | Ítem D; OTE casi no-op |
| 11 | [Manual vs Auto](11_SWEEP_OTE_MANUAL_VS_AUTO.md) | Política híbrida / automation-ready |

## Auditoría y SDD (no “libros de setup”, pero del pack ICT)

- `10_AUDITORIA_REFACCION/` — hallazgos #1–#7  
- `SDD_ICT_BACKTEST.md`, `SDD_REFACCION_2026-07-11.md`  
- `API_SPEC.md`, `TEST_PLAN.md`  
- `logs/` — corridas Capa 2/3  

---

## Cómo se usa en SMC-SYSTEMS

| Capa | Rol |
|------|-----|
| `detectors/` | Materializa reglas (BOS, CHOCH, OB, FVG, liquidez, KZ) |
| `signals/pipeline.py` | Confluencia / filtros |
| `ict_backtest/` | Misma lógica de checklist que el observador (objetivo) |
| `app_observador` | Cita libros y checklist en pestaña Principal |
| Graphify | Indexa **código**; estos `.md` indexan **teoría** |

Trazabilidad: **regla (§0) → detector → pipeline → backtest → métrica (METRICS_CANON)**.

---

## Orden de lectura recomendado

1. `01` + `02` + `05` (tiempo, estructura, liquidez)  
2. `03` + `04` (zonas)  
3. **`08` PO3** (ciclo completo del trade)  
4. `06` / `07` (variantes contratrend / scalping)  
5. `10` + `11` + `09` (filtros, política, optimización)  
6. Roadmap de aplicación → código  

---

*Biblioteca reescrita 2026-07-12 para calidad 10/10 documental. Los checkboxes de código viven en el roadmap de aplicación.*

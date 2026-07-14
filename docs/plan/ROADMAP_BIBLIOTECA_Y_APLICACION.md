# Roadmap — Biblioteca 10/10 y aplicación al sistema

**Fecha:** 2026-07-12  
**Propósito:** convertir la documentación ICT/Wyckoff en **contrato ejecutable** y cerrar el gap libro → código → backtest → observador.  
**No sustituye** `CRONOGRAMA_Y_ROADMAP.md` (hitos A6/A12). Este doc es el plan de **calidad documental + cableado PO3/modelos**.

---

## 1. Principios

1. **Un número, un sitio** → `docs/METRICS_CANON.md`.
2. **Un contrato, un detector/checklist** → cada libro §0 debe poder codificarse.
3. **Vivo = backtest** → una sola función de evaluación (sin copias divergentes).
4. **Medir antes de optimizar** → ablación y WF antes de Optuna agresivo.
5. **Trader manda** → no bot de órdenes hasta A12 + autorización.

---

## 2. Estado de la biblioteca (post reescritura 10/10)

| Área | Acción documental | Estado docs |
|------|-------------------|-------------|
| ICT 01–11 | Estándar ADR-021 + contrato §0 + métricas por enlace | ✅ Reescritos |
| `METRICS_CANON.md` | Fuente única de PF/WR | ✅ Creado |
| `_PLANTILLA_LIBRO.md` | Plantilla obligatoria | ✅ Creada |
| Wyckoff | Mapeo código + § aplicación | ✅ Elevado |
| Índices | Actualizados | ✅ |

---

## 3. Roadmap de aplicación al **código** (orden estricto)

### R0 — Congelar contratos (0.5 día) · docs only
- [x] Contratos §0 en libros (PO3 A/M/D, FVG, OB, Sweep, Turtle, Silver Bullet, Killzones).
- [x] Revisar con operador (Ruben/Eva): ¿aceptamos el "PO3 completo" tal cual? **DECIDIDO 2026-07-13: SÍ, PO3 completo (A+M+D obligatorias) aprobado tal cual por libro 08. Base para R1 `po3_state`.**

**Criterio de done:** checklist firmado o “approved” en este archivo.

---

### R1 — Capa de estado de modelos (2–4 días) · código

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R1.1 | `po3_state` con A/M/D + `complete` + `direction` | `signals/po3.py` ✅ |
| R1.2 | `evaluate(model="po3")` **separado** de Turtle Soup | `ict_backtest/rules.py` ✅ |
| R1.3 | Misma función importada por UI | `app_observador/ui/resumen_widget.py` ✅ |
| R1.4 | Tests sintéticos: solo A, solo M, A+M+D, sin look-ahead | `tests/test_po3.py` ✅ |

**Criterio de done:** pytest verde; UI muestra "PO3 completo / incompleto".  \n**Estado 2026-07-13:** R1 COMPLETO — 8/8 tests `tests/test_po3.py` pasan; UI muestra bloque "ESTADO PO3 (A/M/D)".

---

### R2 — Alinear killzones y zona horaria (1 día)

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R2.1 | Documentar y unificar TZ: UTC canónico + display operador configurable (env SMC_TZ, default Ecuador) | `docs/plan/DECISION_TZ.md`, `app_observador/core/timezone.py` ✅ |
| R2.2 | Vivo y backtest llaman al mismo `killzone_activa_ahora()` (UTC) | `resumen_widget.py` ✅ / `ict_backtest/rules.py` (ya UTC) |
| R2.3 | UI muestra reloj en zona operador + bandas UTC y operador | `mt5_status.py`, `resumen_widget.py` ✅ |
| R2.4 | Tests de bandas London/NY y override por env | `tests/test_timezone.py` ✅ |

**Criterio de done:** pytest verde; UI y backtest coinciden en "en killzone"; reloj mostrado en zona operador.  \n**Estado 2026-07-13:** R2 COMPLETO — 6/6 `tests/test_timezone.py` pasan; KZ-1 cerrado; helper único UTC + display Ecuador (o SMC_TZ). KZ-2 (unificar `detectors/killzones.py` del mapa) queda fuera de R2.

---

---

### R3 — Cerrar huecos de arquitectura documentados (3–5 días)

| Hueco (libro) | Acción |
|---------------|--------|
| Liquidez pinta ≠ sweep filtra (`05`) | Unificar o documentar adapter único `liquidity_context` consumido por pipeline | ✅ R3: `detectors/liquidity_context.py` (`canonical_sweep`); `detect_bos` + `signals/pipeline.py` delegan |
| OTE ~1% no-op (`10`) | Ajustar bandas o desactivar peso hasta WF OOS del test propuesto | 🔶 R4 (decisión + walk-forward; no es código) |
| Open del día en PO3 (`08`) | Feature `session_open` + filtro manipulación vs open | ✅ PO3-2 (R3): `compute_session_open` + filtro duro en `signals/po3.py` |
| CHOCH→BOS gate off (`02`) | Re-medir en XAUUSD + costos; no forzar en EURUSD naive | ✅ gate cableado (default OFF); re-medición en XAUUSD = R4 |

**Criterio de done:** cada hueco = issue cerrado o "wontfix" con razón en METRICS/ libro.  \n**Estado 2026-07-13:** R3 completo en arquitectura — PO3-2 y Liquidez (05) cerrados con código + tests; OTE (10) y CHOCH-gate (02) resueltos como trabajo de R4 (medición/decisiones, no arquitectura).

---

### R3.5 — Cerrar huecos del canon ICT en la TESIS (URGENTE · 2026-07-13)

**Fuente:** `20_TESIS_ICT.md` § investigación de gaps (2026-07-13). La tesis unifica PO3/estructura/liquidez/temporalidad/SL, pero se escapa de 3 capas del canon ICT que separan un setup "ok" de uno "institucional". El backtest v29 ya probó que el SL estructural da edge (PF>1); el siguiente cuello es la CALIDAD de la entrada, no el stop.

| Hueco (canon ICT) | Por qué es urgente | Estado repo | Tarea |
|-------------------|-------------------|-------------|-------|
| **SMT Divergence** (filtrar manipulación real vs continuación) | Sin SMT el robot entra en sweeps que pueden ser continuación, no caza de stops. Es el filtro de entrada más fuerte de ICT. | ❌ Sin detector; ningún libro lo cubre a fondo | Libro `21_SMT_DIVERGENCIA.md` + detector `detectors/smt.py` (par correlacionado EURUSD/DXY, mismo TF) |
| **Breaker Block / MMXM** (zona de entry alternativa al FVG) | El robot solo entra en FVG; ICT usa breaker como falla de OB que se vuelve resistencia. MMXM es el "mapa" del ciclo. | ❌ `ob.py` existe pero no breaker/MMXM | Libro `22_BREAKER_MMXM.md` + extender `detectors/ob.py` con breaker state |
| **OTE (Optimal Trade Entry)** | Entry por retrace a 62–79% Fib del swing, no solo "retorno a FVG". `detectors/fib.py` YA existe pero no integrado en la tesis ni en entry. | ⚠️ `fib.py` existe; libro 10 dice OTE ~no-op; tesis no lo integra | Libro `23_OTE_FIB.md` + cablear OTE como zona de entry en `build_signals_from_frames` |

**Acción documental inmediata (esta sesión):**
- [x] Libros 14/15/16/17/20 creados y en `00_INDICE.md` (SL estructural, intradía, temporalidad, scalping, tesis).
- [ ] Crear libros 21 (SMT), 22 (Breaker/MMXM), 23 (OTE) y enlazarlos a la tesis 20.
- [ ] Actualizar tesis 20 § con los 3 huecos como "pendiente de integración".

**Acción de código (bloquea R4 honesto):**
- [ ] `detectors/smt.py`: divergencia EURUSD vs DXY (o par correlacionado) en mismo TF.
- [ ] `detectors/ob.py`: breaker block state tras falla de OB.
- [ ] `build_signals_from_frames`: entry requiere SMT confirmando el sweep + OTE/Breaker como zona (no solo FVG).
- [ ] Re-correr R4 v30 CON SMT+OTE+Breaker antes de declarar edge.

**Prioridad:** URGENTE. Sin SMT, la medición de R4 (v30) sobre-estima el edge (entra en manipulaciones falsas). El SL estructural (v29) ya resolvió el stop; estos 3 resuelven la entrada.

**Criterio de done:** libros 21/22/23 en índice + detectores smt/breaker cableados + tesis 20 actualizada + R4 v30 incluye los 3 filtros.

---

---

### R4 — Medición aislada (2–3 días)

| Experimento | Qué |
|-------------|-----|
| E1 | Baseline intradia mezcla (actual) |
| E2 | Solo PO3 `complete=True` a-favor | ✅ E2 corrido: PF 0.286 (8 trades, muestra minima) — sin edge |
| E3 | Solo Turtle Soup `counter_trend=True` | ✅ E3 corrido: PF 0.689 (466 trades) — pierde sistematicamente |
| E4 | Solo Silver Bullet (kz + sweep + FVG) | ⏳ pendiente (sugerido antes de descartar ICT intradia M15) |
| E5 | Con `--cost` en todos | ✅ E5 corrido: empeora (PO3 0.194, Turtle 0.511) |

**Estado 2026-07-13:** E2/E3/E5 completados y reportados en METRICS_CANON §8.1.  \n**Veredicto:** NINGUN modelo aislado supera el gate (PF ≥1.10). PO3 aislado = muestra  \nminima (8 trades), no concluyente; Turtle aislado = PF 0.689 concluyente sin edge.  \n**Decision:** NO Optuna sobre estos modelos; documentado "sin edge en EURUSD M15".  \nFalta E4 (Silver Bullet) para cerrar el analisis del stack ICT intradia en M15.
**Gate:** no Optuna hasta que E2 o el modelo elegido tenga PF OOS medio ≥1.10 **y** ningún fold <1 **o** se documente “frágil aceptado para paper”.

---

### R5 — Datos A6 (bloqueante A12) (1–N días, MT5)

- [ ] Descargar ≥3–4 años M15 XAUUSD (+ EURUSD)
- [ ] Rebuild contextos harness si aplica (`_ctx/*.pkl`)

---

### R6 — Backtest profesional: reloj, fill, costos (2–4 días) · docs ✅ · código ⏳

**Libro:** `docs/ict/13_BACKTEST_PROFESIONAL/`  
**Plan detallado:** `docs/plan/PLAN_BACKTEST_PROFESIONAL.md`  
**Motivación:** auditoría 2026-07-13 — el LTF es reloj correcto, pero HTF se lee incompleto; fill al close; costos no default.

| Tarea | Detalle | Estado |
|-------|---------|--------|
| R6.0 | Congelar contrato libro 13 + review operador (`next_open` default) | 📄 docs ✅ · review ⏳ |
| R6.1 | HTF **closed-only** (`row_at_time` + merge_asof) + test multi-TF | ⏳ G1 |
| R6.2 | `fill_mode=next_open` default producción | ⏳ G2 |
| R6.3 | Cost pack ON por default en runners (`--no-cost` = theory) | ⏳ G3 |
| R6.4 | Re-medir Capa 2/3 (ablation reloj) → **METRICS_CANON** | ⏳ |
| R6.5 | DSR/PBO / veredicto auto en optimize ICT (opcional) | ⏳ G6–G7 |
| R6.6 | Gaps sesión, portafolio prop, régimen (post R5) | ⏳ no bloquea sello v1 |

**Criterio de done (sello v1 profesional):** G1+G2+G3 + tests + METRICS actualizado.  
**Gate:** no Optuna agresivo ni declarar edge de producción hasta R6.4.
- [ ] Actualizar `METRICS_CANON` tras re-run

Scripts: `download_multiyear.py`, `download_xauusd_m15.bat`.  
MT5: `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`.

---

### R6 — Walk-forward + Optuna acotado (A12 / Capa 3)

- [ ] Re-run A12 celda `no_session` × XAUUSD tras A6
- [ ] Optuna **pocos** params (≤6) solo sobre modelo ganador de R4
- [ ] WF multi-fold, dirección pasado→futuro, costos ON

**Gate duro (cronograma):** DSR>0, N≥200/fold si posible, PF≥1.10 OOS.

---

### R7 — Observador óptimo (sin bot)

- [ ] Panel: fases A/M/D visuales en mapa o checklist
- [ ] Diario: ficha “réplica del ciclo” del día
- [ ] Shadow mode: log “hubiera entrado PO3” sin orden
- [ ] **No** reactivar loop 24/7 en máquinas que lo desactiven (`start_local.ps1`)

---

### R8 — Paper / live (solo si R6 pasa + autorización)

- Paper trading runner
- Vigilante 2%/4%
- Cumplimiento FundedNext (`tools/fundednext_compliance.py`)
- Deployment A8 al final

---

## 4. Timeline sugerido (calendario)

| Semana | Foco |
|--------|------|
| S0 | R0 revisión contratos + merge docs |
| S1 | R1 PO3 estado + tests + UI |
| S1–S2 | R2 killzones unificadas |
| S2 | R3 huecos (open día, liquidez, OTE decisión) |
| S3 | R4 medición aislada + costos |
| S3–S4 | R5 A6 datos MT5 |
| S4+ | R6 WF/A12 |
| Luego | R7 shadow · R8 solo con OK humano |

---

## 5. Matriz libro → tarea de código

| Libro | Contrato clave | Tarea código primaria |
|-------|----------------|----------------------|
| 01 Killzones | Ventana horaria unificada | Helper único UTC/broker |
| 02 MSS/CHoCH | Secuencia BOS→CHOCH→BOS | Gate opcional; re-test XAUUSD |
| 03 FVG | 3 velas + unfilled | Ya OK; aislar contribución |
| 04 OB | Valid + followthrough post-cierre | Vigilar `shift(-1)` en entrada |
| 05 Liquidez | Sweep = filtro | Unificar fuente de verdad |
| 06 Turtle Soup | Contra + sweep + MSS | `model="turtle"` separado |
| 07 Silver Bullet | KZ + sweep + FVG | `model="silver_bullet"` |
| 08 PO3 | A+M+D complete | **R1 prioridad #1** |
| 09 Optuna | WF + no overfit | Solo tras R4 |
| 10 Sweep+OTE | Pesos con evidencia | Fix OTE o peso 0 |
| 11 Manual vs Auto | Automation-ready | Shadow log, no ejecutor aún |

---

## 6. Definition of Done — “sistema óptimo en el tema PO3”

1. Libro 08 contrato A/M/D implementado en código.  
2. UI y backtest llaman la misma función.  
3. Métricas aisladas PO3 en `METRICS_CANON` con costos.  
4. WF multi-fold sin fold muerto **o** etiqueta explícita “frágil / solo paper”.  
5. Shadow en diario ≥ N días sin desincronía UI↔log.  
6. A6 datos suficientes para no repetir fallo A12 por N bajo.

---

## 7. Anti-objetivos

- No reescribir `signals/pipeline.py` “por estética” (regla edge diagnosis).  
- No optimizar 20 parámetros a la vez.  
- No declarar PF sin costos.  
- No bot de órdenes en esta fase.

---

*Documento vivo. Actualizar checkboxes al cerrar cada R#.*

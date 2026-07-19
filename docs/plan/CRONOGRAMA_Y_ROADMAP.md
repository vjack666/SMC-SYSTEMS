# CRONOGRAMA Y ROADMAP - SMC-SYSTEMS

**Proyecto:** SMC-SYSTEMS (renombrado desde SMC_SUCCESSOR)
**Repositorio:** https://github.com/vjack666/SMC-SYSTEMS
**Versión del Roadmap:** 2.6 (cierre R7 unificación motores + diseño temporalidades/capacidades)
**Fecha de Actualización:** 2026-07-19
**Estado General:** 🟢 Observador FundedNext operativo. **R4 CERRADO (2026-07-17): ICT puro mecánico SIN edge para live/fondeo** — ver `docs/auditorias/R4_CIERRE_FUNDING_2026-07-17.md`. **R7 UNIFICACIÓN COMPLETADA (2026-07-19):** motores legacy BOS/CHOCH/TREND eliminados (`git rm detectors/bos.py/choch.py/trend.py`); única fuente de verdad `ict_backtest/market_structure.py`. Migración validada por `scripts/diag_etapas.py` (la secuencia H4→M15 vive: run_sequence genera señales). Diseño de temporalidades y roadmap por capacidades en `docs/plan/ARQUITECTURA_TEMPORALIDADES.md` + `docs/plan/ROADMAP_CAPACIDADES.md`. Pendiente: R5 datos, A12 solo si aparece modelo viable, R3.5 libros 22/23, R4-tesis/v30 (capacidades Plan/Setup/Ejecución).

> **NOTA DE EJECUCIÓN (2026-07-17):** los hitos R0-R7/A1-A12 de este cronograma
> siguen vigentes como CRONOLOGÍA del proyecto. Pero la **estrategia de implementación
> orientada a la tesis** ahora vive en `docs/plan/ROADMAP_TESIS_DRIVEN_2026-07-17.md`
> (roadmap maestro). Ese doc añade Fase 0 (formalización/SPEC), Fases B-E (cierre de
> deuda conceptual), y suspende backtests de rendimiento hasta Fase G. Este
> cronograma NO se contradice; se complementa. Al commitear el roadmap maestro, este
> doc queda al día con la nota.

---

## 1. Principios Rectores (NO NEGOCIABLES)

1. **Este Cronograma es la ÚNICA fuente de verdad.** `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md` quedó OBSOLETO y redirige aquí. Cualquier decisión se alinea en este documento.
2. **Harness-First Development.** Todo nuevo módulo/feature/refactor pasa por `harness/` y 100% de escenarios antes de completo.
3. **Limpieza y Enfoque.** Solo lo esencial versionado.
4. **Documentación Dual.** Consumible por humanos y agentes IA.
5. **Cierre de Ciclo con Informe Semanal.**
6. **Medir antes de afirmar.** Ningún PF sin costos ni sin re-auditar look-ahead (lección R4: 97% de velas M15/M5 contaminadas por HTF futuro en v2.7).
7. **Trader manda.** No bot de órdenes hasta A12 + autorización.

---

## 2. Estado Actual del Repositorio (2026-07-14)

### Modo de operación real
- **OBSERVADOR FUNDEDNEXT (SIN BOT):** loop `scripts/loop_analisis.py` 24/7 (lun-vie). NUNCA abre órdenes. `vigilante_riesgo.py` SOLO CIERRA (2%/4%).
- Arranque automático vía `start_hermes_session.ps1` (✅ A11 operativo).
- Código de bot heredado (`run_paper_trading.py`, `run_live_trading.py`, MQL5 EA) implementado pero NO cableado al flujo diario.

### Hallazgo crítico post-auditoría R4 (2026-07-13 → 2026-07-14)
- **Look-ahead cross-timeframe (CRÍTICO, ya corregido):** el join H4→M5 usaba velas que aún NO cerraban. Medido: **97.4% de las velas M15/M5 estaban contaminadas por precio futuro del HTF**. Los backtests "buenos" de R4 (PF 1.14 de Turtle) eran FALSO positivo — el modelo veía el futuro. Corregido en `6d4b158`/`07afc0e` (exigir barra cerrada vía `TF_FREQ` + `row_at_time`).
- Tras limpiar look-ahead, modelos R4 re-medidos (v2.7):
  - Silver Bullet: PF 0.896 / 0.639 → **RECHAZADO** (el modelo de verdad pierde).
  - PO3 + displacement: 2 y 0 trades → INCONCLUSO.
- **Turtle Soup v2.8 ALINEADO A TESIS 18 (2026-07-14):** `run_backtest.py` camino sequence usa SL mecha sweep + RR 1:3 + killzone. EURUSD M15 H4→M15: **0 señales** (1787 sweep → 170 displace → 92 BOS → 0 entry). El retorno al cuadro (mitigation) no ocurre tras el BOS con el SL estructural; el modelo no llega a operar. Veredicto: **no concluyente** (no PF<1.10, sino 0 trades). Requiere diagnóstico de por qué el `_touches_zone` no se cumple (cuadro fallback o killzone). GBPUSD pendiente.

### SL Estructural (v29, commit `e2a9c11` 2026-07-13)
- El SL ahora se ancla a la **mecha del sweep** (no ATR de fallback). Filtro `STRUCT_SL_MAX_ATR`.
- Backtest v29: EURUSD PF 1.128, GBPUSD PF 2.101 — PERO sostenidos en `hold_limit` (7/11 y 11/13 trades cerraron por hold, no TP). Rentable vs ATR v28 (<1), pero el éxito vive del hold, no del TP real.

### Tesis de ejecución óptima (2026-07-14, commit `46b074e`)
- **Libro 18** fija la regla dura: 3 capas HTF/ITF/exec; **SL y entry SIEMPRE en exec TF**; RR mínimo 1:3; 3 killzones (London/NY AM/NY PM); M5 estándar / M1 avanzado.
- Libros 15/16/17/20 corregidos a esa regla (ITF agregado, RR 1:3, M3, killzones completas).
- **Hueco de código (v30) PARCIALMENTE cerrado (2026-07-14):** el camino `sequence`/Turtle Soup en `run_backtest.py` YA usa SL estructural de mecha de sweep (`calc_structural_sl`), RR 1:3 y filtro killzone (alineado a libro 18). Falta: `build_signals_from_frames` recibir `exec_tf`/`itf` separados de `ltf` (hoy `exec_tf == ltf`) para el camino checklist/scalping y agregar M3 en `TF_FREQ`.

### Fragmentación confirmada por grafo (2026-07-14, graph.json @ 46b074e)
- 5 módulos ICT en **6 comunidades distintas** (pipeline=1/2/5/73, ict_agent=39/62, sequence=36/70, rules=57, engine=18).
- **Solo 2 aristas cruzadas** en todo el sistema: `engine.py ↔ rules.py` (el motor llama a los checklists). `pipeline.py`, `ict_agent.py`, `sequence.py` son **islas totales** (0 aristas cruzadas).
- Consecuencia: backtest (`sequence.py`/`engine.py`) y señales en vivo (`pipeline.py`) salen de motores distintos con pesos que divergen. Deuda de arquitectura (ver R7).

### Migración event-driven (borrar concepto "aged") — COMPLETA (2026-07-15)
- **Fase 0 (baseline con aged):** EURUSD medido = 28 trades, PF 1.424. GBPUSD NO medible (OOM del host en load_frames — límite de RAM transitoria, no de código).
- **Fase A (MarketObject):** `ict_backtest/market_object.py` creado. Exige `origin_tf`; prohíbe POI en LTF por construcción. TEST OK.
- **Fase B (translation.py):** capa de convivencia DataFrame↔objetos. TEST OK.
- **Fase C (data_feed.build_objects):** envuelve build_features. TEST OK.
- **Fase D (borrar aged):** CONFIRMADO MUERTO en código. En `market_structure.py` la rama de caducidad por tiempo fue eliminada; los detectores (bos/choch/ob) solo tienen comentarios de "Fase D". Tests test_no_aged fallaban antes y ahora pasan.
- **Fase E (POI HTF en sequence.py):** IMPLEMENTADO + testeado por unidad. PERO desactivado por defecto (`htf_poi_fn=None` en todo el sistema vivo). Solo lo activan el test y el script de auditoría.
- **Fase F (backtest A vs A' vs A''):** CORRIDO con datos reales.
    - A  (con aged, baseline):        28 trades | PF 1.424 | +5.7R
    - A' (sin aged, real):            37 trades | PF 1.511 | +8.9R  ← el validado
    - A'' (POI HTF como FILTRO DURO): 31 trades | PF 0.900 | -1.7R  ← PERDEDOR
- **Veredicto:** la migración event-driven es SEGURA y mejora el edge (A' 1.511 > baseline 1.424). El POI HTF como filtro duro destruye el edge (A'' 0.900) → queda DESACTIVADO; su rol real (bonus de quality_score, no gate) es el siguiente paso.

### Libro 21 POI (ontología → biblioteca → código) — 2026-07-15
- Escrito `docs/ict/21_POI.md` tras investigación en fuentes ICT reales (InnerCircleTrader PD Array Matrix, ictkillzone.com, fxopen, tradingstrategyguides).
- Definición canónica: POI = **PD Array en zona correcta (discount/premium) + alineado con sesgo HTF + creado por flujo institucional real**; ROL, no tipo; jerarquía por TIERS (BPR > OB/FVG > breaker); elevado por STACKING multi-TF (OB M15 dentro de FVG H1 = POI T1 apilado).
- **Corrección a nuestra interpretación previa:** el POI NO es exclusivo de HTF. Vive en la ZONA del ITF (M15 intradía); el stacking multi-TF lo eleva. Eso explica por qué forzar "POI HTF como filtro duro" daba PF 0.900.
- Tesis `20_TESIS_ICT.md` actualizada (§5b POI: rol, tiers, stacking, ancla narrativa, BONUS no filtro duro). Índice `00_INDICE.md` actualizado.
- Auditoría empírica (`scripts/auditoria_poi.py`, 10.669 zonas medidas): el POI actual del código detecta "cualquier FVG/OB en ventana" SIN narrativa → 100% sin respaldo estructural HTF. El código aún marca POI sin anclarlo a su BOS/CHOCH. Falta: anclar POI a narrativa en el código.

---

## 3. Hitos y Objetivos

| ID | Objetivo | Descripción | Estado | Prioridad |
|----|----------|-------------|--------|-----------|
| A1 | Actualizar documentación | README, AGENT_ARCHITECTURE, harness | ✅ | Alta |
| A2 | Parameter Tuning (F12) | Optuna integrado | ✅ | Alta |
| A4 | Stochastic Exhaustion (F10) | Wyckoff agent | ✅ | Alta |
| A5 | Tests + cobertura | 6 módulos + harness | ✅ | Alta |
| A7 | Validación cuantitativa (F9/F13) | PurgedKFold, CVaR, DSR, PBO | ✅ | Alta |
| A9 | Plan mejora estrategia | ML off, symbol breakdown | ✅ | Alta |
| A10 | Edge Diagnosis (21×8) | 168/168 celdas | ✅ | Alta |
| A11 | Arranque automático FundedNext | PowerShell + mutex + loop | ✅ | Alta |
| A3 | Discrepancia Harness | 11 adapters documentados | ✅ | Media |
| A6 | Expandir datos | >3-4 años históricos | 🟡 En curso | Alta |
| **R0** | **Contratos PO3 congelados** | A/M/D aprobados (libro 08) | ✅ | Alta |
| **R1** | **Capa de estado PO3** | `po3_state`, tests, UI | ✅ | Alta |
| **R2** | **Killzones + TZ unificadas** | UTC canónico, helper único | ✅ | Alta |
| **R3** | **Huecos arquitectura (liquidez, open día, CHOCH-gate)** | canonical_sweep, PO3-2 | ✅ | Alta |
| **R3.5** | **Huecos canon ICT en tesis (SMT/Breaker/OTE)** | Libros 14-17/20 hechos; **21 (POI) ✅ 22/23 pendientes** | 🔶 Parcial | Alta |
| **R4** | **Auditoría + medición ICT puro** | Look-ahead ✅; SB/PO3 sin edge; **Turtle v2.8 + funding-gate 6m: REJECT_NO_EDGE** (informe 2026-07-17) | ✅ Cerrado | Alta |
| **R4-tesis** | **Tesis ejecución óptima (libro 18)** | 3 capas + SL/entry exec TF + RR 1:3 | ✅ | Alta |
| A12 | Walk-forward OOS celda ganadora | `no_session`×XAUUSD falló 1er pase (PF -0.058, N bajo). **Re-evaluar tras R4 limpio** | 🔴 Pendiente (re-run) | Alta |
| A8 | Deployment Guide (F8) | VPS, systemd/NSSM | 🔴 Pendiente | Baja |
| **R5** | **Datos A6 (bloqueante A12)** | ≥3-4 años M15 XAUUSD/EURUSD | 🟡 En curso | Alta |
| **R6** | **Backtest profesional (reloj/fill/costos)** | G1 closed-only ✅; G2 fill ✅; G3 costs ✅; R6.4 M2: EURUSD M15 PF=-4.89 (GATE NO PASA); **v2 mtf D1→H4→H1→M15 corrido 2026-07-17 (7 majors, costos ON, OOS 0.3): 0-4 trades/símbolo, ninguno pasa gate, coverage 86.1% (C06 POI missing)** — ⚠️ **AUDITADO 2026-07-17: backtest NO reproducible (ict_backtest/v2/ no versionado) + edge_diagnosis con 4 fallas** (docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md) | 🔶 Docs ✅ / Código 🟢 G1-G3 done / v2 mtf 🟢 corrido / 🔴 auditoría abierta | Alta |
| **R9** | **Migración del motor a MarketObject (R9)** | ✅ COMPLETADO (2026-07-15). Representación canónica MarketObject; sequence 100% migrado; equivalencia 15/15 tests; compatibilidad vía adapter intacta. NO incluía eliminar engine.py (deuda R7). | ✅ Cerrado | Alta |
| **R7** | **Unificar motor de decisión (single source of truth)** | **COMPLETADO (2026-07-19):** motores legacy `detectors/bos.py`/`choch.py`/`trend.py` ELIMINADOS (`git rm`); única fuente de verdad `ict_backtest/market_structure.py` (canónico). `signals/pipeline.py`, `ict_backtest/data_feed.py`, `translation.py`, `sequence.py` y scripts migrados a canónico. Tests de producción reescritos; tests legacy movidos a `legacy/tests/`. Migración validada por diagnóstico por etapas (`scripts/diag_etapas.py`: run_sequence genera señales). Diseño de temporalidades/FSM/capacidades en `ARQUITECTURA_TEMPORALIDADES.md` + `ROADMAP_CAPACIDADES.md`. | ✅ Cerrado | Alta |
| **Fase 1 (Plan)** | **Arquitectura de Plan — FSM central + emisores D1/H4/H1** | 🟢 ANDANDO (2026-07-19): `ict_backtest/plan_fsm.py` (PlanFSM reductor puro) + `ict_backtest/plan_emitters.py` (emit_d1/emit_h4/emit_h1, funciones puras) + 11 tests TDD verdes + `scripts/fase1_demo_plan.py` (demo sintética: D1+H4+H1→ZONE_ARMED; H1 veto→NO_TRADE). NO toca producción. Falta cablear loop driver a `run_backtest.py` (Fase 1 nivel 2, con datos reales). Ver `docs/plan/ROADMAP_CAPACIDADES.md`. | 🟢 Andando | Alta |
| **Fase 2 (Setup)** | **Arquitectura de Setup — emisor M15 envuelve run_sequence** | 🟢 ANDANDO (2026-07-19): `emit_m15` en `ict_backtest/plan_emitters.py` traduce la salida de `run_sequence` (phase_log) a SETUP_LIVE (BOS_DONE) / STRUCTURE_OK (ENTRY) / None (sin setup). 4 tests TDD verdes + `scripts/fase2_demo_plan.py` (cascada D1→H4→H1→M15: ZONE_ARMED→SETUP_LIVE→STRUCTURE_OK; sin setup se queda en ZONE_ARMED). Bug reparado: FSM ahora permite ZONE_ARMED→STRUCTURE_OK directo (STRUCTURE_OK superset de SETUP_LIVE). 15 tests totales Fase 1+2 verdes. NO toca producción. Falta loop driver real que llame run_sequence y pase su salida a emit_m15 (Fase 2 nivel 2). | 🟢 Andando | Alta |
| **C (Fase C, capa autoridad zonas)** | **Capa de percepción de autoridad de zonas HTF (C0–C4, TDD)** | ✅ DONE 2026-07-18: `ict_backtest/htf_pd_index.py` (plumbing HTF O(n) closed-only) + `ict_backtest/zone_authority.py` (evaluador, lee-no-crea) + enchufe en `canonical.est_htf_fn`/`sequence.run_sequence`. 16 tests verdes. **NO altera conteo de señales (R1)**; NO crea zonas; NO es gate duro; respeta Contrato de no invasión. Cierra root cause A'' (POI anclado HTF muerto por plumbing, no diseño). Ver `docs/plan/ETAPA_4_FASE_C_PLAN.md`. **Cableada en producción (observador + backtests CLI/v2) 2026-07-18** — ver `test_fase_c_production_wiring.py` + `test_fase_d_paso1_backtest_wiring.py`. | ✅ Cerrado | Alta |
| **D (Fase D, Diagnosis Engine)** | **Infraestructura de autoexplicación post-backtest** | 🔶 DISEÑO APROBADO 2026-07-18 (refinado con 4 reglas de Ruben): el sistema explica POR QUÉ ganó/perdió cuando el PF no alcanza, SIN optimizar params (no es Optuna). Cadena: TradeContext(congelado)→Statistics→Correlation Engine→Hypothesis Generator→Evidence Ranking→Final Report. **Reglas de hierro:** (1) `TradeContext` @frozen INMUTABLE, 1 vez, nunca post-outcome (anti sesgo retrospectiva = look-ahead R4); (2) ids `backtest_id`+`trade_id`+`signal_id`+`context_version`+`context_created_at`; (3) Correlation Engine SEPARADO de Hypothesis Engine; (4) Final Report incluye OBLIGATORIAMENTE "¿qué NO puede concluir?" (anti-sobreajuste). **Separación (Ruben): `simulate_trade` SIMULA; `simulate_trade_with_context` EMITE RawDiagnosticData; `diagnostics.context_builder` CONGELA TradeContext (engine.py queda limpio).** **Paso 1 (Fase C en backtests, METADATA, R1 OK) ✅; Paso 2 (TradeContext emitido+congelado, R1 PnL idéntico, inmutable, ids) ✅ 2026-07-18.** **Paso 2b — MIGRACIÓN MULTI-TF (2026-07-18, reglas #1/#4/#5/#7 de Ruben): el expediente ahora trae la CADENA COMPLETA D1/H4/H1/M15/M5/M1 (observabilidad pura, NO cambia la decisión R7).** Reusa `ict_backtest/v2/context_mtf.py` (closed-only anti look-ahead, ya existente y deshabilitado). Cambios: `run_sequence_backtest` carga `TF_CHAIN=(D1,H4,H1,M15,M5,M1)` + emite `market_stack` por señal; nuevo `diagnostics/mtf_context.py` normaliza a `MarketContextFrame` por rol (D1 bias/premium_discount · H4 poi · H1 liquidity · M15 setup/sweep/displacement/bos/fvg/ob · M5/M1 confirmation/execution); `TradeContext` v2 (`ctx-2.0`) suma `market_context` (v1 intacta, inmutable). TF ausente => `available=False`/`MISSING` (nada inventado). 11 tests verdes (`test_fase_d_mtf_context.py`+`test_fase_d_mtf_wiring.py`). Validación 6m EURUSD: 36 trades, 6 TF 100% disponibilidad, 0 incompletos, D1.premium_discount y H4.poi con datos reales (antes UNKNOWN). Ver `docs/plan/ETAPA_DIAGNOSIS_ENGINE_MTF.md`. **Fase E ✅ CERRADA 2026-07-18** (ver fila E). | 🔶 Diseño ✅ / Paso 1 ✅ / Paso 2 ✅ / 2b multi-TF ✅ / E ✅ CERRADA | Alta |
| **E (Fase E, Motores de Análisis)** | **Statistics / Correlation / Hypothesis engines (solo lectura)** | ✅ CERRADA 2026-07-18 (E1–E4, TDD, 23 tests). **Diseño:** `docs/plan/ETAPA_DIAGNOSIS_ENGINE_FASE_E.md`. **Reglas de arquitectura:** (1) 3 módulos INDEPENDIENTES en `ict_backtest/diagnostics/`; (2) solo CONSUMEN TradeContext v2 / `market_context`, no lo mutan; (3) NO modifican motor de entradas ni R7 (engine/sequence/canonical intactos); (4) NO introducen lógica de trading; (5) análisis antes que optimización (anti edge-hunting: no eligen "mejor" cohorte). **Módulos:** `cohorts.py` (facetas puras, anti look-ahead, leen contexto congelado), `statistics_engine.py` (StatisticsReport: overall + cohorts con Wilson IC95 + comparisons, n y `can_conclude`), `correlation_engine.py` (CorrelationReport: phi / punto-biserial por faceta, `strength`, `can_conclude`), `hypothesis_engine.py` (HypothesisReport: consume los 2 reportes, hipótesis explícitas con evidencia/n/métricas/confianza, `inconclusive[]`), `diagnosis_report.py` (orquestador puro: cadena stats→corr→hypo, sin lógica propia). **E4 corrida real EURUSD 6m (36 trades):** todas las cohortes `can_conclude=False` (n<30 por categoría); única señal tenue M5 confirmación coef +0.27 (small). Conclusión honesta del motor: NO hay edge concluyente con n=36; falta muestra (walk-forward más largo / más pares). Ver `scripts/fase_e_run_real_e4.py`. | ✅ Cerrada | Alta |

**Criterio de completitud:** A1-A11 + R0-R4 + libro 18 en 🟢. Harness 100%. A12 validado con datos suficientes. Solo entonces production-ready para bot.

---

## 4. Fases Futuras

- **Fase R4-clean:** ✅ CERRADA 2026-07-17. Turtle/sequence 6m + costos + sim fondeo (8%/DLL4%/MLL8%): **REJECT_NO_EDGE**. Informe: `docs/auditorias/R4_CIERRE_FUNDING_2026-07-17.md`. No auto-trade ICT.
- **Fase R3.5-libros:** escribir 21 (SMT), 22 (Breaker/MMXM), 23 (OTE) y cablear detectores (bloquea R4-honesto v30).
- **Fase R6 WF/OOS:** re-run A12 tras R5.
- **Fase R7 unificación:** un solo motor de evaluación ICT canónico (`sequence.py`) para backtest, UI y agente. El contrato R7 (R7_UNIFICACION_MOTOR.md) es la autoridad: `engine.py` queda degradado a helpers puros; `ict_agent` delega en `sequence`; `legacy/backtest` y `ml/dataset_builder` quedan DOCUMENTADOS FUERA de alcance de R7 (deuda a resolver post-R7, con decisión explícita). No se promete "matar todas las islas" en R7: el DoD de R7 exige que no haya motor ICT paralelo INVISIBLE, no la migración del legacy/ML en esta fase.
- **Fase Live (A8):** ÚLTIMA, solo con OK humano.
- **Fase R10/R11 — PRINCIPIOS ARQUITECTÓNICOS (motor de interpretación del mercado):** NUEVA dirección de nivel superior a R7, establecida 2026-07-15 (docs/plan/PRINCIPIOS_ARQUITECTONICOS.md). 4 reglas: (1) decisión SIEMPRE del estado/interpretación del mercado, NUNCA constante arbitraria; (2) modelamos mercado no velas (motor sobre MarketObjects+relaciones+contexto; IA sobre entidades); (3) 4 preguntas obligatorias antes de cualquier parámetro arbitrario; (4) interpretación contextual sobre regla fija, SI es objetiva/medible/reproducible/verificable. **NO se aplica dentro de R7 (congelado).** **PRIMER CANDIDATO R10 (registro 2026-07-15):** `bos_gap` (sequence.py=40 vs run_backtest.py=10) es número mágico antipatrón → derivar ventana de confirmación BOS de estado estructural del MarketObject, NO unificar el literal. T3.2B completado como borrado mecánico de isla sin tocar bos_gap; la divergencia 2-vs-5 queda como deuda R10. **R10 PROPUESTA A COMPLETADA Y COMMITEADA (2026-07-16, commit 057a44d, TDD):** `confirmation_window()` SIN INDICADORES (matemática pura rango high-low + tabla empírica de probabilidad de mitigación del backtest); `SequenceConfig.bos_gap: int|None` (40 fijo default / None dinámico); cableado en run_sequence vía `_effective_bos_gap`; tests en `tests/test_r10_bos_gap_dynamic.py`. **AUDITORÍA R10 vs PRINCIPIOS (2026-07-16):** cumple 100% solo P3 (proceso 4 preguntas); P1/P2/P4 parcial — en el fondo `confirmation_window` sigue siendo ventana en NÚMERO DE VELAS (tipo `int`, usos `índice - índice > N`). Es paso intermedio data-driven SIN indicadores, NO la arquitectura final. **R10.B EN PAUSA (2026-07-16, por decisión expresa):** calibrar tabla empírica real sobre histórico queda congelado; la fuerza `r` se relega a calidad/narrativa en R10.C/R11, no a caducidad. **R10.C + R11 — DISEÑO BORRADOR APROBADO (2026-07-16, commit 9ece465), implementación en curso por TDD:** docs/plan/DISENO_R10C_R11.md convierte los Principios en plan ejecutable. **R10.C FASE A (StateMachine, commit 0b3a332): COMPLETADA** — `ict_backtest/state_machine.py`, transición por evento, anti-timer. **R10.C FASE B (Invalidators, commit 0b3a332): COMPLETADA** — `ict_backtest/invalidators.py`: `rompio_swing_que_defendia`, `liquidez_tomada_sin_continuacion` (por precio), `bos_opuesto_en_misma_narrativa` (por grafo). **R10.C FASE C (ObjectGraph, commit 2026-07-16): COMPLETADA** — `ict_backtest/object_graph.py`: `add`/`link`/`parents`/`children`/`opuesto_en` por punteros (id), sin tiempo; B2 validado contra grafo real. **R10.C FASE D (MarketNarrative, commit 2026-07-16, TDD): COMPLETADA** — `ict_backtest/market_narrative.py`: cadena causal desde SWEEP raíz, `is_noise` para sueltos (sin grafo), `signal_objects` por estado. **R10.C FASE E (EventEngine + run_semantic + equivalencia, commit 2026-07-16, TDD): COMPLETADA** — `ict_backtest/event_engine.py`: `emit` por eventos (sin reloj), enlace causal BOS←SWEEP más cercano (zona cruzada, consumo único), `run_semantic` motor canónico; `translation.py` añade SWEEP persistente + zonas a BOS/CHOCH/FVG/OB. RED 2 REDEFINIDO: `Legacy ⊆ Semantic` + integridad causal (doc INFORME_EQUIVALENCIA_R10C.md). **R10.C FASE F (SemanticRules + IA sobre entidades, commit 2026-07-16, TDD): COMPLETADA** — `ict_backtest/semantic_scorer.py`: `SemanticScorer.score(objects, root)` deriva calidad/confianza de ESTADO+NARRATIVA+RELACIONES (entidades), rechaza DataFrame OHLC (TypeError); favorece narrativa completa (sweep->bos) sobre ruido. **R10.C COMPLETO (Fases A-F, TDD, 20 tests verdes).** R10.B EN PAUSA (ver arriba). Siguiente: R6 backtest honesto -> R5 datos -> A12 walk-forward -> A8 vivo.

---

## 5. Métricas de Éxito / Gate

- Profit Factor ≥ 1.25 (backtest 1.61 ✅ — pero ese número es del stack SMC heredado, NO del ICT puro R4).
- **R4 ICT puro:** gate PF ≥ 1.10 **y** meta fondeo 6m. **CERRADO:** SB/PO3/Turtle-sequence **sin edge** para live automatizado (2026-07-17).
- Win Rate ≥ 52% · Max DD ≤ 10% · Sharpe > 1 · Expectancy > 0 (del stack SMC, no R4).
- Edge diagnosis OOS PF ≥ 1.10 en >1 símbolo: ✅ (XAUUSD 1.376, etc.) — falta walk-forward A12.
- Trade count ≥ 200/backtest (actual 91 ⚠️).
- Harness: 100% escenarios antes de merge.

---

## 6. Próximos Pasos Inmediatos

1. ~~**R4-clean**~~ ✅ cerrado 2026-07-17 — sin edge ICT mecánico para fondeo/live.
2. **Producto observador:** app + vigilante + LIMIT demo (sin pretender edge).
3. **R5:** inventario/datos multi-año solo si se prueba un **nuevo** modelo candidato a A12.
4. **A12:** bloqueado hasta haber celda con edge real (R4 no la dio).
5. **R7:** completar deuda pipeline/ML/legacy o dejar documentada.
6. **R3.5:** libros 22/23 opcionales (no desbloquean bot sin edge).
7. Cualquier nuevo desarrollo pasa por harness actualizado.

---

*ÚNICA fuente de verdad a partir de 2026-07-14 (v2.3). Reemplaza versiones previas. Alineado con COMPLETION_REPORT.md, docs/auditorias/AUDIT_R4_FINAL_2026-07-13.md, docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md, y graph.json @ 46b074e (auditoría de islas ICT: 2 aristas cruzadas / 5 módulos).*

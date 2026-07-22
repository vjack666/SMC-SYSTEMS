> **⚠️ SUPERSEDED** — Contrato de ingeniería original (2026-07-17).
> Fuente de verdad vigente: `CRONOGRAMA_Y_ROADMAP.md` (v2.2, 2026-07-10).
> Muchas etapas fueron completadas por caminos distintos a los definidos aquí.
> Este documento NO es fuente de verdad vigente.

# PLAN DE IMPLEMENTACIÓN POR ETAPAS — SMC-SYSTEMS

~~Este documento es el CONTRATO DE INGENIERÍA del proyecto.~~ **SUPERSEDED** por `CRONOGRAMA_Y_ROADMAP.md`.
Define el flujo de trabajo obligatorio a partir de 2026-07-17. Sustituye el modo "arreglar cosas suelto" por un proceso
de etapas con salida clara y criterio de aceptación. Hermes NO avanza de una etapa a la
siguiente sin cerrar la anterior y sin evidencia.

Documentos de entrada (ya existentes, no se tocan):
- Auditoría Arquitectónica: docs/auditorias/AUDITORIA_COMITE_TECNICO_2026-07-17.md
- Auditoría Forense: docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md
- Convergencia: docs/auditorias/INFORME_CONVERGENCIA_ARQUITECTONICA_2026-07-17.md

Regla de commits (Ruben, AGENTS.md): NO commit/push sin OK expreso + roadmaps al día en el
mismo commit. Esto se respeta en todas las etapas.

---

## MODO DE OPERACIÓN — PILOTO AUTOMÁTICO SUPERVISADO (Ruben, 2026-07-17)

No es autónomo. Hermes ejecuta el roadmap en piloto automático DENTRO de cada etapa, pero se
detiene al final de cada etapa para entregar informe y pedir revisión.

Hermes PUEDE trabajar solo en:
- Corregir UN único hallazgo por vez.
- Commits pequeños y atómicos (un commit = un bug).
- Ejecutar tests + backtest tras cada cambio.
- Actualizar documentación (DECISION_LOG, métricas).
- Detenerse automáticamente si encuentra contradicción con las auditorías.

Hermes NO puede decidir solo:
- Cambiar la lógica de ICT.
- Cambiar Silver Bullet.
- Eliminar filtros solo porque generan más operaciones.
- Modificar varios componentes estructurales en el mismo commit.
- Cambiar parámetros sin evidencia experimental.

PUNTOS DE CONTROL (Hermes se detiene y pide revisión):
1. Al terminar cada fase del roadmap.
2. Si un cambio modifica >5–10% de las métricas del backtest.
3. Si necesita cambiar la TEORÍA de la estrategia (no solo la implementación).
4. Si dos auditorías se contradicen.

INFORME OBLIGATORIO AL CIERRE DE CADA FASE:
- Qué hizo · Qué evidencia obtuvo · Qué cambió · Qué impacto tuvo en el backtest ·
  Qué recomienda a continuación.

---

## REGLA DE ORO (vinculante, aplicable a TODAS las etapas 4+)

Hermes tiene PROHIBIDO implementar más de un cambio estructural a la vez. Después de cada
modificación debe:
1. Ejecutar el backtest afectado.
2. Comparar las métricas con la línea base (ETAPA 0).
3. Demostrar con evidencia que el cambio mejoró el sistema O, al menos, no introdujo
   regresiones.
Si un cambio empeora los resultados o altera el comportamiento esperado de la estrategia
ICT / Silver Bullet, debe REVERTIRSE antes de continuar.

NUNCA se recomienda un cambio solo para producir más operaciones (N). NUNCA se tocan los
componentes de la Fase 0 del informe de convergencia (Sequence Engine, Killzones, Entry
next_open, SL estructural, TP RR 1:3, HTF filter, Displacement como concepto).

---

## ETAPA 0 — CONGELAR EL ESTADO ACTUAL  (estado: EN CURSO)
Objetivo: línea base reproducible.
Tareas:
- [ ] Definir y crear tag/rama de referencia (p.ej. `baseline-2026-07-17`). REQUERE OK de Ruben.
- [ ] Guardar resultados actuales del backtest (R6.4, v2 mtf, A12) en results/baseline/.
- [ ] Guardar métricas actuales en docs/METRICS_CANON.md (snapshot explícito de baseline).
- [ ] Documentar configuración actual (símbolos, TFs, costos, semillas, parámetros).
Salida: Baseline completamente reproducible.
Gate de salida: desde un clon limpio en el tag, los backtests de baseline son reproducibles
y sus números están archivados. Hasta que no exista el tag, "baseline" = commit 104964c.

## ETAPA 1 — VALIDAR LOS HALLAZGOS  (estado: PENDIENTE)
Objetivo: demostrar que cada hallazgo realmente existe. SIN modificar código.
Tareas (por cada bug de la matriz de convergencia):
- reproducirlo → medir impacto → demostrar evidencia → indicar archivos afectados.
Salida: VALIDACION_DE_HALLAZGOS.md
Gate de salida: cada hallazgo clasificado A tiene un repro paso a paso con archivo:línea y
salida medible. Sin repros = no se pasa a ETAPA 2.

## ETAPA 2 — ÁRBOL DE DEPENDENCIAS  (estado: PENDIENTE)
Objetivo: causas raíz (no prioridades).
Tareas: árbol causa→efecto→consecuencia por componente (ej. Killzone→menos señales→RR→trades).
Salida: DEPENDENCY_TREE.md
Gate de salida: cada bug tiene su cadena causal hasta la consecuencia observable.

## ETAPA 3 — PLAN DE IMPLEMENTACIÓN  (estado: PENDIENTE)
Ordenar por DEPENDENCIA, no por importancia.
Salida: IMPLEMENTATION_PLAN.md (ej. 1 Killzone → 2 Sequence → 3 RR → 4 Costs, nunca al revés).
Gate de salida: orden topológico validado (un cambio no bloquea a otro mal ordenado).

## ETAPA 4 — CORRECCIÓN DE BUGS  (estado: PENDIENTE)
AHORA sí se modifica código. Un commit = un bug. Cada commit incluye:
descripción · archivos · motivo · evidencia · resultado esperado.
Respeta REGLA DE ORO (un cambio estructural a la vez + revalidación inmediata).
Gate de salida: todos los bugs A corregidos y commiteados individualmente.

## ETAPA 5 — REVALIDACIÓN INMEDIATA  (estado: PENDIENTE)
Tras cada bug: ejecutar Backtest + Tests + Métricas; comparar contra baseline.
No continuar si hay regresiones.
Gate de salida: sin regresiones respecto a baseline en cada paso.

## ETAPA 6 — REFACTOR  (estado: PENDIENTE)
Solo cuando los bugs desaparezcan. Unificar BOS, unificar CHOCH, limpiar código, eliminar
legacy. (Equivale a Fase 2 del informe de convergencia H4/H5/H12/H13/H17/H21/H22.)
Gate de salida: tests de equivalencia BOS/CHOCH pasan; sin motores duplicados.

## ETAPA 7 — CALIBRACIÓN  (estado: PENDIENTE)
displacement · ATR · RR · costos · parámetros. SOLO por experimentos, nunca por intuición.
(Equivale a Fase 3: H6/H19/H23.) Cada ajuste = experimento con semilla fija + reporte por símbolo.
Gate de salida: cada parámetro tiene experimento documentado; nada ajustado "a ojo".

## ETAPA 8 — VALIDACIÓN COMPLETA  (estado: PENDIENTE)
Todos los símbolos · todos los TFs · walk-forward · OOS · Monte Carlo (si aplica).
Gate de salida: coverage por símbolo con N y signo; DSR/PBO aplicados a toda grilla.

## ETAPA 9 — AUDITORÍA FINAL  (estado: PENDIENTE)
Hermes actúa como auditor y debe intentar demostrar que el sistema TODAVÍA tiene errores.
Si no los encuentra: proyecto aprobado.
Gate de salida: hallazgos nuevos = volver a ETAPA 4; silencio = aprobado.

## ETAPA 10 — CONGELAR VERSIÓN  (estado: PENDIENTE)
Generar "SMC SYSTEMS v1.0" con: arquitectura · documentación · métricas · resultados ·
changelog.
Gate de salida: tag v1.0 + release notes.

## ETAPA 11 — BASE DE CONOCIMIENTO (DECISION_LOG)  (estado: VIVO desde ETAPA 0)
Documento vivo docs/plan/DECISION_LOG.md. Cada decisión importante se registra con:
- Problema · Evidencia · Alternativas consideradas · Decisión tomada · Justificación ·
  Impacto esperado · Cómo verificarla.
Es la memoria técnica del proyecto; crece en cada etapa.

---

## VINCULACIÓN CON EL INFORME DE CONVERGENCIA
Los hallazgos H1-H23 del INFORME_DE_CONVERGENCIA_ARQUITECTONICA ya están clasificados A/B/C/D
y mapeados a Fases 0-3. Su traducción a ESTE roadmap:
- Fase 0 (prohibido)  ↔ ETAPA 0/regla de oro (no tocar H1,H2,H6-lógica,H7,H8,H9,H10,H11-regla).
- Fase 1 (bugs)        ↔ ETAPAS 1→4→5 (validar, corregir uno a uno, revalidar).
- Fase 2 (refactor)    ↔ ETAPA 6 (unificar motores, POI, SB, train/serve, limpieza).
- Fase 3 (calibrar)    ↔ ETAPA 7 (solo experimento).
- Fase 4 (validar)     ↔ ETAPAS 8→9→10.
No hay conflicto: el informe de convergencia decide QUÉ; este plan decide CÓMO y EN QUÉ ORDEN.

---

## ESTADO ACTUAL
- HEAD: 104964c (main). Sin tags. Hay archivos modificados sin commitear (app_observador,
  data/ml) de trabajos previos — NO forman parte del baseline hasta que se decidan.
- Etapa actual: ETAPA 0 (preparar baseline; tag pendiente de OK de Ruben).

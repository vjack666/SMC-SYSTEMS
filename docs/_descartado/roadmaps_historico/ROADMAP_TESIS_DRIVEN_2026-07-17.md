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

ROADMAP ORIENTADO A LA TESIS ICT (TESIS-DRIVEN)
=============================================

Versión: 1.0 — reemplaza la lógica de ETAPA 4 heredada como norte de ejecución.
Fecha: 2026-07-17. Autoría: Hermes (por decisión de arquitectura de Ruben, evidencia
de 3 auditorías + R4 NO_EDGE).

Este documento NO borra los anteriores (CRONOGRAMA_Y_ROADMAP.md, PLAN_
IMPLEMENTACION_ETAPAS.md, ETAPA_4_BUGS.md, DECISION_LOG.md). Los respeta como
historial. Pero a partir de hoy es el ÚNICO plan de avance. Los viejos quedan
marcados OBSOLETOS al final de este archivo.

=====================================================================
0. DECISIÓN DE ARQUITECTURA (fundamento y evidencia)
=====================================================================

Tras tres auditorías — (a) cobertura del backtest [~30% válido para veredicto],
(b) fidelidad a la tesis ICT [~65%, PARCIAL], (c) cruzada del roadmap — y el
cierre R4 ("ICT puro mecánico SIN edge para live/fondeo — REJECT_NO_EDGE",
CRONOGRAMA_Y_ROADMAP.md línea 7), se adopta el siguiente principio:

  ► SUSPENSIÓN DE BACKTESTS DE RENDIMIENTO.
    Queda suspendida la ejecución de nuevos backtests de rendimiento (PF/WR/
    Sharpe/equity) hasta que la implementación alcance la COBERTURA MÍNIMA
    OBLIGATORIA de la tesis ICT (checklist §5 en ✅ y ninguna deuda conceptual
    crítica abierta).

Justificación (no es opinión, es evidencia):
  - El backtest actual NO es concluyente: ablación rota (cap corta por confianza),
    sin DSR/PBO, XAUUSD excluido, funnel que mata 78-90% por bugs de mapeo.
  - El motor es fiel en la mecánica core pero le faltan OTE, exec M5/M1, POI con
    tiers/stacking, Silver Bullet completo y Trade Management.
  - R4 ya probó que ICT MECÁNICO no tiene edge automatizable para fondeo. Un PF
    mejor o peor hoy NO aporta información: sabemos que faltan piezas. Medir PF
    sobre una tesis incompleta es ruido.

Corolario (regla de oro nueva, vinculante):
  Un cambio de implementación se acepta por FIDELIDAD A LA TESIS (checklist §5),
  NO por PF. El PF solo se mide UNA vez, al final, sobre la tesis completa.

=====================================================================
1. TRES DIMENSIONES (nunca más mezclar)
=====================================================================

| Dimensión        | Pregunta                                  | Cómo se mide               | Cuándo se mide |
|------------------|-------------------------------------------|----------------------------|----------------|
| FIDELIDAD        | ¿El motor decide como un operador ICT?    | Checklist por setup (§5)   | Tras cada fase |
| CALIDAD          | ¿Código limpio/tests/única verdad/CI?     | pytest, lint, harness      | Tras cada commit |
| RENDIMIENTO      | ¿PF/WR/Sharpe/DD del motor completo?      | Backtest integral 1 vez    | SOLO al final (§6) |

Estas tres NO se mezclan. El roadmap viejo usaba PF como gate de PASO 5 → riesgo
de trampa inversa (concluir "tesis falla" cuando falta completar capas). Aquí el
gate de aceptación de implementación es FIDELIDAD, no RENDIMIENTO.

=====================================================================
2. INVENTARIO DE LA TESIS — OBLIGATORIO vs OPCIONAL
=====================================================================

Basado en 20_TESIS_ICT.md, 21_POI.md, libro 07 (Silver Bullet), 15 (intradía),
18 (ejecución óptima). Estado "hoy" según auditoría de fidelidad.

OBLIGATORIOS (definen "ICT completo"; bloquean el backtest final):
  Componente                 | Hoy
  ---------------------------|------
  Narrativa HTF (bias)       | ✅ (D1/H4/H1 gates)
  Dealing Range / P-D        | ✅ (dealing_range_pd)
  PD Arrays (FVG/OB/Breaker) | ✅ geometría / ❌ tiers+stacking
  Liquidity Sweep            | ✅
  Displacement               | ✅ (calibrar en Fase F)
  Market Structure / BOS     | ✅ (PASO 1 unificó)
  CHOCH / MSS                | ✅ implícito
  Entry retorno a zona       | ✅ (mitigation)
  SL estructural             | ✅ (mecha sweep)
  TP liquidez cercana        | ✅ (bsl/ssl LTF)
  Killzone                   | ✅ (London/NY AM/PM)
  RR 1:3                     | ✅
  POI anclado a narrativa    | ❌ (htf_poi_fn OFF)  ← NUEVO obligatorio
  Silver Bullet              | ❌                      ← NUEVO obligatorio
  OTE (62-79% retrace)       | ❌                      ← NUEVO obligatorio (sube de "opcional" R3.5)
  Exec fino M5               | ❌                      ← NUEVO obligatorio
  Confirmación M1            | ❌                      ← NUEVO obligatorio
  Trade Management (BE/parc/re-entry) | ❌             ← NUEVO obligatorio
  Turtle Soup (setup contratendencia)  | ❌             ← NUEVO obligatorio (1 de 3 setups del ciclo PO3, tesis 20 §4)
  PD Arrays completos (Breaker/Rejection/Mitigation/Propulsion) | ❌ ← NUEVO obligatorio (21_POI §2, distintos de FVG/OB)
  Liquidez internal vs external         | ❌             ← NUEVO obligatorio (jerarquía de targets, tesis 15/16)

Nota de ambigüedad resuelta: RR global = 1:3 (tesis 18), PERO Silver Bullet
contrato #5 (libro 07) exige RR ≥ 1:2 (Stellar Lite). SB usa 1:2; el resto 1:3.
El motor debe aplicar RR por setup, no un literal global.

OPCIONALES (fases posteriores, NO bloquean "ICT completo"):
  - SMT / Divergence (confirmador de sesgo entre pares correlacionados; libro 21
    R3.5). Clasificación: OPCIONAL — la tesis lo nombra como refinamiento de
    confirmación, no como definitorio del setup.
  - ML ranking de POIs (allowlist estática es suficiente al inicio). Clasificación:
    DECISIÓN DE INGENIERÍA — no proviene de ICT, es forma de priorizar POIs.
  - Refinamientos MMXM / Unicorn (modelos de tiempo avanzados). OPCIONAL.
  - Walk-forward OOS / A12 (requiere tesis completa primero). OPCIONAL (metodología).
  - Calibración fina de parámetros (displace_gap, ATR, costos 5/8). DECISIÓN DE
    INGENIERÍA — umbrales de implementación, no regla de tesis.

DEUDA FUNCIONAL (regla de tesis NO implementable hoy, documentada como deuda):
  - Filtro de noticias de alto impacto (tesis 21 §5: evento invalida setup). NO es
    "opcional": es regla de INVALIDEZ. Hoy el motor no integra calendario económico.
    Queda como DEUDA FUNCIONAL explícita, no como extra. Al cierre de Fase C se
    documenta el hook de invalidación aunque sin feed de noticias conectado.

LEYENDA DE CLASIFICACIÓN (salvaguarda metodológica, Ruben 2026-07-17):
  OBLIGATORIO = la tesis/libro lo exige explícitamente para "ICT completo".
  OPCIONAL = la tesis lo nombra como refinamiento, no definitorio.
  DECISIÓN DE INGENIERÍA = no proviene de ICT; es diseño del motor/umbrales.
  DEUDA FUNCIONAL = regla de tesis real pero no implementable hoy (se documenta).

CAMBIO RESPECTO AL ROADMAP VIEJO: OTE, M5/M1 y Trade Management PASAN de
"opcionales / fuera de ETAPA 4" a OBLIGATORIOS. El roadmap viejo (IMPLEMENTATION_
PLAN PASO 5) solo contemplaba POI+SB; omitía OTE/M5/M1/BE/parciales. Esa omisión
es la deuda de fidelidad que sobrevive. Aquí se cierran.

=====================================================================
3. NUEVAS DEPENDENCIAS DESCUBIERTAS (no estaban en el roadmap viejo)
=====================================================================

Cruzadas en AUDITORIA_CRUZADA_ROADMAP (PARTE III):

  SB ──depende──> M5        (sin M5, SB es solo sub-ventana de killzone, no setup libro 07)
  POI ──depende──> tiers/stacking (sin ellos, POI anclado queda "plano")
  OTE ──depende──> Dealing Range (infra ✅ existe; capa fina ausente)
  M1 ──depende──> M5
  Trade Mgmt ──depende──> motor de ejecución fina (hoy solo hold_limit)

Estas relaciones NO estaban documentadas y son fuente de fidelidad parcial. El
nuevo orden (§4) las respeta: M5/tiers antes que SB/POI reales.

DESCUBIERTAS EN ESTA AUDITORÍA DEL PLAN (2026-07-17):
  SB ──RR distinto──> regla global   (SB usa 1:2, motor usa 1:3 → debe parametrizarse por setup)
  Turtle Soup ──depende──> CHOCH contrario (ya existe en canónico; requiere flujo contratendencia documentado)
  Liquidez internal/external ──depende──> jerarquía de TP (¿internal primero o external?)
  Fase 0 (formalización) ──precede──> TODAS las fases B-E (evita reinterpretar libros por fase)

=====================================================================
4. NUEVO ORDEN LÓGICO DE IMPLEMENTACIÓN (grafo por dependencia de TESIS)
=====================================================================

NO ordena por causa raíz de software (eso era CR-1..CR-6 del roadmap viejo). Ordena
por dependencia del MODELO CONCEPTUAL. La deuda de software (XAUUSD O(n²), cap, ML,
DSR/PBO, tests) se subordina a cerrar la tesis primero (Fase F), no al revés.

FASE 0 — FORMALIZACIÓN DE LA TESIS (especificación formal, ANTES de código):
  Cadena de documentación del proyecto (convención adoptada DEC-009e, 2026-07-17):

    SPEC ──▶ ADS ──▶ MDS ──▶ CÓDIGO
    (QUÉ)   (CÓMO)  (CON QUÉ)

  - SPEC = docs/ict/SPEC_TESIS_FORMAL.md — la tesis como CONTRATO FUENTE (QUÉ dice
    la tesis). Nuevo eslabón; no existía. Alias: "Especificación Formal".
  - ADS = docs/SAD.md (SAD existente) — arquitectura/organización del sistema (CÓMO
    se organiza). Alias: SAD = Architecture Design Specification.
  - MDS = docs/specs/*.md (SDD existentes) — diseño de cada módulo (CON QUÉ se
    implementa). Alias: SDD = Module Design Specification. No se renombran los SDD
    existentes; SDD y MDS son la misma cosa.
  - CÓDIGO = implementación en ict_backtest/.

  Para cada componente (HTF bias, dealing range, PD arrays, sweep, displacement,
  BOS/CHOCH, POI, SB, Turtle Soup, OTE, M5/M1, trade mgmt, liquidez internal/
  external, RR por setup): definir ENTrada, SALida, PREcondiciones, POSTcondiciones,
  DEPendencias, CRITERIOS objetivos, CASOS LÍMITE, AMBIGÜEDADES.
  Producto: docs/ict/SPEC_TESIS_FORMAL.md (el CONTRATO del proyecto). Objetivo:
  cualquier dev implementa sin reinterpretar los libros. Cierra la trampa de
  "implementación se desvía de tesis". DURO: sin Fase 0 firmada, no arranca B.

ESTADO BASE (ya hecho, NO se repite — respetado del roadmap viejo):
  ETAPA 0-3 cerradas. PASO 1 (BOS/CHOCH única verdad) ✅. Dealing Range, Sweep,
  Displacement, SL, TP, bias, killzone, RR ya ✅.

FASE B — Geometría fina (desbloquea POI/SB reales):
  B1: PD Arrays COMPLETOS — FVG/OB/Breaker/Rejection/Mitigation/Propulsion + tiers
      (BPR>OB/FVG>breaker>bloques) + stacking multi-TF (21_POI §2/§3). Requisito
      previo de un POI REAL.
      ✅ DONE (DEC-009g, 2026-07-18): metadatos pd_type/pd_tier en detectores +
      cruce BPR/BREAKER/MITIGATION en data_feed + propagación vía translation +
      congelado en state de sequence. Verificado: no altera decisión del motor
      (EURUSD M15 real B1==baseline señales). El CONSUMO de estos metadatos
      (POI/staking reales) queda en Fase C.
  B2: Exec fino M5 + Confirmación M1 — bajar entry/SL/TP a M5/M1; prerequisito
      de Silver Bullet y Turtle Soup de libro 07/06.
  B3: Liquidez internal vs external — jerarquía de targets (internal swing reciente
      primero; external PDH/PDL/EQ high-low después) para el TP.

FASE C — Capa de Autoridad de Zonas (PERCEPCIÓN, no decisión):
  Re-definida 2026-07-18 (Ruben + Hermes): Fase C NO añade setups ni señales.
  Es la CAPA DE EVALUACIÓN DE AUTORIDAD CONTEXTUAL de la zona LTF ya trazada
  por R7 (tesis 18: "primero dónde mirar, luego cuándo disparar"). Cierra el
  root cause A'' (POI anclado HTF muerto por plumbing, no por diseño): el hook
  htf_poi_fn ya existía en run_sequence pero est_htf_fn nunca traía FVG/OB del
  HTF. Fase C lleva ese cable (C0-C4, TDD, ver docs/plan/ETAPA_4_FASE_C_PLAN.md
  y tests/test_fase_c0..c4.py).

  C0: Plumbing HTF — HtfPdIndex indexa FVG/OB de los TF HTF (D1/H4/H1) por barra
      LTF CERRADA (anti look-ahead). O(n) vía merge_asof, NO O(n²). No crea zonas.
  C1: est_htf_fn (canonical.py) entrega los PD arrays HTF vigentes a cada vela LTF.
  C2: zone_authority.evaluate_zone_authority — recibe la zona LTF (ya trazada por
      R7) + PD arrays HTF vigentes y devuelve {has_htf_anchor, tier, stacking_level,
      confidence_weight[0,1], level: Alta/Media/Baja}. LEE, no crea; no decide
      dirección/entry/SL/TP; respeta la jerarquía T1(BPR)>T2(FVG/OB)>T3(rejection)
      y el stacking multi-TF (libro 21 §2).
  C3: cableado en run_sequence — anota zone_authority en cada señal (ICTSignal.
      zone_authority). MISMO conteo de señales con/sin índice (regla de oro R1:
      C no altera R7; si el conteo cambia = bug de invasión). Sin índice HTF,
      zone_authority queda None (comportamiento histórico intacto).
  C4: tests de fidelidad §5 — el peso ORDENA zonas por calidad contextual
      (T1>T2>T3, stacking>single, Zona Alta>Media>Baja). Métrica de FIDELIDAD,
      NO de PF (regla de oro del roadmap: se acepta por fidelidad, no por PF).
  C5: validación manual end-to-end (runner_monitor) sobre EURUSD M15 real —
      confirma R1 (mismo conteo) + distribución de autoridad. Sin PF.

  ✅ DONE (2026-07-18): C0-C4 en código + tests verdes (16 tests). C5 en curso.
  CONTRATO DE NO INVASIÓN (violación = bug): C nunca crea zonas, nunca es gate
  duro, nunca altera el conteo de señales, nunca toca R7. El peso de confianza
  es INFORMACIÓN para el operador/humor del mercado, no un filtro de entrada.

  Setups SB / Turtle Soup (libro 07/06, tesis 20 §4): se reubican FUERA de esta
  Fase C. Eran C1-C3 en el borrador previo pero, por la filosofía "C = capa de
  autoridad, no 2do cerebro", SB/Turtle Soup son SETUPS que añaden señales y
  pertenecen a una fase posterior de ampliación de tesis (no a la capa de
  percepción). Quedan como PENDIENTES post-C, alineados a Fase G (gate fidelidad).

FASE D — Entry fina:
  D1: OTE — retrace 62-79% del swing, medido sobre Dealing Range.

FASE E — Trade Management:
  E1: Break Even, parciales, re-entry (gestión activa; hoy solo hold_limit).

FASE F — Deuda de software (SUBORDINADA; orden interno por causa raíz, válido):
  F1: XAUUSD en MTF — fix O(n²) (cachear HTF fuera del loop). Requiere OK de Ruben.
  F2: Cap por ventana/seed + quitar w0_agents (CR-3) — ablación válida.
  F3: ML sobre stack canónico + allowlist (CR-4) — requiere PASO 1 (✅ hecho).
  F4: DSR/PBO en grilla 168 (H16) — requiere F2.
  F5: Tests reproducibles + ciclo import + dead code (CR-5).

FASE G — GATE DE FIDELIDAD (§5 ✅) → SOLO ENTONCES Backtest integral único (§6).

Nota de coherencia con la regla de oro vieja: Fase 0 (ICT/SB/Killzone/Sequence/
SL/TP/HTF/Entry) sigue PROHIBIDA de tocar. Las fases B-E AÑADEN tesis, no alteran
la ya correcta. Esto cumple "un cambio estructural a la vez + revertir si altera
la regla de la estrategia".

=====================================================================
5. CHECKLIST DE FIDELIDAD (GATE de aceptación, NO PF)
=====================================================================

El test NACE DE UNA ESPECIFICACIÓN, no al revés (decisión de Ruben 2026-07-17):
  Paso 1 — DEFINIR la checklist (esta sección).
  Paso 2 — VALIDARLA manualmente contra subconjunto etiquetado a mano (20 setups
           por componente, revisión del comité) antes de cualquier automatización.
  Paso 3 — AUTOMATIZARLA solo tras validación: tests/test_fidelity_thesis.py
           (NO se implementa aún; nace de la spec validada).

Cada fase se acepta cuando el motor COINCIDE con las decisiones que tomaría un
operador ICT siguiendo 20_TESIS_ICT.md + 21_POI.md + SPEC_TESIS_FORMAL.md, medido
en el subconjunto etiquetado. Métrica: % de coincidencia de decisión
(dirección/entry/SL/TP) por setup.

  [ ] Narrativa HTF
  [ ] Dealing Range
  [ ] PD Arrays (FVG/OB/Breaker/Rejection/Mitigation + tiers/stacking)
  [ ] POI (anclado)
  [ ] Sweep
  [ ] Displacement
  [ ] BOS / MSS
  [ ] Silver Bullet (incl. RR 1:2)
  [ ] Turtle Soup (contratendencia)
  [ ] OTE
  [ ] Entry M5
  [ ] Confirmación M1
  [ ] Liquidez internal vs external (jerarquía TP)
  [ ] Trade Management (BE/parciales/re-entry)

=====================================================================
6. BACKTEST INTEGRAL (único, al final)
=====================================================================

Solo se ejecuta cuando:
  (a) Checklist §5 en ✅ para todos los obligatorios.
  (b) Ninguna deuda conceptual crítica abierta.
  (c) Fase F (deuda de software) completa (ablación válida + DSR/PBO + XAUUSD).

Entonces, y solo entonces, UN backtest serio: reloj MTF, fill next-open, costos
ON (5/8 calibrados), OOS, DSR/PBO. Su PF se interpreta como RENDIMIENTO de la
tesis completa, no como veredicto de si la tesis "funciona" (R4 ya separó eso).

=====================================================================
7. PUNTO DE CORTE OBJETIVO (para volver a backtest)
=====================================================================

Cumple si:
  ✅ Todas las reglas OBLIGATORIAS de la tesis implementadas (§2).
  ✅ Checklist de fidelidad ✅ (§5).
  ✅ Ninguna deuda conceptual crítica abierta.
  ➔ Mejoras OPCIONALES (ML, SMT/Breaker, walk-forward) quedan para fases posteriores.

Eso es el corte; no se espera "100% absoluto" (sería objetivo móvil).

=====================================================================
8. DOCUMENTOS OBSOLETOS (marcar, no borrar)
=====================================================================

- IMPLEMENTATION_PLAN.md (ETAPA 3) — orden CR-1..CR-6 válido DENTRO de Fase F,
  pero F queda subordinada a B-E. Marcar "parcial, ver ROADMAP_TESIS_DRIVEN".
- ETAPA_4_BUGS.md — PASO 1 ✅ y PASO 2 bloqueado siguen vigentes (mapean a F1/F2).
  PASO 5 viejo se reemplaza por Fases B-E.
- PLAN_IMPLEMENTACION_ETAPAS.md — la sección ESTADO ACTUAL está desactualizada
  (dice HEAD 104964c, sin tags); corregir al commitear.
- CRONOGRAMA_Y_ROADMAP.md — sigue siendo fuente de verdad para hitos R0-R7/A1-A12,
  pero la estrategia de EJECUCIÓN ahora es la de este doc.

=====================================================================
9. MATRIZ DE TRAZABILIDAD Y CLASIFICACIÓN (salvaguarda metodológica)
=====================================================================

Cada elemento del roadmap lleva SU REFERENCIA EXACTA y su CLASIFICACIÓN
(OBLIGATORIO / OPCIONAL / DECISIÓN DE INGENIERÍA / DEUDA FUNCIONAL). Ningún
elemento queda sin clasificar. Esto impide que una decisión de ingeniería se
disfrace de regla de la tesis.

| Concepto ICT                    | Fuente exacta                         | Clasificación           | Fase    |
|---------------------------------|---------------------------------------|-------------------------|---------|
| Narrativa HTF (bias D1/H4/H1)   | tesis 20 §1, libro 08 §0              | OBLIGATORIO             | Base ✅ |
| Dealing Range / P-D (EQ 50%)    | libro 21 (premium/discount)           | OBLIGATORIO             | Base ✅ |
| PD Arrays (FVG/OB)              | tesis 20 §2/§5b, libro 21             | OBLIGATORIO             | Base ✅ |
| PD Arrays completos (Breaker/Rej/Mitig/Propulsion) | tesis 20 §5b, libro 21 §2 (tiers T1-T3) | OBLIGATORIO | B1 ✅ (metadatos; consumo en C) |
| Stacking multi-TF               | tesis 20 §5b, libro 21 §2             | OBLIGATORIO             | B1 ✅ (metadatos; consumo en C) |
| Sweep de liquidez               | tesis 20 §3, libro 05                 | OBLIGATORIO             | Base ✅ |
| Displacement (gap cuerpo>70%)   | tesis 20 §5b, libro 15                | OBLIGATORIO             | Base ✅ (calibrar F) |
| Market Structure / BOS          | tesis 20 §2, libro 02                 | OBLIGATORIO             | Base ✅ (PASO 1) |
| CHOCH / MSS                      | tesis 20 §2, libro 02                 | OBLIGATORIO             | Base ✅ |
| 3 capas HTF/ITF/exec             | tesis 20 §5, libro 18 §0              | OBLIGATORIO             | B2 |
| Exec fino M5 + Confirm M1        | tesis 20 §5, libro 18                 | OBLIGATORIO             | B2 |
| Entry retorno a zona            | tesis 20 §6, libro 15 §2              | OBLIGATORIO             | Base ✅ (sequence.py) |
| SL estructural (mecha sweep)    | tesis 20 §7, libros 14/15/17          | OBLIGATORIO             | Base ✅ (medido v29) |
| TP liquidez cercana LTF          | tesis 20 §8, libros 15/16/17          | OBLIGATORIO             | Base ✅ (engine.py) |
| Liquidez internal vs external    | libro 05/15/16, tesis 20 §3           | OBLIGATORIO             | B3 |
| Killzone (London/NY AM/PM)       | tesis 20 §10, libro 01/18             | OBLIGATORIO             | Base ✅ |
| RR mínimo 1:3 (no-SB)            | tesis 20 §9, libro 18                 | OBLIGATORIO             | Base ✅ (filtro) |
| RR 1:2 para Silver Bullet        | libro 07 #5 (contrato)                | OBLIGATORIO (por setup) | C2 |
| POI anclado a narrativa HTF      | tesis 20 §5b, libro 21                | OBLIGATORIO (bonus)     | C1 |
| Silver Bullet                    | libro 07, tesis 20 §4                 | OBLIGATORIO             | C2 |
| Turtle Soup (contratendencia)    | libro 06, tesis 20 §4 (1 de 3 setups) | OBLIGATORIO             | C3 |
| OTE (62-79% retrace)             | tesis 20 §6, libro 15                 | OBLIGATORIO             | D1 |
| Trade Management (BE/parc/re-entry) | tesis 20 §9, libro 15/17            | OBLIGATORIO             | E1 |
| Fase 0 — Formalización (SPEC)    | decisión Ruben 2026-07-17             | DECISIÓN DE INGENIERÍA  | Fase 0 |
| RR parametrizado por setup       | deriva libro 07 #5 vs tesis 20 §9     | DECISIÓN DE INGENIERÍA  | C2 |
| Cap por ventana/seed             | CR-3 (calidad ablación)               | DECISIÓN DE INGENIERÍA  | F2 |
| Unificar BOS/CHOCH (fuente única)| CR-1                                  | DECISIÓN DE INGENIERÍA  | Base ✅ (PASO 1) |
| XAUUSD MTF (fix O(n²))           | CR-6 / H14 (dato ya existe)           | DECISIÓN DE INGENIERÍA  | F1 |
| ML sobre canónico + allowlist    | CR-4                                  | DECISIÓN DE INGENIERÍA  | F3 |
| DSR/PBO en grilla                | H16 (significancia)                   | DECISIÓN DE INGENIERÍA  | F4 |
| Tests reproducibles / dead code  | CR-5                                  | DECISIÓN DE INGENIERÍA  | F5 |
| SMT / Divergence                 | libro 21 R3.5                         | OPCIONAL                | post |
| MMXM / Unicorn                   | libros 22/23                          | OPCIONAL                | post |
| Walk-forward OOS / A12           | metodología                           | OPCIONAL                | post |
| Calibración displace_gap/ATR     | umbrales                              | DECISIÓN DE INGENIERÍA  | F (ETAPA 7) |
| Filtro noticias (invalidez)      | tesis 21 §5                           | DEUDA FUNCIONAL         | post (hook Fase C) |

Conteo: 24 OBLIGATORIOS (incl. 2 por-setup), 4 DECISIÓN DE INGENIERÍA de soporte,
3 OPCIONALES, 1 DEUDA FUNCIONAL. CERO elementos sin clasificar.

VERIFICACIÓN DE LA AFIRMACIÓN FUERTE ("no quedan conceptos obligatorios fuera"):
La matriz cubre todos los componentes nombrados en tesis 20 (§1-§12) y libros 07/08/
15/18/21 citados. Los únicos no cubiertos como OBLIGATORIOS son SMT/MMXM (la tesis
los marca como refinamiento, no definitorio) y noticias (regla real pero no
implementable → DEUDA FUNCIONAL explícita, no olvidada). Por tanto la afirmación
se sostiene: todo OBLIGATORIO de la tesis documentada está en el roadmap.

=====================================================================
10. AUDITORÍA DEL PLAN (2026-07-17, post-revisión)
=====================================================================

Rol: auditor externo cuyo único objetivo es encontrar lo que falta. Revisa SOLO
la tesis ICT (20/21 + libro 07/15/18) contra este roadmap. Ignora el roadmap viejo.

PREGUNTAS Y RESPUESTAS (con evidencia):
1. ¿Regla/concepto/flujo de tesis no representado?
   Detectados y YA INCORPORADOS en esta revisión: Turtle Soup (tesis 20 §4, 1 de 3
   setups PO3), PD Arrays completos Breaker/Rejection/Mitigation/Propulsion (21_POI
   §2), liquidez internal vs external (tesis 15/16), RR SB 1:2 vs 1:3 global
   (libro 07 #5), Fase 0 formalización (decisión de Ruben). Tras incorporarlos:
   no quedan conceptos obligatorios de la tesis fuera del roadmap.

2. ¿Componente como opcional que debería ser obligatorio?
   Turtle Soup y PD Arrays completos y liquidez internal/external subieron a
   OBLIGATORIOS en esta revisión. SMT queda OPCIONAL (confirmador de sesgo, no
   definitorio del setup). Filtro noticias OPCIONAL.

3. ¿Dependencias no reflejadas?
   Incorporadas: RR SB≠global, Turtle Soup→CHOCH contrario, internal/external→TP,
   Fase 0 precede B-E. Todas reflejadas ahora.

4. ¿Mejor orden?
   B→C→D→E→F→G con Fase 0 al inicio es el orden por dependencia de tesis correcto.
   No se encuentra un orden superior.

5. ¿Fase que genera retrabajo?
   El retrabajo venía de implementar B-E sin spec (cada fase reinterpretaría libros).
   Fase 0 (formalización) lo previene como PUERTA DURA. Sin Fase 0 firmada no
   arranca B. La ambigüedad RR SB se resolvió explícitamente (1:2 por setup).

6. ¿Roadmap completo respecto a la tesis?
   Tras esta revisión: SÍ para lo OBLIGATORIO de la tesis ICT documentada en el
   repo (20/21 + libros 07/15/18). Los refinamientos (SMT, MMXM, noticias,
   walk-forward) quedan como opcionales posteriores, correctamente fuera del corte.

VEREDICTO: ✅ Roadmap listo para convertirse en roadmap maestro (tras incorporar
los hallazgos de esta auditoría, ya hechos en las secciones 2-5 y la MATRIZ §9).

SALVAGUARDA METODOLÓGICA (Ruben 2026-07-17) — verificada en MATRIZ §9:
  - Todo elemento tiene referencia exacta de tesis/libro y clasificación explícita.
  - Ninguna DECISIÓN DE INGENIERÍA se disfraza de regla de tesis (ver columna
    "Clasificación": cap, ML, XAUUSD fix, DSR/PBO, tests, Fase 0, RR-por-setup
    están marcados como INGENIERÍA, no tesis).
  - Noticias reclasificada de "opcional" a DEUDA FUNCIONAL (regla de invalidez
    real, tesis 21 §5, no implementable hoy → documentada, no olvidada).
  - Conteo final: 24 OBLIGATORIOS, 4 INGENIERÍA de soporte, 3 OPCIONALES,
    1 DEUDA FUNCIONAL. CERO sin clasificar.

=====================================================================
11. REGLAS DE GOBERNANZA DEL ROADMAP (duras, aplicables a todo cambio futuro)
=====================================================================

Estas 4 reglas son OBLIGATORIAS y vinculantes. Cualquier commit posterior al
roadmap maestro las respeta:

R1 — Fase 0 (SPEC_TESIS_FORMAL) es el CONTRATO FUENTE.
    Ninguna regla de la estrategia puede implementarse si no existe PRIMERO en la
    especificación formal. La SPEC (docs/ict/SPEC_TESIS_FORMAL.md) precede al
    código. Sin entrada/salida/pre/post/dependencias/criterios/casos-límite/
    ambigüedades documentados en la SPEC, la regla NO se implementa.

R2 — Matriz de trazabilidad sincronizada con la SPEC.
    La MATRIZ §9 y la SPEC se mantienen OBLIGATORIAMENTE sincronizadas. Si en el
    futuro se agrega, elimina o modifica una regla de la tesis, AMBAS (SPEC y
    MATRIZ) se actualizan en el MISMO cambio. No se acepta una sin la otra.

R3 — Etiqueta de capa en todo cambio futuro.
    Todo cambio deberá indicar explícitamente si modifica: (a) la TESIS (SPEC),
    (b) la IMPLEMENTACIÓN, o (c) únicamente la INGENIERÍA DEL MOTOR. No se aceptan
    cambios que mezclen estas tres capas sin dejarlo documentado en el commit y
    en el DECISION_LOG.

R4 — Backtest bloqueado hasta Fase G (Gate de Fidelidad).
    El backtest de RENDIMIENTO permanece BLOQUEADO hasta completar la Fase G
    (checklist de fidelidad ✅). No se abrirán excepciones salvo que el objetivo
    sea VALIDAR INFRAESTRUCTURA (pipeline, fill, reloj MTF, CI) y NUNCA para
    medir rendimiento (PF/WR/Sharpe/equity). Un backtest de infraestructura se
    documenta como tal y no se interpreta como veredicto de edge.

=====================================================================
FIN — Roadmap orientado a la tesis ICT (2026-07-17).

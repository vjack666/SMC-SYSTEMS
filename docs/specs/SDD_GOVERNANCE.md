# SDD_GOVERNANCE.md — Gobierno del Desarrollo Spec-Driven (SDD) de SMC-SYSTEMS

**Estado:** VIGENTE · **Autoridad:** meta-SDD (norma de normas del SDD)
**Dominio:** exclusivamente Forex / ICT-SMC. Prohibido introducir binarias, QUOTEX,
OTC de binarias, martingalas, gales, indicadores técnicos (EMA/RSI/ATR/MACD/Bollinger).

> Este documento es el **SDD del propio SDD**. Define cómo una idea pasa a especificación,
> una especificación a implementación, una implementación a verificación semántica, y cómo
> una modificación puede ser auditada posteriormente SIN depender de la memoria de Hermes.
> No es documentación de producto: es el mecanismo que impide que el proyecto olvide qué
> está construyendo.

---

## 0. ÁRBOL DE AUTORIDAD (qué documento manda sobre qué)

Para evitar fuentes duplicadas (anti-patrón del contrato CEO §18), se declara UNA
jerarquía. Cualquier conflicto se resuelve por este orden descendente:

| # | Documento | Rol de autoridad | Puede ser contradicho por |
|---|-----------|------------------|---------------------------|
| 1 | `AGENTS.md` (raíz) | Ley Fundamental motor≠backtest, regla de commit/push | nada (constitución) |
| 2 | `docs/ict/SPEC_TESIS_FORMAL.md` | Contrato formal firmado de la estrategia ICT/SMC | solo revisión explícita del Director |
| 3 | `docs/DECISION_BACKTEST_UNICO.md` | Arquitectura de backtest (canónico único) | nada vigente |
| 4 | `engine/` (código) | Única fuente de decisión en vivo | la tesis (si hay bug, se reporta) |
| 5 | `docs/specs/SDD_GOVERNANCE.md` | **Este meta-SDD** (proceso de evolución) | AGENTS.md / tesis |
| 6 | `docs/specs/INDICE_MDS.md` | Índice maestro de componentes del motor | el motor real (se actualiza a él) |
| 7 | `docs/tesis/SDD_*.md` | Specs de diseño de estrategia (rescate POI, capa LTF) | engine/ + SDD_GOVERNANCE |
| 8 | `research/` (HYP/EXP) | hipótesis/experimentos fuera del producto | research contract |

**Resolución de la triple ubicación histórica:**
- `docs/specs/` = índice de componentes (`INDICE_MDS.md`) + este meta-SDD + specs de app.
- `docs/tesis/SDD_*.md` = specs de DISEÑO de estrategia (los que citan PROTOCOLO_AGENTE
  e ingeniero como "el SDD relevante"). **Estos SON los SDD de estrategia**; se mantienen ahí.
- `openspec/` = **LÍNEA BASE FORENSE CONGELADA** (auditoría SDD-00, 2026-08-07). Histórica,
  no fuente viva. Ver §9. No competir con este meta-SDD.

> CORRECCIÓN DE PUNTEROS (2026-08-11): `PROTOCOLO_AGENTE.md` §2 y `CONTRATO_ORDEN.md` §1/§5
> apuntaban a `docs/specs/` como único SDD. Se aclara: el "SDD relevante" de una tarea de
> motor es `docs/tesis/SDD_*.md` (si existe para ese componente) O se crea aquí el spec.

---

## 1. DEFINITION OF READY (DoR) — cuándo un spec puede implementarse

Una especificación NO pasa a implementación si falta ALGUNO de estos. El Ingeniero la
marca `BLOCKED` y la devuelve al Investigador/Arquitecto.

| # | Check DoR | Evidencia requerida |
|---|-----------|---------------------|
| 1 | **Objetivo** claro y acotado | una frase: "qué problema de mercado resuelve" |
| 2 | **Relación con tesis** | cita `docs/ict/SPEC_TESIS_FORMAL.md` §X o libro ICT |
| 3 | **Comportamiento esperado** | entradas → salidas, determinista |
| 4 | **Entradas** | tipos, forma (OHLC, índices, objetos), anti look-ahead explícito |
| 5 | **Salidas** | tipo, semántica (ej. "POI anclado = MarketObject role=POI, padre BOS") |
| 6 | **Invariantes** | lo que NUNCA cambia (ej. engine no importa ict_backtest) |
| 7 | **Límites** (qué NO hace) | lista explícita de no-hacer |
| 8 | **Casos negativos** | qué pasa si no hay evento padre / dato faltante |
| 9 | **Dato faltante** | comportamiento UNKNOWN/GAP, nunca fail-open silencioso no documentado |
| 10 | **Criterios de falsación** | cómo se demuestra que NO funciona |
| 11 | **Criterios de aceptación** | definibles sin "parece bien" |
| 12 | **Impacto sobre módulos existentes** | lista de archivos afectados |
| 13 | **Prohibiciones explícitas** | "sin ATR/RSI/EMA", "sin gate duro en POI", etc. |

Spec ambiguo → `BLOCKED`, no se implementa. (Contrato CEO §6.)

---

## 2. DEFINITION OF DONE (DoD) — qué significa realmente "DONE"

`DONE` NO = "el código existe". Se descompone en estados obligatorios:

```text
IMPLEMENTED        → código en engine/ (o consumidor), py_compile limpio, 0 imports prohibidos
  ↓
TESTED             → tests nuevos pasan; tests motor existentes no bajan; smoke import OK
  ↓
SEMANTICALLY_VERIFIED → verificación semántica (§4) pasa: identidad, linaje, orden,
                        anti look-ahead, dirección, ausencia de indicadores
  ↓
AUDITED            → Auditor Independiente revisó trazabilidad y veto de PROMOCIÓN
  ↓
ACCEPTED           → Director (o quien mande) firma aceptación con evidencia
```

Un componente NO se declara `ACCEPTED` solo porque sus tests técnicos pasen. Debe
demostrarse que su comportamiento sigue correspondiendo a la tesis (Contrato CEO §7).

---

## 3. ESTADOS FORMALES DEL SDD (máquina de estados)

Todo spec/componente lleva uno de estos estados. Nadie mueve un estado sin autoridad.

```text
DRAFT ──────► READY ──────► IMPLEMENTING ──────► TESTED
                │                                    │
                │                                    ▼
                │                            SEMANTICALLY_VERIFIED
                │                                    │
                │                                    ▼
                │                                AUDITED ──────► ACCEPTED
                │                                    │
   BLOCKED ◄────┘                                    │
   REJECTED ◄────────────────────────────────────────┘ (falla tesis)
   SUPERSEDED ◄── reemplazado por nuevo spec
   DEPRECATED ◄── fuera de uso, archivado
```

| Estado | Significado | Quién puede moverlo |
|--------|-------------|---------------------|
| DRAFT | idea/no formalizado | Investigador/Arquitecto |
| READY | pasó DoR | Investigador → Ingeniero |
| IMPLEMENTING | código en curso | Ingeniero |
| TESTED | tests verdes | Ingeniero |
| SEMANTICALLY_VERIFIED | verificación §4 pasa | Ingeniero + evidencia |
| AUDITED | Auditor selló | Auditor (veto PROMOCIÓN) |
| ACCEPTED | en producto | Director |
| BLOCKED | falta SDD/autoridad | cualquiera → escala |
| REJECTED | cae la tesis | Auditor/Director |
| SUPERSEDED | reemplazado | Director |
| DEPRECATED | obsoleto, archivar | Memoria/Cumplimiento |

---

## 4. VERIFICACIÓN SEMÁNTICA (SEMANTIC VERIFICATION)

`pytest = verde` NO es suficiente. Toda modificación de un componente de decisión debe
demostrar, además, que conserva el SIGNIFICADO de la tesis. Capa mínima obligatoria:

| Dimensión | Qué comprueba | Ejemplo HYP-002 |
|-----------|---------------|-----------------|
| **Identidad** | objetos/eventos tienen id estable y único | `MarketObject.id` uuid, 0 duplicados |
| **Linaje (LINK)** | el padre declarado existe y es anterior | SWEEP.parent = LIQUIDITY idx |
| **Causalidad (CAUSALITY)** | parent declarado == id real del padre | BOS→POI→RETURN enlazados por origen |
| **Orden temporal** | eventos en secuencia lógica | sweep < displace < bos < entry |
| **Dirección** | consistencia de dirección en la cadena | todo el setup misma dirección |
| **Anti look-ahead** | nada lee el futuro | merge_asof backward, closed-only |
| **Autoridad de niveles** | niveles vienen del TF padre ya cerrado | POI anclado a BOS/CHOCH cerrado |
| **Relación HTF/LTF** | LTF se evalúa bajo contexto HTF vigente | `top_down_allows_trade` |
| **Conservación de eventos** | al invalidar, la historia queda | `Expediente.invalidate` no borra |
| **Comportamiento ante UNKNOWN** | declara UNKNOWN, no inventa | Macro=UNKNOWN si no hay dato |

La verificación semántica se ejecuta como un **consumidor puro del motor** (igual que el
backtest): corre el motor y audita la traza. No toca `engine/`. (Patrón validado en
HYP-002 Fase 5/6: `phase5_validation.py` / `phase6_validation.py`.)

---

## 5. REGRESIÓN SEMÁNTICA (SEMANTIC REGRESSION)

Toda modificación debe responder:

> ¿Cambió SOLO la implementación, o cambió el SIGNIFICADO OBSERVABLE del motor?

- Si cambia el significado → riesgo explícito. Los resultados históricos que dependían de
  esa semántica se marcan **POTENCIALMENTE OBSOLETOS** (no se borran).
- Un cambio puede pasar todos los tests unitarios y AUN así modificar la estrategia. Eso
  es riesgo gobernado, no "verde = bien".
- Regla de hierro (`evidence-docs.md` DP-1/DP-2): flags de regresión cero (`require_pd`,
  `enable_pd_index`, `invalidate-on-opposite-swing`) NO se encienden "porque suena mejor".
  Encenderlos invalida series históricas.

---

## 6. MODELO DE TRAZABILIDAD (TRACEABILITY)

Cada requisito importante debe responder: *"Muéstrame dónde está implementado y dónde
está demostrado."* Y cada modificación: *"¿Qué requisito o principio de la tesis modifico?"*

Cadena obligatoria para componentes de decisión:

```text
Tesis (SPEC_TESIS_FORMAL.md)
  ↓  cita
Requisito (SDD_*.md o INDICE_MDS)
  ↓  define
SDD (este meta-SDD + spec de diseño)
  ↓  produce
Diseño (decisiones de módulo en engine/)
  ↓  implementa
Código (engine/*.py, firmas reales)
  ↓  ejercita
Test (tests/test_engine_*)
  ↓  genera
Evidencia (phaseN_validation.py, results/)
  ↓  sella
Auditoría (Auditor Independiente)
  ↓  produce
Decisión (Director: ACCEPTED / REJECTED)
```

`INDICE_MDS.md` ya cubre la mitad (Componente ↔ Dónde vive ↔ SDD). El spec de diseño
(`SDD_*.md`) cierra el tramo Tesis→Requisito→Diseño. La verificación semántica (§4) cierra
Diseño→Código→Evidencia.

---

## 7. ANÁLISIS DE IMPACTO (IMPACT ANALYSIS)

Toda modificación de un componente identifica:

```text
SDD afectado ─┐
tesis afectada ─┤
módulos afectados ─┤→ (si cambia semántica) → resultados históricos
tests afectados ─┤                     marcados POTENCIALMENTE OBSOLETOS
auditorías afectadas ─┘
resultados que podrían quedar obsoletos
```

No borrar evidencia histórica. Si el cambio altera la semántica, lo que dependía de ella
queda marcado, no eliminado.

---

## 8. SEPARACIÓN DE CUATRO CONCEPTOS (obligatoria en todo spec)

El SDD impide confundir:

- **DETECCIÓN** — el sistema identifica un evento (ej. detecta SWEEP).
- **REPRESENTACIÓN** — el sistema conserva correctamente la info del evento (Expediente/MarketObject).
- **TRAZABILIDAD** — el sistema demuestra post-hoc qué eventos están relacionados (linaje).
- **DECISIÓN** — el sistema usa esa info para decidir.

Detectar SWEEP→DISP→BOS→POI→RETURN NO demuestra automáticamente
`SWEEP→ese DISP→ese BOS→ese POI→ese RETURN`. El spec debe poder auditar esta diferencia
(caso HYP-002: la Fase 5/6 demostró que el linaje debe anclarse en el origen, no inferirse
por proximidad temporal).

---

## 9. REGLA DE NO-INVENCIÓN

Si la especificación no define algo: **NO SUPONER · NO COMPLETAR · NO INFERIR COMO REGLA**.
El agente marca `UNKNOWN` / `GAP` / `BLOCKED` y escala. Esta regla es aceptación del SDD.

---

## 10. CERO INDICADORES TÉCNICOS (refuerzo de Ley Fundamental)

No permitir indicador (ATR/RSI/EMA/MACD/Bollinger) solo porque mejora test, reduce
falsos positivos, mejora WR o "parece útil". La justificación viene de la tesis. Única
excepción: VOLUMEN como confirmación (`volume_ratio`), nunca gate. No introducir ATR como
métrica de conveniencia.

---

## 11. INVESTIGACIÓN ≠ PRODUCCIÓN

`research/` (HYP/EXP) es separado del producto. Un resultado experimental NO se convierte
automáticamente en regla del motor. El `RESEARCH_CONTRACT.md` es autoridad para esta
frontera. Promoción explícita + veredicto + decisión pre-registrada (puerta).

---

## 12. CONGELACIÓN DE openspec/ (línea base forense)

`openspec/changes/sdd-00-truth-authority/` es una auditoría forense de 2026-08-07 con
baseline `9842394`. Hoy el HEAD es `76a8faa`: varios "riesgos" de esa auditoría ya se
resolvieron (ej. `engine/poi_anchor.py` ya está trackeado; la migración POI landed).
Por tanto `openspec/` se declara **LÍNEA BASE HISTÓRICA CONGELADA** — evidencia de la
auditoría, NO SDD vivo. No competir con este `SDD_GOVERNANCE.md`. Si se reabre, nuevo spec.

---

## 13. MÍNIMA BUROCRACIA (principio de minimalidad)

Cada artefacto debe responder una pregunta real: ¿por qué? ¿qué? ¿cómo? ¿dónde? ¿cómo se
prueba? ¿cómo se audita? ¿quién lo acepta? ¿qué rompe si cambia? Si un documento no
aporta una de esas, evaluar si debe existir. No crear MD por crear MD (Contrato CEO §20).

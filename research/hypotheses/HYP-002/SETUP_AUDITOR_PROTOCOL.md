# SETUP_AUDITOR_PROTOCOL.md — Protocolo del SETUP AUDITOR (primer EXP de lectura de HYP-002)

> **Diseño (2026-08-10). Documentación y diseño ÚNICAMENTE. CERO Python, CERO ejecución.**
> Autorizado por el Director (ver instrucción exacta). Este es el documento rector del
> experimento de lectura. Resuelve primero una inconsistencia documental (11 vs 9 capas) y luego
> entrega los 12 entregables exigidos. Complementa `SETUP_SPEC.md` (objeto),
> `SETUP_FORMATION_EVIDENCE.md` (matriz motor) y `SETUP_AUDITOR_DESIGN.md` (visión general).

---

## 0. El auditor es un JUEZ FORENSE, no un segundo motor

El SETUP AUDITOR no decide entradas, no calcula WR/PF, no replica la lógica ICT. Es un
**perito** que toma un setup YA EMITIDO por el motor y comprueba, contra los datos observables,
si la historia que el motor cuenta es VERDAD:

> *"Si me muestras un setup emitido por el motor, ¿puede Hermes demostrar exactamente, con datos
> históricos y timestamps, por qué ese setup existe y qué acontecimientos lo formaron?"*

Regla central: **el auditor NO confía ciegamente en las etiquetas del motor**. Si el motor dice
`BOS=True`, el auditor pregunta *"¿qué evidencia demuestra ese BOS?"*; si dice `POI=FVG`, pregunta
*"¿de qué displacement nació?"*; si dice `Sweep=True`, pregunta *"¿qué liquidez tomó exactamente?"*.

---

## 1. RESOLUCIÓN DE INCONSISTENCIA: taxonomía canónica de capas (trazabilidad)

**Problema.** Tres documentos hablan idiomas distintos:
- `SETUP_SPEC.md` §1 → **11 capas**.
- `SETUP_FORMATION_EVIDENCE.md` (matriz) → **9 capas** y afirma "8 de 9".
- `SETUP_AUDITOR_DESIGN.md` → lista "Linaje causal" como capa OBLIGATORIA (implícita 12ª).

**Decisión (no arbitraria).** La taxonomía canónica es la de **SETUP_SPEC: 11 capas**. Razón:
SETUP_SPEC es la *definición formal del objeto* ("definir exactamente qué evidencia debe existir
en cada piso"), la fuente de verdad de qué es "setup completo". Las otras dos vistas son
derivadas y deben reconciliarse con ella:

1. **La matriz de 9 es una VISTA DE AUDITORÍA CONSOLIDADA**, no una taxonomía distinta. Fusionó
   dos capas sin perder información:
   - `Sweep` (capa 4) absorbida por `Liquidez` (capa 3): el sweep es inseparable de la liquidez
     que toma; auditarlo por separado de la liquidez no aporta veredicto propio.
   - `Confirmación estructural` (capa 6) absorbida por `Estructura` (capa 2): el BOS/CHOCH post-
     displacement es la confirmación de la estructura, no un piso independiente del veredicto.
   - Mapeo 11 → 9: `[1]→Contexto, [2+6]→Estructura, [3+4]→Liquidez, [5]→Displacement, [7]→POI,
     [8]→Retorno, [9]→LTF, [10]→Macro, [11]→Estado`.
   - Por tanto "8 de 9" de la matriz = "10 de 11" de SETUP_SPEC (la única ausente en ambas vistas
     es **Macro**, GAP-1). Ambas cuentas son ciertas bajo su taxonomía; el desajuste era de
     *presentación*, no de hecho. Se unifica aquí: **el motor implementa 10 de las 11 capas de
     SETUP_SPEC; la ausente es Macro (capa 10, GAP-1)**.

2. **"Linaje causal" NO es una capa.** Es una **restricción transversal** que debe cumplirse a
   lo largo de las capas de evento (Liquidez→Sweep→Displacement→Confirmación estructural→POI→
   Retorno→LTF). Por eso `SETUP_AUDITOR_DESIGN.md` lo listaba mal como OBLIGATORIA: se corrige
   aquí (ver §4). No cuenta como 12ª capa.

**Trazabilidad:** SETUP_SPEC = canónico (11). Matriz = vista consolidada (9) con mapeo arriba.
Auditor = usa las 11 y reporta causalidad como propiedad transversal.

---

## 2. Taxonomía definitiva y clasificación

| # | Capa SETUP_SPEC (canónica) | Clase            | Debe PASS para COMPLETE |
|---|-----------------------------|------------------|-------------------------|
| 1 | Contexto                    | OBLIGATORIA      | Sí                      |
| 2 | Estructura (previa + cambio)| OBLIGATORIA      | Sí                      |
| 3 | Liquidez (objetivo + tomada)| OBLIGATORIA      | Sí                      |
| 4 | Sweep (evento)              | OBLIGATORIA      | Sí                      |
| 5 | Displacement                | OBLIGATORIA      | Sí                      |
| 6 | Confirmación estructural (BOS/CHOCH) | OBLIGATORIA | Sí               |
| 7 | POI (FVG/OB anclado)        | OBLIGATORIA      | Sí                      |
| 8 | Retorno al POI              | OBLIGATORIA      | Sí                      |
| 9 | Confirmación LTF (M5/M1)    | CONDICIONAL      | PASS o N/A (según tipo) |
| 10| Macro / noticias            | CONTEXTO EXTERNO | Nunca PASS/FAIL setup   |
| 11| Estado (Válido/Invalidado)  | VERDICTO         | Debe ser VÁLIDO         |

(Linaje causal = propiedad transversal sobre capas 3→4→5→6→7→8→9, no fila propia.)

---

## 3. Contrato de entrada / salida

**Entrada (lo que el auditor CONSUME, ya producido por el motor — no lo re-ejecuta):**
- `Expediente.history` — traza vela por vela: `(SWEEP,i),(DISPLACE,i),(BOS,i),(ENTRY,i)`
  (`engine/sequence.py:127-128`, `_build_expediente`/`_advance_expediente`).
- Metadatos de la señal (`engine/sequence.py:618-634`): `sweep_at`, `displace_at`, `bos_at`,
  `entry_at`, `bos_level`, `poi_present`, `htf_aligned`, `htf_reason`.
- Contexto HTF closed-only (`engine/plan.py` `build_context_stack`/`top_down_allows_trade`).
- (Futuro, GAP-1) fuente de calendario macro por timestamp — HOY ausente.

**Salida (por setup):**
```
SETUP-<id>
FORMATION: COMPLETE | INCOMPLETE | INVALIDATED
<capa>      PASS | FAIL | UNKNOWN   [+ evidencia: timestamp + primitiva]
... (11 filas)
CAUSALITY:  COMPLETE | BROKEN       [si BROKEN: dónde se rompió la cadena]
MACRO:      INFO | WARNING | UNKNOWN   [GAP-1: hoy UNKNOWN]
If FAIL:    FALLÓ EN: <capa> — <razón con evidencia>
```

---

## 4. Definición de CAUSALIDAD (linaje)

No es coincidencia temporal. Es ORDEN + DEPENDENCIA a lo largo de las capas de evento:

```
liquidez tomada → sweep de esa liquidez → displacement REAL posterior →
BOS/CHOCH TRAS el displacement → POI nacido de ese BOS → retorno al POI →
confirmación LTF posterior
```

Criterio auditor:
- `sweep_at` debe venir Acompañado de toma de liquidez objetivo (no falso sweep).
- `displace_at > sweep_at` Y es impulso real en dirección setup.
- `bos_at > displace_at` Y en dirección correcta (a-favor o contratendencia).
- `poi_present` anclado al BOS/CHOCH del TF padre ya cerrado (`poi_anchor.py`).
- `entry_at` ocurre por `_touches_zone` (retorno al cuadro), no por BOS instantáneo.
- Si el orden se cumple pero la DEPENDENCIA no (p.ej. BOS en vela sin displacement previo
  válido) → `CAUSALITY: BROKEN` con localización.

---

## 5. Criterios PASS / FAIL / UNKNOWN por capa

| Capa | PASS (evidencia observable + timestamp) | FAIL | UNKNOWN |
|------|------------------------------------------|------|---------|
| Contexto | sesgo D1/H4/H1 sin contradicción (`htf_reason` sin veto) | sesgo RANGING o contradictorio | contexto no disponible |
| Estructura | estructura previa + cambio (CHOCH/BOS/MSS) registrados | sin evento de cambio | — |
| Liquidez | `target_liquidity` BSL/SSL identificado Y tomado (`nearest_liquidity_target` + sweep opuesto) | liquidez objetivo no tomada | nivel no computable |
| Sweep | `sweep_at` presente; tomó la liquidez objetivo | sweep sin toma de liquidez / falso | — |
| Displacement | `displace_at > sweep_at`, impulso real en dir | displacement ausente o previo al sweep | magnitud no registrada |
| Confirm. estructural | `bos_at > displace_at`, dir correcta | BOS sin displacement previo | — |
| POI | `poi_present` anclado al BOS padre cerrado | POI no anclado / suelto | — |
| Retorno | `entry_at` por `_touches_zone` al cuadro | entrada sin retorno al POI | — |
| Confirm. LTF | (CONDICIONAL) confirmación M5/M1 POST-retorno | confirmación exigida pero ausente | GAP-2 (motor 1 LTF) → N/A |
| Macro | (CONTEXTO EXTERNO) INFO/WARNING/UNKNOWN, nunca PASS/FAIL | — | GAP-1 → UNKNOWN |
| Estado | VÁLIDO (no invalidado) | INVALIDADO por `engine/invalidation` | — |

---

## 6. Definición de SETUP COMPLETE / INCOMPLETE / INVALIDATED

- **COMPLETE**: todas las OBLIGATORIAS (1-8, 11) = PASS con `CAUSALITY: COMPLETE`; CONDICIONAL
  (9) = PASS o N/A; Macro (10) = INFO/WARNING/UNKNOWN.
- **INCOMPLETE**: alguna OBLIGATORIA = FAIL → `FORMATION: INCOMPLETE` + `FALLÓ EN: <capa>`.
  (Un "10 PASS / 1 FAIL" NO es COMPLETE; el auditor reporta el fallo por capa.)
- **INVALIDATED**: `engine/invalidation.check_invalidation` marcó el expediente (aunque las capas
  estructurales PASARAN) → el setup nació pero fue invalidado en vida. Distinto de INCOMPLETE
  (nunca terminó de formarse).

---

## 7. Tratamiento de NOTICIAS / MACRO (GAP-1)

- Macro es **CONTEXTO EXTERNO**, no indicador. Produce `INFO` / `WARNING` / `UNKNOWN`. **Nunca**
  PASS/FAIL del setup ni filtro BUY/SELL.
- HOY: capa 10 = **UNKNOWN / PENDING** (GAP-1). El repo confunde `macro_direction` —que es
  tendencia HTF (Contexto, capa 1)— con noticias; `noticias_widget.py` está hardcodeado solo
  para UI. **NO se implementa `engine/macro_calendar` en esta fase** para no contaminar la
  lectura con reglas prematuras. Se registra como contexto, no como veto.
- Una noticia de alto impacto cercana = `WARNING` (el setup puede ser COMPLETE pero con evento
  macro en ventana); solo invalidaría si una regla de invalidación POR NOTICIA está configurada
  (hipótesis a testear APARTE, no axioma). Hasta GAP-1, celda = UNKNOWN.

---

## 8. Plan de muestra piloto y criterio de avance

- **FASE A — piloto 5–10 setups**: objetivo NO estadístico. Descubrir si el auditor PUEDE
  reconstruirlos y qué fallos de capa aparecen. Esperado: mezcla (p.ej. setup perfecto, POI
  dudoso, sweep correcto pero liquidez incorrecta, BOS correcto pero linaje roto). Esto enseña
  CÓMO debe funcionar el auditor.
- **FASE B — 50 setups**: tras estabilizar el protocolo y el reporte por capa en Fase A.
- **FASE C — 100 setups**: meta de auditoría (umbral de muestra para inferencia cualitativa de
  `R_recon` localizable por capa).
- **Criterio de avance A→B**: el auditor reconstruye los 5–10 pilotos SIN excepciones no
  contempladas en el protocolo (el formato de salida es estable y cada FAIL tiene evidencia +
  capa). No se exige tasa de PASS; se exige que el veredicto sea reproducible y trazable.
- **Criterio de avance B→C**: el reporte por capa es consistente entre dos corredores
  independientes (acuerdo de auditoría) sobre los 50.

---

## 9. Regla de NO-MODIFICACIÓN durante el experimento

Al encontrar un fallo del motor (p.ej. `FAIL — POI`), **NO se corrige `poi_anchor.py` en caliente**.
Se sigue: `OBSERVACIÓN → EVIDENCIA → DIAGNÓSTICO → HIPÓTESIS DE DEFECTO → experimento →
recién entonces modificación`. Corregir durante la auditoría destruiría la capacidad de medir
cómo funcionaba el motor original. El fallo se registra como HALLAZGO con evidencia y capa.

---

## 10. Qué NO es el auditor (límites de esta fase)

- NO mide WR / PF / expectancy / resultados económicos.
- NO modifica `engine/` (regla 11 del Director).
- NO ejecuta backtest de rendimiento (regla 12).
- NO es un segundo motor de trading; consume la evidencia ya producida.
- NO fija `R_recon`, 0.90 ni umbral de rendimiento (regla 7).
- NO convierte noticias en filtro (regla 6).

---

## 11. Checklist de entregables (los 12 del Director)

- [x] Protocolo del SETUP AUDITOR (este doc)
- [x] Contrato de entrada/salida (§3)
- [x] Taxonomía definitiva de capas (§1, §2 — canónica 11, resuelve 11≠9)
- [x] Criterios PASS/FAIL/UNKNOWN (§5)
- [x] Definición de causalidad (§4)
- [x] Definición de SETUP COMPLETE (§6)
- [x] Tratamiento de noticias (§7)
- [x] Plan de muestra piloto 5–10 → 50 → 100 (§8)
- [x] Criterio de avance (§8)
- [x] Juez forense, no segundo motor (§0, §10)
- [x] No fix during audit (§9)
- [x] Cero `engine/`, cero backtest rendimiento (§10)

---

*Diseño del SETUP AUDITOR para HYP-002. Sin EXP ejecutable, sin Python, sin ejecución. Resuelve
la inconsistencia 11↔9 y fija la taxonomía canónica. Complementa SETUP_SPEC.md,
SETUP_FORMATION_EVIDENCE.md y SETUP_AUDITOR_DESIGN.md.*
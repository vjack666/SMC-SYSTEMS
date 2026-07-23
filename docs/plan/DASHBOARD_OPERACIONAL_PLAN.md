# DASHBOARD OPERACIONAL — Plan Maestro

**Única fuente de verdad del Dashboard (`app_observador`).**

Última actualización: 2026-07-22

---

## Contexto y alcance

- El Dashboard Operacional es un OBSERVADOR del mercado en tiempo real para la toma de
  decisiones. NO es un bot. NO opera solo.
- **El backtest queda FUERA de alcance.** Son dos sistemas separados:
  - Backtest → laboratorio de investigación y entrenamiento.
  - Dashboard → observador del mercado en vivo.
- No mezclar responsabilidades.

## Filosofía (Ruben)

No nuevas funcionalidades porque sí. Cada mejora debe responder a una pregunta operacional:
- ¿Qué está haciendo el mercado ahora?
- ¿Cuál es el sesgo institucional?
- ¿Dónde está la liquidez?
- ¿Cuál es el mejor setup disponible?
- ¿Qué riesgo tengo si entro?
- ¿Debo esperar?
- ¿Hay conflicto entre temporalidades?
- ¿Estoy operando a favor del Smart Money?

## Regla más importante — NO inventar información

Si el motor todavía no calcula un dato → mostrar exactamente: **EN CONSTRUCCIÓN**.
Nunca valores ficticios, nunca estimaciones, nunca placeholders engañosos.

## Reutilización obligatoria

Antes de código nuevo: auditar el repo, buscar si el dato ya existe, reutilizar. Solo
escribir código nuevo si realmente no existe.

## Estado de fases

| Fase | Nombre | Estado | Fecha |
|------|--------|--------|------|
| 0 | Revivir motor (re-wire `rutina_eurusd`) | ✅ 100% FINALIZADO | 2026-07-22 |
| 0.1 | Wyckoff completo (`fase_wyckoff_m15`) | ✅ 100% FINALIZADO | 2026-07-22 |
| **C** | **Honestidad del veredicto (quitar forceo de votos en `engine.py`)** | ✅ **100% FINALIZADO (2026-07-23)** — cerrada vía SDD 5C (`docs/plan/SDD_CIERRE_SETUP.md` §5C/§9): `run_cycle` resiliente (canonical acotado por timeout + cache atómico, ya no se cuelga ni deja el dashboard mudo). Tests 9 passed (`tests/test_run_cycle_resilient.py`). Evidencia viva con parquet EURUSD real: `docs/evidence/fase4_last_cycle_probe.json`. | 2026-07-23 |
| **NÚCLEO** | **Rediseño del motor: Pipeline jerárquico (matar `votes`, `context_alignment`)** | ✅ **100% FINALIZADO (código + test GREEN + evidencia real)** | 2026-07-22 |
| A | Panel MARKET STATE always-on (síntesis del pipeline) | ✅ 100% IMPLEMENTADO (2026-07-22) — MarketStateWidget lee context_alignment + semáforo + killzone; validado headless (instancia + update_state consume macro/intraday/stages/confidence). Render gráfico pendiente en máquina con display. | 2026-07-22 |
| B | Widget Wyckoff completo (fase + eventos + confianza) | ✅ 100% IMPLEMENTADO (2026-07-22) — lbl_wyk muestra Eventos (lista del motor, no inventada) + confianza. Validado end-to-end con tab visible (no crashea). 🔧 DEUDA CERRADA: extract_levels movido al tope de update_state (antes crasheaba UnboundLocalError si la pestaña era visible). | 2026-07-22 |
| D | `canonical_rr` como advertencia visual en plan_strip | ✅ 100% IMPLEMENTADO (2026-07-22) — umbral Stellar (rr<2.0 = riesgo, antes solo <1.0) + borde rojo RED_SOFT + hint "⚠ RR < 1:2". Reusa theme existente. py_compile OK. | 2026-07-22 |
| E | BOS level numérico + sweep destacado en resumen | ✅ 100% IMPLEMENTADO (2026-07-22) — resumen_estructura pinta bos_level numérico (guarda !=0.0/NaN) + sweep HTML color (rojo BSL / verde SSL). Validado con datos sintéticos realistas (bos_level visible + HTML sweep + intacto sin nivel). | 2026-07-22 |
| **H1** | **Sub-fase de NÚCLEO: H1 como Stage 3 (IntradayEngine) del pipeline** | ✅ **100% FINALIZADO (dentro de NÚCLEO)** | 2026-07-22 |
| **M5** | **Two-pass TriggerEngine real (Stage 5): Trigger reporta ambos lados, VerdictBuilder elige** | ✅ **100% IMPLEMENTADO (2026-07-22)** — `trigger_engine` ya NO recibe bias: devuelve `long`/`short` con checks sweep/bos/fvg (flujo Sweep→Displacement→FVG). `run_pipeline` elige el lado según sesgo derivado (no opera en contra del macro). `stages["M5_TRIGGER"]` ahora muestra checks REALES (no stub). `engine.py` carga M5 aparte (fuera de TIMEFRAMES); sin M5 → PENDING honesto. Tests: 6 passed (4 previos + 2 Two-pass). ⚠ Evidencia en vivo con parquet M5 real PENDIENTE: `analyze_timeframe(M5)` tarda >80s en este entorno (deuda run_cycle lenta) → validar en máquina con MT5/display. | 2026-07-22 |
| **SMT** | **Smart Money Technique (Stage 4b): EURUSD vs GBPUSD en H1** | ✅ **100% IMPLEMENTADO + VALIDADO UI (2026-07-22)** — `smt_engine(a,b)` NO recibe bias: reporta divergencia de AMBOS lados (long/short) con `diverge` + `note`. La señal vive en el DESENCUENTRO: si EURUSD barre y GBPUSD NO → trampa (el que se queda atrás delata). `run_pipeline` usa SMT como FILTRO: diverge en contra del sesgo → −10 confianza; alineado → +5. `context_alignment["smt"]` = DIVERGE/ALIGNED/PENDING + `stages["SMT"]`. `engine.py` carga GBPUSD H1 aparte (`SYMBOL_PAIR="GBPUSD"` en config); sin segundo par → PENDING honesto. MarketStateWidget pinta SMT (rojo DIVERGE / verde ALINEADO) — VALIDADO headless: ambos casos (DIVERGE rojo + ALIGNED verde) renderizan correcto. Tests: 9 passed (6 previos + 2 SMT + 1 PD). ⚠ Evidencia SMT con parquet GBPUSD H1 REAL PENDIENTE: `analyze_timeframe` tarda >80s en este entorno → validar en máquina con MT5. | 2026-07-22 |
| **PREMIUM/DISCOUNT** | **Contextualizar POI en el dealing range del D1 (enriquece Stage 4 POI)** | ✅ **100% IMPLEMENTADO + VALIDADO UI (2026-07-22)** — `poi_engine(m15, d1)` calcula Premium/Discount del POI vs rango D1 (`zone_high`/`zone_low` reusados, cero carga nueva). POI en DISCOUNT + sesgo LONG → bonus de alineación (+5). `context_alignment["premium_discount"]` = DISCOUNT/PREMIUM/PENDING. MarketStateWidget pinta PREMIUM/DISCOUNT (verde DISCOUNT / amarillo PREMIUM) — VALIDADO headless: ambos casos renderizan. Sin D1 → PENDING honesto. Cubierto por test `test_poi_premium_discount_against_d1_range` (GREEN en suite de 9). | 2026-07-22 |

---

## FASE NÚCLEO — Motor de decisión por Pipeline (jerarquía, no votación)

### Por qué existe esta fase

`build_verdict(d1, h4, m15)` está HARDCODEADO a 3 TF y usa **votación** (cuenta
LONG/SHORT por TF). Eso NO representa cómo opera ICT ni cómo opera Ruben: cada
temporalidad tiene UNA responsabilidad en una jerarquía, no un voto. Agregar H1 (o M5,
o SMT, o Premium/Discount) sobre ese motor significía romper la firma cada vez.

Decisión de diseño (Ruben, 2026-07-22): **matar el concepto de `votes`** y convertir
`build_verdict` en un **Pipeline de decisión por etapas**, donde cada TF cumple una
responsabilidad y el dashboard solo REFLEJA el estado de cada etapa.

### Fase 1 — Auditoría (COMPLETA)

- `rutina_eurusd.build_verdict` (líns ~137-197) itera tupla fija
  `((d1,"D1"),(h4,"H4"),(m15,"M15"))` y suma `votes` por tendencia + confirmaciones
  M15 (BOS/sweep). HARDCODEADO a 3 TF.
- `engine.run_cycle` carga D1/H4/M15 vía `config.TIMEFRAMES` y llama `build_verdict(d1,h4,m15)`.
- `config.TIMEFRAMES = ["D1","H4","M15"]` (H1 ausente).
- Consumidores de `veredicto.votes` (6 módulos, SOLO lectura): `main_window`,
  `resumen_widget` (línea 264 imprime `votos L:x/S:y`), `lab_setup_widget`,
  `scanner_report`, `position_sizer_bridge`, `engine` log. El botón LIMIT usa
  `canonical`, NO `votes`.
- UI ya tiene estructura mental por etapas (`lab_setup_widget`: grupos 1) Estructura,
  2) Wyckoff, 3) Lógica del setup, 4) Veredicto honesto). El pipeline ENCaja con esa UI.

### Fase 2 — Diseño (PENDIENTE OK de Fase 3)

**Pipeline por etapas (cada Stage = función pura `stage(tf_data) -> dict`):**

```
Stage 1  BiasEngine      (D1)   → macro:  LONG / SHORT / NEUTRAL
Stage 2  ContextEngine   (H4)   → confirma bias macro
Stage 3  IntradayEngine  (H1)   → contexto operativo del día   [SUB-FASE H1]
Stage 4  POIEngine       (M15)  → zona OTE/OB/FVG + invalidación
Stage 5  TriggerEngine   (M5)   → [EN CONSTRUCCIÓN] Two-pass futuro
Stage 6  RiskEngine              → riesgo día / R:R
Stage 7  ExecutionPlan           → plan entry/SL/TP + handoff CSV
```

`VerdictBuilder` junta los stages → `context_alignment`. Agregar SMT / Premium-Discount
/ Judas / Silver Bullet / Turtle Soup / AMD / News = INSERTAR un Stage entre POI y Trigger
sin tocar los existentes.

**Salida `context_alignment` (reemplaza `votes`):**
```json
{
  "macro": "LONG",
  "intraday": "LONG",
  "poi": "VALID",
  "trigger": "PENDING",
  "confidence": 84,
  "stages": {
    "D1": "✔", "H4": "✔", "H1": "✔",
    "M15_POI": "✔ discount/OB/FVG",
    "M5_TRIGGER": "□ sweep / □ bos / □ fvg"
  }
}
```

**Compatibilidad gradual (no romper UI en Fase 3):**
- `result["veredicto"]` emite `context_alignment` + `bias` + `votes` DERIVADO (calculado
  desde la alineación, marcado LEGADO). Así `resumen_widget` sigue funcionando, pero
  `votes` ya NO es fuente de verdad. En fase posterior la UI migra a `context_alignment`
  y se elimina `votes`.
- H1 entra como Stage 3 (IntradayEngine) del pipeline. No es "un TF más que vota".

**Scope de Fase 3 (lo que se implementa con OK):**
1. `app_observador/core/pipeline.py`: Stages 1-4 + VerdictBuilder. Stage 5 (M5) = stub
   que emite `trigger: PENDING` / `EN CONSTRUCCIÓN`.
2. `engine.run_cycle` usa el pipeline en vez de `build_verdict`.
3. H1 se carga (`_load(SYMBOL,"H1")` + `analyze_timeframe`) y alimenta Stage 3.
4. `result["veredicto"]` = `context_alignment` + `bias` + `votes` (derivado, legacy).
5. `config.TIMEFRAMES = ["D1","H4","H1","M15"]`; `TIMEFRAMES_MAPA` incluye H1.
6. Tests: `test_rutina_eurusd_wiring.py` refactorizado a pipeline; GREEN.
7. Documentación al día.

**NO se toca en Fase 3:** la UI (sigue leyendo `votes`/estructura legacy), SMT/Premium-
Discount/etc (etapas futuras), M5 real (solo stub), backtest.

**Definición de terminado:** código finalizado · test GREEN (pipeline con H1) · evidencia
de lectura en vivo con H1 en `context_alignment` · documentación al día · sin tareas colgando.

### Fase 3 — Implementación (COMPLETA)

- `app_observador/core/pipeline.py` NUEVO: `bias_engine`/`context_engine`/`intraday_engine`/
  `poi_engine`/`trigger_engine` (stub M5) + `run_pipeline` (VerdictBuilder). Funciones PURAS.
- `engine.run_cycle` importa `pipeline as decision_pipeline` y reemplaza
  `build_verdict(d1,h4,m15)` por `run_pipeline(d1,h4,h1,m15)`. Log de veredicto ahora usa
  `context_alignment`. `tfs_data` anotado `dict[str,tuple]` (lint limpio).
- `config.TIMEFRAMES = ["D1","H4","H1","M15"]`; `TIMEFRAMES_MAPA` incluye H1.
- `rutina_eurusd.build_verdict` SE MANTIENE (legacy) para no romper el test existente; el
  pipeline es la fuente de verdad nueva. `votes` en pipeline es LEGADO derivado.
- `votes` LEGADO en pipeline = conteo de capas alineadas (macro/ctx/intraday), NO democracia.

### Fase 4 — Validación (COMPLETA, datos reales)

EURUSD 22-jul (parquet fresco), timeout 55s, SIN MT5:
```
bias        : SHORT
macro       : SHORT | intraday: SHORT | poi: VALID | trigger: PENDING
confidence  : 65%
stages      : D1 ✔ | H4 □ (no confirma macro) | H1 ✔ | M15_POI ✔ | M5_TRIGGER □
votes LEGADO: {LONG: 1, SHORT: 2}
```
Prueba del paradigma: H4 BULLISH no "vota", se marca `□` y baja confianza a 65%.
El pipeline REFLEJA jerarquía, no cuenta cabezas. H1 participa como Stage 3.

### Fase 5 — Demostración (COMPLETA)

Evidencia viva arriba (datos reales). `test_pipeline_emits_context_alignment_not_democracy`
GREEN confirma salida `context_alignment` + `votes` legacy + `M5_TRIGGER` en stages.

### Fase 6 — Cierre

✅ FINALIZADA. Código + test (4 passed) + evidencia real + documentación al día.
DEUDA RELACIONADA (no bloquea): `votes` legacy sigue en salida hasta que la UI migre a
`context_alignment`. `run_cycle` completo sigue lento/cuelga en canonical R7 (ver Fase C) —
pero el pipeline en sí está validado de forma aislada con datos reales.

---

## FASE C — Honestidad del veredicto

### Fase 1 — Auditoría (COMPLETA)

**Objetivo:** el veredicto que ve el operador debe reflejar el consenso REAL de las
temporalidades, no uno inflado por el plan canónico R7.

**Dónde nace el dato (votos honestos):**
- `scripts/rutina_eurusd.py` → `build_verdict()` (líneas ~140-169): suma `votes["LONG"] += 1`
  / `votes["SHORT"] += 1` por cada TF (D1/H4/M15) según tendencia y CHOCH. Son votos REALES.
- Ejemplo real 2026-07-22: D1 bajista + M15 bajista = S:2; H4 alcista = L:1 → `L:1 / S:2`.

**Dónde se transforma mal (fabricación de consenso):**
- `app_observador/core/engine.py:202-207` (dentro de `run_cycle`, paso 6 plan canónico R7):
  ```python
  if plan["side"] == "LONG":
      verd["votes"] = {"LONG": max(int(votos_LONG), 2), "SHORT": int(votos_SHORT)}
  else:
      verd["votes"] = {"LONG": int(votos_LONG), "SHORT": max(int(votos_SHORT), 2)}
  ```
  Esto FUERZA el voto del lado del plan canónico a 2, aunque el análisis real dijera 1.
  Crea un falso "empate 2:2" o "falso consenso fuerte" que el operador no pidió.

**Dónde se muestra (y se miente):**
- `app_observador/ui/main_window.py:_update_principal` pasa `verd.get("votes")` al
  `resumen_widget`, que pinta "L:x / S:y". Hoy pinta L:2/S:2 cuando el real era L:1/S:2.

**Dónde se pierde:**
- La distinción entre "votos del análisis top-down" y "señal del plan canónico R7".
- El plan canónico YA tiene su propio chip en `plan_strip` (entry/sl/tp/rr). No necesita
  colarse en el veredicto.

**Único lugar que fabrica votos:** search confirma que solo `engine.py:203,207` usan
`max(...,2)`; `build_verdict` usa `+=1` honesto. Es un punto único de falla.

### Fase 2 — Diseño (PENDIENTE OK)

- **Qué se conecta:** se ELIMINA el bloque `engine.py:202-207` que reescribe `verd["votes"]`.
- **Por qué:** el plan canónico R7 es UNA señal más, no autoridad que pisa el consenso de
  TFs. Forzar votos viola la regla "no inventar información".
- **Impacto:** el resumen mostrará votos reales (L:1/S:2). El plan canónico sigue visible
  en su chip propio (plan_strip) como información separada y honesta.
- **Reutilización:** cero código nuevo. Solo se borra lógica que distorsionaba.
- **Riesgo:** bajo. El `result["veredicto"]["canonical_*"]` sigue poblado para plan_strip;
  solo deja de pisar `votes`. Hay que verificar que `plan_strip` no dependa de `votes`
  inflados para habilitar el botón LIMIT (usa `canonical`, no `votes`).

### Fase 3 — Implementación (COMPLETA)

Cambio mínimo: borrado `engine.py:202-207` (bloque que reescribía `verd["votes"]` con
`max(...,2)` según el side del plan canónico). El resto del paso 6 se conserva:
`canonical_entry/side/rr/engine` se adjuntan a `verd` y `result["canonical"]` queda poblado
para el chip de `plan_strip`. Lint OK.

### Fase 4 — Validación (PARCIAL, datos reales)

**Demostrado con datos reales (2026-07-22, EURUSD en vivo):**
- `rutina_eurusd.build_verdict(d1,h4,m15)` → `votes = {'LONG': 2, 'SHORT': 1}`, BIAS LONG.
  Son los votos HONESTOS del consenso top-down.
- El parche eliminó la ÚNICA línea que reescribía `votes` (`engine.py:202-207`). Confirmado
  por diff + lint + `grep "max(int"` → "SIN forceo de votes (limpio)".
- Auditoría de consumidores: `veredicto.votes` se lee en 6 módulos
  (`main_window`, `resumen_widget`, `lab_setup_widget`, `scanner_report`,
  `position_sizer_bridge`, `engine` log). TODOS solo LECTURA. NINGUNO depende de que
  esté forzado a 2. El botón LIMIT usa `canonical`, no `votes`.

**EN CONSTRUCCIÓN (no demostrado aún — limitación de entorno, NO es MT5):**
- Evidencia de `last_cycle.json` vivo del dashboard con engine parcheado: NO generable aquí.
  IMPORTANTE (corrección 2026-07-22): la causa NO es MT5. `rutina_eurusd._load` lee de
  `data/raw/*.parquet` (`pd.read_parquet`), no de MT5 en vivo; los parquet EURUSD D1/H4/H1/
  M5/M15 ESTÁN y están frescos (22-jul). `mt5_status.py` YA tiene abstracción
  (`conectado=False` si MT5 no está). MT5 está cubierto.
- Causa REAL del bloqueo: (a) `run_cycle` es LENTO — P1 (cargar+analizar D1/H4/M15 +
  build_verdict) tardó 24.1s con parquet fresco; (b) el paso 6 (`_canonical_plan` / sequence
  R7) se COLGA indefinidamente en este entorno (timeout 80s → rc=124, SIN excepción, por eso
  el proceso background muere silencioso). El cache se movió ANTES del paso 6, pero P1+P2+P3
  dentro de `run_cycle` supera los 40s de espera y el proceso no alcanza a escribir en la
  prueba. DEUDA REAL: lentitud de carga parquet + cuelgue del sequence R7, NO MT5.
- Ruta de cierre honesta: correr `run_cycle` en máquina con recursos / MT5 real → el cache
  se escribe con `veredicto.votes` honestos y `canonical` poblado o "EN CONSTRUCCIÓN".

### Fase 5 — Demostración (PARCIAL)
- Evidencia viva parte 1: `VOTOS REALES build_verdict: {'LONG': 2, 'SHORT': 1}` (stdout real).
- Evidencia parte 2 (cache vivo del dashboard): PENDIENTE de entorno (ver Fase 4).

### Fase 6 — Cierre
✅ **100% FINALIZADA (2026-07-23).** La deuda "run_cycle frágil / cache mudo" se cerró
con el ticket **5C** del SDD (`docs/plan/SDD_CIERRE_SETUP.md` §5C): el paso 6
(`_canonical_plan`) quedó acotado por timeout (`_canonical_plan_bounded` +
`CANONICAL_TIMEOUT_S`) y el cache se escribe SIEMPRE de forma atómica
(`_write_cache_atomic`, tmp + `os.replace`) ANTES del canonical. `canonical` tiene
3 estados honestos: `"EN CONSTRUCCIÓN"` / `None` / dict. Tests: 9 passed
(`tests/test_run_cycle_resilient.py`). Evidencia viva con parquet EURUSD real (SIN
MT5): `docs/evidence/fase4_last_cycle_probe.json` — cache escrito y no mudo.
Deuda restante (no bloquea): lentitud de `analyze_timeframe` (M5/SMT) → ticket 5D.

---

## Definición de terminado (Ruben)

Una tarea SOLO está terminada cuando:
✓ el motor produce el dato · ✓ la UI lo consume · ✓ el usuario lo ve ·
✓ existe evidencia de lectura en vivo · ✓ está documentado · ✓ quedó en el roadmap.

# SETUP_FORMATION_EVIDENCE.md — Matriz de evidencia de formación del setup (auditoría, solo lectura)

> **Auditoría (2026-08-10). Documentación y diseño ÚNICAMENTE. CERO Python modificado.**
> Orden del Director: auditar HYP-002 + SETUP_SPEC contra el código actual del motor,
> determinar qué componentes del setup completo EXISTEN, cuáles están INCOMPLETOS y cuáles
> están MAL CONECTADOS, y entregar una matriz de evidencia. Complementa `SETUP_SPEC.md`.

## Método

Se leyó el motor (`engine/`) y se trazó cada capa de `SETUP_SPEC.md` a su primitiva real.
Citas en `archivo:línea`. No se ejecutó código; es mapeo estático de la tesis (lo que exige
SETUP_SPEC) contra el código (lo que hace el motor).

---

## Matriz por capa

| # | Capa SETUP_SPEC            | ¿Existe en el motor? | Evidencia (`file:line`)                                                                 | Veredicto        |
|---|----------------------------|----------------------|------------------------------------------------------------------------------------------|------------------|
| 1 | Contexto (HTF, dir, régimen) | SÍ                  | `engine/plan.py:324` `build_context_stack` + `:375` `top_down_allows_trade`; 3 capas D1→H4→H1 (AGENTS.md: cerradas); `engine/bias/narrative.py:88-94` gate relajado `non_neutral>=2` | PRESENTE         |
| 2 | Liquidez (extremo, objetivo, sweep) | SÍ        | `engine/liquidity_levels.py:42` `detect_liquidity_htf` (BSL/SSL anclado a sesgo HTF), `:121` `nearest_liquidity_target`; `engine/sequence.py:157` `_has_sweep` (sweep opuesto a dirección) | PRESENTE         |
| 3 | Reacción / Displacement    | SÍ                  | `engine/sequence.py:170` `_has_displacement` (acepta LTF o HTF)                          | PRESENTE         |
| 4 | Estructura (BOS/CHOCH/MSS, relación con sweep) | SÍ | `engine/sequence.py:205` `_has_bos`, `:189` `_has_choch`; **orden causal codificado** en máquina de fases `IDLE→SWEEP→DISPLACE→BOS→ENTRY` (`:525-637`) | PRESENTE + LINAJE CAUSAL CODIFICADO |
| 5 | POI (FVG/OB, origen del displacement) | SÍ (anclado) | `engine/sequence.py:241` `_latest_fvg_zone`, `:254` `_latest_ob_zone`; `engine/poi_anchor.py:86` `make_htf_poi_fn` ancla POI a BOS/CHOCH del TF padre YA CERRADO (anti look-ahead por timestamp `:120`) | PRESENTE + ANCLADO |
| 6 | Retorno al POI            | SÍ                  | `engine/sequence.py:271` `_touches_zone` + `:607` ENTRY cuando retorna al cuadro          | PRESENTE         |
| 7 | Confirmación LTF (M5/M1 trigger) | PARCIAL/GAP   | `run_sequence` corre en UN LTF (default `M15`, `sequence.py:641`). No hay bifurcación M5→M1 fina dentro del motor. Coincide con nota AGENTS.md: "falta exec fino M5/M1" | INCOMPLETO       |
| 8 | Macro (noticias, proximidad, impacto) | AUSENTE (en motor) | "macro" en repo = `macro_direction`/`macro_trend` = **tendencia HTF** (contexto piso 1: `engine/plan.py:49`, `trend_context.py:210`), NO noticias. `app_observador/ui/noticias_widget.py:108-124` tiene noticias **hardcodeadas** solo para UI, no alimentan el motor de setup | AUSENTE en motor |
| 9 | Estado (FORMÁNDOSE/COMPLETO/INVALIDADO/NO-SETUP) | SÍ | `SequenceState.phase` (`sequence.py:59,89`) = FORMÁNDOSE; `engine/invalidation.py` `build_rules`+`check_invalidation` (`:539,:324-337`) = INVALIDADO; `Expediente` (`engine/expediente.py`) cierra `outcome="ENTRY"` = COMPLETO; reset sin ENTRY = NO-SETUP | PRESENTE         |

---

## Hallazgos transversales (lo que el motor SÍ garantiza)

- **Anti look-ahead (sin mirar el futuro):** el motor consume `MarketObject[]` de velas
  cerradas (`sequence.py:133` `_candle_objects`); anclaje POI por timestamp cross-TF
  `e.time <= ltf_t` (`poi_anchor.py:120`); contexto HTF *closed-only*
  (`plan.py` + AGENTS.md). Cumple la exigencia "sin información futura" de HYP-002.
- **Linaje causal ya codificado (no solo coincidencia):** la máquina de fases
  `IDLE→SWEEP→DISPLACE→BOS→ENTRY` (`sequence.py:525-637`) es la PRUEBA de causalidad — el
  BOS solo cuenta si viene TRAS displacement que vino TRAS sweep. Esto responde exactamente a
  la distinción del Director "evento ≠ causalidad": el motor ya la implementa como secuencia,
  no como lista de banderas.
- **Expediente = trazabilidad vela por vela:** `SequenceState.history` / `Expediente.advance`
  registran `(SWEEP,i),(DISPLACE,i),(BOS,i),(ENTRY,i)` — es la evidencia "muéstrame por qué
  este setup existe" que pide el Director.

---

## GAPs para el experimento de lectura (SETUP AUDITOR)

- **GAP-1 (CRÍTICO — capa 8 MACRO/noticias):** no hay módulo de calendario económico conectado
  al motor. La "macro" existente es tendencia HTF (contexto), no noticias. `noticias_widget.py`
  está hardcodeado para UI (semana fija). Para HYP-002 se requiere: (a) un `engine/macro_calendar`
  que anote proximidad/impacto por timestamp; (b) que el SETUP AUDITOR lo registre como
  `WARNING`/`INFO` (nunca PASS/FAIL automático del setup). HOY: capa macro AUSENTE en lectura.
- **GAP-2 (MEDIO — capa 7 confirmación LTF):** el motor corre en un solo LTF; no hay confirmación
  fina M5→M1. Requerido por SETUP_SPEC para "trigger LTF". No es bloqueante para auditar las
  capas 1-6/8-9, pero sí para declarar setup "COMPLETO" con confirmación fina.
- **GAP-3 (MENOR — capa 5 POI como fallo de capa):** `poi_present` es **bonus, no gate**
  (`require_pd=False`, `sequence.py:479`; anotado en señal `:628`). El motor SABE si el POI está
  anclado, pero no falla si falta. Para el SETUP AUDITOR eso es correcto (se reporta), pero el
  SETUP_SPEC exige "POI origen = BOS". El auditor debe poder emitir `FALLÓ EN: POI (no anclado)`
  usando `poi_present` ya expuesto — el dato existe, solo falta el reporte por capa.

---

## Conclusión de la auditoría (sin ejecutar)

El motor ya implementa **8 de 9 capas** del SETUP_SPEC, incluyendo el linaje causal codificado
y el anti look-ahead. El GAP real que bloquea la "lectura completa" de HYP-002 es **GAP-1
(macro/noticias no conectado al motor)** — exactamente la capa que el Director y la regla rectora
piden incorporar como contexto externo ANTES del rendimiento. GAP-2 (confirmación LTF fina) y
GAP-3 (POI como fallo de capa en el reporte) son menores.

Esto define el **primer experimento verdaderamente importante** del laboratorio (Director):
un SETUP AUDITOR que, dada una muestra de setups emitidos, reconstruya la cadena causal vela por
vela usando `Expediente.history`, marque PASS/FAIL por capa (1-6, 9 ya disponibles; 7 parcial;
8 ausente) y localice el fallo en una capa concreta. Sin WR. Sin modificar el motor (GAP-1 se
añade solo cuando el Director lo autorice).

*Auditoría de HYP-002. Sin EXP, sin ejecución, sin tocar código. Complementa `SETUP_SPEC.md` y
`hypothesis.md`.*
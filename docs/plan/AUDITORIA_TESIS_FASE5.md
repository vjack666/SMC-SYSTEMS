# AUDITORÍA DE TESIS — Fase 5 (por qué el motor canónico da 0 señales)

**Fecha:** 2026-07-19
**Autor:** Hermes (auditoría de lectura, sin modificar producción)
**Contexto:** el plan por capacidades (Fases 1–4) está verde y aislado. Al conectarlo
a datos reales en modo OBSERVE (calificador, no filtro), el motor canónico dio 0 señales
con ventana chica y crasheó por DF vacío al recortar. Esto NO es culpa del plan (el
`score_plan` es calificador, 6 tests verdes). Es el motor base el cuello de botella.

**Veredicto:** el motor backtesteado es una VERSIÓN SIMPLIFICADA de la tesis ICT
(libros 18/21/08). El 0 de señales NO es evidencia de "la estrategia ICT no tiene edge":
es evidencia de que faltan capas de la tesis por implementar. Abajo, la brecha exacta
con citas de código.

---

## §1 Lo que el motor SÍ hace hoy (crédito)

- `sequence.py`: secuencia event-driven `SWEEP_DONE → DISPLACE_DONE → BOS_DONE → ENTRY`
  con memoria de zona y reset (líns 52, 350, 374–434). Requiere sweep + displacement +
  BOS + FVG/OB en la dirección (líns 418–434).
- HTF closed-only: `est_htf_fn(i)` lee trend/sweep del HTF en vela ya cerrada (sequence.py:316,
  run_backtest.py:194). Sin look-ahead.
- SL estructural en mecha de sweep, fill next-open, costs ON, RR 1:3, killzone
  (R6 cerrado, código en `ict_backtest/`).
- POI anclado parcial (Fase C): `run_backtest.py:248-256` construye `anchored` PD zones
  desde `est_htf_fn` y las pasa a `build_context_stack`. PERO solo si `est_htf_fn is not None`.

## §2 Brecha A1 — 3 capas reales (HTF bias → ITF zona → LTF exec) AUSENTES

**Tesis (libro 18 §1, §37):** ICT usa 3 capas funcionales con TF distintos:
HTF (bias, D1/H4/H1) → ITF (zona/POI, H4/M15) → LTF exec (M15/M5/M1). *"El HTF siempre
tiene autoridad sobre el LTF. El sesgo se escribe arriba; el LTF debe coincidir."*

**Código hoy:** el motor usa SOLO 2 TF reales en la generación de señales: `H4 → M15`
(`run_backtest.py:100,213` `generate_sequence_signals(symbol, "H4", "M15", ...)`).
- D1 se carga en `TF_CHAIN` pero NO se usa para sesgo en `run_sequence` (solo context snapshot Fase D).
- H1/M5/M1 ausentes en el flujo de señales: `run_sequence` NO los consulta para gate.
- El plan por capacidades (Fases 1–4) SÍ modela las 6 capas, pero está aislado; no cableado
  al loop de `run_sequence_backtest` (eso es el "loop driver" pendiente, nivel 2).

**Impacto:** sin capa HTF de sesgo real (D1/H4/H1 decidan dirección) y sin capa ITF de
zona (H4/M15 POI anclado), el motor solo ve la secuencia M15. La tesis 18 dice que operar
el entry TF sin bias TF es el error que quiebra cuentas retail. El motor lo hace por diseño.

## §3 Brecha B — POI anclado a narrativa HTF DESACTIVADO por defecto

**Tesis (libro 21 §4):** *"Un POI suelto (cualquier FVG/OB en ventana) NO es un POI ICT
real. El POI real está anclado a una narrativa: el desplazamiento estructural que lo creó
(BOS/CHOCH en esa dirección en el TF padre)."* Auditoría empírica del repo
(`tests/AUDITORIA_POI_REPORT.md`, 10.669 zonas): **100% de los POI aceptados carecían de
BOS/desplazamiento HTF que los respaldara** → "todo FVG/OB = POI", no POI de narrativa.

**Código hoy:** `run_backtest.py:187` → `est_htf_fn = None` por DEFECTO. Solo se define
si se pasa `--htf-poi` (línea 194). O sea el ancla narrativa está APAGADA en el backtest
estándar. `sequence.py` usa `est_htf_fn` solo para sweep/displacement en HTF (líns 147–168),
pero el FVG/OB (ENTRY) NO se valida contra un BOS/CHOCH HTF padre. Cualquier FVG/OB cuenta
como entrada sin respaldo (libro 21: 100% sin ancla).

**Impacto:** el filtro más definitorio de ICT está muerto por defecto. El motor acepta
geometría suelta sin "por qué".

## §4 Brecha C — dealing range / premium-discount AUSENTE

**Tesis (libro 21 §0, §2; libro 08 PO3):** un POI válido exige estar en la ZONA CORRECTA
del dealing range (discount para long, premium para short, EQ = 50% fib del swing HTF).
Sin eso, un OB perfecto en premium en día bullish es wrong-side (libro 21:50, SKIP tier).

**Código hoy:** NO existe módulo `dealing_range`. `build_objects`/`market_structure.py`
no clasifican zona premium/discount. El POI no filtra por zona (libro 21 §6 mapeo:
"`role=POI` pero NO filtra zona/sesgo/respaldo"). Power of Three (AMD) está implementado
en `signals/po3.py` (R1) pero NO está cableado al backtest de señales canónico.

**Impacto:** no hay filtro de calidad de zona. Entra en cualquier precio.

## §5 Brecha D — POI como BONUS, no filtro duro (ya resuelta en diseño)

**Tesis (libro 21 §4):** *"El POI es un BONUS de calidad (`quality_score += 20`), NO un
filtro duro que anule la señal. La auditoría demostró que usar POI HTF como filtro duro
destruye el edge (A'' PF 0.900 vs A' PF 1.511)."*

**Estado:** Fase E lo usó como filtro duro (mal). El plan por capacidades (Fase 5
`score_plan`) lo resuelve: M5/M1 son BONUS (+0.5), no condición; el plan califica, no
filtra. Esto es coherente con tu regla de no sobrefiltrar. ✅ Ya aplicado en diseño.

## §6 Por qué da 0 señales (respuesta a la duda de fondo)

No es el plan. Es la suma de:
1. **Motor estricto (sequence.py):** requiere sweep + displacement + BOS + FVG/OB con
   `confirm_bars=2` (StructureConfig) y `require_displacement=True` (sequence.py:67,73).
   Con ventanas cortas barely hay velas suficientes para completar la secuencia.
2. **Sin POI anclado (Brecha B):** aunque any FVG/OB cuenta, el sequence es event-driven
   y estricto; sin contexto HTF que valide, las pocas secuencias que emergen no pasan el
   filtro de calidad (que hoy no existe, pero el motor base es tan estricto que igual da 0).
3. **Fragilidad a datos chicos:** `load_tf` con `start` recortado dejó algún TF vacío →
   `detect_market_structure` rompe (`_atr` index 0). El motor no tolera ventanas cortas.
4. **Brecha A1/C:** sin 3 capas ni dealing range, el motor es una versión despojada; la
   tesis dice que sin eso el setup "no tiene contexto, el setup no" (libro 18:47).

**Conclusión:** el 0 de señales es un SÍNTOMA de versión simplificada, no de "sin edge".
Exactamente el CAVEAT del AGENTS.md (R6): *"antes de declarar stack ICT sin edge, falta
cerrar la brecha B (POI anclado) y A1 (3 capas reales)."*

## §7 Qué falta implementar (mapeo, SIN tocar código ahora)

| # | Brecha | Tesis | Dónde cablear | Estado |
|---|--------|-------|---------------|--------|
| A1 | 3 capas reales | 18 §1/§37 | loop driver: cablear PlanFSM (Fases 1–4) a `run_sequence_backtest` | Pendiente nivel 2 |
| B | POI anclado narrativa HTF | 21 §4 | `est_htf_fn` ON por defecto + ancla BOS/CHOCH padre en `build_objects` | Pendiente |
| C | dealing range premium/discount | 21 §0/§2, 08 | nuevo módulo `dealing_range` + filtro zona en `build_objects` | Pendiente |
| D | POI como bonus | 21 §4 | `score_plan` ya lo hace (M5/M1 bonus) | ✅ Diseñado |
| E | PO3/AMD cableado al backtest | 08 | `signals/po3.py` → `run_sequence` | Pendiente |

**Orden sugerido (tu filosofía: primero medir, luego concluir):** cerrar B (POI anclado)
y A1 (loop driver) primero — son los que la tesis marca como definitorios. C (dealing
range) y E (PO3) son refinamiento de calidad. D ya está.

## §8 Nota de gobernanza

- Este documento es AUDITORÍA DE LECTURA. No modifica `run_backtest.py`, `sequence.py`,
  `market_structure.py` ni ningún módulo de producción.
- El plan por capacidades (Fases 1–4) y `score_plan` (Fase 5) siguen verdes y aislados.
- No se commitea nada hasta OK expreso de Ruben, con roadmaps al día.

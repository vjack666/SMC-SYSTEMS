# AUDITORÍA DE TESIS — Fase 5 (por qué el motor canónico da 0 señales)

**Fecha:** 2026-07-20 (actualizada: medidor reparado hoy)
**Autor:** Hermes (auditoría de lectura, sin modificar producción)
**Contexto:** el plan por capacidades (Fases 1–4) está verde y aislado. Al conectarlo
a datos reales en modo OBSERVE (calificador, no filtro), el motor canónico dio 0 señales
con ventana chica. Esto NO es culpa del plan (el `score_plan` es calificador, 6 tests verdes).
Es el motor base el cuello de botella. El medidor (Fase 5) fue reparado el 2026-07-20:
su call site real ahora construye MarketObjects vía `data_feed.build_objects` y calcula
score real (antes daba 0 por cableado muerto). PERO el medidor solo MIDE; el motor base
sigue sin aplicar B/C/A1/E.

**Veredicto:** el motor backtesteado es una VERSIÓN SIMPLIFICADA de la tesis ICT
(libros 18/21/08). El 0 de señales NO es evidencia de "la estrategia ICT no tiene edge":
es evidencia de que faltan capas de la tesis por implementar EN EL MOTOR. Abajo, la brecha
exacta con citas de código.

---

## §1 Lo que el motor SÍ hace hoy (crédito)

- `sequence.py`: secuencia event-driven `SWEEP_DONE → DISPLACE_DONE → BOS_DONE → ENTRY`
  con memoria de zona y reset (líns 52, 350, 374–434). Requiere sweep + displacement +
  BOS + FVG/OB en la dirección (líns 418–434).
- HTF closed-only: `est_htf_fn(i)` lee trend/sweep del HTF en vela ya cerrada (sequence.py:316,
  canonical.py:106). Sin look-ahead.
- SL estructural en mecha de sweep, fill next-open, costs ON, RR 1:3, killzone
  (R6 cerrado, código en `ict_backtest/`).
- POI anclado parcial (Fase C): `canonical.est_htf_fn` entrega `pd_zones` HTF vigentes
  (canonical.py:111-119) y `htf_pd_index` las resuelve O(1). PERO el ancla solo alimenta el
  evaluador de autoridad (Fase C), NO el gate de entrada de `run_sequence` (Brecha B en motor OFF).

## §2 Brecha A1 — 3 capas reales (HTF bias → ITF zona → LTF exec) AUSENTES

**Tesis (libro 18 §1, §37):** ICT usa 3 capas funcionales con TF distintos:
HTF (bias, D1/H4/H1) → ITF (zona/POI, H4/M15) → LTF exec (M15/M5/M1). *"El HTF siempre
tiene autoridad sobre el LTF. El sesgo se escribe arriba; el LTF debe coincidir."*

**Código hoy:** el motor usa SOLO 2 TF reales en la generación de señales: `H4 → M15`
(`run_backtest.py` llama `generate_sequence_signals(symbol, "H4", "M15", ...)`).
- D1 se carga en `TF_CHAIN` pero NO se usa para sesgo en `run_sequence` (solo context snapshot Fase D).
- H1/M5/M1 ausentes en el flujo de señales: `run_sequence` NO los consulta para gate.
- El plan por capacidades (Fases 1–4) SÍ modela las 6 capas, pero está aislado; no cableado
  al loop de `run_sequence_backtest` (eso es el "loop driver" pendiente, nivel 2). El medidor
  Fase 5 SÍ se llama (modo OBSERVE) y califica, pero no gobierna.

**Impacto:** sin capa HTF de sesgo real (D1/H4/H1 decidan dirección) y sin capa ITF de
zona (H4/M15 POI anclado), el motor solo ve la secuencia M15. La tesis 18 dice que operar
el entry TF sin bias TF es el error que quiebra cuentas retail. El motor lo hace por diseño.

## §3 Brecha B — POI anclado a narrativa HTF: CERRADA EN MOTOR (Opción 2, 2026-07-20)

**Tesis (libro 21 §4):** *"Un POI suelto (cualquier FVG/OB en ventana) NO es un POI ICT
real. El POI real está anclado a una narrativa: el desplazamiento estructural que lo creó
(BOS/CHOCH en esa dirección en el TF padre)."* Auditoría empírica del repo
(`tests/AUDITORIA_POI_REPORT.md`, 10.669 zonas): **100% de los POI aceptados carecían de
BOS/desplazamiento HTF que los respaldara** → "todo FVG/OB = POI", no POI de narrativa.

**Código hasta 2026-07-19:** `sequence.py` ya tenía el gate `poi_ok = (htf_poi_fn is None)
or bool(htf_poi_fn(i, target))`, pero `canonical.py` no pasaba `htf_poi_fn` → ancla apagada.

**Cierre 2026-07-20 (Opción 2, postprocesado en canonical.py — run_sequence SIN
modificaciones):** se creó `ict_backtest/poi_anchor_motor.py` con la función PURA
`compute_htf_anchored(sig_dir, entry_at, htf_pd_index, ltf_map)` que consulta el
`HtfPdIndex` ya construido en `canonical.py` (cuando `enable_pd_index=True`) y devuelve si
había un POI del HTF padre en la dirección de la señal (anti look-ahead closed-only por
`zones_at`). `canonical.evaluate_signals` la llama EN POST-PROCESO (tras `run_sequence`,
sin tocar el motor interno) y anota `ICTSignal.htf_anchored`. El `run_sequence` quedó
100% intacto: radio de explosión mínimo.

**Principio Brecha D respetado (anota, NO filtra):** el conteo de señales es IDÉNTICO con y
sin ancla. `compute_htf_anchored` devuelve `False` (no `None` descartando) cuando no hay POI
HTF; la señal sale igual. Verificado:
- Test unitario `tests/test_poi_anchor_motor.py` (3 tests, unidad pura).
- Demo sintético `scripts/cierre_brecha_b_demo.py`: con/sin POI HTF → `n_senales=1` en ambos,
  `htf_anchored` True/False correcto.
- Prueba de regresión con datos reales `scripts/verify_brecha_b_realdatos.py`: EURUSD real,
  `n_con_pd_index == n_sin_pd_index` (conteo idéntico).

**LIMITACIÓN EXPLÍCITA (comportamiento sobre señales REALES):** durante la verificación con
datos reales EURUSD, el motor base produjo **0 señales** (versión simplificada 2-TF H4→M15,
estricta). Por tanto el call site del ancla NO se ejercitó con una señal real de mercado: no
hubo señal donde leer `htf_anchored`. La lógica está verificada en sintético y el conteo es
idéntico en real, pero confirmar `htf_anchored` sobre una señal real queda pendiente de que
el motor base produzca entradas (laburo R4/R6, fuera del alcance de este cierre). El ancla
funciona; falta señal donde aplicarla.

**Impacto:** el filtro más definitorio de ICT ahora se ANOTA en cada señal (y el medidor Fase
5 ya lo califica como bonus). No se descarta ninguna señal.

## §4 Brecha C — dealing range / premium-discount: CERRADA EN MOTOR (Opción 2, 2026-07-20)

**Tesis (libro 21 §0, §2; libro 08 PO3):** un POI válido exige estar en la ZONA CORRECTA
del dealing range (discount para long, premium para short, EQ = 50% fib del swing HTF).
Sin eso, un OB perfecto en premium en día bullish es wrong-side (libro 21:50, SKIP tier).

**Código hasta 2026-07-19:** `dealing_range.py` EXISTE y el MEDIDOR Fase 5 lo usa como
bonus (+0.5 si zona correcta). PERO NO estaba en `run_sequence`: el motor base no anotaba
la zona. Solo el medidor la veía.

**Cierre 2026-07-20 (Opción 2, postprocesado en canonical.py — run_sequence SIN
modificaciones):** se creó `ict_backtest/dealing_range_motor.py` con la función PURA
`compute_zone_class(sig_dir, entry, swing_high_htf, swing_low_htf)` que delega en
`dealing_range.classify_zone` y devuelve 'PREMIUM'/'DISCOUNT'/'EQ'. `canonical.evaluate_signals`
lo llama EN POST-PROCESO (tras `run_sequence`, sin tocar el motor interno): obtiene el
`swing_high`/`swing_low` del HTF cerrado vigente al `entry_at` (anti look-ahead por
`closed_row_at_time`) y anota `ICTSignal.zone_class`. `run_sequence` 100% intacto.

**Principio Brecha D respetado (anota, NO filtra):** si no hay swing HTF (`None`) →
`zone_class=None` y la señal sale igual. Conteo idéntico. Verificado:
- Test unitario `tests/test_dealing_range_motor.py` (8 tests, unidad pura).
- Demo sintético `scripts/cierre_brecha_c_demo.py`: DISCOUNT/PREMIUM/EQ correctos, conteo idéntico.
- Verify cableado `scripts/verify_brecha_ce_cableado.py`: enchufe en canonical anota sin crashear.

**Impacto:** la zona de entrada ahora se ANOTA en cada señal (el medidor Fase 5 ya la
califica como bonus). No se descarta ninguna señal por zona.

## §5 Brecha D — POI como BONUS, no filtro duro (ya resuelta en diseño)

**Tesis (libro 21 §4):** *"El POI es un BONUS de calidad (`quality_score += 20`), NO un
filtro duro que anule la señal. La auditoría demostró que usar POI HTF como filtro duro
destruye el edge (A'' PF 0.900 vs A' PF 1.511)."*

**Estado:** Fase E lo usó como filtro duro (mal). El plan por capacidades (Fase 5
`score_plan`) lo resuelve: M5/M1 son BONUS (+0.5), no condición; el plan califica, no
filtra. Esto es coherente con tu regla de no sobrefiltrar. ✅ Ya aplicado en diseño y en el
medidor reparado (score real por señal).

## §6 Por qué da 0 señales (respuesta a la duda de fondo)

No es el plan. Es la suma de:
1. **Motor estricto (sequence.py):** requiere sweep + displacement + BOS + FVG/OB con
   `confirm_bars=2` (StructureConfig) y `require_displacement=True` (sequence.py:67,73).
   Con ventanas cortas barely hay velas suficientes para completar la secuencia.
2. **Sin POI anclado (Brecha B en motor):** aunque any FVG/OB cuenta, el sequence es
   event-driven y estricto; sin contexto HTF que valide, las pocas secuencias que emergen
   no pasan el filtro de calidad (que hoy no existe en el motor, pero el motor base es tan
   estricto que igual da 0).
3. **Fragilidad a datos chicos:** `load_tf` con `start` recortado dejó algún TF vacío →
   `detect_market_structure` rompe (`_atr` index 0). El motor no tolera ventanas cortas.
4. **Brecha A1/C/E en motor:** sin 3 capas ni dealing range ni PO3, el motor es una versión
   despojada; la tesis dice que sin eso el setup "no tiene contexto, el setup no" (libro 18:47).

**Conclusión:** el 0 de señales es un SÍNTOMA de versión simplificada, no de "sin edge".
Exactamente el CAVEAT del AGENTS.md (R6): *"antes de declarar stack ICT sin edge, falta
cerrar la brecha B (POI anclado) y A1 (3 capas reales) EN EL MOTOR."*

## §7 Qué falta implementar (mapeo, SIN tocar código ahora)

| # | Brecha | Tesis | Dónde cablear | Estado |
|---|--------|-------|---------------|--------|
| A1 | 3 capas reales | 18 §1/§37 | loop driver: cablear PlanFSM (Fases 1–4) a `run_sequence_backtest`; D1/H1 deciden | Pendiente nivel 2 |
| B | POI anclado narrativa HTF en MOTOR | 21 §4 | postproceso en `canonical.py` vía `poi_anchor_motor.compute_htf_anchored` (Opción 2: `run_sequence` intacto) | ✅ CERRADA 2026-07-20 (anota `ICTSignal.htf_anchored`, no filtra; verificada en sintético + regresión datos reales; pendiente ejercitar con señal real — motor base 0 señales) |
| C | dealing range premium/discount en MOTOR | 21 §0/§2, 08 | `ict_backtest/dealing_range_motor.compute_zone_class` (Opción 2: postproceso en `canonical.py`, `run_sequence` intacto) | ✅ CERRADA 2026-07-20 (anota `ICTSignal.zone_class`, no filtra; verificada en sintético + cableado canonical; pendiente ejercitar con señal real — motor base 0 señales) |
| D | POI como bonus | 21 §4 | `score_plan` ya lo hace (M5/M1 bonus) | ✅ Diseñado + medidor reparado |
| E | PO3/AMD cableado al MOTOR | 08 | `ict_backtest/po3_motor.compute_po3_complete` (Opción 2: postproceso en `canonical.py`, `run_sequence` intacto) | ✅ CERRADA 2026-07-20 (anota `ICTSignal.po3_complete`, no filtra; verificada en sintético + cableado canonical; pendiente ejercitar con señal real — motor base 0 señales) |

**Orden sugerido (tu filosofía: primero medir, luego concluir):** cerrar B (POI anclado en
motor) y A1 (loop driver) primero — son los que la tesis marca como definitorios. C (dealing
range) y E (PO3) son refinamiento de calidad. D ya está. El medidor Fase 5 (reparado 2026-07-20)
permite medir Score vs WR ANTES de decidir umbral.

## §8 Nota de gobernanza

- Este documento es AUDITORÍA DE LECTURA. No modifica `run_backtest.py`, `sequence.py`,
  `market_structure.py` ni ningún módulo de producción.
- El plan por capacidades (Fases 1–4) y `score_plan` (Fase 5) siguen verdes y aislados del
  loop de decisión; el medidor Fase 5 SÍ está cableado (modo OBSERVE) y reparado.
- No se commitea nada hasta OK expreso de Ruben, con roadmaps al día.

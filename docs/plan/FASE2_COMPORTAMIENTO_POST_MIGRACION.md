# FASE 2 — INFORME DE COMPORTAMIENTO POST-MIGRACIÓN ATR→RANGO

**Fecha:** 2026-07-20
**Alcance:** Backtest de 1 mes (EURUSD, ventana 2026-06→2026-07), configuración
de producción `htf=H4 -> ltf=M15`, motor `run_sequence` (canónico, event-sequence).
**Objetivo:** observar el comportamiento del motor tras la migración, NO medir
win rate ni rentabilidad. Validar que la arquitectura sigue el camino correcto.

**Datos:** EURUSD tiene LOS 6 TF en disco (D1/H4/H1/M15/M5/M1). Ventana de 1 mes
= 3056 barras M15, 128 H4, 360 H1, 22 D1, 4320 M5, 21498 M1.

**Herramienta de instrumentación:** `scripts/fase2_instrument.py` (no toca el
motor; parchea funciones puras con contadores y llama primitivas públicas).
Salida cruda: `results/fase2_informe_EURUSD_M15_1m.json`.

---

## PREGUNTA 1 — ¿En qué temporalidad se calcula REALMENTE el SL estructural?

**Respuesta: en el LTF (M15). El HTF NO participa en el cálculo del SL.**

Flujo completo (evidencia, no suposición):

1. `canonical.evaluate_signals` (línea 164):
   `rng_series = avg_candle_range(ltf_df, window=50)`
   → la volatilidad/riesgo se saca de `ltf_df` (el M15). NO de `ms[htf]`.

2. Por cada setup (línea 165-174):
   `rng = float(rng_series.iloc[entry_at])`
   → el `rng` es el rango promedio high-low de la barra M15 de entrada.

3. (línea 180-181):
   `sweep_row = ltf_df.iloc[s["sweep_at"]]`
   `sl = calc_structural_sl(sweep_row, direction, rng)`
   → el SL se ancla a la MECHA del sweep (sweep_low/sweep_high de la vela M15)
   ± `STRUCT_SL_BUFFER_RANGE * rng` (0.3 × rango M15).

4. `engine.calc_structural_sl` (engine.py:317): prioriza mecha de sweep; si no
   hay, cae a swing roto; si tampoco, devuelve `None` (motor no opera). El buffer
   usa el `rng` que vino del M15.

**Conteo empírico:** `calc_structural_sl` fue llamado **4 veces** (= las 4 señales
finales que pasaron el filtro). En todos los casos el `rng` provenía de
`avg_candle_range(ltf_df)` → M15. Confirmado por el tag de agua inyectado en el
script (la serie del LTF quedó marcada y coincidió en las 4 llamadas).

**Veredicto:** el SL estructural nace y se calcula 100% en M15. El HTF (H4) sólo
aporta el `trend` (sesgo) que habilita o resetea la secuencia (sequence.py:380),
pero NO el nivel de SL ni su volatilidad. Esto es coherente con ICT (SL anclado a
la estructura del TF de ejecución), pero significa que la "volatilidad de
contexto" es la del LTF, no un rango MultiTF ponderado.

---

## PREGUNTA 2 — ¿El motor ya usa el contexto MultiTF completo o sigue en H4+M15?

**Respuesta: el contexto MultiTF COMPLETO se construye, pero run_sequence SOLO
usa la capa H4. D1/H1/M15/M5/M1 viajan disponibles y NO influyen en la decisión.**

Recorrido real de los datos (evidencia empírica + código):

- **Construcción:** `canonical.est_htf_ctx_fn` (canonical.py:122-134) llama
  `build_multitf_context(ms, t, tfs=("D1","H4","H1","M15","M5","M1"))`.
  **Medido: 3056 construcciones** (= 1 por barra M15 del mes). El contexto
  incluye los 6 TF, closed-only, anti-look-ahead (reusa `build_context_stack`).

- **Reducción en run_sequence** (sequence.py:374-376):
  `est_htf = extract_htf_layer(_ctx, htf)`  con `htf = "H4"`.
  `extract_htf_layer` (multitf_context.py:55-73) devuelve SOLO
  `{trend, sweep_up, sweep_down, pd_zones}` de la capa H4.

- **Consumo** (sequence.py:380-381):
  `htf_trend = est_htf.get("trend")` → `bias`.
  Nada más. Los otros 5 TF (`_ctx["D1"/"H1"/"M15"/"M5"/"M1"]`) están en `_ctx`
  pero run_sequence NO los lee.

- **POI anclado DESACTIVADO** (sequence.py:403):
  `poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))`
  → `htf_poi_fn=None`, así que el filtro más definitorio de ICT (zona LTF solo
  si hay POI HTF en esa dirección) está MUERTO. Cualquier FVG/OB cuenta.

**Participación efectiva por TF en la decisión final:**

| TF   | ¿Participa en la decisión? | Rol real |
|------|---------------------------|----------|
| D1   | NO                        | disponible en `_ctx`, no leído |
| H4   | SÍ (único)               | `trend` → sesgo/bias (sequence.py:380) |
| H1   | NO                        | disponible en `_ctx`, no leído |
| M15  | SÍ                        | TF de ejecución: sweep/displace/BOS/entry/SL/rng |
| M5   | NO                        | disponible en `_ctx`, no leído |
| M1   | NO                        | disponible en `_ctx`, no leído |

**Veredicto:** arquitectura en estado "Opción A / Fase 1" (infra de lectura lista,
cascada MultiTF no activada). El motor sigue siendo efectivamente **H4 (sesgo) +
M15 (todo lo demás)**. Los 4 TF restantes están cableados a nivel de datos pero
no deciden.

---

## PREGUNTA 3 — Comparación de comportamiento (estructuras / setups / señales / motivos)

### 3a. Estructuras detectadas por TF (ventana 1 mes)

| TF   | BOS  | CHOCH | Total | Filas |
|------|-----:|------:|------:|------:|
| D1   |    1 |     0 |     1 |    22 |
| H4   |   26 |    10 |    36 |   128 |
| H1   |   86 |   120 |   206 |   360 |
| M15  |  786 |   850 |  1636 |  3056 |
| M5   | 1255 |  1269 |  2524 |  4320 |
| M1   | 6499 |  6132 | 12631 | 21498 |
| **TOTAL** | | | **17034** | |

Nota: estas son estructuras crudas del market_structure (sin filtro). La
gran mayoría (M1/M5) es ruido que el motor nunca mira.

### 3b. Setups vs señales finales

- **Setups (raw_sigs de run_sequence):** 6
- **Señales finales (evaluate_signals):** 4
- **Tasa de conversión setup→señal:** 4/6 = 66.7%

### 3c. Motivos de aceptación / descarte (setup→señal)

| Motivo | Cantidad |
|--------|---------:|
| OK (pasa todos los filtros) | 4 |
| Fuera de killzone (London/NY) | 2 |
| Entry fill falla | 0 |
| rng inválido (≤0) | 0 |
| SL None (sin mecha de sweep ni swing) | 0 |
| Risk inválido o excesivo (> 6×rango) | 0 |
| TP no cumple RR 1:3 | 0 |

**Lectura:** de los 6 setups, 2 se descartan por fuera de killzone (filtro de
sesión, línea 177-179 canonical). Los 4 restantes pasan todo: SL estructural
válido, risk dentro de 6×rango, RR 1:3 forzado. Ningún descarte por volatilidad
excesiva ni por SL inválido → tras la migración a rango, el filtro
`STRUCT_SL_MAX_RANGE` (6×rango M15) no está rechazando nada en este mes. El
comportamiento del filtro de volatilidad es benigno (no es el cuello de botella).

### 3d. Contra el baseline (ATR)

No se corrió un backtest ATR paralelo en esta Fase 2 (el ATR fue eliminado del
código en Fase 1; no hay rama viva para comparar A/B en runtime). Lo que SÍ se
verificó: la magnitud de los umbrales se conservó idéntica (0.3 buffer, 6.0 max,
0.5 fallback) para que el conteo de señales sea comparable. Con esos múltiplos
equivalentes, el recorrido de datos y la lógica de filtrado son byte-a-byte los
mismos que con ATR salvo la fuente de volatilidad. Por ende, la diferencia de
comportamiento es SOLO el valor del `rng` (rango puro vs ATR suavizado), no la
arquitectura ni los conteos de filtro.

> Pendiente de Fase 2-B (no hecha aquí, fuera de alcance): correr A vs A'
> (mismo motor, `rng` = ATR baseline vs rango) sobre el mismo mes para medir el
> delta de señales/SL. Requiere revivir temporalmente el ATR en un script aislado
> (no re-introducirlo al motor).

---

## HALLAZGOS ARQUITECTÓNICOS (lo que falta para MultiTF real)

1. **run_sequence solo decide con H4** (capa extraída vía `extract_htf_layer`).
   D1/H1/M5/M1 no influyen. → Siguiente paso: activar la cascada en
   `run_sequence` para que lea, además del `trend` H4, el `trend` D1 (bias
   madre) y valide el POI en H1 (zona de confirmación), antes de operar en M15.
   Esto es la **Brecha A1 (3 capas reales)** del CAVEAT.

2. **POI anclado muerto** (`htf_poi_fn=None`, sequence.py:403). → Siguiente
   paso: cablear `htf_poi_fn` para que la zona LTF (FVG/OB) solo cuente si hay
   un POI HTF en esa dirección (libro 21). Es la **Brecha B** del CAVEAT.

3. **Volatilidad del SL es del LTF únicamente** (P1). → Siguiente paso
   (Fase 3 / P1 completo): derivar el buffer del SL de la estructura del
   MarketObject (mecha de sweep real), no de un promedio de N velas del LTF.
   Hoy es "rango promedio" — más crudo que ATR, pero todavía una media fija.

4. **dealing_range / premium-discount, po3_state, filtro de régimen:** presentes
   como cálculo (canonical.py:196-230, bucle PO3 recorre los 6 TF) pero NO como
   filtro de ejecución. El bucle PO3 construye `po3_structure` y `po3_complete`
   por señal, pero no vetan el trade. → Siguiente paso: promover esos cálculos a
   filtros reales (Brechas C/E).

---

## Veredicto final (Ruben)

- La migración ATR→rango **no rompió el camino de datos ni la arquitectura**:
  el motor corre, construye el contexto MultiTF completo (3056× con 6 TF) y
  decide con H4+M15 exactamente como antes.
- El SL estructural se calcula en **M15** (no HTF) — confirmado por flujo + conteo.
- El contexto MultiTF está **cableado a nivel de datos pero no decide**: solo H4
  (sesgo) y M15 (ejecución) participan. D1/H1/M5/M1 son ignorados en la decisión
  final. Esto es estado conocido (Fase 1 = infra de lectura; Fase 2 activaría la
  cascada), NO un bug nuevo.
- No forcé nada: dejé documentado exactamente dónde ocurre la limitación y cuál
  es el siguiente paso arquitectónico (Brechas A1/B/C/E del CAVEAT).
- Prioridad cumplida: se validó **comportamiento**, no se optimizó resultado.
  No se midió win rate ni rentabilidad (fuera de alcance por pedido).

**Archivos:**
- Informe crudo: `results/fase2_informe_EURUSD_M15_1m.json`
- Instrumentación: `scripts/fase2_instrument.py`

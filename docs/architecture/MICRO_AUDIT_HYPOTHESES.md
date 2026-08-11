# MICRO_AUDIT_HYPOTHESES.md — Inventario de hipótesis reales (FASE 3B.2)

> **Auditoría de descubrimiento (2026-08-10).** FASE 3B.2 = mapear el conocimiento científico
> EXISTENTE en el repo. CERO creación de HYP/EXP, CERO ejecución, CERO modificación de código,
> CERO migración. Solo descubrimiento + clasificación + trazabilidad desde el repositorio.
>
> Regla fundamental del contrato (RESEARCH_CONTRACT.md §0): si no está en el repo, no es evidencia.
> ADR-005 fue invocado por el Director pero **NO EXISTE en el repositorio** (grep de `ADR-005`
> en `docs/` = 0 hits, ni archivo ADR alguno). Se aplica el criterio literal del Director:
> REAL = descubrimiento (datos reales), FOREX = validación (backtest/experimento). Ver FASE D.

## FASE A — DESCUBRIMIENTO (fuentes reales del repo)

Fuentes consultadas (todas en repo, con evidencia física):
- `docs/lab/LABORATORIO_ICT_SMC.md` — laboratorio de falsación, T1-T10.
- `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` — corridas 30k/113k M15, baselines.
- `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` — T8, diagnóstico de sesgo.
- `docs/specs/INDICE_MDS.md` + SDD `MDS_B1_POI_ANCLADO`, `MDS_B2_3CAPAS`, `MDS_BOS_CHOCH` — reglas de motor.
- `docs/architecture/RESEARCH_CONTRACT.md` — contrato vigente (leído).

NO se usó memoria de conversación como fuente.

## FASE B/C — CLASIFICACIÓN Y FICHAS DE CANDIDATOS

### CAND-01 — "BOS/CHOCH es predictivo de dirección en k velas"
- **Tipo**: HALLAZGO / RESULTADO EXPERIMENTAL (ya medido, no confirmó edge sobre ruido en EURUSD).
- **Origen**: `docs/lab/LABORATORIO_ICT_SMC.md` §3.1 (medición T10) + `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §3, §7.
- **Pregunta científica**: cuando el motor detecta BOS/CHOCH, ¿el precio confirma la ruptura en k velas?
- **Predicción**: `against_hit_pct` > baseline por permutación.
- **Variable medible**: `against_hit_pct` (D1/H4/H1/M15), `aligned_hit_pct`.
- **Criterio de refutación**: si `against_hit_pct` ≤ baseline (ruido), la estructura no aporta edge.
- **Evidencia existente**: EURUSD 113k M15 → against_hit 72-75%; baseline contra 0.72-0.77.
  **Conclusión medida**: NO supera el baseline de ruido en este dataset (edge no demostrado).
- **Dominio**: REAL (datos EURUSD reales). Pendiente FOREX en otros símbolos.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio refutación**: SÍ. **Protocolo determinista**: SÍ (runner existe).
- **Estado**: RESULTADO — parcialmente REFUTADA en EURUSD (el ~72-75% es ruido browniano del tramo).

### CAND-02 — "La alineación exacta D1=H4=H1 está disponible y filtra mejor"
- **Tipo**: HALLAZGO / RESULTADO EXPERIMENTAL.
- **Origen**: `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` (T8) + `docs/lab/LABORATORIO_ICT_SMC.md` §3.2.
- **Pregunta**: ¿qué tan disponible es el filtro D1→H4→H1 en datos reales?
- **Predicción**: `aligned_hit_pct` > 0 en tramos significativos.
- **Criterio de refutación**: si `aligned_hit = 0%` sistemáticamente, el gate estricto anula el filtro.
- **Evidencia**: EURUSD 113k/30k M15 → `aligned_hit = 0%` en todos los TF. No es bug; es hecho del dataset (gate exige match exacto de strings).
- **Dominio**: REAL.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ.
- **Estado**: RESULTADO — REFUTADA bajo gate estricto en EURUSD.

### CAND-03 — "Relajar el gate de alineación (≥2/3 no NEUTRAL, sin contradicción) activa el filtro HTF y mejora señales"
- **Tipo**: HIPÓTESIS (propuesta de motor formulada como predicción falsable).
- **Origen**: `docs/lab/LABORATORIO_ICT_SMC.md` §11.1; `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.12.
- **Pregunta**: ¿relajar el criterio de alineación produce señales `aligned` útiles donde el gate estricto da 0%?
- **Predicción**: tras relajar `aligned` en `engine/bias/narrative.py`, `aligned_hit_pct` > 0 y el filtro HTF aporta señales; o `against_hit` mejora respecto a baseline.
- **Variable medible**: `aligned_hit_pct`, `against_hit_pct` post-relajación.
- **Criterio de refutación**: si tras relajar sigue `aligned_hit = 0%` y `against_hit` no supera baseline, la hipótesis cae.
- **Evidencia existente**: solo la observación de que el gate actual da 0% (CAND-02). No hay corrida con gate relajado.
- **Dominio**: REAL (descubrimiento en datos); validación FOREX vía backtest del motor.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio refutación**: SÍ. **Protocolo determinista**: SÍ (cambiar `aligned` en motor + re-correr `scripts/measure_structure_effectiveness.py` con mismos params).
- **Estado**: HIPÓTESIS candidata a HYP (cumple las 3 condiciones).

### CAND-04 — "El sesgo NEUTRAL perpetuo en rangos es defecto del criterio de empate 2-2, no del mercado"
- **Tipo**: HIPÓTESIS de defecto de motor (diagnóstico formulado como causa falsable).
- **Origen**: `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` (conclusión corregida, §Líneas 54-67).
- **Pregunta**: ¿el empate 2-2 en `_bias_from_swings` anula el sesgo; un criterio de mayoría/ponderado lo restaura?
- **Predicción**: cambiar el desempate por tramo más reciente / mayoría simple → el bias deja de ser 100% NEUTRAL y `aligned/against` recupera sentido.
- **Variable medible**: % de velas NEUTRAL antes vs después del fix; distribución BULLISH/BEARISH.
- **Criterio de refutación**: si tras el fix el bias sigue 100% NEUTRAL, la causa no era el empate.
- **Evidencia existente**: T8 verificado por instrumentación: empate 2-2 → NEUTRAL perpetuo; H4/H1 100% NEUTRAL en 18.436 eventos.
- **Dominio**: REAL.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ (ya hay fix M1 en `engine/bias/narrative.py` desempate por tramo reciente — ver §6 M1 de HALLAZGOS; parcialmente ejecutado).
- **Estado**: HIPÓTESIS candidata a HYP (nota: M1 ya aplicó "tramo más reciente"; falta evaluar si restaura aligned real).

### CAND-05 — "Otros símbolos/tramos (ej GBPUSD tendencial) presentan alineación donde EURUSD no"
- **Tipo**: HIPÓTESIS.
- **Origen**: `docs/lab/LABORATORIO_ICT_SMC.md` §11.2; `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.12.
- **Pregunta**: ¿existe `aligned_hit > 0` en símbolos/tramos con tendencia donde EURUSD (rango) da 0%?
- **Predicción**: GBPUSD (u otro tendencial) muestra `aligned_hit_pct` > 0 bajo el mismo gate.
- **Variable medible**: `aligned_hit_pct` por símbolo.
- **Criterio de refutación**: si todos los símbolos dan `aligned_hit = 0%`, la alineación no es propiedad del régimen sino del gate.
- **Evidencia existente**: solo EURUSD medido. 0 hallazgos en otros símbolos.
- **Dominio**: REAL (descubrimiento en datos reales de otros símbolos).
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ (`SMCS_EFFECTIVENESS_SYMBOL=GBPUSD` ya soportado por el runner).
- **Estado**: HIPÓTESIS candidata a HYP.

### CAND-06 — "BOS quality score (bos_real) filtra fakeouts sin eliminar señal útil"
- **Tipo**: HALLAZGO / RESULTADO (ya implementado y medido).
- **Origen**: `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.0.
- **Evidencia**: elimina 18-22% de BOS como fakeouts en M15 (5k dataset); `bos_real` filtra ruido.
- **Dominio**: REAL.
- **Falsable**: conceptualmente SÍ, pero ya medido → es RESULTADO, no abierta.
- **Estado**: HALLAZGO (no candidata a HYP; ya resuelta).

### CAND-07 — "CHOCH confirmado no es edge: baseline permutado = 1.0"
- **Tipo**: HALLAZGO / RESULTADO EXPERIMENTAL.
- **Origen**: `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.2; `docs/lab/LABORATORIO_ICT_SMC.md` §7.3.
- **Evidencia**: CHOCH 100% confirmed_against en 113k = coincide con baseline aleatorio (1.0). El 100% no es edge, es ruido.
- **Dominio**: REAL.
- **Estado**: HALLAZGO — REFUTA la utilidad predictiva de CHOCH en solitario.

### CAND-08 — "MSS compuesto reduce ruido de eventos pero no genera aligned_hit"
- **Tipo**: HALLAZGO.
- **Origen**: `docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md` §7.7.
- **Evidencia**: M15 29438→11649 eventos; 100% en `against`; 0 aligned.
- **Dominio**: REAL.
- **Estado**: HALLAZGO.

### CAND-09 — "POI anclado (PD arrays) mejora la tasa de acierto de entrada vs POI no anclado"
- **Tipo**: HIPÓTESIS (regla de motor formulada como fuente de edge, NO medida en los docs leídos).
- **Origen**: `docs/specs/MDS_B1_POI_ANCLADO.md` (regla ✅ HECHA en `engine/poi_anchor.py` + `zone_authority.py`).
- **Pregunta**: ¿anclar POI al BOS/CHOCH del TF padre cerrado mejora el acierto de entrada respecto a POI sin anclar?
- **Predicción**: entradas sobre POI anclado tienen WR/PF superiores a POI no anclado.
- **Variable medible**: WR/PF por grupo (anclado vs no).
- **Criterio de refutación**: si anclado ≠ no anclado en WR/PF, la ancla no aporta edge.
- **Evidencia existente**: implementación hecha; NO vi medición comparativa en `docs/tesis/`.
- **Dominio**: REAL (descubrimiento) → validación FOREX pendiente.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ (backtest segmentando por `poi["anchored"]`).
- **Estado**: HIPÓTESIS candidata a HYP (premisa de la regla B1 no verificada empíricamente).

### CAND-10 — "3 capas HTF/ITF/exec top-down mejora efectividad vs 1-2 capas"
- **Tipo**: HIPÓTESIS (premisa de la arquitectura B2, no medida comparativamente).
- **Origen**: `docs/specs/MDS_B2_3CAPAS.md` (`engine/plan.py` build_context_stack D1→M1, ✅ HECHO).
- **Pregunta**: ¿la lectura top-down de 3 capas (D1/H4/H1) supera a 1-2 capas en efectividad?
- **Predicción**: secuencia top-down reduce falsos setups y mejora WR vs single-TF.
- **Variable medible**: WR/PF top-down vs single-TF.
- **Criterio de refutación**: si WR top-down ≤ single-TF, la jerarquía no aporta.
- **Evidencia**: implementación hecha; NO vi A/B comparativo en `docs/tesis/`.
- **Dominio**: REAL → FOREX pendiente.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ.
- **Estado**: HIPÓTESIS candidata a HYP.

### CAND-11 — "El sesgo HTF (D1/H4/H1) mejora la efectividad del backtest cuando hay alineación"
- **Tipo**: HIPÓTESIS de tesis (premisa central del motor ICT/SMC).
- **Origen**: `docs/lab/LABORATORIO_ICT_SMC.md` §2.1 (tesis); AGENTS.md (Ley Fundamental).
- **Pregunta**: ¿operar solo a favor del sesgo HTF alineado mejora WR/PF vs ignorar sesgo?
- **Predicción**: señales aligned tienen WR/PF > señales against.
- **Variable medible**: WR/PF aligned vs against.
- **Criterio de refutación**: si aligned ≯ against, el filtro HTF no es edge.
- **Evidencia**: en EURUSD aligned=0% → no medible; CAND-03/05 son los caminos para hacerla medible.
- **Dominio**: REAL (descubrimiento de la tesis) → validación FOREX pendiente.
- **Falsable**: SÍ. **Predicción medible**: SÍ. **Criterio**: SÍ. **Protocolo**: SÍ.
- **Estado**: HIPÓTESIS candidata a HYP (tesis central, aún no validada por datos).

### CAND-12 — ADR-005 (separación REAL/FOREX)
- **Tipo**: NO REPRODUCIBLE DESDE REPO.
- **Origen**: invocado por el Director en la orden de 3B.2; **no existe archivo ADR-005 ni ADR alguno en `docs/`** (grep = 0).
- **Decisión**: NO se convierte en candidata científica. Se aplica el criterio literal del Director
  (REAL=descubrimiento, FOREX=validación) sobre la evidencia disponible, sin depender del ADR.
- **Estado**: DESCARTADA como fuente (falta artefacto documental).

## FASE D — SEPARACIÓN REAL / FOREX

Aplicando el criterio del Director (REAL=descubrimiento, FOREX=validación) sobre evidencia real:

| CAND | Dominio | Evidencia disponible | Nota |
|------|---------|----------------------|------|
| 01 | REAL | EURUSD M15 (REAL data) corrida canónica 113k | edge NO demostrado vs ruido; pendiente FOREX otros símbolos |
| 02 | REAL | EURUSD M15 corrida 113k/30k | refutada bajo gate estricto |
| 03 | REAL→FOREX | observación de CAND-02 | pendiente corrida con gate relajado (FOREX) |
| 04 | REAL | T8 instrumentado cable/EURUSD | fix M1 parcial ya en motor |
| 05 | REAL | solo EURUSD medido | pendiente descubrimiento en GBPUSD (REAL) |
| 06 | REAL | 5k M15 | resuelta |
| 07 | REAL | 113k M15 | refuta CHOCH solitario |
| 08 | REAL | 113k M15 | hallazgo |
| 09 | REAL→FOREX | implementación B1, sin medir | pendiente FOREX |
| 10 | REAL→FOREX | implementación B2, sin A/B | pendiente FOREX |
| 11 | REAL→FOREX | tesis, sin validar por datos | pendiente FOREX |
| 12 | — | ADR-005 inexistente en repo | no reproducible |

Ninguna hipótesis descubierta en REAL se presenta como ya validada en FOREX.

## FASE E — TRAZABILIDAD

Cada CAND cita archivo + sección + evidencia disponible (arriba). Las afirmaciones que solo
existirían en conversación (p.ej. "EXP-069/EXP-071 existen") fueron verificadas y resultaron
ser **convención documental, no artefacto físico** (ver MICRO_AUDIT_RESEARCH_LINEAGE.md) →
NO se convirtieron en candidatas.

## FASE F — MATRIZ FINAL

| ID | Candidato | Tipo | Predicción | Falsable | Criterio refutación | Protocolo determ. | Dominio | Evidencia | Estado |
|----|-----------|------|-----------|----------|---------------------|-------------------|---------|-----------|--------|
| 01 | BOS/CHOCH predictivo | HALLAZGO/RES | against_hit>baseline | SÍ | ≤baseline | SÍ | REAL | 113k EURUSD | REFUTADA parcial EURUSD |
| 02 | Alineación exacta disponible | HALLAZGO/RES | aligned>0 | SÍ | =0% | SÍ | REAL | 113k EURUSD | REFUTADA gate estricto |
| 03 | Relajar gate activa filtro | HIPÓTESIS | aligned>0 post-relajación | SÍ | sigue 0% | SÍ | REAL→FOREX | obs CAND-02 | candidata HYP |
| 04 | NEUTRAL perpetuo=defecto empate | HIPÓTESIS | fix restaura bias | SÍ | sigue NEUTRAL | SÍ | REAL | T8 | candidata HYP |
| 05 | Otros símbolos tienen alineación | HIPÓTESIS | GBPUSD aligned>0 | SÍ | todos 0% | SÍ | REAL | solo EURUSD | candidata HYP |
| 06 | bos_real filtra fakeouts | HALLAZGO/RES | — | — | — | — | REAL | 5k M15 | resuelta |
| 07 | CHOCH no es edge | HALLAZGO/RES | baseline=1.0 | — | — | — | REAL | 113k | refuta CHOCH solitario |
| 08 | MSS reduce ruido, 0 aligned | HALLAZGO | — | — | — | — | REAL | 113k | hallazgo |
| 09 | POI anclado > no anclado | HIPÓTESIS | WR anclado>no | SÍ | igual WR | SÍ | REAL→FOREX | B1 hecho, sin medir | candidata HYP |
| 10 | 3 capas > 1-2 capas | HIPÓTESIS | WR top-down>single | SÍ | ≤ single | SÍ | REAL→FOREX | B2 hecho, sin A/B | candidata HYP |
| 11 | Sesgo HTF mejora backtest | HIPÓTESIS | WR aligned>against | SÍ | igual | SÍ | REAL→FOREX | tesis, sin validar | candidata HYP |
| 12 | ADR-005 | NO REPRODUCIBLE | — | — | — | — | — | inexistente | descartada |

## SEPARACIÓN DE GRUPOS

1. **Candidatos que podrían convertirse en HYP** (cumplen las 3 condiciones):
   CAND-03, CAND-04, CAND-05, CAND-09, CAND-10, CAND-11.
2. **Candidatos que necesitan reformulación**:
   CAND-01 / CAND-02 (ya son RESULTADOS; se reformulan como "¿en QUÉ régimen/símbolo sí hay edge?" → derivan a CAND-05/03).
3. **Observaciones/hallazgos que NO son hipótesis**:
   CAND-06, CAND-07, CAND-08 (resultados medidos, cerrados).
4. **Afirmaciones sin evidencia reproducible**:
   CAND-12 (ADR-005 inexistente en repo).
5. **Elementos descartados**:
   CAND-12 (falta artefacto). EXP-069/EXP-071 (convención, no físicos — ver auditoría previa).

## CONCLUSIÓN PARA EL DIRECTOR

El laboratorio YA tiene una frontera científica operando de facto (LABORATORIO_ICT_SMC.md +
HALLAZGOS_*.md + runner medible con baseline). Lo que faltaba era el *catálogo trazable*.
Hay **6 hipótesis reales candidatas a HYP** (03-05, 09-11) que nacen de evidencia del repo,
no inventadas. Ninguna se promueve hoy: el Director decide cuál merece ser HYP-NNN.

---
*Auditoría 3B.2 (descubrimiento). Sin HYP/EXP, sin ejecución, sin modificación de código.*

---

## FASE G — REVISIÓN CIENTÍFICA (2ª pasada, 2026-08-10)

> Orden del Director: NO crear HYP-001 todavía; separar edge / ingeniería / auxiliares /
> independientes; re-evaluar CAND-03/04/05/11; completar campos; registrar ADR-005 como deuda;
> entregar jerarquía + recomendación razonada. Sin tocar Python, sin ejecutar, sin migrar.

### G.1 Separación de naturaleza

| CAND | Naturaleza | ¿Por qué? |
|------|-----------|-----------|
| 03 | **AUXILIAR (preparatoria)** | Su único propósito científico es hacer testeable CAND-11: sin relajar el gate, `aligned_hit=0%` y la tesis central es unfalsiable en la práctica. No es un edge en sí. |
| 04 | **INGENIERÍA / DIAGNÓSTICO** | Pregunta si el algoritmo de sesgo está mal (defecto de implementación), no si el mercado tiene edge. No debe competir por HYP-001 ni contaminar una prueba de edge. |
| 05 | **AUXILIAR (preparatoria)** | Igual que 03: determina si el efecto de alineación depende del símbolo. Si EURUSD=0% pero GBPUSD>0%, CAND-11 se vuelve falsable; si todos=0%, CAND-11 cae por el gate, no por el mercado. |
| 09 | **INDEPENDIENTE (edge, POI)** | Rama propia: ¿la ancla de POI aporta edge? No es paso para HTF. |
| 10 | **INDEPENDIENTE (edge, arquitectura)** | Rama propia: ¿jerarquía 3 capas aporta edge? No es paso para HTF. |
| 11 | **TESIS PADRE (edge, HTF)** | La pregunta central del motor: ¿el contexto HTF aporta edge? Todas las demás de edge cuelgan de ella o la hacen testeable. |

**Conclusión sobre CAND-03 y CAND-05:** NO son HYP independientes. Son **hipótesis auxiliares**
que habilitan la falsabilidad de la tesis padre (CAND-11). Convertirlas en EXP-NNN directos sería
prematuro: su valor científico es preparar el terreno para probar CAND-11, no responder una
pregunta de edge por sí mismas. Esto corrige la 1ª pasada, que las listó como "candidatas a HYP"
al mismo nivel que 11.

### G.2 Jerarquía

```text
TESIS PADRE (edge, mercado)
└── CAND-11  ¿El contexto HTF (D1/H4/H1 alineado) aporta edge sobre ignorar sesgo?

     HIPÓTESIS AUXILIARES (hacen testeable a CAND-11)
     ├── CAND-03  ¿Relajar el gate de alineación produce aligned>0 y señal útil?
     └── CAND-05  ¿El efecto de alineación depende del símbolo (GBPUSD>0 donde EURUSD=0)?

     HIPÓTESIS INDEPENDIENTES (otras ramas de edge)
     ├── CAND-09  ¿POI anclado aporta más edge que POI no anclado?
     └── CAND-10  ¿3 capas HTF/ITF/exec aportan más edge que 1-2 capas?

     HIPÓTESIS DE INGENIERÍA / DIAGNÓSTICO (NO edge, NO contaminan prueba de edge)
     └── CAND-04  ¿El sesgo NEUTRAL perpetuo es defecto del empate 2-2, no del mercado?

HALLAZGOS CERRADOS (no hipótesis, ya medidos)
├── CAND-01  BOS/CHOCH predictivo → no supera baseline en EURUSD
├── CAND-02  Alineación exacta disponible → 0% en EURUSD (gate estricto)
├── CAND-06  bos_real filtra fakeouts (18-22% M15)
├── CAND-07  CHOCH solitario no es edge (baseline=1.0)
└── CAND-08  MSS reduce ruido, 0 aligned
```

### G.3 Fichas completas (solo candidatas que sobreviven como científicas)

#### CAND-11 — TESIS PADRE — "¿El contexto HTF aporta edge?"
- **Pregunta científica**: ¿operar solo a favor del sesgo HTF alineado mejora WR/PF vs ignorar sesgo?
- **Predicción cuantitativa**: `WR_aligned > WR_against` y `PF_aligned > 1.0` en población con aligned>0.
- **Variable primaria**: `WR` (win rate) y `PF` (profit factor) segmentados por `aligned` vs `against`.
- **Baseline**: WR aleatorio ≈ 0.50; PF del tramo bajo estrategia contra-sesgo (against) ya medido (~edge nulo en EURUSD, CAND-01).
- **Criterio de falsación**: si `WR_aligned ≤ WR_against` (o `PF_aligned ≤ 1.0`), la tesis HTF no aporta edge.
- **Protocolo determinista**: backtest canónico (`ict_backtest/run_backtest`) con `top_down_allows_trade` activo, segmentando fills por `HtfBias.aligned`; mismos params que corrida R6.4; misma semilla/costs ON.
- **Datos necesarios**: EURUSD/GBPUSD/USDCHF/USDCAD M15 + HTF, ~4.5 años (los del repo). Población con `aligned>0` requiere previamente CAND-03/05.
- **Dominio REAL/FOREX**: REAL (descubrimiento de la tesis ICT/SMC) → FOREX (validación por backtest canónico).
- **Dependencia**: depende de CAND-03 y CAND-05 para volverse *medible* (hoy `aligned=0%` en EURUSD la hace unfalsiable). No depende de CAND-04 (ingeniería).
- **Decisión si positiva**: el motor HTF queda validado como fuente de edge → promoción a `engine/` ya consolidada, se documenta evidencia. Si negativa: el filtro HTF se reubica como sesgo teórico sin valor predictivo; se revisa la tesis.

#### CAND-03 — AUXILIAR — "¿Relajar el gate de alineación produce aligned>0?"
- **Pregunta científica**: ¿al relajar `aligned` (≥2/3 no NEUTRAL, sin contradicción) aparecen señales `aligned` donde el gate estricto da 0%?
- **Predicción cuantitativa**: `aligned_hit_pct > 0` post-relajación en EURUSD 113k M15.
- **Variable primaria**: `aligned_hit_pct` por TF.
- **Baseline**: `aligned_hit_pct = 0%` bajo gate estricto (CAND-02, ya medido).
- **Criterio de falsación**: si tras relajar sigue `aligned_hit = 0%`, el gate no era el cuello de botella (la causa es el mercado/otro parámetro).
- **Protocolo determinista**: cambiar `aligned` en `engine/bias/narrative.py` (snapshot del commit actual ANTES del cambio) + re-correr `scripts/measure_structure_effectiveness.py` con `SMCS_EFFECTIVENESS_MAX_BARS=113123`. **PRE-REQUISITO (ver G.4): congelar hash del motor actual antes de tocarlo.**
- **Datos necesarios**: EURUSD M15 113k (ya en repo).
- **Dominio REAL/FOREX**: REAL (descubrimiento) → FOREX (validación del cambio de motor).
- **Dependencia**: es auxiliar de CAND-11. Su resultado decide si CAND-11 es testeable.
- **Decisión si positiva**: habilita la prueba de CAND-11 (la tesis padre se vuelve falsable). Si negativa: se descarta el gate como cuello de botella y se investiga el sesgo en sí (acerca a CAND-04).

#### CAND-05 — AUXILIAR — "¿La alineación depende del símbolo?"
- **Pregunta científica**: ¿existe `aligned_hit > 0` en símbolos tendenciales (GBPUSD) donde EURUSD (rango) da 0%?
- **Predicción cuantitativa**: `aligned_hit_pct(GBPUSD) > 0` bajo el mismo gate que EURUSD.
- **Variable primaria**: `aligned_hit_pct` por símbolo.
- **Baseline**: `aligned_hit_pct(EURUSD) = 0%` (CAND-02).
- **Criterio de falsación**: si todos los símbolos dan `aligned_hit = 0%`, la alineación no es propiedad del régimen sino del gate (empuja a relajar gate = CAND-03).
- **Protocolo determinista**: `SMCS_EFFECTIVENESS_SYMBOL=GBPUSD` (ya soportado por runner) con mismos params; comparar contra EURUSD.
- **Datos necesarios**: GBPUSD M15 + HTF (~4.5 años) del repo.
- **Dominio REAL/FOREX**: REAL (descubrimiento en datos reales de otros símbolos).
- **Dependencia**: auxiliar de CAND-11; complementaria a CAND-03.
- **Decisión si positiva**: la tesis HTF es testeable en población GBPUSD → habilita CAND-11. Si negativa en todos: la alineación es artefacto de gate, no de mercado.

#### CAND-09 — INDEPENDIENTE — "¿POI anclado aporta más edge que POI no anclado?"
- **Pregunta científica**: ¿entradas sobre POI anclado (BOS/CHOCH padre cerrado) superan en WR/PF a POI no anclado?
- **Predicción cuantitativa**: `WR(anclado) - WR(no_anclado) > 0` y `PF(anclado) > PF(no_anclado)`.
- **Variable primaria**: WR/PF por grupo `poi["anchored"]`.
- **Baseline**: WR/PF del conjunto total de entradas (sin segmentar).
- **Criterio de falsación**: si `WR(anclado) ≈ WR(no_anclado)`, la ancla no aporta edge.
- **Protocolo determinista**: backtest canónico segmentando fills por `poi["anchored"]` (campo ya emitido por `engine/poi_anchor.py`); mismos params R6.4.
- **Datos necesarios**: los del repo (EURUSD etc. M15+HTF).
- **Dominio REAL/FOREX**: REAL (descubrimiento de la regla B1) → FOREX (validación).
- **Dependencia**: ninguna con HTF; rama propia.
- **Decisión si positiva**: la regla B1 queda validada empíricamente (hoy solo está implementada). Si negativa: la ancla es complejidad sin edge → candidata a simplificación.

#### CAND-10 — INDEPENDIENTE — "¿3 capas aportan más edge que 1-2 capas?"
- **Pregunta científica**: ¿la lectura top-down D1→H4→H1 mejora WR/PF vs single-TF o 2 capas?
- **Predicción cuantitativa**: `WR(3capas) > WR(1-2capas)` y `PF(3capas) > 1.0`.
- **Variable primaria**: WR/PF por configuración de capas.
- **Baseline**: WR/PF single-TF (M15 solo).
- **Criterio de falsación**: si `WR(3capas) ≤ WR(1-2capas)`, la jerarquía no aporta edge.
- **Protocolo determinista**: backtest A/B (top-down vs single-TF) con `build_context_stack` activo/desactivado; mismos params/costs/seed.
- **Datos necesarios**: los del repo.
- **Dominio REAL/FOREX**: REAL (descubrimiento de arquitectura B2) → FOREX.
- **Dependencia**: ninguna con HTF.
- **Decisión si positiva**: la jerarquía B2 queda validada. Si negativa: 3 capas = complejidad sin edge.

#### CAND-04 — INGENIERÍA — "¿El NEUTRAL perpetuo es defecto del empate 2-2?"
- **Pregunta científica**: ¿el empate 2-2 en `_bias_from_swings` anula el sesgo; un criterio de mayoría/ponderado lo restaura?
- **Predicción cuantitativa**: tras fix, % velas NEUTRAL baja de 100% y distribución BULLISH/BEARISH recupera sentido (aligned/against > 0).
- **Variable primaria**: % velas NEUTRAL antes vs después; conteo BULLISH/BEARISH.
- **Baseline**: T8 verificado: H4/H1 100% NEUTRAL en 18.436 eventos; D1 94% NEUTRAL.
- **Criterio de falsación**: si tras el fix el bias sigue 100% NEUTRAL, la causa no era el empate.
- **Protocolo determinista**: ya hay fix M1 (desempate por tramo reciente) en `engine/bias/narrative.py`; medir con `compute_htf_bias_series` sobre buffer real. **No requiere nuevo EXP de edge; es diagnóstico de motor.**
- **Datos necesarios**: EURUSD M15 20k (T8).
- **Dominio REAL/FOREX**: REAL (diagnóstico de implementación).
- **Dependencia**: ninguna con CAND-11 (no contamina prueba de edge).
- **Decisión si positiva**: el motor HTF queda correcto de base (pre-requisito para que CAND-03/11 midan sesgo real, no artefacto de bug). Si negativa: la causa es más profunda (quizá la propia noción de tramo).

### G.4 PRE-REQUISITO CRÍTICO (corrección de la 1ª pasada)

La 1ª pasada dijo "CAND-03 es barata de ejecutar". El Director corrige: **barato ≠ mejor HYP-001**, y
además **no se debe modificar `engine/bias/narrative.py` para probar CAND-03 sin congelar primero
la versión actual**. Si no se congela, el resultado mezcla efecto-de-hipótesis con efecto-de-cambio-
de-implementación, violando la regla de reconstruibilidad de 3B.

→ Por tanto, cualquier ejecución futura de CAND-03/04 exige: (a) `git rev-parse HEAD` del motor
actual como `results/experiments/.../run/commit`, (b) el cambio de `aligned` como diff versionado,
(c) re-corrida con el mismo commit base + el diff aplicado. Hoy NO se hace (solo auditoría).

### G.5 ADR-005 — DEUDA DE TRAZABILIDAD

ADR-005 ("REAL=descubrimiento, FOREX=validación") fue invocado por el Director en la orden de 3B.2
pero **NO EXISTE físicamente en el repositorio** (grep `ADR-005`/`ADR*` en `docs/` = 0). No se
inventa su contenido ni se convierte en evidencia. Se registra como **deuda de trazabilidad
arquitectónica**: una decisión conceptual usada para separar dominios, pero sin artefacto que la
respalden. Debe resolverse (crear el ADR o citar su fuente real) ANTES de que el laboratorio
dependa de la separación REAL/FOREX en un EXP-NNN. Mientras tanto, se aplica el criterio literal del
Director sobre la evidencia del repo.

### G.6 RECOMENDACIÓN RAZONADA DE HYP-001

Criterios del Director para HYP-001: que enseñe algo **fundamental sobre el edificio**, no la más
rápida de correr; y que no sea ingeniería (CAND-04 queda fuera).

- CAND-03 / CAND-05 son auxiliares, no HYP-001 (preparan a CAND-11).
- CAND-09 / CAND-10 son ramas válidas pero más acotadas (validan una regla concreta B1/B2).
- **CAND-11 es la TESIS PADRE**: si HYP-001 debe enseñar algo fundamental, es si el propio
  contexto HTF — corazón de la arquitectura ICT/SMC del motor — aporta edge real. Es la pregunta
  de la que cuelgan todas las demás de edge.

**Pero CAND-11 hoy NO es medible** (`aligned=0%` en EURUSD). Asignarla como HYP-001 sin antes
resolver la falsabilidad produciría una hipótesis bonita pero unfalsiable en la práctica.

**Recomendación**: HYP-001 debería ser **CAND-11 (tesis padre)**, PERO su primer EXP-NNN no puede
correr hasta ejecutar primero las auxiliares CAND-03 y CAND-05 (que habilitan `aligned>0`). Es
decir: HYP-001 = la tesis; su plan de experimentación declara explícitamente que CAND-03 y CAND-05
son experimentos preparatorios obligatorios. Esto evita (a) elegir la candidata "barata" y (b)
mezclar ingeniería con edge.

Alternativa si el Director prefiere arrancar por una rama independiente medible ya: CAND-09 o
CAND-10 (reglas ya implementadas, backtest segmentado directo, sin depender del gate). Pero eso
enseña menos sobre el edificio central que CAND-11.

**Veredicto (AUTORIZADO 2026-08-10): HYP-001 = CAND-11**, con CAND-03 y CAND-05 como
experimentos auxiliares obligatorios de habilitación en su plan. Materializada en
`research/hypotheses/HYP-001/hypothesis.md` + `status.yaml` (estado: formulada).
La prueba padre (EXP-001) queda PROHIBIDA hasta resolver los auxiliares y congelar
el hash del motor (ver G.4). Sin commit/push (orden del Director).

### G.7 Estado de esta 2ª pasada

- Separación edge / ingeniería / auxiliar / independiente: hecha (G.1, G.2).
- Re-evaluación CAND-03/04/05/11: hecha (G.1, G.3, G.4).
- Campos completos (predicción/baseline/variable/protocolo/datos/dominio/dependencia/decisión): en G.3.
- ADR-005: registrado como deuda (G.5).
- Jerarquía + recomendación: en G.2, G.6.
- **Sin HYP-001 asignada. Sin EXP. Sin tocar Python. Sin ejecutar.** Solo este documento actualizado.

*Fin de la 2ª pasada científica (3B.2). Pendiente de autorización del Director para asignar HYP-001.*

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

# PROPUESTA — Brecha A1 real: 3 capas HTF en el motor único (sin 2do cerebro)

**Fecha:** 2026-07-20
**Autor:** Hermes (propuesta, NO implementada)
**Estado:** BORRADOR para revisión de Ruben. No toca producción (regla Fase 0 / R2).
**Ancla:** `docs/ict/SPEC_TESIS_FORMAL.md` §1/§9, `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md` §0 #2,
`docs/plan/ETAPA_4_FASE_C_PLAN.md` §1-§2 (un solo cerebro), `ict_backtest/v2/context_mtf.py:136` (gate ya existe).

---

## 0. CONTEXTO — por qué esto, y no "PlanFSM como cerebro de dirección"

Auditoría previa (`AUDITORIA_PLANFSM_CEREBRO.md`) descartó convertir al PlanFSM en un
"cerebro de dirección": violaría el contrato de no invasión de la Fase C
("un solo cerebro. C es capa de CONTEXTO, no de decisión") y la regla "no 2do cerebro".

La tesis real (libro 18 §0, SPEC §1/§9) dice:
- El HTF (D1/H4/H1) DICTA el sesgo como filtro top-down.
- El motor único (R7 = run_sequence) DECIDE el setup dentro de ese filtro.

O sea: la dirección no se "delega a un FSM nuevo". Se FILTRA en el motor único. Eso es
lo que la Brecha A1 ("3 capas reales") exige y lo que hoy NO hace run_sequence (saca la
dirección solo de H4, `sequence.py:380`).

---

## 1. HALLAZGO CLAVE — el gate ya existe, solo está desconectado

`ict_backtest/v2/context_mtf.py:136` ya implementa:

```python
def top_down_allows_trade(
    stack: dict[str, Any],
    direction: int,
    *,
    require_d1: bool = True,
    require_h4: bool = True,
    require_h1: bool = True,
    require_pd: bool = True,
    counter_trend: bool = False,
) -> tuple[bool, str]:
    """Gate: D1 → H4 → H1 → PD. Returns (ok, reason)."""
```

- Toma el `stack` (D1/H4/H1/dealing) y la `direction` propuesta por el setup.
- Devuelve `(ok, reason)`: ok=False con motivo (`d1_against_long`, `h4_ranging`, etc.)
  si el setup no coincide con el sesgo HTF.
- Soporta `counter_trend=True` (para Turtle Soup: trade contra D1, ver SPEC §18).
- Es puro, cerrado-only (usa `build_context_stack`), sin look-ahead.

ESTÁ SOLO EN EL MOTOR v2 LEGACY (no versionado, marcado no reproducible en R6). El motor
canónico (run_sequence / canonical) NO lo llama. Por eso el motor "piensa en H4→M15".

Cerrar la Brecha A1 = cablear `top_down_allows_trade` al motor canónico como FILTRO de
dirección, NO escribir lógica nueva de dirección.

---

## 2. DISEÑO DE CABLEADO (propuesta, no implementada)

### 2.1 Dónde se enchufa
En `run_sequence` (sequence.py), tras calcular `direction` desde H4 (l.380) y ANTES de
confirmar el entry:
- Construir `stack` desde `MultiTFContext` (ya disponible vía `multitf_context.py`,
  cerrado-only) para D1/H4/H1/dealing.
- Llamar `ok, reason = top_down_allows_trade(stack, direction, counter_trend=...)`.
- Si `ok=False` → el setup no opera (se registra `reason` para diagnóstico/fidelidad).
- Anotar `ICTSignal.htf_aligned = (ok, reason)` (bonus de contexto, NO cambia conteo base
  salvo que se quiera vetar; ver §3).

### 2.2 Para qué setups
- PO3 / a-favor (`counter_trend=False`): exige D1/H4/H1 alineados con `direction`.
- Turtle Soup (`counter_trend=True`, SPEC §18): exige dirección CONTRA D1/H4.

### 2.3 Anti-look-ahead
`build_context_stack` y `MultiTFContext` ya son cerrado-only (R6). El `stack` se reconstruye
con barras ≤ t. Sin OHLC futuro.

### 2.4 Sin 2do cerebro
run_sequence sigue siendo el ÚNICO que decide entry/SL/TP. `top_down_allows_trade` solo
responde "¿este setup coincide con el sesgo HTF?". No genera señal, no redefine dirección,
no toca SL. Cumple el contrato de no invasión de la Fase C (R1-R2).

---

## 3. MODO DE APLICACIÓN (decisión de ingeniería, requiere OK de Ruben)

Dos opciones, ambas respetan "un solo cerebro":

- **Opción A (filtro duro):** `ok=False` → no opera. Cierra A1 como gate real. Riesgo:
  como el POI duro (A'' PF 0.900), un filtro direccional duro PUEDE matar señales si el
  stack H4/H1 no coincide con la dirección M15 legítima. Hay que medir conteo primero.
- **Opción B (anotación + bonus, recomendada para arrancar):** `ok/ reason` se anota en
  `ICTSignal.htf_aligned` y alimenta `quality_score` (igual que la Fase C). El motor corre
  IGUAL. Permite medir, en fidelidad (no PF), cuántos setups M15 ya coincidían con HTF vs
  cuántos no. Sin matar señales. Cumple R1 (no altera conteo).

Recomiendo **Opción B para el primer paso** (igual filosofía que Fase C), y solo si el
análisis de fidelidad lo justifica, evaluar Opción A como knob configurable APAGADO por
default (nunca en producción sin OK).

---

## 4. POR QUÉ NO ES "A1 Nivel 2 ya cerrada"

El cronograma marca "A1 Nivel 2 CERRADA (Opción B)" pero eso es la compuerta de
EJECUCIÓN del PlanFSM (`plan_gate`, umbral STRUCTURE_OK) — veta señales que no maduraron.
NO es la Brecha A1 de "3 capas reales en el motor" (D1/H4/H1 decidiendo filtro). Son
dos cosas distintas que el cronograma aplana bajo el mismo nombre. Esta propuesta cierra
la Brecha A1 FUNCTIONAL; A1 Nivel 2 era solo la compuerta de madurez.

---

## 5. VERIFICACIÓN (cuando se implemente, bajo tu gobernanza)

1. TDD RED→GREEN: test que `top_down_allows_trade` con stack BULLISH D1/H4/H1 + direction>0
   devuelve ok; con D1 BEARISH + direction>0 devuelve `d1_against_long`.
2. Call site real: parchear `run_sequence` y correr `scripts/diag_etapas.py` con datos
   chicos (800-1500 velas) — NO backtest de PF (bloqueado hasta Fase G).
3. Métrica de aceptación = FIDELIDAD (checklist §5 del roadmap maestro): % de setups M15
   que ya coincidían con HTF antes/después de anotar. NO PF.
4. Demo sintética (sin parquet): un setup M15 long con D1/H4/H1bullish pasa; uno con D1
   bearish se anota `d1_against_long` y (Opción A) se veta.

---

## 6. TRAZABILIDAD

- SPEC §1 (Narrativa HTF), §9 (3 capas), §18 (Turtle Soup counter_trend).
- Libro 18 §0 #2 (HTF manda sobre LTF, top-down).
- ROADMAP_TESIS_DRIVEN_2026-07-17.md §9 (Brecha A1 = OBLIGATORIO, fase B2).
- ROADMAP_CAPACIDADES.md §3 (3 capas reales A1 = Pendiente).
- ETAPA_4_FASE_C_PLAN.md §1-§2 (un solo cerebro, C = contexto no decisión).
- Código: `ict_backtest/v2/context_mtf.py:136` (gate ya existe, legacy);
  `ict_backtest/sequence.py:380` (run_sequence saca dirección de H4 hoy);
  `ict_backtest/multitf_context.py` (stack cerrado-only ya disponible).

---

## 7. PENDIENTE (no hecho)

- [ ] OK de Ruben sobre Opción A vs B.
- [ ] Firma de Fase 0 (SPEC_TESIS_FORMAL sigue DRAFT) antes de implementar — tu regla R1.
- [ ] Escribir los MDS (`docs/specs/*.md`) por componente que exige R2 (hoy NO existen).
- [ ] Implementar cableado en run_sequence (tras OK + Fase 0 firmada).

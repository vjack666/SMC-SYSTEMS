# FASE 4 — DECISIÓN ARQUITECTÓNICA: IDENTIDAD Y LINAJE CAUSAL DEL SETUP

**Fecha:** 2026-08-11 · **Autor:** CEO Hermes (diseño; SIN modificar engine/)
**Hipótesis de auditoría offline (Arquitectura B): FALSADA en Fase 3** (77% AMBIGUOUS / 35 setups).
**Regla:** AUDITAR → DIAGNOSTICAR → DECIDIR → MODIFICAR → VALIDAR. Modificación NO autorizada aún.

---

## 1. ESTADO ACTUAL DE LA ARQUITECTURA (evidencia del repo)

Lectura de `engine/sequence.py`, `engine/expediente.py`, `engine/market_object.py`, `engine/fvg_poi.py`.

- `SequenceState` (sequence.py L89-107): `phase, direction, sweep_idx, displace_idx, bos_idx,
  bos_level, zone_high, zone_low, zone_pd_type, zone_authority, htf_aligned, poi_present,
  expediente`. **Sin id/parent_id por evento.** Sí conserva niveles de BOS y zona POI (no emitidos).
- `Expediente` (expediente.py): `id` (hash señal), `phase_events: list[PhaseEvent]`.
  `PhaseEvent` (L29-44): `phase, idx, time, condition` — **sin id ni parent_id ni nivel de precio**.
  Guarda anti-look-ahead YA EXISTE: `advance()` exige `idx >= _last_idx` (expediente.py L99-112).
- `MarketObject` (market_object.py L49-75): **YA EXISTE EN engine/** con `id` (uuid), `symbol`,
  `type, origin_tf, role, direction, zone_high, zone_low, creation_time, state, meta,
  parent_object, related_objects, bar_index, bar_time`. **El motor NO lo popula para
  sweep/displacement/bos** (solo lo usa como tipo en `_touches_zone`). `engine/sequence.py:50`
  lo importa de `engine.market_object` (no de `ict_backtest`). `ict_backtest/market_object.py`
  es solo un shim/re-export — la fuente única es `engine.market_object`.

**Conclusión de estado:** hay trazabilidad *temporal* (índices en cascada + Expediente con guarda
anti-look-ahead), pero **no identidad causal de objetos**: los eventos no tienen `id`/`parent_id`,
no se crean `MarketObject` enlazados, y la señal emitida descarta `zone_high/zone_low` y niveles de
sweep/displacement que `SequenceState` sí posee.

---

## 2. RESULTADO DE FASE 3 (incorporado)

B falsada: 35 setups EURUSD M15, UNIQUE 11% / AMBIGUOUS 77% / NONE 31%. Unión más frágil
BOS→POI (≥2 candidatos en 50-60%). La reconstrucción post-hoc por proximidad no demuestra
causalidad: proximidad ≠ causalidad. **La identidad debe existir en el instante del evento.**

---

## 3. MODELO CAUSAL PROPUESTO (tesis ICT/SMC, sin reglas nuevas)

Cada transición = evento hijo que CITA al evento padre YA CERRADO en su mismo instante.

| Transición | Significado causal | Evidencia OHLC |
|---|---|---|
| LIQUIDITY → SWEEP | Cluster BSL/SSL (stops). El sweep lo toma (stop-hunt) y cierra adentro en la MISMA vela (CRIT §6). | mecha rompe swing high/low; close vuelve adentro. |
| SWEEP → DISPLACEMENT | Tras barrer, precio se aleja con cuerpo >70% rango en dir setup (impulso institucional M del PO3). | `|close−open|/(high−low) > 0.70`, mecha corta a favor. |
| DISPLACEMENT → BOS/CHOCH | El cuerpo rompe estructura: BOS en continuación, CHOCH en reversión. | cierre supera swing high/low previo. |
| BOS/CHOCH → POI | El POI (FVG/OB) queda anclado al evento que originó la ruptura (FVG más cercano anterior en dir del BOS — ver `fvg_poi.fvg_for_bos`). | zona FVG/OB entre sweep y BOS. |
| POI → RETURN | El retorno al POI completa el setup (mitigación de la zona). | precio toca `zone_high/zone_low`. |

---

## 4. MODELO DE OBJETOS/EVENTOS PROPUESTO

Cada evento = un `MarketObject` con `id` propio + `parent_object` = id del evento padre.
Tipo por evento: `LIQUIDITY | SWEEP | DISPLACEMENT | BOS | CHOCH | POI | RETURN`.
El `Expediente` ya existe y se conserva (bitácora inmutable); solo se le añade el grafo.

---

## 5. GRAFO DE LINAJE

```
LIQUIDITY(id=L) --sweep_takes--> SWEEP(id=S, parent=L)
   S --precedes--> DISPLACEMENT(id=D, parent=S)
   D --breaks--> BOS/CHOCH(id=B, parent=D)
   B --anchors--> POI(id=P, parent=B)        # FVG/OB en dir, entre S y B
   P --mitigates--> RETURN(id=R, parent=P)
```
Cada flecha = `child.parent_object == parent.id`, resuelta en el instante del evento (no post-hoc).

---

## 6. CONTRATO MÍNIMO DE IDENTIDAD (por evento)

`id | parent_id | timestamp | timeframe | direction | event_type | level | child_id |
 evidencia_OHLC | state | invalidation | causal_link`.

---

## 7. QUÉ DEBE ALMACENAR `MarketObject` (ya existe; completar)

Añadir por evento: `parent_object` (ya existe, hoy None), `related_objects` (ya existe),
`creation_time = bar_time`, `zone_high/zone_low` del nivel del evento (sweep mecha, displacement
body, BOS nivel, POI zona), `direction`, `origin_tf`. **No** añadir ATR ni indicadores.

## 8. QUÉ DEBE ALMACENAR `Expediente` (ya existe; completar)

`PhaseEvent` gana: `event_id` (uuid del MarketObject de ese evento) y `parent_event_id`.
Conservar `phase, idx, time, condition`. El grafo queda en `phase_events` + `event_id/parent_event_id`.

## 9. QUÉ DEBE ALMACENAR `SequenceState`

Añadir: `sweep_id, displace_id, bos_id, poi_id` (uuid de los MarketObject creados). Conservar
niveles ya existentes. La señal emitida DEBE incluir `zone_high/zone_low` y niveles de
sweep/displacement (DERIVABLE desde OHLC por índice) para que el auditor no los re-derive.

---

## 10. CÓMO SE RELACIONAN LOS EVENTOS

En `run_sequence_traced`, en el instante que se confirma cada fase (vela ya cerrada):
1. Crear `MarketObject` del evento con `id=uuid`, `parent_object=id_del_padre_ya_cerrado`.
2. `SequenceState.xxx_id = id`; `Expediente.advance(phase, idx, time, condition)` + registrar
   `event_id/parent_event_id`.
3. La guarda anti-look-ahead existente impide índices futuros.

## 11. CANDIDATOS MÚLTIPLES

El motor YA decide UN evento por fase (un displacement único entre sweep y BOS; un BOS por ruptura).
Por tanto NO hay ambigüedad en formación — el `parent_object` es determinista por construcción.
La ambigüedad de Fase 3 venía de reconstruir post-hoc; con id enlazado DESAPARECE (OBSERVABLE).

## 12. EVITAR LOOK-AHEAD

`parent_object` apunta a un evento YA registrado (`idx <= _last_idx`). El evento hijo se etiqueta
con el id del padre en el MISMO barrido de vela donde se confirma el hijo, usando solo datos
cerrados. La guarda `advance(idx >= _last_idx)` lo blinda. No se lee precio futuro.

## 13. SETUP INCOMPLETO

`outcome = "OPEN"` (ya existe en Expediente) + fases alcanzadas parciales. El auditor marca las
uniones faltantes UNKNOWN. No se fuerza PASS.

## 14. SETUP INVALIDADO

`Expediente.invalidate(idx, reason)` ya existe (L114-127): añade `PhaseEvent("INVALID")` y marca
`outcome="INVALID"`. El linaje se corta: el auditor marca la unión rota INVALIDATED.

## 15. DOS SETUPS SIMULTÁNEOS

Cada `run_sequence` maneja UNA secuencia por barrido; setups paralelos = expedientes distintos con
`id` distinto (hash symbol|tf|birth_idx|dir). No colisionan: el `MarketObject.id` es uuid, no hash.

## 16. QUÉ NO DEBE AÑADIRSE AL MOTOR

- ATR / RSI / EMA / cualquier indicador para "arreglar" trazabilidad (ley arquitectónica).
- Macro/News: capa de CONTEXTO aparte, no filtro de setup (regla del Director).
- Score de calidad de POI: es del backtester/auditor, no del motor de decisión.
- Predicción de resultado: WR/PF/edge bloqueados hasta FORMACIÓN validada.

## 17. CAMBIOS DE CÓDIGO NECESARIOS (Arquitectura A — SOLO diseño, no ejecutado)

1. `engine/sequence.py`: en cada confirmación de fase, crear `MarketObject` con `id`+`parent_object`
   y guardar `xxx_id` en `SequenceState`; pasar `event_id/parent_event_id` a `_advance_expediente`.
2. `engine/expediente.py`: `PhaseEvent` gana `event_id`, `parent_event_id`.
3. `engine/sequence.py` señal emitida: incluir `zone_high/zone_low` + niveles sweep/displacement.
4. (Sin nuevo módulo; `MarketObject` ya existe en engine/).

## 18. RIESGOS DE MODIFICAR EL MOTOR

- Regresión de la ÚNICA fuente de decisión (Ley Fundamental): cualquier bug en la creación de ids
  contamina señales en vivo. Mitigación: ids son puros (uuid + parent ya cerrado), sin rama nueva.
- Acople auditoría→motor: el motor pasaría a cargar preocupación de trazabilidad. Mitigación: el
  grafo es un subproducto barato de lo que el motor YA decide (1 evento por fase).
- Ruptura del backtester canónico: `run_sequence_traced` conserva firma `(signals, phase_seen, expedientes)`;
  añadir campos a la señal es aditivo y no rompe consumidores.

## 19. ALTERNATIVAS CONSIDERADAS

- **B (reconstrucción offline):** FALSADA en Fase 3 (77% ambiguo). Descartada para DEMOSTRAR
  formación; útil solo como fallback RECONSTRUCTED cuando no haya id.
- **Híbrida (ids parciales + reconstrucción donde falte):** aceptable transicionalmente, pero
  introduce dos caminos de verdad. No recomendada como objetivo final.
- **No hacer nada:** ilegible causalmente. Descartada.

## 20. DECISIÓN RECOMENDADA: ARQUITECTURA A

Por evidencia (Fase 3 demostró que B no alcanza) y porque el coste es bajo: `MarketObject` YA
existe en `engine/` con los campos necesarios. A = motor conserva ids enlazados en el instante del
evento. Esto convierte 100% de uniones de AMBIGUOUS→OBSERVABLE (el motor ya elige 1 evento por fase).
NO se toca `engine/` hasta autorización expresa de la fase de MODIFICACIÓN.

## 21. CRITERIOS DE FALSACIÓN DE A

A es falsable si, tras implementarse:
- algún `child.parent_object` apunta a un evento con `idx > child.idx` (look-ahead) → rechazar;
- algún `parent_object` es None en una fase que debería tener padre → rechazar;
- el auditor sigue marcando >5% AMBIGUOUS en 50 setups → la ambigüedad no era solo post-hoc.

## 22. PLAN DE VALIDACIÓN POSTERIOR (fase MODIFICACIÓN, tras autorización)

1. Implementar §17 en `engine/` + tests unitarios de `MarketObject`/`Expediente`.
2. Re-correr el auditor (Fase 3 `b_falsifiability.py` adaptado) sobre 50 setups: esperar UNIQUE≈100%.
3. Cerrar GAP-1 macro (fuente con timestamp) como capa de CONTEXTO, no filtro.
4. Solo entonces: OOS/OTC → ESTADÍSTICA → EDGE. WR/PF siguen bloqueados hasta (3).

---

**CIERRE DE FASE 4:** se responde la pregunta del Director — *"¿qué información debe tener el motor
en memoria en el instante de cada evento para demostrar meses después el linaje?"*: los `MarketObject`
con `id`+`parent_object` por evento (sweep→displacement→bos→poi→return), guardados en `SequenceState`
y expuestos en `Expediente`, sin look-ahead. Diseño entregado; modificación pendiente de autorización.

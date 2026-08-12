# HYP-002 M4 — Auditoría de continuidad operacional del mercado

**Estado:** CERRADA (todas las auditorías PASS; deuda fuera de alcance documentada)
**Fecha:** 2026-08-12
**Motor auditado:** `engine/sequence.py` (consumidor puro; el lab NO contiene lógica de decisión)
**Autor del lab:** Hermes (autónomo, directiva Ruben: una sola misión, un solo informe)
**Fuera de alcance (por directiva):** estadística / WR / PF / edge, Macro/News,
concurrencia de setups en el mismo lane (arquitectura single-lane).

---

## 1. Veredicto

**M4 — APROBADA.** El sistema mantiene una representación operacional correcta
de un mercado continuo a través de: reinicios múltiples (crash+resume), gaps,
velas duplicadas, fuera-de-orden, cambio de sesión (flip de sesgo + reset),
lifecycle de setups (nacen / mueren) y determinismo post-recuperación.

Ningún defecto dentro de alcance requirió modificar el motor. Se documenta UNA
deuda de contrato (no bug) que pertenece al adaptador real de feed, no al motor.

---

## 2. Lo que se construyó (laboratorio)

`research/hypotheses/HYP-002/functional_replay/operational_continuity_battery.py` — consumidor puro del motor (FUERA de ict_backtest/, arquitectura M4):

- `FeedAdapter`: simula la entrega operacional de velas (gaps, duplicados,
  fuera-de-orden, drops) sobre un feed base de `MarketObject` (CANDLE).
- `run_session(...)`: dirige el motor barra-a-barra desde el adaptador y
  persiste `SequenceState` en cada barra (snapshot por barra = simulación de
  "guardar estado en cada tick").
- `_resume_session(...)`: simula N crashes — en cada corte guarda snapshot,
  cae la conexión, y reconecta reanudando con el estado restaurado.
- `audit_*`: 7 auditorías por escenario.
- `run_all()`: orquestador; escribe `lab_report_m4.json`.

Tests: `tests/test_operational_continuity.py` — 10 tests e2e, todos PASS.

---

## 3. Resultados de las 7 auditorías

| # | Auditoría | Resultado | Nota |
|---|-----------|-----------|------|
| 1 | Continuous baseline | 2 señales (no trivial) | grafo causal bien formado (LIQUIDITY→…→CONTRACT) |
| 2 | **Multi-restart** (2 crashes, cuts 15/35) | PASS | resumed_n=2 == continuous_n=2; causal_graphs_equal=True |
| 3 | Gaps (barras faltantes) | PASS | n_signals=2 (el motor no depende de barras contiguas para señalar) |
| 4 | Duplicados | PASS | no_duplicate_signals=True (indexa por bar_index absoluto) |
| 5 | Fuera-de-orden | PASS* | comportamiento definido (no crash); ver deuda §4 |
| 6 | Cambio de sesión (BULLISH→BEARISH→RANGING) | PASS | resetea en RANGING, flip de dirección objetivo |
| 7 | Lifecycle (nacen / mueren) | PASS | 2 nacen; el que muere resetea sin emitir |
| 8 | **Determinismo post-recuperación** | PASS | run1==run2==continuous (grafo causal) |

`* PASS` = comportamiento definido y documentado; no es un fallo del motor.

---

## 4. Deuda fuera de alcance (documentada, NO se cambia la tesis)

### 4.1 — Normalización fuera-de-orden es responsabilidad del adaptador real
El motor indexa por `bar_index` del objeto, pero su memoria de contexto
(`CTX_WINDOW`) asume un feed cronológicamente ordenado. Un feed fuera-de-orden
corrumpe la ventana de contexto. **El adaptador real DEBE ordenar el feed antes
de entregarlo al motor.** No se corrige en M4 (sería cambiar el contrato del
motor y regresionar M3); es deuda del adaptador de feed en vivo.

### 4.2 — Persistencia usa índices ABSOLUTOS del feed (contrato M3)
`SequenceState` guarda `sweep_idx`, `bos_idx`, etc. como posiciones ABSOLUTAS
del feed. Por diseño (M3), el adaptador de reanudación debe entregar el FEED
COMPLETO y reanudar con `start_i = última vela ya procesada`. Un adaptador que
entregue SLICES incrementales (sin el feed completo en buffer) invalidaría los
índices. El adaptador real debe (a) retener el buffer completo, o (b) de-duplicar
señales por `entry_at`. Esto quedó demostrado y documentado en el lab; no es un
bug, es el contrato de reanudación.

### 4.3 — El motor es detector de pasada única (single-pass)
Tras cada ENTRY el motor hace `state.reset()` y re-detecta. Por eso la señal
recuperada tras N crashes es la UNION de los tramos, de-duplicada por `entry_at`,
y coincide con la corrida continua. Esto es correcto para replay/backtest y para
un adaptador que re-feedea el buffer completo; se documenta para el diseño del
adaptador en vivo.

### 4.4 — Concurrencia de setups en el mismo lane
La arquitectura es single-lane: un setup a la vez por instancia de `run_sequence`.
Setups simultáneos en el mismo TF no están soportados por diseño. Fuera de
alcance de M4 (requeriría cambio de arquitectura, no de tesis).

---

## 5. Lo que M4 NO tocó (disciplina mantenida)

- NO se abrió estadística, WR, PF ni edge.
- NO se tocó Macro/News.
- NO se modificó `engine/` (el lab es consumidor puro).
- `run_sequence` legacy intacto; `run_sequence_traced` 4-tuple ya auditado en
  M3-follow-up (consumidores de research corregidos a 4-tuple).

---

## 6. Evidencia

- `research/hypotheses/HYP-002/artifacts/m4_stdout.txt` — salida JSON de `run_all()`.
- `research/hypotheses/HYP-002/artifacts/lab_report_m4.json` — copia estructurada.
- `tests/test_operational_continuity.py` — 10 tests e2e (todos PASS).

---

## 7. Conclusión para la siguiente fase

El edificio ahora demuestra:

```
¿sabe qué ocurrió?        SÍ (M1/M2)
¿sabe quién causó qué?    SÍ (M1/M2)
¿lo ve vela-a-vela?       SÍ (M3)
¿sobrevive reinicio?      SÍ (M3)
¿representación operacional
 continua y correcta?     SÍ (M4)
```

Estamos posicionados para medir edge sabiendo que el motor se comporta como un
sistema de mercado y no como una función que procesa un DataFrame. La siguente
fase (estadística) puede proceder con la disciplina operacional validada.

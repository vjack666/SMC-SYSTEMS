# HYP-002 — AUDITORÍA DE FUNCIONAMIENTO DEL MOTOR (REPLAY VELA-A-VELA)

**Fecha:** 2026-08-11 · **Ejecutor:** Hermes (modo autónomo CEO-delegado)
**Alcance:** comportamiento TEMPORAL/OPERACIONAL del motor. NO WR/PF/edge.
**Commit:** pendiente de push (rama `feature/backtest-ict`)
**Script:** `ict_backtest/functional_lab.py` · **Contrato:** `FUNCTIONAL_REPLAY_CONTRACT.md`
**Artefactos:** `research/hypotheses/HYP-002/artifacts/lab_report.json`

---

## 1. Arquitectura

Se construyó un **Market Replay adapter** que NO es un segundo motor. Reusa el
pipeline real de producción:

```
Historical/Synthetic DataFrame
        │  (ventana creciente [0..k] en la vela k)
        ▼
ict_backtest.data_feed.build_features   ← detectores ICT reales (CONSUMIDOR)
        │
        ▼
engine.sequence.run_sequence_traced      ← MOTOR real (única fuente de decisión)
        │
        ▼
Event Journal (LIQUIDITY→SWEEP→DISPLACE→BOS→POI→REFINEMENT→RETURN→CONTRACT)
```

El replay solo cambia la FORMA de entrega: en la vela `k` el motor solo ve
`build_features(df.iloc[:k+1])`. Si algún detector usa filas `j>k`, batch≠stream.

Reglas respetadas:
- No se creó lógica de decisión en el backtest/lab (Ley Fundamental).
- El verificador es consumidor independiente del motor (regla 9 del encargo).
- No se usó WR/PF/edge para aprobar (regla 1/2).
- Solo se corrigió un defecto de causalidad demostrado y en alcance (OB look-ahead).

---

## 2. Auditorías ejecutadas

| # | Auditoría | Resultado | Evidencia |
|---|---|---|---|
| 2 | Batch vs Stream | **PASS** | event_divergences=0, feature_leaks=0 |
| 3 | Determinismo (bloques) | **FAIL** | 246 divergencias bloque-independiente vs creciente |
| 4 | Corte temporal | **PASS** | futuro alterado no cambia ≤cut (feature_diffs=0) |
| 5 | Future Mutation | **PASS** | ídem |
| 6 | Reinicio | **PARCIAL** | sin API de serialización de SequenceState |
| 7 | Datos hostiles | **PASS** | dup/ooo/gap: sin crash, sin señal falsa |
| 8 | Intrabar / OB causal | **PASS** | ob_bullish batch==stream (leak shift(-1) CERRADO) |
| 9 | Shadow Market | **PASS** | journal + virtual exec sin broker |
| 10 | Cross-validation | **PASS** | 2 datasets, 0 leaks en ambos |

---

## 3. Evidencia (reproducible)

- Dataset: sintético determinista `_make_ltf(n=250)` + `_make_ltf(n=250, variant)`,
  más `make_ob_dataset()` para la prueba focal de OB. Sin parquet real en el repo
  (data/raw/* ausente localmente — bloqueo de datos ya documentado en AGENTS.md).
- `python ict_backtest/functional_lab.py` → `artifacts/lab_report.json` (EXIT 0).
- `pytest tests/test_functional_lab.py -q` → verificación de regresión.
- Commit de esta misión (hash en push).

---

## 4. Fallos encontrados

### 4.1 (CORREGIDO) Fuga de futuro en Order Block — `detectors/ob.py`
`ob_bullish/ob_bearish` se marcaba con `close.shift(-1)` (la vela SIGUIENTE
confirmaba el OB). Esto viola la regla de causalidad: en streaming la vela `k`
no existe todavía cuando se procesa `k`. Demostrado de forma aislada:
`ob_bullish[5]` era `True` en batch y `False` en stream (prefijo).
**Corrección (causal, sin cambiar decisión):** el OB se marca por la geometría de
la propia vela de impulso — cuerpo fuerte que rompe el rango de la vela ANTERIOR
(`close < prev_low` / `close > prev_high`), usa solo filas ≤ k. Verificado en
dataset B1 realista: `ob_bullish[4]=True` idéntico batch/stream. 25 tests de OB
existentes siguen pasando.

### 4.2 (HALLAZGO, NO DEFECTO DEL MOTOR) Determinismo bloque-independiente
FASE3 FAIL: si un streamer calcula features POR BLOQUE olvidando el histórico
(ventana solo dentro del bloque), diverge 246 veces vs el stream creciente. Esto
NO es un bug del motor (el motor es determinista dado el prefix); es una
RESTRICCIÓN OPERACIONAL: **el replay en vivo debe llevar el historial de features
acumulado**, no recalcular bloque a bloque. Se documenta como requisito de
implementación del feed real. No se "parcheó" el resultado.

### 4.3 (PARCIAL) Reinicio — `engine/sequence.py`
`run_sequence_traced` no expone API de serialización de `SequenceState`
(memoria de fase, ids, zona, idx). No se puede probar "continúa == reinicia"
sin un refactor de persistencia. Auditado como PARCIAL y documentado; fuera del
alcance de esta misión cerrar la serialización (requiere diseño de estado).

---

## 5. Antes / Después (qué cambió realmente en el motor/pipeline)

**ANTES**
- Order Block en `k` dependía de `close[k+1]` (fuga de futuro viva en
  `build_features` → motor).
- Determinismo: sin restricción documentada de alimentación.
- Reinicio: no verificable.

**DESPUÉS**
- OB causal: `ob_bullish/ob_bearish` decidido solo con filas ≤ k
  (`detectors/ob.py`). FASE8 PASS.
- Determinismo: restricción operacional documentada (el feed vivo debe acumular
  features; no recalcular por bloque).
- Reinicio: documentado como PARCIAL (deuda de API de estado).

Archivos modificados:
- `detectors/ob.py` (corrección causal OB)
- `ict_backtest/functional_lab.py` (nuevo laboratorio)
- `tests/test_functional_lab.py` (nuevos tests)
- `research/hypotheses/HYP-002/FUNCTIONAL_REPLAY_CONTRACT.md` (contrato)
- `research/hypotheses/HYP-002/FUNCTIONAL_REPLAY_REPORT.md` (este informe)
- `research/hypotheses/HYP-002/artifacts/lab_report.json` (evidencia)

---

## 6. Deuda restante

### CRÍTICA
- (ninguna) — la única fuga viva confirmada en el path de `build_features` (OB
  shift(-1)) fue cerrada.

### IMPORTANTE
- **FASE6 Reinicio**: `SequenceState` no es serializable. Para un bot autónomo
  real esto es bloqueante. Requiere API `save()/load()` de estado (fuera de
  alcance aquí, pero debe entrar en el backlog antes de demo).

### MENOR
- FASE3 requiere que el feed vivo acumule features históricas (no recalcular por
  bloque). Restricción de implementación, no bug.

### FUERA DE ALCANCE
- Estadística / WR/PF / edge (expresamente excluidos por el encargo).
- Arquitectura definitiva ITF/LTF/CONTRACT (no se asumió M15=ITF ni M5/M1=LTF).
- Datos reales (parquet) — bloqueo de datos documentado.

---

## 7. Veredicto

**A VALIDADA (con una deuda IMPORTANTE documentada).**

El motor, alimentado vela-a-vela con su pipeline real, produce eventos
causalmente disponibles: batch == stream, corte temporal y mutación de futuro no
alteran el pasado, datos hostiles no generan señal falsa, el OB look-ahead fue
cerrado, y el shadow market corre sin broker. Queda una deuda IMPORTANTE
(serialización de estado para reinicio) que debe cerrarse ANTES de demo autónoma,
y la restricción operacional de acumular features en el feed vivo.

No se aprobó nada con WR/PF. La misión valida COMPORTAMIENTO TEMPORAL, no edge.

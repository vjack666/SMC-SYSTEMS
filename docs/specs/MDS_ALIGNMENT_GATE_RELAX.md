# MDS — Relajación del gate de alineación HTF

> **Estado: ✅ IMPLEMENTADO** — el gate relajado YA vive en el motor
> (`engine/bias/narrative.py`, propiedad `HtfBias.aligned`, camino B del
> 2026-08-08). Este documento se reconcilió con el código real (regla §9g-c).

## 1. Objetivo

Hacer operable el filtro D1→H4→H1 en datos reales. Hoy el gate exige `D1 == H4 == H1 != NEUTRAL`, lo que produce `aligned_hit = 0%` en EURUSD 113k M15. Sin alineación, el laboratorio no puede medir si el sesgo HTF aporta edge.

Este MDS relaja la definición a “sin contradicción mayor / al menos 2 de 3 no NEUTRAL”, manteniendo la restricción de no importar lógica de decisión al motor.

---

## 2. Alcance

### 2.1 Dentro
- Cambio de `aligned` en `compute_htf_bias_series()` / `compute_htf_bias()` (`engine/bias/narrative.py`).
- Reglas de transición tolerantes a divergencias menores.
- Actualización de tests afectados.
- Corrida de laboratorio 113k M15 para validar nueva métrica `aligned_hit_pct`.

### 2.2 Fuera
- No se modifica detección BOS/CHOCH.
- No se modifica runner de efectividad estructural.
- No se agrega lógica de entrada/SL/TP.

---

## 3. Definición operativa actual vs propuesta

### 3.1 Actual
```
aligned = (D1 == H4 == H1) and D1 != NEUTRAL
```
- Problema: cualquier divergencia, incluso temporal, cierra el filtro.

### 3.2 Propuesta (= definición IMPLEMENTADA)
```
aligned = (
  count_non_neutral([D1, H4, H1]) >= 2
  and not contradictory([D1, H4, H1])
)
contradictory = (
  (BULLISH in non_neutral) and (BEARISH in non_neutral)
)
```
- Sin contradicción: no mezcla bullish/bearish simultáneamente.
- Mínimo 2/3 con dirección: permite 1 NEUTRAL sin romper la regla.

### 3.3 Código REAL vigente (`engine/bias/narrative.py`)

```python
@dataclass(frozen=True)
class HtfBias:
    d1: Bias
    h4: Bias
    h1: Bias

    @property
    def aligned(self) -> bool:
        """True si al menos 2/3 TFs tienen dirección y no hay contradicción."""
        vals = [self.d1, self.h4, self.h1]
        non_neutral = [v for v in vals if v != NEUTRAL]
        if len(non_neutral) < 2:
            return False
        return len(set(non_neutral)) == 1
```

Equivalencia: `len(set(non_neutral)) == 1` implementa exactamente
`not contradictory(...)` cuando ya hay ≥2 no-NEUTRAL.

`compute_htf_bias(d1, h4, h1, swing_lookback=2)` devuelve ese `HtfBias`
(sesgo por TF vía `_bias_for_frame`, que usa la estructura VIGENTE: último
CHOCH activo y, si no hay, último BOS activo).
`compute_htf_bias_series(d1, h4, h1, m15, swing_lookback=2)` recalcula en cada
cierre H4 y emite la serie `direction` / `aligned` (bool) propagada por `ffill`
sobre la línea temporal H1 ∪ M15. La `direction` global sale de
`_compose_htf_bias` (D1/H4 autoridad, H1 desempate 2/3).

### 3.4 Nota — sesgo HTF canónico vs gate EXP-012

El **sesgo HTF es CANÓNICO**: `_bias_for_frame` usa CHOCH canónico SIEMPRE y
**no** aplica el GATE DURO EXP-012. Ese gate vive únicamente en
`engine.bos.structure.detect_market_structure` (estructura LTF / entrada, flag
`exp012_choch`). Censurar CHOCH en el sesgo desalineaba sesgo↔estructura
(ALIGNED 42% → 1.5%, medido en `results/motor_veltick_EURUSD_M15.json`).
El sesgo es la "verdad lenta" del motor; el ruido de CHOCH solo daña la
EJECUCIÓN (capa LTF), no el contexto direccional.

---

## 4. Criterios de aceptación

1. `aligned_hit_pct > 0%` en EURUSD 113k M15 en al menos 1 TF.
2. `aligned_hit_pct` estable al comparar corridas 30k y 113k.
3. Tests unitarios del motor pasan.
4. El cambio no altera detección BOS/CHOCH ni métricas `against_hit_pct`.
5. Documentación actualizada.

---

## 5. Archivos involucrados

| Archivo | Cambio |
|---------|--------|
| `engine/bias/narrative.py` | Modifica `compute_htf_bias()` y `compute_htf_bias_series()` |
| `tests/test_engine_bias.py` | Agrega/actualiza tests para alineación relajada |
| `docs/tesis/HALLAZGOS_SESGO_BACKTEST.md` | Actualiza interpretación |
| `scripts/measure_structure_effectiveness.py` | Usa nuevo gate sin cambios estructurales |

---

## 6. Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Aumento artificial de `aligned_hit` | Medir también contra baseline aleatoria y contra versión estricta |
| Señales `aligned` débiles sin edge real | Correr laboratorio completo y comparar métricas aligned/against |
| Tests existentes rotos | Actualizar expectativas en bloque; no eliminar cobertura |

---

## 7. Plan de implementación

1. Refactor `compute_htf_bias()` y `compute_htf_bias_series()`.
2. Actualizar tests.
3. Correr `pytest` y fijar 36/36 verde.
4. Correr laboratorio 30k y 113k.
5. Documentar resultados.
6. Commit con mensaje explícito.

---

## 8. Estado

- **Redacción: ✅ completa**
- **Implementación: ✅ hecha** — `HtfBias.aligned` en `engine/bias/narrative.py`
  (líneas ~87-94), consumida por `compute_htf_bias()` y
  `compute_htf_bias_series()`. Camino B del 2026-08-08.
- **Validación: ✅ por suite** — `tests/test_engine_bias.py`: 36 passed.
- **Cierre**: este MDS queda CERRADO. Cualquier cambio futuro de la definición
  de `aligned` requiere un MDS nuevo, no reabrir éste.

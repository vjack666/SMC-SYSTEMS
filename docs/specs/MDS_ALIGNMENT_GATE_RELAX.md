# MDS — Relajación del gate de alineación HTF

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

### 3.2 Propuesta
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

- Redacción: en progreso
- Implementación: pendiente
- Validación: pendiente

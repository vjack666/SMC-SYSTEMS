# 04 — Validación OOS y control de overfit

| Campo | Valor |
|-------|-------|
| **ID** | `13/04_VALIDACION_OOS_OVERFIT` |
| **Versión** | 1.0 |
| **Fecha** | 2026-07-13 |
| **Estado** | Stable |

---

## 1. Teoría

In-sample (IS) es el terreno de **diseño**.  
Out-of-sample (OOS) es el terreno de **verdad provisional**.  
Walk-forward (WF) es el terreno de **estabilidad en el tiempo**.

Si optimizás 12–100 trials y solo publicás el mejor fold, el PF es un **premio de lotería**, no un estimador del edge futuro (multiple testing / data snooping).

Conceptos clave (literatura quant):

| Concepto | Idea |
|----------|------|
| **Walk-forward** | Entrena en pasado, valida en el futuro inmediato; rueda |
| **Purge** | Saca del train las observaciones que solapan el test (labels que cruzan el corte) |
| **Embargo** | Hueco temporal post-test para no filtrar info de frontera |
| **PBO** | Probability of Backtest Overfitting (López de Prado et al.) |
| **DSR** | Deflated Sharpe Ratio — Sharpe penalizado por intentos y longitud |
| **N trades** | Sin tamaño de muestra, el PF es ruido |

---

## 2. Práctica

1. **Congelar** reglas de entrada antes de Optuna agresivo.  
2. Ablation: un modelo a la vez (PO3 solo, Turtle solo, …) — ya en R4.  
3. Optuna **solo** sobre el train del fold; el test del fold es sagrado.  
4. Reportar: PF OOS medio ± std, **peor fold**, N trades OOS, y si hay costs.  
5. Si un fold PF < 1 o N OOS << 100 → veredicto **frágil**, no “edge robusto”.

---

## 3. Algoritmo (gates del proyecto)

Los números viven en [METRICS_CANON](../../METRICS_CANON.md).  
Gates conceptuales:

```text
NO declarar edge de producción si:
  - no hay multi-fold OOS, o
  - algún fold crítico PF < 1 sin justificación, o
  - N OOS insuficiente, o
  - corrida sin costos cuando el live tiene spread, o
  - reloj multi-TF / fill no auditado
```

---

## 4. Código SMC-SYSTEMS

| Pieza | Ruta | Estado |
|-------|------|--------|
| WF multi-fold ICT | `ict_backtest/optimize.py` | ✅ post-fix #5 (dirección correcta) |
| PurgedKFold | `ml/stats_validator.py` | ✅ implementado |
| CVaR / DSR / PBO | `ml/stats_validator.py` | ✅ código; ⚠️ no siempre en pipeline ICT |
| Optuna | `ict_backtest/optimize.py`, `ml/tuner.py` | ✅ |
| Ablation R4 | roadmap + METRICS §8 | ✅ E2/E3/E5; E4 pendiente |

---

## 5. Huecos

| ID | Hueco | Prioridad |
|----|-------|-----------|
| G6 | Cablear DSR/PBO al final de cada Optuna ICT | Media |
| G7 | N OOS mínimo por símbolo en gate (// METRICS) | Alta (política) |
| G8 | No re-tunear tras mirar OOS (contaminación) | Proceso |

---

## En resumen

Optimizar sin protocolo OOS es **fabricar un pasado hermoso**.  
El profesional se obsesiona con el **peor fold**, no con el mejor PF del log.

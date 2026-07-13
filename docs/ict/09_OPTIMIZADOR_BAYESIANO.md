# Anexo — Optimizador bayesiano (validación del backtest)

| Campo | Valor |
|-------|-------|
| **ID** | `09_OPTIMIZADOR_BAYESIANO.md` |
| **Versión** | 2.0 (10/10) |
| **Fecha** | 2026-07-12 |
| **Estándar** | ADR-021 (adaptado: no es regla ICT) |
| **Estado** | Stable |
| **Tipo** | **ANEXO DE VALIDACIÓN** — no es libro de setup ICT |
| **Métricas** | [METRICS_CANON](../METRICS_CANON.md) §3 |
| **Ubicación ideal** | `docs/plan/` o `docs/avances/` (se mantiene aquí por enlaces históricos) |

---

## 0. Contrato de uso (sí / no)

| # | Condición | Obligatorio |
|---|-----------|:-----------:|
| 1 | El **modelo de setup** ya está definido (PO3/Turtle/SB) y medido sin tunear de más | Sí |
| 2 | Optimización solo sobre **pocos** hiperparámetros (≤6) | Sí |
| 3 | Validación **walk-forward** multi-fold, pasado→futuro | Sí |
| 4 | Reportar con **costos** cuando se declare PF “final” | Sí |
| 5 | Si un fold OOS tiene PF&lt;1 → edge **frágil**, no “listo live” | Sí |

**Prohibido:** Optuna sobre 20 knobs antes de R4 (roadmap biblioteca).

---

## 1. Teoría (simple)

Buscamos parámetros del motor (`displace_gap`, `bos_gap`, `require_displacement`, `tp_mode`, …) que maximicen una métrica (PF) **sin memorizar ruido**.

- **Grid/Random:** caros o ciegos.  
- **Bayesiano (Optuna TPE):** modelo surrogate que propone trials prometedores.  
- **Riesgo central:** overfitting in-sample.

---

## 2. Práctica en trading research

1. Fijar definición del setup (libros 06–08).  
2. Baseline sin optimizar.  
3. Optuna **in-sample** de una ventana.  
4. Evaluar OOS en folds siguientes.  
5. Publicar media ± std de PF OOS + N trades.  
6. Solo entonces hablar de paper.

---

## 3. Algoritmo en el repo

Capa 3: `ict_backtest/optimize.py` + `sequence.py`.  
Log: `docs/ict/logs/CAPA3_REFAC_WF.log`.

Params tipicos buscados: `displace_gap`, `bos_gap`, `require_displacement`, `tp_mode`.

---

## 4. Código

| Pieza | Ruta |
|-------|------|
| Optimización | `ict_backtest/optimize.py` |
| Secuencia | `ict_backtest/sequence.py` |
| Stats ML (DSR, PBO, …) | `ml/stats_validator.py` (estándar A7/A12) |

---

## 5. Auditoría

| ID | Estado |
|----|--------|
| #5 WF dirección | ✅ corregida |
| Capa 3 veredicto | Edge frágil (METRICS §3) |
| Costos en corrida final | ⚠️ pendiente |

---

## 6. Resultados

[METRICS_CANON §3](../METRICS_CANON.md#3-ict_backtest-post-auditoría-2026-07-11):  
mejores params in-sample y PF OOS 3.389±2.303 con **21 trades** — insuficiente para live.

---

## 7. Checklist de aplicación

- [ ] No lanzar Optuna hasta R4 (modelos aislados)  
- [ ] Re-run con `--cost`  
- [ ] A6 datos antes de A12  
- [ ] Publicar solo en METRICS_CANON  

---

## En resumen

Este “libro” es el **manual de no mentirse con el optimizador**. El 10/10 no es más trials: es **definición de setup → medición limpia → WF → costos → decisión**.

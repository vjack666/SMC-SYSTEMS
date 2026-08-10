# HYP-001 — ¿El contexto HTF (D1/H4/H1 alineado) aporta edge sobre ignorar el sesgo?

> **Tesis padre del laboratorio (FASE 3B.2, 2026-08-10).** Materializada desde
> CAND-11 del inventario (`docs/architecture/MICRO_AUDIT_HYPOTHESES.md`, Fase G).
> NO es un experimento; es una AFIRMACIÓN a destruir. Puede resultar REFUTADA.

## Pregunta científica

¿Operar únicamente a favor del sesgo HTF alineado (D1=H4=H1 en dirección, sin
contradicción) mejora el win rate (WR) y profit factor (PF) respecto a ignorar el
sesgo HTF (operar contra-sesgo o sin filtro)?

## Tesis

El contexto multi-timeframe (la columna HTF del edificio SMC-SYSTEMS) es una fuente
real de edge predictivo, no solo complejidad arquitectónica.

## Predicción cuantitativa

En la población donde `HtfBias.aligned == True`:

- `WR_aligned > WR_against` (objetivo: ventaja estadística de dirección)
- `PF_aligned > 1.0` (la ventaja es económicamente positiva tras costs)

Si la predicción no se cumple, la tesis cae (ver criterio de falsación).

## Variable primaria

- `WR` (win rate) y `PF` (profit factor) de fills, segmentados por
  `HtfBias.aligned` vs `against` (campo emitido por `engine/bias/narrative.py`
  vía `compute_htf_bias_series`, ya consumido por `top_down_allows_trade`).

## Baseline

- `WR` aleatorio ≈ 0.50.
- `PF` del tramo bajo estrategia contra-sesgo ya medido: ~edge nulo en EURUSD
  (CAND-01: `against_hit` 72-75% ≈ baseline por permutación 0.72-0.77 → ruido).
- El baseline de comparación es `against` (la misma estrategia sin el filtro
  aligned), no un valor arbitrario.

## Criterio de falsación

HYP-001 queda REFUTADA si, en la población con `aligned>0`:

- `WR_aligned <= WR_against` (el filtro no mejora la dirección), O
- `PF_aligned <= 1.0` (la ventaja no es económicamente positiva tras costs).

No hay forma de "ajustar la narrativa": el veredicto lo dicta la comparación
`aligned` vs `against` sobre la misma corrida.

## Dominio REAL / OTC

- **REAL (descubrimiento)**: nace de la tesis ICT/SMC del motor (documentada en
  `docs/lab/LABORATORIO_ICT_SMC.md` §2.1 y AGENTS.md Ley Fundamental).
- **OTC (validación)**: se valida por backtest canónico (`ict_backtest/run_backtest`)
  segmentando fills por `HtfBias.aligned`.

> Nota de trazabilidad: la separación REAL/OTC aplica el criterio del Director.
> ADR-005 (que la define formalmente) es DEUDA de trazabilidad — no existe físicamente
> en el repo. Ver `MICRO_AUDIT_HYPOTHESES.md` Fase G.5.

## Dependencia: auxiliares de habilitación (NO evidencia de éxito)

HYP-001 **hoy no es medible** porque en EURUSD M15 113k el gate estricto da
`aligned_hit = 0%` (CAND-02), con lo que la población `aligned>0` es vacía y la
tesis es unfalsiable en la práctica.

Para volverla medible se requieren DOS experimentos auxiliares (obligatorios en el
plan de EXP-001, pero que NO cuentan como evidencia de que HTF funciona):

- **CAND-03** (auxiliar): relajar el gate de alineación (`aligned` = ≥2/3 no
  NEUTRAL sin contradicción) para producir `aligned>0` en EURUSD.
- **CAND-05** (auxiliar): probar en otros símbolos (GBPUSD tendencial) donde la
  alineación pueda existir aunque EURUSD dé 0%.

Solo tras obtener `aligned>0` (vía auxiliares) se ejecuta la PRUEBA PADRE limpia:
`aligned` vs `against` sobre la misma corrida → veredicto.

## Decisión que permite

- **PROMOVIDA**: el filtro HTF queda validado como fuente de edge → se documenta
  evidencia; el motor HTF se mantiene. (No es "el motor funciona por construcción";
  es "el filtro HTF superó la comparación aligned vs against".)
- **REFUTADA**: el filtro HTF se reubica como sesgo teórico sin valor predictivo;
  se revisa la arquitectura HTF del edificio. Descubrir esto ahorra construir más
  pisos sobre una columna que no sostiene peso.
- **INCONCLUSIVA**: evidencia insuficiente (población aligned pequeña, datos
  insuficientes) → nuevo EXP con más datos.

## Qué NO afirma HYP-001

- NO afirma que HTF funciona (eso es lo que se va a intentar destruir).
- NO afirma que POI/3-capas/BOS aportan edge (otras ramas: CAND-09/10).
- NO es una prueba de la implementación del motor (CAND-04 es ingeniería, aparte).
- NO mezcla resultado de auxiliares con veredicto de la tesis.

---
*Materializada 2026-08-10 desde CAND-11. Sin EXP, sin ejecución, sin tocar código.*

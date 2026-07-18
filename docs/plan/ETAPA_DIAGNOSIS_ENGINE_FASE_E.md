# Fase E — Motores de Análisis (Statistics / Correlation / Hypothesis)

Fecha: 2026-07-18 · Autor: Hermes (bajo dirección de Ruben)
Estado: DISEÑO APROBADO. Implementación pendiente de OK.

## Premisa (regla #7 de Ruben, ya cumplida)

Fase D entregó el expediente multi-TF fiel (TradeContext v2 / market_context,
cadena D1→M1 con datos reales, 0 placeholders UNKNOWN, validado en 6m EURUSD
real). Solo AHORA tiene sentido la estadística: sobre contexto real, no ruido.

Fase E NO optimiza resultados. Primero construye la capa de análisis y
evidencia. Nada de caza de edges ni split-selección.

## Reglas de arquitectura (obligatorias)

1. `StatisticsEngine`, `CorrelationEngine`, `HypothesisEngine` son MÓDULOS
   INDEPENDIENTES bajo `ict_backtest/diagnostics/`. No se conocen entre sí.
2. Solo CONSUMEN `TradeContext` v2 / `market_context`. Nunca lo mutan.
3. No modifican el motor de entradas ni R7. No tocan `engine.py`/`sequence.py`/
   `canonical.py`. Solo LECTURA de contextos ya congelados.
4. No introducen lógica de trading nueva. Si descubren un patrón, lo REPORTAN
   (HypothesisEngine), no lo ejecutan.
5. Toda métrica lleva `n` y una medida de incertidumbre. Si `n < MIN_N`
   (30 por cohorte), el reporte marca `can_conclude=False` y dice por qué.
   El reporte final SIEMPRE incluye "qué NO puede concluir".

## Módulos

### 1. `cohorts.py` (helper, sin lógica de trading)
Funciones puras que reciben UN `TradeContext` y devuelven una faceta leída de
`market_context`. Solo lectura.

- `htf_alignment(ctx) -> "aligned" | "not"`  (D1/H4/H1 mismo bias)
- `has_htf_poi(ctx) -> bool`  (H4.poi == "PD", ancla Fase C)
- `m5_confirms(ctx) -> bool`  (M5.confirmation == bias de entrada)
- `m1_clean(ctx) -> bool`  (M1 microestructura == dirección de entrada)
- `d1_pd_state(ctx) -> "DISCOUNT" | "PREMIUM" | "PD" | "EQ"`

### 2. `statistics_engine.py`
- Entrada: `list[TradeContext]` (v2)
- Salida: `StatisticsReport` (@frozen)
  - `overall: OverallStat`  (n, win_rate, pf, avg_r, expectancy_r)
  - `cohorts: list[CohortStat]`  para los predicados de `cohorts.py`:
    cada uno con `name, n, win_rate, pf, avg_r, ci95_low, ci95_high` (Wilson)
  - `comparisons: list[Comparison]`  (a, b, delta_wr, delta_pf, verdict)
- Regla: reporta TODOS los cohorts pedidos con `n` honesto. NO elige el mejor.
  Si `n < MIN_N`, `can_conclude=False`.

### 3. `correlation_engine.py`
- Entrada: `list[TradeContext]` (v2)
- Salida: `CorrelationReport` (@frozen)
  - `associations: list[Association]`
    (`feature, outcome, coef, n, strength, can_conclude`)
  - Asociación punto-biserial / phi entre faceta de `market_context` y
    outcome (`pnl_r` o `win`). Fuerza por `|coef|` y `n`.
- Separado de Hypothesis: solo MIDE, no interpreta.

### 4. `hypothesis_engine.py`
- Entrada: `StatisticsReport` + `CorrelationReport`  (NO raw contexts →
  separación limpia entre motores)
- Salida: `HypothesisReport` (@frozen)
  - `hypotheses: list[Hypothesis]`
    (`statement, evidence_for, evidence_against, confidence, can_conclude`)
  - `inconclusive: list[str]`  (qué no se puede concluir y por qué)
- No introduce lógica de trading. Solo rank de evidencia.

### 5. `diagnosis_report.py` (orquestador)
- Entrada: `list[TradeContext]`
- Cadena: `statistics -> correlation -> hypothesis -> HypothesisReport`
- Es el ÚNICO que llama a los 3; los 3 no se referencian entre sí.
- Salida: tupla `(StatisticsReport, CorrelationReport, HypothesisReport)`.

## Cohortes iniciales (responden las preguntas de Ruben)

- Alineación HTF: D1/H4/H1 mismo bias vs no.
- M5: entrada con M5.confirmation alineado vs sin/opuesto.
- M1 ruido: entrada con microestructura M1 opuesta (falsos) vs limpia.
- HTF POI anclado: H4.poi=="PD" vs no.

## Ejemplo de salida esperada (forma, no número prometido)

- "Alineados WR 64% (n=22, IC95 48-78%), PF 1.6 vs No-alineados WR 35%
  (n=14) PF 0.9 — delta +29pp, confianza media (n total 36 < 60)".
- "Con M5 confirmado PF 1.8 vs sin M5 PF 0.9".
- "M1: +0.05R promedio pero +18% trades con microestructura opuesta".
- "NO SE CONCLUYE X: n=14 insuficiente para IC estable".

## Orden de implementación (propuesta, TDD)

- E1: `cohorts.py` + `statistics_engine.py` + tests con contexts sintéticos.
- E2: `correlation_engine.py` + tests.
- E3: `hypothesis_engine.py` + tests (consume reportes de E1/E2).
- E4: `diagnosis_report.py` + test de integración sobre contexts reales 6m.
- E5 (opcional, aparte): `smc_monitor/` dashboard de solo lectura.

## NO-GO

- No tocar `engine.py`, `sequence.py`, `canonical.py`, `run_backtest.py`.
- No agregar señales, filtros, SL/TP ni ningún parámetro de trading.
- No elegir el split "ganador" y presentarlo como edge.

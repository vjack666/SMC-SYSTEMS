# Auditoría final R4 — Fixes de IA externa + veredicto limpio (2026-07-13)

**Fuente del hallazgo:** IA externa revisó el repo en commit `b641a83` (código
real, no resumen). Yo verifiqué cada punto empíricamente antes de aplicar.

## Hallazgos de la IA externa (todos CONFIRMADOS por mí en código real)

1. **[CRÍTICO] Look-ahead cross-timeframe en join H4→M5.**
   `row_at_time` hacía asof `times <= tt`: para vela M5 09:03 seleccionaba
   barra H4 `time=08:00` que cierra 12:00. El sesgo H4 usaba precio futuro.
   **Medido:** 48694/50000 = **97.4%** de velas M5 afectadas. Ver
   `AUDIT_LOOKAHEAD_HTF.md`.

2. **[MEDIO] exec_tf duplicado en `checklist_scalping`.**
   Reimplementaba la búsqueda de prioridad de TF 2 veces y `evaluate` ya pasa
   `exec_tf` que la función ignoraba. → Firma limpia `checklist_scalping(..., exec_tf)`.

3. **[MEDIO] Displacement asimétrico en `sequence.py`.**
   `_has_displacement` solo miraba vela LTF; `_has_sweep` aceptaba LTF O HTF.
   → `_has_displacement(row, dir, est_htf)` con fallback HTF.

4. **[BAJO] Test H1 mal escrito.** Asumía `confirm_bars=1`; motor usa 2.
   → Test lee `StructureConfig().confirm_bars` y agrega velas de confirmación.

## Parches aplicados (autorizados por Ruben — commit posterior)
- `ict_backtest/_util.py`: `row_at_time(df, t, freq=None)` exige barra cerrada.
- `ict_backtest/engine.py`: `_build_estructura` pasa `freq=TF_FREQ[tf]` (HTF).
- `ict_backtest/rules.py`: `checklist_scalping` acepta `exec_tf` (elimina dup).
- `ict_backtest/sequence.py`: `_has_displacement(..., est_htf)` fallback HTF.
- `ict_backtest/engine.py`: `choch_status` mapeado desde `choch_signal`.
- `tests/test_ict_backtest.py`: H1 usa `confirm_bars` real. **Suite 7/7 passed.**

## R4 v2.7 — CORRIDA LIMPIA (resultados concluyentes)
Silver Bullet SIN displacement (ruptura NY AM no usa impulse M5); PO3 CON disp.

| Exp | PF | WR | Trades | Total R |
|-----|----|----|--------|---------|
| EURUSD Silver (M5) | **0.896** | 32.4% | 71 | -4.9 |
| GBPUSD Silver (M5) | **0.639** | 25.0% | 72 | -19.5 |
| EURUSD PO3+disp (M15) | 0.000 | 0% | 2 | -2.0 |
| GBPUSD PO3+disp (M15) | 0.000 | 0% | 0 | 0.0 |

## Veredicto (gate PF≥1.10)
- **Silver Bullet: RECHAZADO** (PF<1 con muestra real 71/72). No era bug: al
  destaparlo da señales y pierde. Modelo sin edge → archivar.
- **PO3: INCONCLUSO** (2/0 trades). Dispara poco en M15.
- **Turtle Soup: PENDIENTE** re-medir limpio (v2 PF 1.143 estaba contaminado).
- v2/v2.5/v2.6 son **contaminados** por look-ahead → no usar para Optuna.

## Siguiente paso propuesto
Re-correr **Turtle Soup** con look-ahead limpio (v2.8) para veredicto final del
único modelo que rozó el gate. Si Turtle limpio también cae <1.10, R4 no pasa
el gate y se documenta "sin edge para live" antes de Optuna.

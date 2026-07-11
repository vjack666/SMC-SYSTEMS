# TEST PLAN — `ict_backtest/` y observador

**Proyecto:** SMC-SYSTEMS
**Versión:** 1.0
**Fecha:** 2026-07-11

---

## 1. Estrategia de pruebas

| Nivel | Qué cubre | Dónde | Velocidad |
|-------|-----------|-------|-----------|
| **Unitario** | Reglas puras (swing, BOS/CHOCH, costos, WF split) | `tests/test_ict_backtest.py` | <1s (datos sintéticos) |
| **Integración** | Pipeline completo (load → detect → sequence → sim) | `tests/test_*.py` existentes | <10s |
| **Smoke** | El módulo importa y corre sin error | `ict_backtest/_smoke.py` | <5s |
| **Harness** | Escenarios de operación | `harness/` (11 adapters, 14 scenarios) | variable |
| **Corrida pesada (OOS)** | Walk-forward real sobre 50k velas | `optimize.py` (background) | ~2h |

Principio: **datos sintéticos pequeños para reglas** (deterministas, rápidos);
**datos reales solo para corridas pesadas** (NFR-Q2).

---

## 2. Cobertura actual (`tests/test_ict_backtest.py`)

| Test | Regla cubierta | Assert clave |
|------|---------------|--------------|
| `test_swing_no_lookahead` | #1 look-ahead | swing_high expuesto en idx 15 (no 10) |
| `test_swing_planos_no_marcan` | #1 (planos) | serie plana → 0 swings |
| `test_choch_differs_from_bos` | #2 CHOCH real | `bos_dir != choch_dir` en algún punto |
| `test_engine_spread_reduces_pnl` | #4 costos | `pnl_r(con cost) < pnl_r(sin cost)` |
| `test_engine_sl_before_tp_on_tie` | SL conservador | empate SL/TP → sale por SL |
| `test_walkforward_multi_fold` | #5 WF | 4 folds, avanzan en el tiempo |
| `test_walkforward_no_inverted` | #5 (dirección) | in-sample = pasado, no final |

**Comando:** `pytest tests/test_ict_backtest.py -v` → esperado 7 passed.

---

## 3. Casos de prueba por requisito (SRS)

| Requisito | Test | Estado |
|-----------|------|--------|
| FR-10 (sin look-ahead) | `test_swing_no_lookahead` | ✅ |
| FR-11 (sequence) | integración run_sequence | ✅ (manual) |
| FR-12 (costos) | `test_engine_spread_reduces_pnl` | ✅ |
| FR-13 (WF multi-fold) | `test_walkforward_*` | ✅ |
| FR-20 (reproducible) | logs + commit SHA | ✅ (proceso) |
| NFR-Q1 (sin look-ahead) | `test_swing_no_lookahead` | ✅ |
| NFR-A2 (≥3 folds) | `test_walkforward_multi_fold` | ✅ |
| NFR-A3 (PF con costos) | `simulate_trade(cost=...)` | ✅ (disponible) |

---

## 4. Pruebas pendientes / propuestas (medio plazo)

- **TP4.1:** `test_sequence_end_to_end` — correr `run_sequence` sobre un
  DataFrame sintético con un setup ICT completo y verificar 1 señal esperada.
- **TP4.2:** `test_bos_detection` — BOS alcista/bajista sobre serie sintética.
- **TP4.3:** `test_equity_curve` — `plot_equity_curve.py` genera PNG no vacío.
- **TP4.4:** `test_cost_impact_range` — barrer spread 0→3 pips y verificar
  monotonía decreciente de PF.
- **TP4.5:** `test_walkforward_robustness` — inyectar ruido y verificar que PF
  OOS cae (no overfit silencioso).

---

## 5. Criterios de aceptación para un release de `ict_backtest`

1. `pytest tests/test_ict_backtest.py` → 7 passed (mínimo; más los TP4.x).
2. `pytest tests/` completo → solo falla `test_ml_trainer` (preexistente,
   ajeno a sklearn).
3. Corrida Capa 3 walk-forward: PF OOS promedio > 1.0 en TODOS los folds
   (robustez) O, si algún fold <1, documentado en avance.
4. Todo PF reportado lleva costos explícitos en el log.

---

## 6. Ambiente de prueba
- Python 3.11+ (C:\Python314 para MT5 real; venv `smc_probe` para offline).
- Dependencias: pandas, numpy, optuna, matplotlib, pytest.
- NO requiere MT5 para `ict_backtest` (lee Parquet local).

---

## 7. Procedimiento de regresión
Tras cualquier cambio en `market_structure.py`, `engine.py`, `sequence.py` o
`optimize.py`:
```
pytest tests/test_ict_backtest.py -v
```
Si pasa, commitear con `refactor:`/`fix:` y actualizar `docs/AVANCES_*.md`.

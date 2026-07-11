# Diagnóstico de Ejecución y Estrategia — 2026-07-09

**Propósito:** el usuario pidió "ver qué es capaz de hacer" el sistema antes de
revisar la estrategia, de cara a la demo. Se ejecutó el sistema offline (sin MT5)
con datos parquet cacheados reales.

## 1. Entorno de ejecución (hallado, no asumido)
- Python: `smc_probe` venv (Python 3.14.6) en `C:/Users/v_jac/smc_probe`.
- Paquetes presentes: pandas 3.0.3 (CoW), numpy 2.5, pyarrow, scikit-learn 1.9,
  scipy, optuna, xgboost 3.3, langgraph, joblib, pyyaml, pytest.
- PySide6: **NO instalado** en `smc_probe` → la UI de escritorio NO arranca aquí.
- MT5: import OK vía stub global (no requiere terminal real para importar).
- Datos reales cacheados en `data/raw/`: M15/H4/D1 para EURUSD, GBPUSD, USDCHF,
  USDJPY, AUDUSD, NZDUSD, USDCAD, XAUUSD.

## 2. Cómo se ejecutó (offline, sin MT5)
- Entrypoint real: `backtest/real/__main__.py` arranca `MT5Connector()` (requiere
  terminal vivo). Se saltó usando `backtest/engine.py::run_combined_backtest`
  con `load_frame(..., auto_download=False)` (engine.py:379) → lee parquet cacheado.
- Script auxiliar creado: `scripts/_smc_quick_backtest.py` (usa datos cacheados).
- Medición aislada del filtro ML: `scripts/_smc_measure_ml_gate.py`.
- Inspección del modelo: `scripts/_smc_inspect_model.py`.

## 3. Resultados reales de ejecución (backtest offline)

### 3.1 Stack de señales BASE (ML-off, datos completos, 4 símbolos)
- Total trades: 62 | WR 53.2% | **PF 0.953** | DD 6.7% | Sharpe -0.30
- Por símbolo: EURUSD PF 0.0 (WR 0%), GBPUSD PF 1.48, USDCHF PF 0.85, USDJPY PF 1.65
- Conclusión: **el stack base de señales ICT/Wyckoff es apenas perdedor por sí solo.**

### 3.2 Filtro ML (medición aislada, 2 símbolos, 15k barras)
- Base signals: 720
- Aceptadas por el gate ML: 22 (3.1%) | Rechazadas: 698 (96.9%)
- ACEPTADAS  -> WR 59.1% | **PF 0.978**
- RECHAZADAS -> WR 57.7% | **PF 1.045**
- Lift (aceptadas/rechazadas): **0.94x — el filtro acepta las PEORES y rechaza
  las MEJORES.**

### 3.3 Modelo en producción (`ml/models/quality_filter.pkl`)
- Tipo: `CalibratedClassifierCV` (XGBoost + isotonic), schema v4, 67 features.
- `n_samples`: 1320 (README dice 1,649 — discrepancia).
- `holdout roc_auc`: **0.551** (≈ azar, 0.5 = moneda al aire).
- `precision` 0.576, `recall` 0.984 → acepta casi todo al descalibrarse; con
  umbral `base_ml_threshold=0.60` colapsa al 3% porque casi todas las probs < 0.60.

## 4. Contradicción con COMPLETION_REPORT.md
- El report afirma: WR 63.7%, PF 1.612, Sharpe 3.33, DD 4.96% (4 símbolos, ML ON).
- **NO se reproduce** con el modelo actual ni con el stack base:
  - Base (ML-off): PF 0.95.
  - Con ML (medición aislada): las aceptadas dan PF 0.98, peor que las rechazadas.
- El report probablemente se generó con un modelo/parámetros distintos, o los
  datos han cambiado. **Bandera roja para la demo.**

## 5. Auditoría de la estrategia (signals/pipeline.py)
Stack ICT/Wyckoff coherente y bien estructurado:
- `_session_filter` (línea 71): Londres 07-11 UTC, NY 13-17 UTC (Asia solo XAUUSD).
- Filtros en cascada: ATR (161), BOS (176), OB/FVG proximidad 1.5 ATR (199),
  CHOCH anti-opuesto 10b (213), swing 1.5 ATR (221), micro EMA/RSI (225),
  sweep+OTE (230-249).
- Confluence score ponderado (283-298); señal si `confluence_score >= 2` (302).
- SL estructural 20b swing + fallback ATR; TP 2×ATR; max hold 16b (engine.py).
- La lógica de simulación (SL/TP con excursión, R-multiples) es sana.

**Problema de la estrategia:** el stack base NO es rentable por sí solo. Toda la
rentabilidad del report dependía del filtro ML, y el filtro ML actual es
efectivamente aleatorio (AUC 0.55) y además está invertido (lift 0.94x).

## 6. Tests
- `tests/test_pipeline_integration.py` + `tests/test_ml_inference.py`: 5 pass, 1 fail.
- FAIL: `test_scalping_config_has_ml_flags` espera
  `ScalpingConfig.use_ml_quality_filter == True`, pero el default es `False`
  (pipeline.py:49). Test desactualizado, NO bug de estrategia.

## 7. Veredicto para la demo
- El sistema CORRE (backtest, ML, agentes, simulación) — el código está vivo.
- La estrategia base es sólida en diseño pero NO rentable sola (PF ~0.95).
- El filtro ML (la pieza que prometía rentabilidad) está roto: AUC 0.55 y
  selectividad invertida. El COMPLETION_REPORT NO es reproducible hoy.
- **Recomendación antes de demo:** no presentar el report de PF 1.61 como actual;
  o bien (a) re-entrenar el filtro ML con features que separen ganadores, o
  (b) demo mostrar el stack base honestamente (señales + gestión de riesgo), o
  (c) investigar por qué el report difiere (modelo/distintos datos).

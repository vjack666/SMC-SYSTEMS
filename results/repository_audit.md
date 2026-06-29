# Repository Audit

## 1) Arbol resumido del proyecto

- backtest/
  - combined_backtest.py
  - fvg_mitigation_backtest.py
  - bos_backtest.py
  - retrain_models.py
- modules/
  - fvg/ (detector.py, ml_model.py, backtest.py, models/)
  - bos/ (detector.py, ml_model.py, backtest.py, models/)
  - choch/ (detector.py, ml_model.py, backtest.py, models/)
  - ob/ (detector.py, ml_model.py, backtest.py, models/)
  - trend/ (context_engine.py, ml_model.py, backtest_impl.py, models/)
  - pullback/ (view.py)
  - indicators/ (core.py, ml_model.py)
- ml/
  - feature_pipeline.py
  - train_quality_model.py
  - regime_detector.py
  - models/quality_filter.pkl
- strategy/
  - scalping_setup.py
- scripts/
  - run_fvg_mitigation_backtest.py
  - train_fvg_only.py
  - generate_fvg_setup_gallery.py
  - plot_last_backtest_trade.py
  - audit_*.py
- data/mt5/
  - *_{M15,H1,H4,D1}.parquet
- results/
  - multiples salidas CSV/JSON/MD/PNG

## 2) Scripts de entrada identificados

- run_system.py
  - runner principal del sistema combinado y auditorias globales.
- scripts/run_fvg_mitigation_backtest.py
  - runner directo del backtest FVG A/B (inmediato vs mitigacion).
- scripts/train_fvg_only.py
  - runner de entrenamiento FVG-only (modelo v3).
- backtest/bos_backtest.py y modules/*/backtest.py
  - entradas por modulo.

## 3) Pipeline de datos identificado

1. Carga de parquet desde data/mt5 via _load(...) (M15/H1/H4/D1).
2. Normalizacion temporal a UTC y orden por time.
3. Split temporal train/test por indice (normalmente 60/40 o 70/30 segun flujo).
4. Persistencia de resultados en results/ como CSV/JSON/MD.

## 4) Pipeline de features identificado

FVG actual (modules/fvg/ml_model.py):

- fvg_bullish
- fvg_bearish
- gap_size_atr
- atr_ratio
- body_ratio

Detector FVG (modules/fvg/detector.py):

- Regla de 3 velas con no superposicion de extremos:
  - bullish: low[i] > high[i-2]
  - bearish: high[i] < low[i-2]

## 5) Pipeline ML identificado

- Entrenamiento FVG:
  - scripts/train_fvg_only.py
  - usa _collect_m15 + detect_fvg + build_feature_frame + build_labels
  - validacion walk-forward interna via _evaluate_walk_forward
  - guarda modelo en modules/fvg/models/fvg_v3.pkl
- Scoring FVG:
  - score_frame(...) retorna ml_confidence
- En el backtest de mitigacion se carga modelo joblib y se filtra por confidence_threshold.

## 6) Pipeline de backtesting identificado

- Backtest FVG experimental actual:
  - backtest/fvg_mitigation_backtest.py
  - Estrategias actuales:
    - A_immediate
    - B_mitigation
  - Salidas actuales:
    - results/fvg_mitigation_trade_log.csv
    - results/fvg_mitigation_metrics.csv
    - results/fvg_mitigation_diagnostics.csv
    - results/fvg_mitigation_comparison_summary.json

- Backtest combinado de sistema:
  - backtest/combined_backtest.py
  - orientado a estrategia de confluencia multi-modulo.

## 7) Dependencias entre modulos

- scripts/run_fvg_mitigation_backtest.py -> backtest/fvg_mitigation_backtest.py
- backtest/fvg_mitigation_backtest.py -> modules/fvg/backtest.py (_load), modules/fvg/detector.py, modules/fvg/ml_model.py
- strategy/scalping_setup.py -> bos/choch/fvg/ob/indicators/trend
- run_system.py -> combined_backtest.py + ml + risk

Dependencia critica para esta tarea:

- fvg_mitigation_backtest.py es el mejor punto de integracion para A/B/C/D/E
  sin romper baseline existente.

## 8) Riesgos de modificacion

1. Riesgo de romper baseline A/B ya validado si se reescribe logica existente.
2. Riesgo de leakage/lookahead al calcular estructura y estados con informacion futura.
3. Riesgo de incompatibilidad de columnas si nuevos features no existen en todos los simbolos.
4. Riesgo de degradacion de performance por loops anidados en 100k+ barras.
5. Riesgo de inconsistencia de metricas si A-E no comparten mismos costos/periodo/simbolo.

Mitigaciones propuestas:

- Mantener A/B legacy intacto y crear camino experimental paralelo por flags.
- Crear paquete nuevo pac_sequence/ sin modificar detectores base.
- Registrar logs de transiciones e invalidaciones para auditoria.
- Verificacion automatica de no-leakage y reproducibilidad al final.

## Plan de integracion concreto (sin romper compatibilidad)

### Archivos nuevos a crear

1. pac_sequence/__init__.py
2. pac_sequence/event_schema.py
3. pac_sequence/state_machine.py
4. pac_sequence/feature_builder.py
5. pac_sequence/validation.py
6. backtest/fvg_pac_experiments.py
7. scripts/run_fvg_mitigation_backtest.py (se actualiza para CLI A-E; si se prefiere cero impacto se agrega scripts/run_fvg_pac_experiments.py)

### Archivos existentes a tocar

1. scripts/run_fvg_mitigation_backtest.py
   - agregar argparse y flag --experiment {A,B,C,D,E,ALL}
   - mantener comportamiento default compatible con ejecucion anterior
2. backtest/fvg_mitigation_backtest.py
   - no se elimina logica legacy
   - opcional: solo wrapper de compatibilidad hacia nuevo motor

### Cambios experimentales

- Toda la logica ICT/PAC secuencial en pac_sequence/ y backtest/fvg_pac_experiments.py.
- Salidas nuevas en results/:
  - experiment_A.csv ... experiment_E.csv
  - comparison_table.csv
  - state_transition_log.csv
  - invalidation_log.csv
  - feature_importance.csv
  - expectancy_report.csv
  - drawdown_report.csv
  - symbol_breakdown.csv
  - audit_summary.md

### Cambios reversibles

- Reversibles por bandera:
  - --experiment A/B/C/D/E
- Reversibles por codigo:
  - eliminar paquete pac_sequence y archivo de backtest experimental sin tocar pipeline legacy.

## Validacion logica interna previa a implementacion

Checklist de coherencia:

- Punto de integracion elegido: backtest FVG actual (confirmado).
- Baseline A existente preservable (confirmado).
- Dependencias disponibles para estructura/OB/FVG/sesion (confirmado).
- Outputs requeridos por usuario mapeados a archivos concretos (confirmado).

Estado: AUDITORIA COMPLETADA. LISTO PARA IMPLEMENTACION EXPERIMENTAL.

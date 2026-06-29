# LEGACY AUDIT REPORT — MIGRACIÓN A SMC SUCCESSOR

> **Auditoría**: 28 Jun 2026  
> **Equipo**: Arquitectura, Trading Algorítmico, Quant, ML/MLOps, Auditoría, Migraciones  
> **Proyectos auditados**: SMC SYSTEMS, GRID SCAPL 2 (grid-v2.0-master), GRID_SCALP_COPIA  
> **No encontrados**: ict-engine-v6.0-enterprise-sic-main, GRID_SCALP (original)  
> **Destino**: `SMC_SUCCESSOR/`

---

## 0. ESTADO DE LOS PROYECTOS

| Proyecto | Estado | Acceso |
|----------|--------|--------|
| SMC SYSTEMS | ✅ Completo, 76 archivos .py | `~/Desktop/SMC SYSTEMS/` |
| GRID SCAPL 2 | ✅ Completo, 150+ archivos .py (sin .venv) | `~/Desktop/GRID SCAPL 2/` |
| GRID_SCALP_COPIA | ✅ Completo, 9 archivos .py | `~/Desktop/GRID_SCALP_COPIA/` |
| ict-engine-v6.0-enterprise-sic-main | ❌ **No encontrado** en `~/Desktop/` | — |
| GRID_SCALP (original) | ❌ **No encontrado** (solo existe GRID_SCALP_COPIA) | — |
| SMC_SUCCESSOR | ✅ Proyecto destino, solo harness + 1 test | `~/Desktop/SMC SYSTEMS/SMC_SUCCESSOR/` |

---

## FASE 1 — INVENTARIO

---

### 1.1 SMC SYSTEMS

```
Lenguaje:         Python 3.11+
Framework:        pandas, numpy, scikit-learn, XGBoost, LightGBM
Arquitectura:     Modular analysis → ML filter → Combined backtest
Punto de entrada: run_system.py → main()
Dependencias:     MetaTrader5, pandas, numpy, scikit-learn, xgboost,
                  lightgbm, matplotlib, seaborn, joblib, tqdm, pyarrow
Archivos clave:
  run_system.py                  Orquestador: 5 iteraciones de calibración + ML
  strategy/scalping_setup.py     Generación de señales (9 filtros)
  backtest/combined_backtest.py  Backtest multi-símbolo con risk governor
  ml/feature_pipeline.py         Feature engineering (30+ features)
  ml/train_quality_model.py      Entrenamiento XGBoost (fallback a LGBM/CatBoost)
  ml/regime_detector.py          Clasificación de régimen (5 estados)
  risk/dynamic_threshold_engine.py  Umbral dinámico por régimen
  risk/meta_risk_governor.py     Máquina de estados NORMAL→CAUTION→DEFENSIVE→LOCKDOWN
  modules/trend/context_engine.py   Análisis MTF (D1+H4+M15)
  modules/bos/detector.py        Break of Structure
  modules/fvg/detector.py        Fair Value Gap (3-velas)
  modules/choch/detector.py      Change of Character
  modules/ob/detector.py         Order Blocks (impulse + followthrough)
  modules/structural_sl/detector.py  Stop Loss estructural (ICT) ❌ DESCONECTADO
  modules/indicators/core.py     ATR, RSI, EMA
  pac_sequence/state_machine.py  Máquina de estados PAC ❌ DESCONECTADO
  data/mt5/downloader.py         Descarga OHLCV desde MetaTrader 5
```

#### Árbol completo (archivos .py propios, excluyendo .venv)

```
SMC SYSTEMS/
├── run_system.py
├── data/mt5/downloader.py
├── strategy/scalping_setup.py
├── ml/
│   ├── feature_pipeline.py
│   ├── train_quality_model.py
│   └── regime_detector.py
├── risk/
│   ├── dynamic_threshold_engine.py
│   └── meta_risk_governor.py
├── backtest/
│   ├── combined_backtest.py
│   ├── bos_backtest.py
│   ├── trend_backtest.py
│   ├── fvg_mitigation_backtest.py
│   ├── fvg_pac_experiments.py
│   └── retrain_models.py
├── pac_sequence/
│   ├── state_machine.py
│   ├── feature_builder.py
│   ├── event_schema.py
│   └── validation.py
├── modules/
│   ├── trend/         (10 archivos .py + 5 modelos .pkl)
│   ├── bos/           (4 archivos .py + 2 modelos .pkl)
│   ├── fvg/           (3 archivos .py + 2 modelos .pkl)
│   ├── choch/         (3 archivos .py + 2 modelos .pkl)
│   ├── ob/            (3 archivos .py + 2 modelos .pkl)
│   ├── swing/         (4 archivos .py + 2 modelos .pkl)
│   ├── fractal/       (4 archivos .py + 2 modelos .pkl)
│   ├── indicators/    (3 archivos .py + 2 modelos .pkl)
│   ├── structural_sl/ (3 archivos .py)
│   └── pullback/      (1 archivo .py)
├── paper_trading/     (config, logs, reports)
├── scripts/           (40+ scripts de auditoría, validación, entrenamiento)
├── results/           (90+ archivos: CSV, JSON, MD, PNG)
└── SMC_SUCCESSOR/     (proyecto destino)
```

---

### 1.2 GRID SCAPL 2 (grid-v2.0-master)

```
Lenguaje:         Python 3.11+
Framework:        pandas, numpy, scikit-learn, plotly, pytest
Arquitectura:     Bot en vivo (MT5) + backtesting + ML pipeline
Punto de entrada: run.py → core.mt5_bot.main()
                  run_system.py (report reader)
Dependencias:     MetaTrader5, pandas, numpy, scikit-learn, plotly,
                  joblib, tqdm, rich, pytest
Archivos clave:
  run.py                           Entry point real → mt5_bot.main()
  run_system.py                    Lector de status.json (reportes)
  core/mt5_bot.py                  Bot MT5 en vivo
  core/automated_bot.py            Bot automatizado con scheduling
  core/smc_analysis.py             Análisis SMC (BOS, FVG, CHOCH, OB)
  core/smc_decision_engine.py      Motor de decisión BUY/SELL
  core/smc_zone_selection.py       Selección de zonas SMC
  core/entry_zone_selector.py      Selector de zona de entrada
  core/entry_validator.py          Validador de entradas
  core/trend_detector.py           Detección de tendencia
  core/market_regime_engine.py     Clasificador de régimen
  core/m1_trigger.py               Trigger M1 para entradas
  core/ml_bos_engine.py            Motor ML para BOS
  core/risk_manager.py             Gestor de riesgo
  core/hard_risk_layer.py          Capa dura de riesgo (límites)
  core/learning_engine.py          Motor de aprendizaje
  core/historical_context.py       Contexto histórico
  core/dynamic_window.py           Ventana dinámica
  core/live_session_logger.py      Logger de sesión en vivo
  core/journal.py                  Diario de operaciones
  core/data_config.py              Configuración de datos
  ml/feature_engine_v2.py          Ingeniería de features (39 vars)
  ml/structural_labeling.py        Labeling estructural de velas
  backtesting/combined_backtest.py Backtest combinado
  backtesting/engine/backtest_engine.py  Motor genérico de backtest
  backtesting/ml/fvg_ml/           Subsistema FVG ML (10 archivos)
  backtesting/replay/live_shadow_replay.py  Replay sombra
  data/mt5_ingestion/ingest_mt5_data.py  Ingesta de datos
```

#### Árbol reducido (solo proyecto, sin .venv)

```
GRID SCAPL 2/
├── run.py                          # Entry point → core.mt5_bot.main()
├── run_system.py                   # Lector de reportes
├── pyrightconfig.json
├── core/             (21 archivos .py)
│   ├── mt5_bot.py                  ★ Bot MT5 en vivo
│   ├── automated_bot.py            ★ Bot automatizado
│   ├── smc_analysis.py             ★ Análisis SMC
│   ├── smc_decision_engine.py      ★ Motor de decisión
│   ├── smc_zone_selection.py       ★ Zonas SMC
│   ├── entry_zone_selector.py      ★ Zona de entrada
│   ├── entry_validator.py          ★ Validador
│   ├── trend_detector.py           ★ Tendencia
│   ├── market_regime_engine.py     ★ Régimen
│   ├── m1_trigger.py               ★ Trigger M1
│   ├── ml_bos_engine.py            ★ ML BOS
│   ├── risk_manager.py             ★ Riesgo
│   ├── hard_risk_layer.py          ★ Límites duros
│   ├── learning_engine.py          ★ Aprendizaje
│   ├── historical_context.py       ★ Contexto
│   ├── dynamic_window.py           ★ Ventana dinámica
│   ├── live_session_logger.py      ★ Logger
│   ├── journal.py                  ★ Diario
│   └── data_config.py              ★ Config datos
├── backtesting/    (25+ archivos .py)
│   ├── combined_backtest.py
│   ├── engine/backtest_engine.py
│   ├── execution/execution_simulator.py
│   ├── ml/fvg_ml/        ★ Subsistema FVG ML completo
│   ├── ml/structural_features.py
│   ├── ml/structural_feature_engine.py
│   ├── ml/structural_inference.py
│   ├── ml/physiology_inference.py
│   ├── ml/meta_model.py
│   ├── ml/feature_engineering.py
│   ├── montecarlo/montecarlo_engine.py
│   ├── walkforward/walkforward_runner.py
│   ├── replay/live_shadow_replay.py
│   └── metrics/performance_metrics.py
├── ml/              (3 archivos .py)
│   ├── feature_engine_v2.py        ★ 39 features estructurales
│   └── structural_labeling.py      ★ Labeling (9 clases)
├── models/registry/model_registry.py  Registro de modelos
├── data/mt5_ingestion/ingest_mt5_data.py  Ingesta
├── scripts/         (20+ scripts de auditoría y entrenamiento)
├── research/dataset/checks/    (7 validadores de integridad)
├── dashboard/ml_bos_dashboard/ (3 archivos: dashboard, embedding, xai)
├── training/train_ml_bos.py
├── benchmark/legacy_vs_ml.py
├── tests/           (tests de integración)
├── tools/audit_bos_dependencies.py
└── visualization/structural_replay.py
```

---

### 1.3 GRID_SCALP_COPIA

```
Lenguaje:         Python 3.11+
Framework:        pandas, numpy, rich, MetaTrader5
Arquitectura:     Bot consola con menú interactivo
Punto de entrada: run_bot.py → mostrar_menu()
Dependencias:     MetaTrader5, pandas, numpy, rich
Archivos clave:
  run_bot.py                           Lanzador con menú interactivo
  estrategias/integracion_estrategia.py  Orquestador de estrategias
  estrategias/estocastico_m15.py        Señal estocástico
  estrategias/bollinger_grid.py         Grid + Bollinger Bands
  estrategias/mt5_forexclub.py          Conexión MT5 ForexClub
  estrategias/gestion_riesgo.py         Gestión de riesgo
  _internal/estrategias/bos_detector.py Break of Structure
  validar_mt5.py                        Validador de conexión MT5
  verificar_integracion.py              Verificador de acoplamiento
  auditoria_completa.py                 Auto-auditoría
```

---

## FASE 2 — ARQUITECTURA REAL

---

### 2.1 SMC SYSTEMS — Flujo de datos

```
  DATA LAYER
  ┌─────────────────────────────────────────────────────────────────┐
  │ MetaTrader 5 → downloader.py → Parquet OHLCV                   │
  │   EURUSD, GBPUSD, XAUUSD @ M15/H1/H4/D1                        │
  │   (2+ años de historia local)                                   │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  FEATURE ENGINEERING
  ┌─────────────────────────────────────────────────────────────────┐
  │ build_scalping_context() (strategy/scalping_setup.py:65)        │
  │   • detect_bos()     → bos_direction (+1/-1/0)                 │
  │   • detect_choch()   → choch_signal (BULLISH/BEARISH/NONE)     │
  │   • detect_fvg()     → fvg_bullish, fvg_bearish                │
  │   • detect_order_blocks() → ob_bullish, ob_bearish             │
  │   • add_atr(), add_ema(), add_rsi()                             │
  │   • build_trend_context_frame() → macro_direction,             │
  │     trend_confidence, trend_score, regime_state, d1/h4 trends  │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  SIGNAL GENERATION (M15)
  ┌─────────────────────────────────────────────────────────────────┐
  │ 9 filtros secuenciales:                                         │
  │   trend_filter + session_filter + atr_filter + ob_fvg_filter   │
  │   + bos_filter + choch_filter + swing_filter + micro_filter    │
  │   + volume_filter                                               │
  │                                                                  │
  │ 5 filtros puntuados → confluence_score (0-5)                    │
  │ signal_confidence = 0.40 + (confluence_score/5.0) * 0.55       │
  │                                                                  │
  │ ★ DECISIÓN BUY/SELL:                                            │
  │   signal_direction = 1  (BUY)  si macro_direction == BULLISH    │
  │                      = -1 (SELL) si macro_direction == BEARISH  │
  │   (strategy/scalping_setup.py:188-189)                          │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  ML QUALITY FILTER
  ┌─────────────────────────────────────────────────────────────────┐
  │ run_combined_backtest() (backtest/combined_backtest.py:379)     │
  │   • detect_regimes() → market_regime (5 estados)                │
  │   • Por cada señal: feature_row (30+ features)                  │
  │   • _predict_quality_probability(model, features) → P(trade_win)│
  │   • threshold_for_regime(regime) → 0.60-0.75                    │
  │   • mode_threshold_add(governor.mode) → +0.03/+0.08/+1.00      │
  │   • allow_trade = P ≥ threshold + mode_add                      │
  │   • governor_state.mode == LOCKDOWN → bloquea todo              │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  TRADE SIMULATION
  ┌─────────────────────────────────────────────────────────────────┐
  │ _simulate_trade_with_stats() (combined_backtest.py:154)         │
  │   SL = entry ± ATR         (SL fijo de 1 ATR)                  │
  │   TP = entry ± 2*ATR       (R:R fijo 1:2)                      │
  │   hold max = 16 barras M15  (~4 horas)                          │
  │   Exit: SL hit / TP hit / hold_limit (close al precio actual)    │
  │   Tracking: MFE, MAE, exit_reason, hold_bars                     │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  RISK GOVERNANCE (post-trade)
  ┌─────────────────────────────────────────────────────────────────┐
  │ next_state(governor_state) → NORMAL/CAUTION/DEFENSIVE/LOCKDOWN  │
  │   • consecutive_losses + 1 si trade perdedor                    │
  │   • day_drawdown_pct = drawdown del día                         │
  │   • total_drawdown_pct = drawdown acumulado                     │
  │   • LOCKDOWN si ≥5 pérdidas consec o DD≥4% diario o DD≥8% total │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  OUTPUTS
  ┌─────────────────────────────────────────────────────────────────┐
  │ results/combined_metrics.json  (win_rate, PF, Sharpe, DD...)    │
  │ results/combined_trades.csv    (trade log completo)             │
  │ results/ml_trade_dataset.csv   (features para retraining)       │
  │ results/oos_metrics.json       (out-of-sample)                  │
  └─────────────────────────────────────────────────────────────────┘
```

---

### 2.2 GRID SCAPL 2 — Flujo de datos

```
  DATA LAYER
  ┌─────────────────────────────────────────────────────────────────┐
  │ MetaTrader 5 → ingest_mt5_data.py → Parquet OHLCV               │
  │   Múltiples símbolos y timeframes                                │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  CORE ANALYSIS
  ┌─────────────────────────────────────────────────────────────────┐
  │ mt5_bot.py → main() (entrada desde run.py)                     │
  │   • Conecta MT5, selecciona símbolos                            │
  │   • Inicia sesión (live_session_logger)                         │
  │   • Carga data_config → parámetros por símbolo/TF               │
  │                                                                  │
  │ Por cada vela M15:                                               │
  │   • smc_analysis() → BOS, FVG, CHOCH, OB, sweeps                │
  │   • trend_detector → tendencia MTF                              │
  │   • market_regime_engine → régimen actual                       │
  │   • smc_zone_selection → zonas de interés                       │
  │   • entry_zone_selector → mejor zona para entrada               │
  │   • entry_validator → valida condiciones de entrada             │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  DECISION ENGINE
  ┌─────────────────────────────────────────────────────────────────┐
  │ smc_decision_engine() → BUY / SELL / HOLD                       │
  │   • Evalúa zonas seleccionadas vs precio actual                 │
  │   • m1_trigger → entrada en M1 exacta                          │
  │   • ml_bos_engine → confianza ML para BOS                       │
  │   • Calcula señal final                                         │
  │                                                                  │
  │ ★ DECISIÓN BUY/SELL:                                             │
  │   BUY  → estructura alcista + zona demanda + trigger M1         │
  │   SELL → estructura bajista + zona oferta + trigger M1          │
  │   (core/smc_decision_engine.py)                                  │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  RISK MANAGEMENT
  ┌─────────────────────────────────────────────────────────────────┐
  │ risk_manager.py → tamaño posición, SL/TP                        │
  │ hard_risk_layer → límites absolutos (max DD, max diario, etc.)  │
  │   • Position sizing por ATR o % riesgo                          │
  │   • SL estructural vs ATR                                       │
  │   • TP dinámico basado en estructura                            │
  │   • Límite de grids máximos                                     │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  EXECUTION & LEARNING
  ┌─────────────────────────────────────────────────────────────────┤
  │ automated_bot → ejecuta órdenes en MT5                          │
  │ learning_engine → registra resultados, actualiza modelos        │
  │ journal → escribe diario de operaciones                         │
  │ live_session_logger → log de sesión                             │
  └─────────────────────────────────────────────────────────────────┘
                                  ↓
  BACKTESTING (modo offline)
  ┌─────────────────────────────────────────────────────────────────┐
  │ backtest_engine → simula trades históricos                      │
  │ walkforward_runner → validación walk-forward                    │
  │ montecarlo_engine → simulación Monte Carlo                      │
  │ replay/live_shadow_replay → replay sombra                       │
  │ fvg_ml/ → pipeline FVG ML completo                               │
  └─────────────────────────────────────────────────────────────────┘
```

---

### 2.3 GRID_SCALP_COPIA — Flujo de datos

```
  run_bot.py → mostrar_menu()
    │
    ├─ [1] VIVO:    integracion_estrategia.ejecutar_bot_automatico()
    │                 │
    │                 └─ Cada M15:
    │                    mt5_forexclub.monitorear_continuo()
    │                     → obtiene velas de MT5
    │                     → estocastico_m15.calcular_estocastico()
    │                        → señal de primera operación
    │                     → bos_detector.detectar_bos()
    │                        → confirma dirección
    │                     → bollinger_grid.calcular_bandas_bollinger()
    │                        → mide volatilidad
    │                     → bollinger_grid.validar_condiciones_grid()
    │                        → decide si abrir grid
    │                     → gestion_riesgo.validar_todas_condiciones_grid()
    │                        → 3 condiciones: distancia, ancho, pérdida
    │
    ├─ [2] SINTÉTICO: genera datos de ejemplo y procesa
    ├─ [3] DESCARGA:  descarga única MT5 + analiza
    ├─ [4] VALIDAR:   validar_mt5.py (prueba conexión)
    └─ [5] FORZAR:    análisis inmediato (sin esperar)
```

---

## FASE 3 — TRADING ENGINE / SMC / ICT

---

### 3.1 SMC SYSTEMS

#### BUY/SELL — Decisión

```
Archivo:  strategy/scalping_setup.py:188-189

BUY  (direction=1):  signal_pass AND macro_direction == "BULLISH"
SELL (direction=-1): signal_pass AND macro_direction == "BEARISH"

donde:
  signal_pass = mandatory_pass AND confluence_score >= 2
  mandatory_pass = session_filter AND atr_filter
  confluence_score = trend + bos + ob_fvg + choch + swing  (0-5)
```

#### BOS (Break of Structure)

```
Archivo:  modules/bos/detector.py:35-70

bullish_break = close > swing_high.shift(1)
bearish_break = close < swing_low.shift(1)
bos_direction = 1 si bullish, -1 si bearish, 0 si nada

Liquidity sweep: low < min(low, 20) AND close > prior_low
                 high > max(high, 20) AND close < prior_high
```

#### FVG (Fair Value Gap)

```
Archivo:  modules/fvg/detector.py:6-26

fvg_bullish = low > high.shift(2)   (gap alcista)
fvg_bearish = high < low.shift(2)   (gap bajista)
```

#### CHOCH (Change of Character)

```
Archivo:  modules/choch/detector.py:10-30

bullish_break = close > swing_high.rolling(20).max().shift(1)
bearish_break = close < swing_low.rolling(20).min().shift(1)

CHOCH_BULLISH si bearish_context AND bullish_break
CHOCH_BEARISH si bullish_context AND bearish_break
```

#### Order Blocks

```
Archivo:  modules/ob/detector.py:6-30

ob_bullish = vela bajista fuerte (body_ratio>0.7) + followthrough alcista
ob_bearish = vela alcista fuerte (body_ratio>0.7) + followthrough bajista
```

### 3.2 GRID SCAPL 2

#### BUY/SELL — Decisión

```
Archivo:  core/smc_decision_engine.py (estimado)

BUY:
  - Estructura alcista confirmada (higher highs + higher lows)
  - BOS alcista detectado
  - FVG/OB alcista como zona de demanda
  - Precio en zona de entrada
  - Trigger M1 confirmado
  - Régimen no caótico

SELL:
  - Estructura bajista confirmada (lower highs + lower lows)
  - BOS bajista detectado
  - FVG/OB bajista como zona de oferta
  - Precio en zona de entrada
  - Trigger M1 confirmado
  - Régimen no caótico
```

#### ML para BOS

```
Archivo:  ml/feature_engine_v2.py — 39 features estructurales
Archivo:  ml/structural_labeling.py — 9 clases de label

Clases: VALID_BOS, FAILED_BOS, SWEEP, CHOCH, RANGE,
        REVERSAL, CONTINUATION, EXPANSION

Features incluyen: swing strength, structure velocity, displacement,
  breakout efficiency, retracement depth, equal highs/lows,
  sweep/liquidity, ATR normalization, volatility, impulse,
  acceleration, HTF alignment, synchronization, consensus,
  wick/candle features, FVG gap/fill, session features
```

### 3.3 GRID_SCALP_COPIA

#### BUY/SELL — Decisión

```
No hay un motor de decisión centralizado. La lógica está distribuida:

1. estocastico_m15 → señal de primera operación (cruce %K/%D)
2. bos_detector → confirma la dirección con Break of Structure
3. bollinger_grid → valida volatilidad y condiciones de grid
4. gestion_riesgo → valida distancia, ancho de bandas, pérdida previa

Decision BUY/SELL viene del estocástico + BOS + dirección del grid anterior.
```

---

## FASE 4 — RISK MANAGEMENT

---

### 4.1 SMC SYSTEMS

| Componente | Archivo | Función | Fórmula |
|-----------|---------|---------|---------|
| **Stop Loss** | `combined_backtest.py:90` | `_build_signals_from_context` | `sl = entry ± atr` (1 ATR) |
| **Take Profit** | `combined_backtest.py:91` | `_build_signals_from_context` | `tp = entry ± 2*atr` (2 ATR) |
| **SL Estructural** | `modules/structural_sl/detector.py:134` | `calculate_structural_stop` | Origin swing ± distancia (NO USADO) |
| **Position Sizing** | No implementado (riesgo % fijo) | — | 0.5% por trade (paper_trading/config.json) |
| **Drawdown Control** | `risk/meta_risk_governor.py:27` | `next_state` | LOCKDOWN si DD total ≥ 8% o DD diario ≥ 4% |
| **Límite pérdidas** | `risk/meta_risk_governor.py:27` | `next_state` | CAUTION tras 2 pérdidas, DEFENSIVE tras 3, LOCKDOWN tras 5 |
| **Umbral dinámico** | `risk/dynamic_threshold_engine.py:18` | `threshold_for_regime` | 0.60 + ajustes por régimen (+0.08 HIGH_VOL, +0.15 CHAOTIC, etc.) |
| **Ajuste por modo** | `risk/meta_risk_governor.py:63` | `mode_threshold_add` | CAUTION +0.03, DEFENSIVE +0.08, LOCKDOWN +1.00 |
| **Sesiones** | `strategy/scalping_setup.py:49` | `_session_filter` | Londres 7-11 UTC, NY 13-17 UTC |

### 4.2 GRID SCAPL 2

| Componente | Archivo | Descripción |
|-----------|---------|-------------|
| **Risk Manager** | `core/risk_manager.py` | Position sizing, SL/TP dinámicos, exposición |
| **Hard Risk Layer** | `core/hard_risk_layer.py` | Límites absolutos: max DD, max diario, max posiciones |
| **SL** | `core/risk_manager.py` | SL estructural (basado en ICT) + ATR backup |
| **TP** | `core/risk_manager.py` | TP basado en estructura de mercado (no fijo) |
| **Position Sizing** | `core/risk_manager.py` | % riesgo por trade, ajustado por volatilidad |

### 4.3 GRID_SCALP_COPIA

| Componente | Archivo | Función | Fórmula |
|-----------|---------|---------|---------|
| **Distancia mínima** | `gestion_riesgo.py:95` | `verificar_distancia_minima` | M1: 0.0010, M5: 0.0015, M15: 0.0020 |
| **Ancho Bollinger** | `gestion_riesgo.py:116` | `verificar_ancho_bollinger` | M1: 0.0003, M5: 0.0008, M15: 0.0012 |
| **Grid sizing** | `gestion_riesgo.py:58-62` | Constantes | Lote inicial 0.1, incremento 0.1, máximo 1.0, grids máximos 10 |
| **Estado pérdida** | `gestion_riesgo.py:133` | `verificar_ultima_en_perdida` | Solo abrir grid si última op está en pérdida |

---

## FASE 5 — MACHINE LEARNING

---

### 5.1 SMC SYSTEMS — ML Quality Filter

| Aspecto | Detalle |
|---------|---------|
| **Modelo** | XGBoost (fallback: LightGBM → CatBoost → HistGradientBoosting) |
| **Archivo** | `ml/train_quality_model.py:30-86` |
| **Features** | 30+ (trend_confidence, atr_ratio, bos_strength, fvg_size, ema_distance, rsi, volume_ratio, rr_ratio, etc.) |
| **Target** | `win` (1 si PnL > 0, 0 si no) |
| **Dataset** | `results/ml_trade_dataset.csv` — generado por backtest |
| **Split** | `train_test_split(test_size=0.25, random_state=42)` — **aleatorio, NO temporal** |
| **Validación** | Calibration con `CalibratedClassifierCV` (isotonic/sigmoid) |
| **Inferencia** | `combined_backtest.py:511` — `_predict_quality_probability(model, feature_row)` |
| **Umbral** | 0.60 base + ajustes por régimen + ajustes por governor mode |
| **Retraining** | `run_system.py:414-420` — entrenado en cada iteración |

#### Riesgos detectados en ML

| # | Riesgo | Evidencia | Impacto |
|---|--------|-----------|---------|
| 1 | **Lookahead bias** | `train_test_split` aleatorio (línea 155). Datos futuros pueden estar en train y test simultáneamente | 🔴 ALTO |
| 2 | **Data leakage en features** | `pnl_r` y `win` se excluyen manualmente (feature_pipeline.py:78-84), pero el backtest genera features post-trade | 🟡 MEDIO |
| 3 | **Importance proxy** | La importancia se calcula como correlación de Pearson con el target (train_quality_model.py:210), NO como permutation importance o SHAP | 🟡 MEDIO |
| 4 | **Sin walk-forward** | No hay validación temporal. El split aleatorio no simula condiciones de mercado futuras | 🔴 ALTO |
| 5 | **Calibration CV frágil** | `calibration_cv = min(3, min_class_count)` puede ser 0 o 1, saltándose la calibración | 🟢 BAJO |
| 6 | **Sin detección de overfitting** | No se compara rendimiento train vs test sistemáticamente | 🟡 MEDIO |

### 5.2 SMC SYSTEMS — Regime Detector

| Aspecto | Detalle |
|---------|---------|
| **Archivo** | `ml/regime_detector.py:37-70` |
| **Clases** | TRENDING, RANGING, HIGH_VOL, LOW_VOL, CHAOTIC |
| **Features** | atr_ratio, ema_distance, ema_slope, directional efficiency, compression |
| **Método** | Reglas heurísticas (no ML) — umbrales sobre indicadores derivados |
| **Riesgo** | Sin validación estadística de los umbrales. Son valores fijos |

### 5.3 GRID SCAPL 2 — ML Pipeline

| Aspecto | Detalle |
|---------|---------|
| **Modelos** | Múltiples: ML_BOS, FVG_ML, Meta Model, Physiology Model |
| **Features** | `feature_engine_v2.py` — 39 features estructurales |
| **Labeling** | `structural_labeling.py` — 9 clases (VALID_BOS, FAILED_BOS, SWEEP, CHOCH, etc.) |
| **Pipeline FVG** | 10 archivos en `backtesting/ml/fvg_ml/` con dataset builder, feature engineering, training, inference, validation, schema, telemetry |
| **Inferencia** | `structural_inference.py`, `physiology_inference.py`, `fvg_inference.py` |
| **Registro** | `models/registry/model_registry.py` |
| **Dashboard** | `dashboard/ml_bos_dashboard/` con XAI (SHAP-like) y embeddings |

### 5.4 GRID_SCALP_COPIA — ML

**NO EXISTE ML.** El sistema es 100% basado en reglas (estocástico + BOS + Bollinger).

---

## FASE 6 — CALIDAD DEL SOFTWARE

---

### 6.1 SMC SYSTEMS — Código muerto y módulos sin conexión

| Módulo | Archivos | Clasificación | Evidencia |
|--------|----------|--------------|-----------|
| `pac_sequence/` | 4 archivos .py | 🔴 **DESCARTAR** | `run_state_machine()` nunca es importado. 0 referencias en `combined_backtest.py` o `scalping_setup.py` |
| `modules/structural_sl/` | 3 archivos .py | 🔴 **DESCARTAR** (lógica) / 🟡 **REVISAR** (concepto) | `calculate_structural_stop()` nunca se llama. El backtest interno usa señales fake (alterna cada 50 velas) |
| `modules/trend/mtf_analyzer.py` | 1 archivo | 🔴 **DESCARTAR** | `analyze_mtf()` no es llamado; su lógica está duplicada en `context_engine.py` |
| `modules/trend/detector.py` | 1 archivo | 🔴 **DESCARTAR** | `detect_trend()` no se usa; el pipeline usa `build_trend_context_frame()` |
| `modules/trend/session_filter.py` | 1 archivo | 🔴 **DESCARTAR** | No usado; `scalping_setup.py` tiene su propio `_session_filter()` |
| `modules/trend/data_loader.py` | 1 archivo | 🔴 **DESCARTAR** | No usado; datos se cargan directamente |
| `modules/bos/data_loader.py` | 1 archivo | 🔴 **DESCARTAR** | No usado |
| `modules/trend/structure_classifier.py` | 1 archivo | 🔴 **DESCARTAR** | Solo usado por `mtf_analyzer.py` (muerto) |
| `modules/swing/swing_detector.py` | 1 archivo | 🔴 **DESCARTAR** | Solo usado por `mtf_analyzer.py` (muerto) |
| `modules/fractal/fractal_detector.py` | 1 archivo | 🔴 **DESCARTAR** | Alternativa no integrada |
| `modules/pullback/view.py` | 1 archivo | 🔴 **DESCARTAR** | Herramienta visual no integrada |
| `strategy/scalping_setup.py:209` | `build_scalping_signals()` | 🔴 **DESCARTAR** | Nunca llamada. Duplicada por `_build_signals_from_context()` en combined_backtest |
| Cada `ml_model.py` por módulo (×7) | 7 archivos + 14 .pkl | 🔴 **DESCARTAR** | Ninguno se usa en el pipeline real. Solo `ml/models/quality_filter.pkl` importa |
| `backtest/bos_backtest.py` | 1 archivo | 🔴 **DESCARTAR** | No usado por `combined_backtest.py` |
| `backtest/trend_backtest.py` | 1 archivo | 🔴 **DESCARTAR** | No usado por `combined_backtest.py` |
| `backtest/__init__.py` | 1 archivo | 🔴 **DESCARTAR** | Exporta módulos muertos |
| `backtest/fvg_mitigation_backtest.py` | 1 archivo | 🔴 **DESCARTAR** | Script experimental no conectado |
| `backtest/fvg_pac_experiments.py` | 1 archivo | 🔴 **DESCARTAR** | Script experimental no conectado |
| `backtest/retrain_models.py` | 1 archivo | 🔴 **DESCARTAR** | No usado |

### 6.2 GRID SCAPL 2 — Riesgos de arquitectura

| # | Riesgo | Evidencia |
|---|--------|-----------|
| 1 | **Duplicación con SMC SYSTEMS** | Ambos proyectos tienen trend_detector, market_regime_engine, BOS/FVG/CHOCH detection con lógica diferente pero mismo propósito |
| 2 | **Scripts vs módulos** | 20+ scripts en `scripts/` duplican lógica que existe en `core/` y `backtesting/`. Difícil saber cuál es la versión correcta |
| 3 | **ML Fragmentado** | Features en `ml/feature_engine_v2.py`, `ml/structural_labeling.py`, `backtesting/ml/structural_features.py`, `backtesting/ml/structural_feature_engine.py` — 4 implementaciones distintas de features |
| 4 | **FVG ML Aislado** | Subsistema FVG ML en `backtesting/ml/fvg_ml/` (10 archivos) con schema, telemetry, validación — pero no hay evidencia de integración con el bot en vivo |
| 5 | **Sin punto de entrada unificado** | `run.py` y `run_system.py` hacen cosas distintas. No hay un solo comando para "ejecutar todo" |
| 6 | **Configuración distribuida** | `data_config.py`, `config/paths.py`, `pyrightconfig.json` — cada uno con paths distintos. Sin schema centralizado |

### 6.3 GRID_SCALP_COPIA — Riesgos

| # | Riesgo | Evidencia |
|---|--------|-----------|
| 1 | **Copia sin control de versiones** | Es una copia de GRID_SCALP original. No hay git, no hay historial |
| 2 | **Import frágil** | `sys.path.insert(0, ...)` para cargar estrategias (run_bot.py:10). Si hay conflicto de nombres, falla silenciosamente |
| 3 | **Sin tests** | Solo hay `auditoria_completa.py` que es auto-auditoría, no tests unitarios |
| 4 | **Terminal MT5 hardcodeada** | `C:\Program Files\ForexClub MT5\terminal64.exe` (validar_mt5.py:52) |
| 5 | **Sin gestión de estado** | No persiste estado entre ejecuciones. Cada vez que arranca, empieza de cero |

---

## FASE 7 — COMPARACIÓN ENTRE PROYECTOS

| Proyecto | Mejor módulo | Problema principal | Valor para SMC_SUCCESSOR |
|----------|-------------|-------------------|-------------------------|
| **SMC SYSTEMS** | `modules/trend/context_engine.py` — Análisis MTF ponderado (D1×0.6 + H4×0.4 + M15 con momentum, aceleración, microestructura) | ~70% del código está muerto o desconectado. Pipeline real es muy delgado. SL = 1 ATR fijo ignora la estructura ICT | 🟢 **ALTO** — La lógica de señales y el pipeline de backtest son rescatables |
| **SMC SYSTEMS** | `risk/meta_risk_governor.py` — Máquina de estados con thresholds configurables | El governor es global por símbolo, no hay separación | 🟢 **ALTO** — Arquitectura limpiamente encapsulada |
| **SMC SYSTEMS** | `ml/regime_detector.py` — Clasificación heurística de 5 regímenes | Umbrales fijos sin validación estadística | 🟡 **MEDIO** — Concepto útil, pero necesita calibración |
| **SMC SYSTEMS** | `ml/train_quality_model.py` — Pipeline de entrenamiento XGBoost con calibración | Lookahead bias por split aleatorio | 🟡 **MEDIO** — Base sólida pero requiere walk-forward |
| **GRID SCAPL 2** | `core/smc_decision_engine.py` + `smc_zone_selection.py` — Motor de decisión ICT con zonas | Depende de todo el core, difícil de extraer | 🟢 **ALTO** — Arquitectura más fiel a ICT que SMC SYSTEMS |
| **GRID SCAPL 2** | `ml/structural_labeling.py` — 9 clases de label estructural | No hay dataset de validación pública | 🟢 **ALTO** — Sistema de labeling más granular que SMC SYSTEMS |
| **GRID SCAPL 2** | `ml/feature_engine_v2.py` — 39 features estructurales | Solapamiento con `structural_features.py` | 🟢 **ALTO** — Feature set más completo |
| **GRID SCAPL 2** | `backtesting/ml/fvg_ml/` — Pipeline FVG ML completo (10 archivos) | Aislado del resto del sistema | 🟡 **MEDIO** — Buen blueprint para migrar |
| **GRID SCAPL 2** | `core/hard_risk_layer.py` — Límites duros de riesgo | Sin tests | 🟡 **MEDIO** — Concepto importante |
| **GRID SCAPL 2** | `backtesting/engine/backtest_engine.py` — Motor de backtesting | No está claro si es mejor que `combined_backtest.py` de SMC SYSTEMS | 🟡 **MEDIO** — Evaluar cuál usar |
| **GRID SCAPL 2** | `backtesting/execution/execution_simulator.py` — Simulación de ejecución | Sin documentación de slippage model | 🟡 **MEDIO** — Útil para backtesting realista |
| **GRID_SCALP_COPIA** | `estrategias/gestion_riesgo.py` — Gestión de riesgo para grids | Atado a Bollinger Grid, no genérico | 🟡 **MEDIO** — Lógica de grid reutilizable |
| **GRID_SCALP_COPIA** | `estrategias/bollinger_grid.py` — Estrategia grid con Bollinger | Sin backtesting histórico, solo señales en vivo | 🔴 **BAJO** — Solo como referencia |

---

## FASE 8 — PLAN DE MIGRACIÓN

### Estrategia de extracción

```
FASE 0 — PREPARACIÓN (SMC_SUCCESSOR ya tiene harness básico)
  ├─ Establecer convenciones de código, naming, tipos
  └─ Definir interfaces (protocols/ABCs) para cada componente

FASE 1 — CORE (imposible prescindir de esto)
  ├─ [SMC] strategy/scalping_setup.py    → Módulo SIGNAL
  │   build_scalping_context()           → Refactorizar a pipeline configurable
  │   _session_filter()                  → Extraer a módulo aparte
  │
  ├─ [SMC] backtest/combined_backtest.py → Módulo BACKTEST
  │   run_combined_backtest()            → Extraer configuración (CombinedBacktestConfig)
  │   _simulate_trade_with_stats()       → Mantener como core
  │   _compute_metrics()                 → Extraer a módulo METRICS
  │
  ├─ [SMC] risk/meta_risk_governor.py    → Módulo RISK
  │   GovernorState, next_state()        → Mantener tal cual
  │
  ├─ [GRID2] core/smc_analysis.py        → Módulo ANALYSIS
  │   Lógica SMC combinada               → Unificar con detectores de SMC SYSTEMS
  │
  └─ [GRID2] core/trend_detector.py      → Módulo TREND
      Mejor que SMC SYSTEMS              → Usar como base

FASE 2 — FEATURES (mejoras respecto al legacy)
  ├─ [GRID2] ml/structural_labeling.py   → Módulo LABELING
  ├─ [GRID2] ml/feature_engine_v2.py     → Módulo FEATURES
  ├─ [GRID2] backtesting/ml/fvg_ml/      → Módulo FVG_ML
  ├─ [GRID2] core/entry_zone_selector.py → Módulo ZONE_SELECTOR
  ├─ [GRID2] core/entry_validator.py     → Módulo VALIDATOR
  ├─ [GRID2] core/hard_risk_layer.py     → Módulo HARD_RISK
  ├─ [GRID2] backtesting/execution/      → Módulo EXECUTION
  └─ [GRID2] backtesting/replay/         → Módulo REPLAY

FASE 3 — EXPERIMENTAL (requiere validación antes de integrar)
  ├─ [SMC] ml/regime_detector.py         → Mejorar con validación estadística
  ├─ [SMC] modules/structural_sl/        → Re-implementar con interfaces clean
  ├─ [GRID2] ml/structural_inference.py  → Requiere dataset de validación
  ├─ [GRID2] ml/physiology_inference.py  → Experimental
  └─ [GRID2] ml/meta_model.py            → Meta-modelo sobre submodelos

FASE 4 — LEGACY (solo conservar como referencia)
  ├─ [SMC] pac_sequence/                 → No migrar. Concepto interesante pero desconectado
  ├─ [SMC] modules/pullback/             → No migrar
  ├─ [SMC] modules/fractal/              → No migrar (no usado)
  ├─ [SMC] modules/trend/mtf_analyzer.py → No migrar (duplicado)
  ├─ [SMC] Cada ml_model.py por módulo   → No migrar
  ├─ [SMC] backtest/bos_backtest.py      → No migrar
  ├─ [SMC] backtest/trend_backtest.py    → No migrar
  ├─ [GRID2] scripts/ (20+ scripts)      → No migrar directamente, extraer lógica útil
  └─ [GRID_SCALP_COPIA]                   → No migrar. Conservar como referencia de grid
```

### Roadmap recomendado

```
Semana 1-2:   FASE 0 + FASE 1 (CORE)
              ├─ Extraer signal pipeline de SMC SYSTEMS
              ├─ Extraer backtest engine
              ├─ Extraer risk governor
              ├─ Extraer smc_analysis de GRID SCAPL 2
              └─ Unificar trend detection

Semana 3-4:   FASE 2 (FEATURES)
              ├─ Integrar structural labeling y features
              ├─ Integrar FVG ML pipeline
              ├─ Integrar zone selector + validator
              └─ Integrar execution simulator

Semana 5-6:   FASE 3 (EXPERIMENTAL)
              ├─ Mejorar regime detector con ML (en lugar de reglas)
              ├─ Re-implementar structural SL
              ├─ Agregar walk-forward validation al training ML
              └─ Integrar live shadow replay

Semana 7-8:   FASE 4 (CONSOLIDACIÓN)
              ├─ Tests de integración
              ├─ Documentación
              ├─ Benchmark vs legacy
              └─ Limpieza de código muerto
```

### Advertencias críticas para la migración

1. **No confiar en la documentación.** PROJECT_OVERVIEW.md describe PAC sequences y structural stops como si fueran parte del pipeline. NO LO SON.

2. **No asumir que los experimentos son reproducibles.** Los experimentos "F" requieren structural_sl que no está conectado. Los "resultados" actuales pueden ser del pipeline ATR-based, no del ICT-based.

3. **Unificar features ML.** Hay 4 implementaciones distintas de features estructurales entre SMC SYSTEMS y GRID SCAPL 2. Elegir UNA.

4. **Implementar walk-forward validation.** El split aleatorio en `train_quality_model.py` es data leakage garantizado. Usar partición temporal.

5. **Separar risk governor por símbolo.** El governor global actual contamina pérdidas entre símbolos.

6. **El harness de SMC_SUCCESSOR debe probar cada extracción.** Como dice su README: "No strategies are implemented yet. Every future module must be introduced through the harness first."

---

## RESUMEN EJECUTIVO

```
SMC SYSTEMS:
  Código total:    76 archivos .py
  Código vivo:     ~6-8 archivos (run_system, combined_backtest, scalping_setup, feature_pipeline,
                    train_quality_model, regime_detector, risk modules, 4 detectores, indicators)
  Código muerto:   ~50+ archivos (70%)
  ML:              XGBoost quality filter con lookahead bias confirmado
  Valor:           Pipeline de backtesting bien estructurado, lógica de señales rescatable

GRID SCAPL 2:
  Código total:    150+ archivos .py (sin .venv)
  Código vivo:     ~25 archivos core + backtesting
  Código muerto:   Scripts duplicados, ML fragmentado
  ML:              Labeling estructural (9 clases), 39 features, pipeline FVG ML completo
  Valor:           Motor de decisión ICT más completo, mejor feature engineering

GRID_SCALP_COPIA:
  Código total:    9 archivos .py
  Código vivo:     9 (todo conectado)
  ML:              No existe
  Valor:           Bajo — solo como referencia de estrategia grid + Bollinger

RECOMENDACIÓN:
  Usar SMC SYSTEMS como base del pipeline de backtesting.
  Usar GRID SCAPL 2 como base del motor SMC/ICT y ML.
  DESCARTAR pac_sequence, structural_sl (actual), módulos ml_model.py, scripts duplicados.
  NO MIGRAR GRID_SCALP_COPIA (solo referencias).
```

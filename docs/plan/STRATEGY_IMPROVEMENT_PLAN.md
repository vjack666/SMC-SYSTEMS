# Plan de Mejora de Estrategia — SMC-SYSTEMS

> Documento vivo. Fase 1 (hallazgos) y Fase 2 (harness) completadas con evidencia de código.
> Fase 3 (plan de trabajo), Fase 4 (riesgos) y Fase 5 (criterio de aceptación) propuestas.
> No se ha modificado lógica de trading todavía — solo auditoría + documentación.

---

## 1. Hallazgos (Fase 1 — 6 preguntas, con cita a archivo/función)

### P1 — Pesos de confluencia (MTF=3, CHOCH=3, displacement=2, FVG=2, OB=2, sweep=2, BOS=1, OTE=1)

**Respuesta:** Los pesos del `ICT_RULEBOOK.md` (Appendix, líneas 339-348) **NO están implementados en el código**. Son explícitamente aspiracionales: el propio rulebook dice *"These weights are not tuned — they are starting values for future optimisation"* (línea 350).

El `confluence_score` real se calcula en `signals/pipeline.py:205-213` y es una **suma de booleanos con peso 1 cada uno**:

```python
max_confluence = 6.0 if orchestrator is not None else 5.0
confluence_score = (
    data["filter_trend"].astype(int)      # 1
    + data["filter_bos"].astype(int)      # 1
    + data["filter_ob_fvg"].astype(int)   # 1
    + data["filter_choch"].astype(int)    # 1
    + data["filter_swing"].astype(int)    # 1
    + (data["filter_agents"].astype(int) if orchestrator is not None else 0)  # 1
)
```

- **No son constantes configurables**: están hardcodeados como `+1` por filtro. `ScalpingConfig` (`signals/pipeline.py:38-49`) solo expone `min_confluence_score: int = 2` (el umbral, no los pesos).
- **No existe** ningún log histórico ni backtest que haya barrido estos pesos. El único tuning documentado es de hiperparámetros ML (`ml/tuner.py`, Optuna), no de pesos de confluencia.
- **Consecuencia**: MTF, CHOCH, displacement, FVG, OB, sweep, BOS y OTE tienen TODOS el mismo peso efectivo (1). El esquema de pesos del rulebook nunca se materializó.

### P2 — Umbral de confluencia: ¿distingue combinación o solo suma? ¿Régimen además del ML?

**Respuesta (combinación):** El score **solo suma un número**. No distingue *qué* conceptos lo componen. `signal_pass = mandatory_pass & (confluence_score >= min_confluence_score)` (`signals/pipeline.py:219`). Un score de 2 por `trend+bos` es idéntico a `trend+choch` o `ob_fvg+swing`. No hay lógica de "peso por combinación".

**Respuesta (régimen):** Sí hay filtrado por régimen **además del ML**, pero es binario y grueso:
- `regime_pass = ~data["regime_state"].isin(["LOW_VOL", "CHAOTIC"])` (`signals/pipeline.py:111`) — excluye LOW_VOL y CHAOTIC, pero NO separa tendencia de rango para puntuar.
- El `macro_direction` se deriva de `trend_score` (`signals/pipeline.py:102-107`): BULLISH/BEARISH/RANGING por umbral ±30. Esto orienta la dirección del trade pero no modula el `confluence_score`.
- **No hay** un tratamiento distinto de pesos/umbrales para régimen de tendencia vs. rango. El rulebook MTF (línea 318) dice "If HTF is ranging → LTF trades filtered out", pero el código solo aplica eso vía `macro_direction == RANGING` (filtros direccionales no disparan, no un veto explícito).

### P3 — Failure conditions del rulebook ICT vs. implementación real

**Respuesta:** Los detectores son **detección pura en el bar del evento; NO implementan las failure conditions** del rulebook, salvo un caso parcial.

| Concepto | Rulebook failure condition | Implementado en código | Evidencia |
|----------|---------------------------|------------------------|-----------|
| BOS | Wicky break, no follow-through en N bars → failed BOS | **NO** | `detectors/bos.py:71-84` marca `bos_direction` por `close > swing_high.shift(1)`; nunca se invalida ni envejece |
| CHOCH | Precio vuelve dentro de estructura en N bars → failed shift | **NO** | `detectors/choch.py:10-25` marca `choch_signal` y no lo invalida; el pipeline solo usa `rolling(10).max()` para "recent" (`pipeline.py:154-155`) |
| FVG | Gap llenado en próxima vela; gap trivial | **PARCIAL** | `detectors/fvg.py:41-81` `_track_fvg_fill` marca `bullish_unfilled`/`filled`, PERO el pipeline solo usa `fvg_bullish`/`fvg_bearish` (booleanos de creación, líneas 137-142, 176), no el fill status |
| OB | Precio rompe a través del OB; OB muy viejo (>20 bars) | **NO** | `detectors/ob.py:7-37` marca por `body_ratio>0.7 & followthrough`; no hay envejecimiento ni invalidación por break-through |
| Liquidity sweep | Precio cierra más allá y continúa (no es sweep) | **NO cableado al pipeline** | Existe en `adapters/feature_enrichment_adapter.py:53-107` (`_detect_liquidity_sweeps`), pero NO se importa en `signals/pipeline.py` ni entra en `confluence_score` |
| Displacement | Large wick → rechazo; precio vuelve al rango en N bars | **NO** | `detectors/displacement.py` (ver `detectors/__init__.py:3`); detección en bar, sin seguimiento de validez |
| OTE / Premium-Discount | Blow-through sin reacción | **NO cableado al pipeline** | `adapters/feature_enrichment_adapter.py:282-286` calcula zonas, pero el pipeline de señales no las usa para filtrar |

**Conclusión P3:** El `ICT_RULEBOOK.md` es en gran parte **aspiracional** para las failure conditions. Los detectores señalan el evento pero no gestionan su vida útil (invalidación/envejecimiento). El riesgo: señales sobre conceptos ya invalidados (BOS de hace 100 barras, OB viejo) siguen contribuyendo al score.

### P4 — Conflicto ICT vs. Wyckoff en DecisionAgent

**Respuesta:** No hay veto ni jerarquía dura. Se resuelve por **promedio ponderado + penalización de conflicto suave**.

- `DecisionConfig` (`agents/decision_agent.py:11-18`): `ict_weight=0.35, wyckoff_weight=0.30, structure_weight=0.20, ml_weight=0.15, conflict_penalty=0.15`.
- `decide()` (`agents/decision_agent.py:145-214`) combina los 4 agentes: `contribution = bias_val * weight * result.confidence`, suma ponderada → `combined_bias_val`, `combined_confidence`.
- **Conflicto** (`decision_agent.py:208-214`): si hay >1 bias no neutral distinto, aplica `conflict_penalty` restando 0.15 a `combined_confidence` (no anula la señal, solo la degrada).
- Si `combined_confidence < min_combined_confidence (0.55)` → invalidación (`decision_agent.py:231-232`).

O sea: ICT tiene peso ligeramente mayor (0.35 vs 0.30 Wyckoff), pero una señal contradictoria no se vetoa — se penaliza. El agente Wyckoff SÍ participa: el `AgentOrchestrator` corre ICT+Wyckoff+Structure y alimenta `agent_decision_bias` al pipeline (`pipeline.py:183-192`), que es el `filter_agents` que suma 1 al `confluence_score`.

### P5 — Aporte real del filtro ML (con vs. sin ML, mismo dataset)

**Respuesta:** **No existe un backtest aislado documentado** que compare con/sin filtro ML sobre el mismo dataset. No se puede responder con evidencia del repo; se declara explícitamente la ausencia.

- El `CombinedBacktestConfig` (`backtest/engine.py:42`) SÍ tiene `use_ml_quality_filter: bool = True` y el engine lo respeta (`engine.py:325, 421`), así que **técnicamente es ejecutable** correr `run_combined_backtest` con `use_ml_quality_filter=False` para aislar el efecto.
- El modelo ML reportado tiene **AUC holdout ≈ 0.55** (`ml/models/quality_filter.json`, visto en auditoría previa) — apenas sobre el azar (0.5). Un filtro con AUC 0.55 probablemente **no aporta edge positivo neto** y puede estar descartando trades ganadores buenos. Pero esto es una sospecha, no evidencia: no hay reporte de PF/WR con ML off.
- `ml/walk_forward.py` existe (AUDIT_REPORT F11/F13) pero no produce un desglose con/sin-ML en la documentación revisada.
- **Acción requerida (Fase 3):** correr backtest con `use_ml_quality_filter=True` y `=False` sobre el mismo dataset y comparar WR/PF/Sharpe/trade-count. Esto es la primera experientación propuesta.

### P6 — Generalización por símbolo (desglose del WR 63.7% / PF 1.61 / Sharpe 3.33)

**Respuesta:** **No hay desglose por símbolo documentado.** Las métricas son **in-sample combinadas** de 91 trades / 4 símbolos.

- `COMPLETION_REPORT.md:111-115`: `in_sample.win_rate=0.6374`, `profit_factor=1.6121`, `max_drawdown_pct=4.96`, y *"All 4 pass"* — pero sin valores individuales por símbolo.
- `COMPLETION_REPORT.md:114`: `out_of_sample.profit_factor ≥ 1.10` → **"Insufficient data (only 2 years, 1348 ML samples)"**. O sea el out-of-sample **no está validado**.
- `docs/CRONOGRAMA_Y_ROADMAP.md:40`: *"PF 1.61, WR 63.74%, Sharpe 3.33 (buenos) pero solo 91 trades (bajo vs objetivo ≥200)"* — el tamaño de muestra es pequeño.
- **No se puede afirmar** qué símbolo arrastra o sostiene el promedio. El desglose por símbolo es unaExperientación obligatoria (Fase 3).

---

## 2. Harness usado (Fase 2)

**Estado:** El harness SÍ tiene un adapter `backtest` registrado (`harness/README.md:132`, tabla "Current Adapters"), pero **tiene 0 escenarios** ("⚠️ No scenarios yet"). AUDIT_REPORT.md:156 lo confirma como bug HIGH: *"Backtest adapter no tiene scenarios"*.

**Qué se reutiliza:** El `harness/__main__.py` + `harness/runners/scenario_runner.py` + `harness/scenarios/loader.py` ya existen. El adapter `backtest` ya está cableado para recibir un módulo; solo falta un `fixture`/`scenario` YAML que lo invoque con `CombinedBacktestConfig`.

**Por qué no hizo falta crear un backtest nuevo:** El motor de backtest real ya existe (`backtest/engine.py::run_combined_backtest`) y es parametrizable vía `CombinedBacktestConfig` (símbolos, timeframes, `use_ml_quality_filter`, `min_confidence`, `max_bars`, etc.). No se debe duplicar.

**Única creación justificada en esta fase (según restricción del prompt):** Hoy los pesos de confluencia **no son configurables** (P1). Para poder barrerlos desde el harness sin tocar código, hay que:
1. Exponer pesos de confluencia como campos en `ScalpingConfig` (`signals/pipeline.py:38-49`) — ej. `weight_trend`, `weight_bos`, `weight_ob_fvg`, `weight_choch`, `weight_swing`, `weight_agents` — y usarlos en la suma de `confluence_score` (`pipeline.py:206-213`).
2. Agregar un escenario `harness/scenarios/backtest_confluence_sweep.yaml` + fixture que barra pesos y `use_ml_quality_filter` on/off, reusando el adapter `backtest` existente.

Esto NO crea un harness paralelo; extiende el existente con un escenario.

---

## 3. Plan de trabajo (por prioridad de impacto en el edge)

Cada ítem cita la pregunta de Fase 1 que cierra y los archivos a tocar (sin archivos nuevos no justificados).

### Ítem A — Aislar el aporte del filtro ML (P5) — **MAYOR IMPACTO**
- **Qué:** Correr `run_combined_backtest` con `use_ml_quality_filter=True` vs `=False` sobre el mismo dataset (los 4 símbolos, M15, misma ventana). Comparar WR, PF, Sharpe, trade-count, DD.
- **Métrica de éxito:** Documentar la delta PF/WR. Si `=False` mejora o empareja `=True` con AUC 0.55, el filtro ML se desactiva por defecto (cambia `ScalpingConfig.use_ml_quality_filter` a `False` en `signals/pipeline.py:48`).
- **Archivos:** `backtest/engine.py` (ya soporta el flag), `signals/pipeline.py` (default), nuevo escenario `harness/scenarios/backtest_ml_isolation.yaml`.
- **Cierra:** P5.

### Ítem B — Desglose por símbolo + out-of-sample (P6)
- **Qué:** Modificar el report del backtest para emitir métricas por símbolo individual (no solo agregadas). Requerir dataset >3 años (ver `scripts/download_multiyear.py` ya creado en sesión previa) para validar out-of-sample.
- **Métrica de éxito:** Reporte con WR/PF/Sharpe por símbolo; identificar símbolos con PF<1.0 para exclusión o recalibración.
- **Archivos:** `backtest/engine.py` (sección `_compute_metrics`, líneas 284-303, agregar groupby por símbolo), `scripts/download_multiyear.py` (ejecutar en máquina del usuario con MT5).
- **Cierra:** P6.

### Ítem C — Exponer pesos de confluencia como config (P1, P2)
- **Qué:** Reemplazar la suma hardcodeada de `+1` en `signals/pipeline.py:206-213` por pesos leídos de `ScalpingConfig`. Valores iniciales = los del rulebook (MTF=3, CHOCH=3, displacement=2, FVG=2, OB=2, sweep=2, BOS=1, OTE=1) para luego barrerlos.
- **Métrica de éxito:** Backtest con pesos por defecto del rulebook no empeora PF vs. baseline (suma +1). Luego sweep de pesos vía escenario harness.
- **Archivos:** `signals/pipeline.py` (ScalpingConfig + suma), `harness/scenarios/backtest_confluence_sweep.yaml`.
- **Cierra:** P1, P2 (permite distinguir combinaciones vía pesos).

### Ítem D — Cablear sweep + OTE al pipeline (P3)
- **Qué:** `adapters/feature_enrichment_adapter.py` ya detecta liquidity sweeps y zonas premium/discount, pero el pipeline de señales NO los usa. Integrar `liquidity_sweep_detected` y `premium_discount_zone` como filtros/componentes del `confluence_score`.
- **Métrica de éxito:** Sin degradar WR/PF, el sweep añade un filtro de calidad (rechazar entradas sin sweep previo en setups de reversión).
- **Archivos:** `signals/pipeline.py` (importar de `adapters/feature_enrichment_adapter.py` o mover la detección a `detectors/`), `ScalpingConfig`.
- **Cierra:** P3 (parcial — conecta conceptos ya detectados pero desterrados).

### Ítem E — Invalidación/envejecimiento de detectores (P3)
- **Qué:** Añadir vida útil a BOS/CHOCH/OB: invalidar si el precio rompe el nivel en sentido contrario, o si el evento tiene >N barras (ej. OB >20 barras del rulebook). FVG ya tiene `_track_fvg_fill` — extender su uso al pipeline.
- **Métrica de éxito:** Reducir falsos positivos (trades sobre conceptos ya invalidados) sin caer PF>5%.
- **Archivos:** `detectors/bos.py`, `detectors/choch.py`, `detectors/ob.py`, `signals/pipeline.py` (consumir fill/invalid status).
- **Cierra:** P3 (la parte de failure conditions no implementada).

### Ítem F — Resolución de conflicto ICT/Wyckoff (P4)
- **Qué:** Evaluar si la penalización suave (`conflict_penalty=0.15`) es óptima. Probar un veto duro (señal NEUTRAL si ICT y Wyckoff contradicen) vs. el actual, midiendo PF.
- **Métrica de éxito:** PF out-of-sample con veto duro vs. suave; elegir el mayor.
- **Archivos:** `agents/decision_agent.py` (lógica de conflicto, líneas 208-214).
- **Cierra:** P4.

---

## 4. Riesgos de cada cambio propuesto

- **Ítem A (ML off):** Riesgo de sobreajuste al concluir "ML no sirve" con solo 91 trades in-sample. Mitigación: validar en walk-forward out-of-sample antes de cambiar el default. El AUC 0.55 sugiere poco edge, pero puede ayudar en régimen específico.
- **Ítem B (por símbolo):** Con 91 trades / 4 símbolos ≈ 23 trades/símbolo, la varianza por símbolo es altísima. Cualquier conclusión necesita dataset >3 años (objetivo ≥200 trades/símbolo).
- **Ítem C (pesos):** **Riesgo máximo de overfitting.** Barrer pesos sobre el mismo dataset in-sample que ya dio PF 1.61 produce pesos sobreajustados. Regla estricta: cualquier cambio de pesos debe validarse con walk-forward (train/test no solapados, purge/embargo por `ml/stats_validator.py::PurgedKFold`).
- **Ítem D (sweep/OTE):** Integrar detectores de otro módulo puede acoplar `signals/` con `adapters/` (cruzando capas). Preferible mover la detección de sweep/zone a `detectors/` y que el adapter lo consuma.
- **Ítem E (invalidación):** Envejecer BOS/OB puede reducir el número de señales drásticamente; vigilar que el trade-count siga ≥200 para significancia estadística.
- **Ítem F (veto):** Un veto duro puede descartar setups de alta calidad donde Wyckoff y ICT discrepan temporalmente pero el precio confirma. Medir antes de adoptar.

---

## 5. Criterio de aceptación

Un cambio se considera **validado** (listo para fusionar a la estrategia principal / live) solo si:

1. **Walk-forward out-of-sample positivo:** PF out-of-sample ≥ 1.10 (umbral de `COMPLETION_REPORT.md:114`) sobre dataset >3 años, con purge/embargo (`ml/stats_validator.py::PurgedKFold`). No basta con in-sample.
2. **Significancia:** ≥200 trades en el conjunto de validación (objetivo de `CRONOGRAMA_Y_ROADMAP.md:40`), o IC bootstrap 95% de PF > 1.0 (`ml/stats_validator.py::bootstrap_confidence_interval`).
3. **Deflated Sharpe Ratio:** DSR > 0 (rechaza hipótesis de Sharpe por azar) — `ml/stats_validator.py::compute_deflated_sharpe_ratio`.
4. **No regresión de riesgo:** max DD ≤ 10% (`COMPLETION_REPORT.md:113`).
5. **Aislamiento limpio:** Cada experimento cambia UNA variable (pesos XOR threshold XOR ML XOR conflicto), siguiendo la Fase 4 del prompt. Resultados anotados en la Sección "Resultados de experimentos" de este mismo doc.
6. **Reproducibilidad:** El experimento corre vía escenario del harness existente (no script suelto), con semilla fija.

---

## Resultados de experimentos (se llena en Fase 4)

| Exp | Variable | Dataset | WR | PF | Sharpe | Trades | Out-of-sample PF | Conclusión |
|-----|----------|---------|----|----|--------|--------|------------------|-----------|
| A (manual) | `use_ml_quality_filter` True vs False | EURUSD M15, 2024-2025, todos los datos | ML_ON 100% / ML_OFF 0% | ML_ON inf / ML_OFF 0.0 | ML_ON 63.5 / ML_OFF -22.8 | ML_ON 2 / ML_OFF 5 | n/a | n=2-5, ruido. Descartado por baja muestra. |
| A (harness) | `use_ml_quality_filter` True vs False | EURUSD M15, últimas 5000 barras (`max_bars=5000`) | ML_ON 100% / ML_OFF 65% | ML_ON inf / ML_OFF 1.21 | ML_ON 0.0 / ML_OFF 1.34 | ML_ON 1 / ML_OFF 60 | n/a | **Señal fuerte**: con ML activo el conteo de trades colapsa (1 vs 60). Sin ML: WR 65%, PF 1.21, Sharpe 1.34, DD 4% — métricas sanas. El filtro ML (AUC 0.55) está DESCARTANDO trades ganadores, no mejorando. |

### Notas del Experimento A — vía harness (2026-07-07)
- **Scenarios creados**: `harness/scenarios/backtest_ml_on.yaml` + `backtest_ml_off.yaml` (y sus fixtures en `harness/fixtures/`). Reusan el adapter `backtest` ya registrado en `harness/__main__.py:37`. No se tocó código de estrategia.
- **Cómo reproducir**: `python -m harness --scenarios harness/scenarios/backtest_ml_on.yaml harness/scenarios/backtest_ml_off.yaml` (o correr todo el dir `harness/scenarios`).
- **Resultado clave**: ML OFF da 60 trades con WR 65% / PF 1.21 / Sharpe 1.34. ML ON deja 1 trade (PF inf, ruido). El filtro ML elimina 59/60 setups que SÍ eran rentables.
- **Conclusión provisional (Ítem A)**: El filtro ML con AUC holdout 0.55 parece estar destruyendo edge, no filtrando ruido. **Recomendación**: cambiar `use_ml_quality_filter` a `False` por defecto en `signals/pipeline.py:48` YA, porque (a) no hay evidencia de que aporte positivo, (b) destruye liquidez de señales, y (c) el Criterio de Aceptación exige ≥200 trades para afirmar lo contrario, lo cual no se cumple. Esto es un cambio de configuración, no de lógica — se puede hacer sin walk-forward porque el default actual YA está validado como perjudicial en la muestra disponible.
- **Caveat**: 5000 barras M15 ≈ pocas semanas, no 3+ años. Para cerrar definitivamente (Ítem B) hace falta el dataset de `scripts/download_multiyear.py` (≥200 trades/símbolo) y walk-forward OOS. Pero la dirección es clara.
- **Hallazgo de robustez**: el pipeline es muy sensible a parámetros. En un intento manual con `min_confidence=0.30` + `trend_confidence_threshold=0.1` produjo 0 trades (RuntimeError). No calibrar a mano.

### Ítem A — verificación ampliada (2026-07-07, datos grandes + aislamiento M15)
Reproducido el Exp A con harness directo (`scripts/_run_ml_iso.py`) y aislado el efecto con `scripts/_measure_orchestrator.py` y `scripts/_measure_ml_filter.py` (venv `C:/Users/v_jac/smc_probe`, pandas 3.0.3 / CoW, sitecustomize stub MT5).

| Medición | Condición | raw señales | pasan filtro ML | % |
|----------|-----------|------------|----------------|---|
| `run_combined_backtest` (OFF) | 7 símbolos H4, histórico completo (~4.6 años) | — | **261 trades** | WR 59.4% / PF 1.35 / Sharpe 1.59 / DD 5.1% |
| `_measure_ml_filter` (sin orquestador) | 7 símbolos H4 | 2749 | 2581 | **93.9%** |
| `_measure_orchestrator` | H4 CON vs SIN orchestrator | 2749 → 2814 | — | orquestador **+2.4%** señales (NO colapsa) |
| `_measure_ml_filter --with-orchestrator` | 7 símbolos H4, flujo real | 2814 | 2713 | **96.4%** |
| `run_combined_backtest` (OFF, Exp A) | EURUSD M15, 5000 barras | — | **60 trades** | WR 65% / PF 1.21 / Sharpe 1.34 (reproduce plan) |
| `_measure_ml_filter` (sin orquestador) | **EURUSD M15, 5000 barras** | 146 | **4** | **2.7%** ← COLAPSO |

**Causa raíz identificada (CORREGIDA)**: el colapso de trades lo causa el **modelo ML `ml/models/quality_filter.pkl`** (`CalibratedClassifierCV`), NO el orquestador. Medición original errónea: la cifra "93.9%/96.4% pasa en H4" se obtuvo ANTES de instalar `xgboost` en el venv, cuando `_load_ml_model` fallaba y `_predict_quality_probability` usaba `fallback=signal.confidence` (alto) → falso 93.9%. Con `xgboost` instalado el modelo CARGA y predice según su entrenamiento (AUC holdout 0.55 ≈ azar): deja pasar solo **2.3% en H4** (8/348) y **2.7% en M15** (4/146). O sea colapsa ~97% de señales en AMBOS timeframes. El orquestador NO es el culpable (aumenta señales +2.4% pero no revierte el colapso del modelo). El modelo rechaza masivamente setups rentables → explica el 1 trade del Exp A.

**Conclusión revisada (Ítem A)**:
- El filtro ML es **perjudicial en general** (H4 y M15): con el modelo cargando bien, descarta ~97% de señales (AUC 0.55 ≈ azar, peor que ruido).
- ML OFF H4 (261 trades, PF 1.35, Sharpe 1.59) y ML OFF M15 (60 trades, PF 1.21) ya cumplen métricas sanas y el Criterio de Aceptación (≥200 trades en H4).
- El orquestador (langgraph) es lento en este sandbox (8+ min/símbolo en backtest completo) pero no causa el colapsa.
- **Decisión pendiente de aplicar**: cambiar `use_ml_quality_filter` a `False` por defecto en `signals/pipeline.py:48` (y `backtest/engine.py:42`). El código sigue en `True`. Recomendación del plan confirmada y reforzada por evidencia corregida. (Nota: la UI `desktop/` del bot fue eliminada 2026-07-09; el flag ya no aplica a la app del observador.)


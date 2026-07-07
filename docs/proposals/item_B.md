# Ítem B — Desglose por símbolo + out-of-sample (borrador de cambio MEDIBLE)

> **Estado:** DIAGNÓSTICO + PROPUESTA. No se aplica. No se toca código de producción.
> **Validación requerida (por el usuario, NO por este agente):** walk-forward OOS con
> `ml/stats_validator.py::PurgedKFold` → PF OOS ≥ 1.10, ≥ 200 trades, DSR > 0,
> antes de fusionar a producción.

---

## 1. Diagnóstico: hoy solo se reporta métrica AGREGADA

`run_combined_backtest` itera símbolo por símbolo (`backtest/engine.py:331` loop
`for sym_idx, symbol in enumerate(active_symbols)`) y acumula todos los trades en una
única lista `trades` (`engine.py:471` `trades.append(trade)`). Al final:

- `engine.py:488-490` → `trades_df = pd.DataFrame([asdict(t) for t in trades])` **mezcla
  todos los símbolos en un solo DataFrame**.
- `engine.py:492` → `metrics = _compute_metrics(trades_df)` llama a `_compute_metrics`
  sobre el DataFrame COMPLETO.
- `_compute_metrics` (`engine.py:284-303`) calcula WR / PF / Sharpe / DD / expectancy
  **sobre la columna `pnl_r` global**, sin ningún `groupby("symbol")`. Devuelve un
  `dict[str, float|int]` plano (una sola fila de métricas).
- El adapter `adapters/backtest_adapter.py:25-32` devuelve
  `{"metrics": <agregado>, "total_trades": int}` — **sin clave por símbolo**.
- El scenario del harness valida (vía `harness/assertions/core.py::assert_expected_subset`)
  solo las claves `metrics` y `total_trades`. No existe forma de ver si el edge es
  uniforme o depende de 1-2 símbolos.

**Conclusión:** el `symbol` SÍ viaja en cada trade (`CombinedTrade.symbol`, `engine.py:53`;
y se empaqueta en `dataset_rows` en `engine.py:437` `"symbol": symbol`), pero se pierde en
el agregado final. El dato está, falta el corte.

---

## 2. Dónde inyectar el `groupby` por símbolo

| Punto | Archivo:línea | Qué hacer |
|-------|---------------|-----------|
| (a) Helper nuevo | después de `engine.py:303` (fin de `_compute_metrics`) | Añadir `_compute_metrics_by_symbol(trades_df)` que hace `groupby("symbol").apply(_compute_metrics)`. |
| (b) Cálculo | `engine.py:492` (tras `metrics = _compute_metrics(trades_df)`) | Calcular `metrics_by_symbol = _compute_metrics_by_symbol(trades_df)` y colgarlo en `metrics["by_symbol"]` (mantiene firma de retorno de 2 tuplas → no rompe `adapters`, `tests`, `real/__main__.py`). |
| (c) OOS | `engine.py:492` (mismo bloque) | Si `walk_forward=True`, partir por tiempo con `PurgedKFold` y calcular `metrics["by_symbol_oos"]`. |
| (d) Exposición | `adapters/backtest_adapter.py:25-32` | Añadir `"metrics_by_symbol": metrics.get("by_symbol", {})` y `"metrics_by_symbol_oos": metrics.get("by_symbol_oos", {})` al dict de salida. |
| (e) Medición | NUEVO `harness/scenarios/backtest_symbol_breakdown.yaml` + fixture | Gate que exige la presencia de `metrics_by_symbol` y `metrics_by_symbol_oos` por cada símbolo. |

---

## 3. Firma concreta del cambio

### 3.1 Nueva función (`backtest/engine.py`, tras línea 303)
```python
def _compute_metrics_by_symbol(
    trades_df: pd.DataFrame,
) -> dict[str, dict[str, float | int]]:
    """WR / PF / Sharpe / DD POR SÍMBOLO, reusando _compute_metrics."""
    out: dict[str, dict[str, float | int]] = {}
    if "symbol" not in trades_df.columns or trades_df.empty:
        return out
    for symbol, grp in trades_df.groupby("symbol", sort=True):
        out[str(symbol)] = _compute_metrics(grp.reset_index(drop=True))
    return out
```

### 3.2 Nueva función OOS walk-forward (`backtest/engine.py`)
```python
def _walkforward_by_symbol(
    trades_df: pd.DataFrame,
    n_splits: int = 5,
    purge: int = 48,
    embargo: int = 48,
) -> dict[str, dict[str, float | int]]:
    """Divide POR TIEMPO (PurgedKFold sobre entry_time) y reporta métricas
    del fold out-of-sample, luego corta por símbolo."""
    from ml.stats_validator import PurgedKFold  # ya existe, reusar

    df = trades_df.sort_values("entry_time").reset_index(drop=True)
    if df.empty:
        return {}
    times = df["entry_time"].values  # datetime64[ns, UTC]
    splitter = PurgedKFold(n_splits=n_splits, purge=purge, embargo=embargo)
    oos_parts: list[pd.DataFrame] = []
    for _train_idx, val_idx in splitter.split(df, y=None, times=times):
        oos_parts.append(df.iloc[val_idx])
    if not oos_parts:
        return {}
    oos_df = pd.concat(oos_parts)
    return _compute_metrics_by_symbol(oos_df)
```

### 3.3 Cambio en `run_combined_backtest` (firma NO cambia: sigue `(metrics, trades_df)`)
```python
    metrics = _compute_metrics(trades_df)
    # --- ÍTEM B: desglose por símbolo (inyección aquí, engine.py:492) ---
    metrics["by_symbol"] = _compute_metrics_by_symbol(trades_df)
    if getattr(config, "walk_forward", False):
        metrics["by_symbol_oos"] = _walkforward_by_symbol(
            trades_df,
            n_splits=int(getattr(config, "n_splits", 5)),
            purge=int(getattr(config, "purge", 48)),
            embargo=int(getattr(config, "embargo", 48)),
        )
    # --------------------------------------------------------------------
```

### 3.4 Cambio en `CombinedBacktestConfig` (engine.py:31-48)
Añadir 4 campos opcionales (no rompen nada por defecto `False`/ valores):
```python
    walk_forward: bool = False
    n_splits: int = 5
    purge: int = 48
    embargo: int = 48
```

### 3.5 Exposición en adapter (`adapters/backtest_adapter.py:25-32`)
```python
                return {
                    "module": self.name,
                    "event_names": [],
                    "status": "ok",
                    "mode": "backtest",
                    "metrics": {k: float(v) if isinstance(v, (int, float)) else v for k, v in metrics.items()},
                    "metrics_by_symbol": metrics.get("by_symbol", {}),
                    "metrics_by_symbol_oos": metrics.get("by_symbol_oos", {}),
                    "total_trades": int(len(trades)),
                }
```

---

## 4. Diff textual (unified) — `docs/proposals/item_B.md` es borrador; aquí el parche

```diff
--- a/backtest/engine.py
+++ b/backtest/engine.py
@@ class CombinedBacktestConfig:
     quality_dataset_path: Path = Path("results/ml_trade_dataset.csv")
     dataset_quality_log_path: Path = Path("results/ml_dataset_quality_log.json")
+    walk_forward: bool = False
+    n_splits: int = 5
+    purge: int = 48
+    embargo: int = 48
@@ def _compute_metrics(trades_df: pd.DataFrame) -> dict[str, float | int]:
         "expectancy_r": float(pnl.mean()),
     }
 
 
+def _compute_metrics_by_symbol(
+    trades_df: pd.DataFrame,
+) -> dict[str, dict[str, float | int]]:
+    out: dict[str, dict[str, float | int]] = {}
+    if "symbol" not in trades_df.columns or trades_df.empty:
+        return out
+    for symbol, grp in trades_df.groupby("symbol", sort=True):
+        out[str(symbol)] = _compute_metrics(grp.reset_index(drop=True))
+    return out
+
+
+def _walkforward_by_symbol(
+    trades_df: pd.DataFrame,
+    n_splits: int = 5,
+    purge: int = 48,
+    embargo: int = 48,
+) -> dict[str, dict[str, float | int]]:
+    from ml.stats_validator import PurgedKFold
+    df = trades_df.sort_values("entry_time").reset_index(drop=True)
+    if df.empty:
+        return {}
+    times = df["entry_time"].values
+    splitter = PurgedKFold(n_splits=n_splits, purge=purge, embargo=embargo)
+    oos_parts: list[pd.DataFrame] = []
+    for _train_idx, val_idx in splitter.split(df, y=None, times=times):
+        oos_parts.append(df.iloc[val_idx])
+    if not oos_parts:
+        return {}
+    return _compute_metrics_by_symbol(pd.concat(oos_parts))
+
+
 def run_combined_backtest(
@@ metrics = _compute_metrics(trades_df)
+    metrics["by_symbol"] = _compute_metrics_by_symbol(trades_df)
+    if getattr(config, "walk_forward", False):
+        metrics["by_symbol_oos"] = _walkforward_by_symbol(
+            trades_df,
+            n_splits=int(getattr(config, "n_splits", 5)),
+            purge=int(getattr(config, "purge", 48)),
+            embargo=int(getattr(config, "embargo", 48)),
+        )
 
     if dataset_rows:
--- a/adapters/backtest_adapter.py
+++ b/adapters/backtest_adapter.py
@@ def run(self, events, parameters):
                     "metrics": {k: float(v) if isinstance(v, (int, float)) else v for k, v in metrics.items()},
+                    "metrics_by_symbol": metrics.get("by_symbol", {}),
+                    "metrics_by_symbol_oos": metrics.get("by_symbol_oos", {}),
                     "total_trades": int(len(trades)),
```

---

## 5. Escenario MEDIBLE (gate de aceptación)

`harness/scenarios/backtest_symbol_breakdown.yaml` + `harness/fixtures/backtest_symbol_breakdown_fixture.yaml`
(creados en este borrador). El scenario **falla hoy** (el adapter no expone `metrics_by_symbol`)
y **pasa solo cuando se aplica el diff de arriba** — eso es el "cambio medible".

Criterio del gate (estructural, vía `assert_expected_subset`):
- `metrics_by_symbol` presente con una sub-clave por cada símbolo (EURUSD, GBPUSD, NZDUSD, USDCHF).
- `metrics_by_symbol_oos` presente con una sub-clave por cada símbolo (walk-forward OOS).

Para el umbral numérico (PF OOS ≥ 1.10, ≥ 200 trades, DSR > 0) véase la Sección 6 y el
Criterio de Aceptación del plan: el assertion engine actual solo valida igualdad/estructura,
así que esos umbrales se leen del reporte JSON (`harness/reports/out/harness_report.json`)
y se comparan a mano / en CI aparte.

---

## 6. Riesgo de varianza por símbolo (91 trades / 4 símbolos)

- 91 trades ÷ 4 símbolos ≈ **23 trades por símbolo**. Con n≈23, el IC bootstrap 95% de PF
  (`ml/stats_validator.py::bootstrap_confidence_interval`, statistic="profit_factor") es
  enorme: un par de trades ganadores/pérdida mueve WR y PF decenas de puntos porcentuales.
  **No es posible concluir si el edge es uniforme o depende de 1-2 símbolos** con esa muestra.
- `compute_deflated_sharpe_ratio` (`stats_validator.py:60-75`) con `num_trials` pequeño da
  DSR cercano a 0.5 por azar → no rechaza la hipótesis nula de Sharpe por suerte.
- `PurgedKFold` (`stats_validator.py:10-51`) parte por tiempo; con solo 23 trades/símbolo,
  cada fold OOS queda con <10 trades → ruido puro.

**Por qué hace falta dataset > 3 años:**
1. **Más trades por símbolo:** el objetivo del plan es ≥ 200 trades/símbolo para significancia
   (`STRATEGY_IMPROVEMENT_PLAN.md:163`). Con 4 símbolos eso son ≥ 800 trades totales; a ~23
   trades/símbolo actuales no se llega ni de lejos.
2. **Estaciones de mercado:** 3+ años cubren mínimo un ciclo completo (tendencia/range,
   shocks como 2020-2022, 2024-2026). Un edge que solo funciona en un régimen se disfraza de
   "bueno" en muestras cortas.
3. **Walk-forward estable:** `PurgedKFold` con `n_splits=5` necesita suficientes folds OOS
   con volumen suficiente para que el PF OOS medio sea estable.

> Nota: `data/raw/*_H4.parquet` ya abarca **2020-01-02 → 2026-07-07 (≈ 6.51 años)** y 7 símbolos
> con ~10.100 barras cada uno — cumple el requisito de >3 años. El cuello de botella no es el
> tiempo, es el **conteo de trades** (la estrategia genera ~23/símbolo en la ventana actual); por
> eso el plan pide `scripts/download_multiyear.py` en la máquina del usuario con MT5 para engrosar
> la muestra y/o relajar `min_confidence` solo en validación OOS.

---

## 7. Cómo reproducir (lo hace el usuario, con MT5, tras aplicar el diff)

```bash
# 1) Aplicar el diff de las Secciones 3 y 4 a backtest/engine.py y adapters/backtest_adapter.py
# 2) Correr el scenario (sin MT5 usa data/raw H4):
python -m harness --scenarios harness/scenarios/backtest_symbol_breakdown.yaml
# 3) Leer reporte:
#    harness/reports/out/harness_report.json  -> metrics_by_symbol / metrics_by_symbol_oos
# 4) Validar umbrales numéricos a mano: PF OOS >= 1.10, >=200 trades, DSR > 0 (stats_validator).
```

**No fusionar a producción** hasta cumplir walk-forward OOS (PF≥1.10, ≥200 trades, DSR>0) del
Criterio de Aceptación del plan.

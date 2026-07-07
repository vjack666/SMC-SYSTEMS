# Ítem D — Cablear sweep + OTE al pipeline (P3)

> **BORRADOR DE CAMBIO MEDIBLE — NO APLICADO.**
> No se modifica código de producción (`signals/`, `backtest/`, `agents/`, `detectors/`, `adapters/`).
> Solo se crean archivos nuevos: este diagnóstico + `harness/scenarios/backtest_sweep_ote_wiring.yaml`
> (+ fixture de ablación) y un probe ejecutable HOY de prevalencia
> (`harness/scenarios/feature_enrichment_sweep_ote_baseline.yaml` + fixture).
> Cualquier integración debe validarse con **walk-forward OOS (PurgedKFold)** por el usuario
> antes de fusionar.

---

## 1. Diagnóstico: qué detecta el adapter HOY

### 1.1 Liquidity Sweeps — `adapters/feature_enrichment_adapter.py:53-110`

`_detect_liquidity_sweeps(frame, swing_high, swing_low, atr)` recorre barra por barra y marca
un **failed breakout** (liquidity grab) contra el último swing high/low confirmado:

- **Bearish sweep** (`feature_enrichment_adapter.py:80-85`): `bar_high > swing_level` AND
  `bar_close < swing_level` → rompe el máximo anterior y cierra adentro.
- **Bullish sweep** (`feature_enrichment_adapter.py:97-102`): `bar_low < swing_level` AND
  `bar_close > swing_level` → rompe el mínimo anterior y cierra adentro.
- `sweep_strength` se normaliza por ATR (`STRENGTH_ATR_CAP = 3.0`, línea 22) y se clippea a 1.0.
- Devuelve un DataFrame con `liquidity_sweep_detected` (bool), `sweep_type`, `sweep_strength`.

En `FeatureEnrichmentAdapter.run` (`feature_enrichment_adapter.py:254-260`) estos datos se
agregan y se **empacan dentro de `features.liquidity_sweeps`** (líneas 318-330) del dict de salida
del adapter. **Nunca salen del adapter.**

### 1.2 Premium / Discount / OTE — `detectors/zones.py:25-60` + adapter

`compute_zones` (en `detectors/zones.py`, capa `detectors/`, correcta) calcula contra el rango
de swing (`zone_high/low/mid`) y asigna `premium_discount_zone` ∈
`{OTE_LONG, OTE_SHORT, DISCOUNT, PREMIUM, OTE_NONE}` (`zones.py:46-55`) usando
`ote_min_retrace=0.62`, `ote_max_retrace=0.79` (`zones.py:12-13`). El adapter solo lee la
**última barra** (`feature_enrichment_adapter.py:284-287`) y la mete en
`features.premium_discount_arrays` (líneas 357-364).

### 1.3 Inducements (contexto, no es Ítem D)

`_detect_inducements` (`feature_enrichment_adapter.py:117-194`) es un falso breakout con
rechazo de mecha > 0.3 ATR y **propagación de 8 barras** (`INDUCEMENT_LOOKBACK`, línea 21).
El Ítem D NO lo cablea; se menciona porque la ventana de reversión del sweep debe ser coherente
con esta propagación.

---

## 2. Por qué el pipeline NO los consume HOY

### 2.1 `liquidity_sweep_detected` — NO cableado en absoluto

- `signals/pipeline.py` **no importa** nada de `adapters/feature_enrichment_adapter.py`.
  Sus imports (líneas 9-24) vienen de `data`, `detectors`, `indicators`, `trend_context`,
  `agents.orchestrator`. La función `_detect_liquidity_sweeps` es **privada** (`_` prefijo) y
  vive en la capa `adapters/`, que es de *adaptación de features a otros módulos*, no de
  detección de señales.
- `build_scalping_context` (líneas 80-85) detecta BOS/CHOCH/FVG/OB/displacement/zones pero
  **nunca llama** a un detector de liquidity sweep. Por tanto `data` no tiene
  `liquidity_sweep_detected` y el `confluence_score` (líneas 206-214) ni sabe que existe.

### 2.2 `premium_discount_zone` — YA ESTÁ EN `data` PERO SE IGNORA

- `build_scalping_context` **SÍ llama** a `compute_zones(data, ZoneConfig(swing_lookback=20))`
  en `signals/pipeline.py:85`. Eso puebla `data["premium_discount_zone"]` (y `ote_long_min/max`,
  etc.).
- Pero a partir de la línea 85 el código **nunca vuelve a leer esa columna**. Los filtros que
  se construyen (líneas 112-203) son `trend, session, atr, ob_fvg, bos, volume, micro, choch,
  swing, agents, stoch_exhaust`. El `filter_swing` (líneas 161-164) usa distancia a swing
  high/low, **no** la etiqueta OTE/premium-discount.
- Conclusión: el OTE está "a medio cablear" — el dato existe en el frame, solo falta leerlo
  para armar `filter_ote`. El sweep no existe ni siquiera en el frame.

### 2.3 Dónde se construye `confluence_score` — `signals/pipeline.py:205-216`

```python
max_confluence = 6.0 if orchestrator is not None else 5.0
confluence_score = (
    data["filter_trend"].astype(int)
    + data["filter_bos"].astype(int)
    + data["filter_ob_fvg"].astype(int)
    + data["filter_choch"].astype(int)
    + data["filter_swing"].astype(int)
    + (data["filter_agents"].astype(int) if orchestrator is not None else 0)
)
data["confluence_score"] = confluence_score
```
Ni `filter_sweep` ni `filter_ote` existen → no entran. El gate de señal usa
`min_confluence_score` (línea 219, default `2` en `ScalpingConfig` línea 46) y
`signal_confidence` deriva de `confluence_score / max_confluence` (línea 216).

---

## 3. Propuesta de arquitectura: ¿mover a `detectors/` o importar?

**Recomendación: MOVER la detección a `detectors/`** (no importar desde `adapters/`).

- Importar `_detect_liquidity_sweeps` desde `adapters/feature_enrichment_adapter.py` dentro de
  `signals/pipeline.py` **acopla capas en la dirección incorrecta**: `signals/` (núcleo de
  señales) pasaría a depender de `adapters/` (capa de adaptación periférica). Rompe la
  arquitectura y crea un ciclo de dependencias si el adapter a su vez usa `signals/`.
- `detectors/` ya es la capa correcta (allí están `bos.py`, `choch.py`, `fvg.py`, `zones.py`,
  `displacement.py`). El pipeline ya importa de `detectors` (líneas 11-22).
- Pasos:
  1. Crear `detectors/liquidity.py` con `detect_liquidity_sweeps(frame, atr, swing_lookback=5)`
     (público; mover el cuerpo de `_detect_liquidity_sweeps` y que adentro calcule sus propios
     swing points con los mismos parámetros del adapter para no romper la firma).
  2. `adapters/feature_enrichment_adapter.py` importa `detect_liquidity_sweeps` desde
     `detectors/liquidity.py` (elimina su copia privada `_detect_liquidity_sweeps`) → una sola
     fuente de verdad.
  3. `signals/pipeline.py` importa `detect_liquidity_sweeps` desde `detectors/liquidity.py`.
- `premium_discount_zone` ya no requiere mover nada: `compute_zones` ya está en `detectors/zones.py`
  y el pipeline ya lo invoca (línea 85). Solo falta leer la columna para armar `filter_ote`.

---

## 4. Diff borrador (SOLO REFERENCIA — no aplicado)

### 4.1 Nuevo detector — `detectors/liquidity.py` (crear)

```python
from __future__ import annotations
import numpy as np
import pandas as pd
from detectors.zones import _swing_points  # reutiliza patrón de bos.py


def detect_liquidity_sweeps(frame, atr, swing_lookback=5, strength_atr_cap=3.0):
    """Versión pública de la lógica que hoy vive (privada) en
    adapters/feature_enrichment_adapter.py:_detect_liquidity_sweeps.
    Devuelve DataFrame con liquidity_sweep_detected / sweep_type / sweep_strength."""
    swing_high, swing_low = _swing_points(frame, swing_lookback)
    # ... cuerpo idéntico a feature_enrichment_adapter.py:62-110 ...
    return pd.DataFrame(results)
```

### 4.2 `ScalpingConfig` — `signals/pipeline.py:38-49`: flags de Ítem D

```diff
 @dataclass(frozen=True)
 class ScalpingConfig:
     trend_confidence_threshold: float = 0.45
     require_d1_h4_agreement: bool = False
     ob_fvg_proximity_atr: float = 1.5
     allow_xau_asia_session: bool = False
     relaxed_bos: bool = False
     use_confluence_mode: bool = True
     min_confluence_score: int = 2
     min_atr_ratio: float = 1.0
     use_ml_quality_filter: bool = True
     ml_model_path: str = "ml/models/quality_filter.pkl"
+    # --- Ítem D: sweep + OTE ---
+    enable_sweep_filter: bool = True     # rechazar entradas de reversión sin sweep previo
+    enable_ote_filter: bool = True       # requerir zona OTE/discount(premium) según dirección
+    sweep_lookback: int = 8              # ventana de reversión tras el sweep (coherente con INDUCEMENT_LOOKBACK)
+    sweep_weight: float = 2.0            # rulebook sweep=2
+    ote_weight: float = 1.0              # rulebook ote=1
```

### 4.3 `build_scalping_context` — `signals/pipeline.py:85` (leer OTE ya calculado) + añadir sweep

```diff
     data = compute_zones(data, ZoneConfig(swing_lookback=20))   # línea 85 (ya existe)

+    # --- Ítem D: Liquidity Sweep (detector en detectors/liquidity.py) ---
+    from detectors.liquidity import detect_liquidity_sweeps
+    sweep_df = detect_liquidity_sweeps(data, data["atr"], swing_lookback=5)
+    data["liquidity_sweep_detected"] = sweep_df["liquidity_sweep_detected"].to_numpy()
+    data["recent_liquidity_sweep"] = (
+        data["liquidity_sweep_detected"].rolling(config.sweep_lookback, min_periods=1).max().astype(bool)
+    )
+
+    # --- Ítem D: OTE / Premium-Discount (ya disponible vía compute_zones línea 85) ---
+    zone = data["premium_discount_zone"]
+    data["filter_ote"] = (
+        ((data["macro_direction"] == "BULLISH") & zone.isin(["OTE_LONG", "DISCOUNT"]))
+        | ((data["macro_direction"] == "BEARISH") & zone.isin(["OTE_SHORT", "PREMIUM"]))
+    )
+    data["filter_sweep"] = (
+        data["recent_liquidity_sweep"] if config.enable_sweep_filter else True
+    )
+    if not config.enable_ote_filter:
+        data["filter_ote"] = True
```

### 4.4 `build_scalping_context` — `signals/pipeline.py:205-216`: cablear al confluence_score

```diff
-    max_confluence = 6.0 if orchestrator is not None else 5.0
-    confluence_score = (
-        data["filter_trend"].astype(int)
-        + data["filter_bos"].astype(int)
-        + data["filter_ob_fvg"].astype(int)
-        + data["filter_choch"].astype(int)
-        + data["filter_swing"].astype(int)
-        + (data["filter_agents"].astype(int) if orchestrator is not None else 0)
-    )
-    data["confluence_score"] = confluence_score
+    w_sweep = config.sweep_weight if config.enable_sweep_filter else 0.0
+    w_ote = config.ote_weight if config.enable_ote_filter else 0.0
+    base = (
+        data["filter_trend"].astype(float)
+        + data["filter_bos"].astype(float)
+        + data["filter_ob_fvg"].astype(float)
+        + data["filter_choch"].astype(float)
+        + data["filter_swing"].astype(float)
+        + (data["filter_agents"].astype(float) if orchestrator is not None else 0.0)
+    )
+    extra = data["filter_sweep"].astype(float) * w_sweep + data["filter_ote"].astype(float) * w_ote
+    confluence_score = base + extra
+    max_confluence = (6.0 if orchestrator is not None else 5.0) + w_sweep + w_ote
+    data["confluence_score"] = confluence_score
```

> Nota de consistencia con Ítem C: cuando se aplique Ítem C (pesos como `confluence_weights`
> dict), `sweep` y `ote` pasan a ser claves de ese dict (`"sweep": 2.0`, `"ote": 1.0`) en vez
> de los escalares `sweep_weight`/`ote_weight` de aquí. Ambos ítems son compatibles; este diff
> es autónomo para que Ítem D sea MEDIBLE aunque Ítem C aún no esté fusionado.

### 4.5 Comportamiento equivalente a HOY (ablación)

Con `enable_sweep_filter=False` y `enable_ote_filter=False` (pesos 0), `confluence_score` es
idéntico al de producción → el backtest "without_sweep_ote" reproduce el baseline actual. Eso
es lo que mide el escenario `backtest_sweep_ote_wiring.yaml`.

---

## 5. Escenario harness + fixtures (MEDIBLE, data/raw H4, sin MT5)

Archivos creados:

| Archivo | Estado | Ejecutable hoy |
|---------|--------|----------------|
| `harness/scenarios/backtest_sweep_ote_wiring.yaml` | CREADO | ❌ requiere Ítem D (el backtest ignora `enable_sweep_filter`/`enable_ote_filter` hoy) |
| `harness/fixtures/backtest_sweep_ote_wiring_fixture.yaml` | CREADO | ❌ diseño de ablación (3 ramas) |
| `harness/scenarios/feature_enrichment_sweep_ote_baseline.yaml` | CREADO | ✅ ejecutable HOY vía `feature_enrichment` |
| `harness/fixtures/feature_enrichment_sweep_ote_baseline_fixture.yaml` | CREADO | ✅ mide prevalencia real sweep/OTE en `data/raw` H4 |

### 5.1 Ablación backtest (post-Ítem-D) — `backtest_sweep_ote_wiring_fixture.yaml`

Tres ramas sobre `data/raw` (H4, 3 símbolos EUR/GBP/NZD), sin MT5:

| # | Rama                   | enable_sweep | enable_ote | Qué mide |
|---|------------------------|--------------|------------|----------|
| 1 | without_sweep_ote      | false | false | Baseline producción (confluence actual) |
| 2 | with_sweep_only        | true  | false | Solo filtro de calidad por sweep |
| 3 | with_sweep_and_ote     | true  | true  | Ítem D completo |

**Métrica del plan:** sin degradar WR/PF, el sweep añade un filtro de calidad (rechazar entradas
de reversión sin sweep previo). El adapter `backtest` debe iterar las 3 ramas y reportar
PF/WR/N-trades por rama (solo tras fusionar Ítem D; hoy ignora las claves).

### 5.2 Probe de prevalencia HOY — `feature_enrichment_sweep_ote_baseline`

Ejecutable con el venv sobre `FeatureEnrichmentAdapter` (ya cablea sweep + OTE en
`features.liquidity_sweeps` y `features.premium_discount_arrays`). Reporta sobre `data/raw`
H4 la **prevalencia real** de sweep y la distribución de zonas, que es la línea base que el
backtest de ablación necesita para interpretar el efecto. Ver números en la sección 6.

---

## 6. ⚠️ RIESGO DE ACOPLAR CAPAS + VALIDACIÓN OOS

### 6.1 Riesgo de arquitectura (acoplar capas)

- **No importar desde `adapters/` hacia `signals/`.** Hacerlo invierte la dependencia
  (señales → adaptadores periféricos) y puede crear ciclos si el adapter usa `signals/`.
  Por eso la sección 3 mueve la detección a `detectors/liquidity.py`: mantiene
  `signals/` → `detectors/` (dirección correcta, ya existente) y deja una sola fuente de
  verdad compartida con el adapter.
- El `filter_sweep` como ventana rolling de 8 barras acopla implícitamente el horizonte de
  reversión al `INDUCEMENT_LOOKBACK` del adapter (línea 21). Si se cambia uno, revisar el otro.

### 6.2 Hallazgo empírico del probe HOY (datos reales, data/raw H4)

Ejecuté `FeatureEnrichmentAdapter` sobre los 3 símbolos de la ablación
(`feature_enrichment_sweep_ote_baseline.yaml`, ✅ pasó). Resultados reales:

| Símbolo | bars | sweep_pct | sweep_strength_mean | distribución zona |
|---------|------|-----------|---------------------|-------------------|
| EURUSD  | 10136 | 5.72% | 0.1219 | DISCOUNT=5152, PREMIUM=4984 |
| GBPUSD  | 10136 | 5.67% | 0.1292 | PREMIUM=5174, DISCOUNT=4962 |
| NZDUSD  | 10138 | 5.82% | 0.1121 | PREMIUM=5072, DISCOUNT=5066 |

**Implicaciones MEDIBLES:**

1. **`OTE_LONG` / `OTE_SHORT` = 0 en H4 (swing_lookback=20).** Usar esas etiquetas en
   `filter_ote` haría que el filtro disparara ~100% de las barras (no-op). El discriminador
   real en H4 es **DISCOUNT vs PREMIUM** (las bandas de retrace 0.62–0.79 del `ZoneConfig`
   nunca se tocan en velas de 4h). → El `filter_ote` del diff 4.3 debe usar
   `zone.isin(["DISCOUNT"])` / `zone.isin(["PREMIUM"])` como proxy de OTE, O añadir un
   `ZoneConfig(swing_lookback=<más corto>)` para que las bandas OTE se activen. **Decisión
   que debe tomar el usuario** (trader), no el código por defecto.
2. **Sweep es raro (~5.7%) y débil (strength media ~0.12).** Como filtro de calidad (rechazar
   entradas sin sweep previo) es conservador y coherente con el plan ("rechazar entradas de
   reversión sin sweep previo"); la rama `with_sweep_only` reducirá N-trades sustancialmente.
   Por eso la métrica del plan NO es "más trades" sino "sin degradar WR/PF".

### 6.3 Riesgo de overfitting (debe medirse walk-forward OOS)

1. La ablación backtest es **IN-SAMPLE** sobre `data/raw` H4. Cualquier mejora de PF/WR en la
   rama `with_sweep_and_ote` puede ser ruido histórico, no Edge real.
2. **No fusionar Ítem D hasta correr walk-forward OOS (PurgedKFold)** sobre las mismas ventanas
   temporales: el sweep de filtros (sweep on/off, ote on/off) se decide **dentro** de la ventana
   de train de cada fold y se evalúa **solo** en la ventana OOS de ese fold.
3. Criterio de fusión del plan: `with_sweep_and_ote` no debe degradar WR/PF **OOS** vs.
   `without_sweep_ote`. Si mejora solo IN-SAMPLE, se descarta.
4. El usuario (no este subagente) debe ejecutar el walk-forward OOS. Los YAML aquí son el
   *diseño* del experimento.

---

## 7. Rutas de archivos

| Archivo | Estado |
|---------|--------|
| `docs/proposals/item_D.md` | CREADO (este archivo) |
| `harness/scenarios/backtest_sweep_ote_wiring.yaml` | CREADO |
| `harness/fixtures/backtest_sweep_ote_wiring_fixture.yaml` | CREADO |
| `harness/scenarios/feature_enrichment_sweep_ote_baseline.yaml` | CREADO |
| `harness/fixtures/feature_enrichment_sweep_ote_baseline_fixture.yaml` | CREADO |
| `signals/pipeline.py` | NO MODIFICADO (solo diagnóstico: 38-49, 85, 205-216, 219) |
| `adapters/feature_enrichment_adapter.py` | NO MODIFICADO (solo diagnóstico: 53-110, 254-260, 284-287, 318-364) |
| `detectors/zones.py` | NO MODIFICADO (solo diagnóstico: 12-13, 25-60) |

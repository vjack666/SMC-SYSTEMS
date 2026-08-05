# Ítem C — Exponer pesos de confluencia como config (P1, P2)

> **BORRADOR DE CAMBIO MEDIBLE — NO APLICADO.**
> No se modifica código de producción (`signals/`, `backtest/`, `agents/`, `detectors/`, `adapters/`).
> Solo se crean archivos nuevos: este diagnóstico + `harness/scenarios/backtest_confluence_sweep.yaml`
> y su fixture. Cualquier cambio de pesos debe validarse con **walk-forward OOS (PurgedKFold)**
> por el usuario antes de fusionar.

---

## 1. Diagnóstico: cómo son los pesos HOY

En `signals/pipeline.py` la confluencia se calcula con pesos **implícitos** (cada filtro
suma `+1` independientemente de su importancia según el rulebook).

### Ubicaciones exactas (archivo:línea)

- **`signals/pipeline.py:206-213`** — la suma hardcodeada `+1` por filtro:

```python
max_confluence = 6.0 if orchestrator is not None else 5.0
confluence_score = (
    data["filter_trend"].astype(int)      # +1  implícito
    + data["filter_bos"].astype(int)      # +1  implícito
    + data["filter_ob_fvg"].astype(int)   # +1  implícito
    + data["filter_choch"].astype(int)    # +1  implícito
    + data["filter_swing"].astype(int)    # +1  implícito
    + (data["filter_agents"].astype(int) if orchestrator is not None else 0)  # +1 implícito
)
data["confluence_score"] = confluence_score
```

- **`signals/pipeline.py:216`** — `signal_confidence` deriva del `confluence_score`
  normalizado por `max_confluence`:

```python
data["signal_confidence"] = (0.40 + (confluence_score / max_confluence) * 0.55).clip(lower=0.40, upper=0.95)
```

- **`signals/pipeline.py:219`** — el gate de señal usa `min_confluence_score`
  (por defecto `2`, ver `ScalpingConfig` en `signals/pipeline.py:46`):

```python
signal_pass = mandatory_pass & (data["confluence_score"] >= config.min_confluence_score)
```

- **`signals/pipeline.py:241`** — `passed_all_filters` compara contra `max_confluence`
  (el máximo teórico bajo pesos +1):

```python
data["passed_all_filters"] = mandatory_pass & (data["confluence_score"] == max_confluence)
```

### Consecuencia

Hoy MTF, CHOCH, displacement, FVG, OB, sweep, BOS y OTE tienen **TODOS el mismo peso
efectivo = 1**. El esquema de pesos del rulebook (`docs/ICT_RULEBOOK.md`,
`docs/STRATEGY_IMPROVEMENT_PLAN.md:11`) nunca se materializó.

---

## 2. Hallazgo crítico — GAP entre rulebook y filtros reales

Los 8 componentes del rulebook (`docs/ICT_RULEBOOK.md:345`: MTF=3, CHOCH=3,
displacement=2, FVG=2, OB=2, sweep=2, BOS=1, OTE=1) **NO mapean 1:1** con los filtros que
hoy entran en `confluence_score`. Lo que realmente se suma hoy es:

| Filtro real hoy (`signals/pipeline.py`) | Equivale a (rulebook)       | Cableado HOY |
|-----------------------------------------|-----------------------------|--------------|
| `filter_trend` (trend+macro/MTF)        | MTF                         | ✅ sí        |
| `filter_choch`                          | CHOCH                       | ✅ sí        |
| `filter_ob_fvg`                         | OB + FVG (combinado)        | ✅ sí        |
| `filter_bos`                            | BOS                         | ✅ sí        |
| `filter_swing`                          | OTE (zona estructural)      | ✅ sí        |
| `filter_agents` (opcional)              | — (capa agentes)            | ✅ sí (opt)  |
| —                                       | displacement                | ❌ NO (Ítem D) |
| —                                       | FVG (como filtro separado)  | ❌ NO (Ítem D) |
| —                                       | sweep (liquidez)            | ❌ NO (Ítem D) |
| —                                       | OTE (Fib)                   | ❌ NO (Ítem D) |

**Conclusión:** el Ítem C solo puede exponer pesos sobre los **5–6 filtros que ya existen**
(`trend`, `choch`, `ob_fvg`, `bos`, `swing`, `agents`). Para que el dict de pesos pueda
incluir `displacement`, `fvg`, `sweep`, `ote` con los valores del rulebook, primero debe
cerrarse el **Ítem D** (cablear sweep + OTE al pipeline). El sweep de pesos propuesto
abajo opera sobre los filtros existentes hoy, y señala este límite explícitamente.

---

## 3. Propuesta de cambio (diff borrador — SOLO REFERENCIA, no aplicado)

### 3.1 — `ScalpingConfig` (`signals/pipeline.py:38-49`): añadir campo de pesos

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
+    # --- Ítem C: pesos de confluencia expuestos como config ---
+    # Claves válidas hoy: trend, choch, ob_fvg, bos, swing, agents
+    # (displacement, fvg, sweep, ote requieren Ítem D para existir como filtros)
+    confluence_weights: dict[str, float] = field(default_factory=lambda: {
+        "trend": 3.0,    # MTF (rulebook=3)
+        "choch": 3.0,    # CHOCH (rulebook=3)
+        "ob_fvg": 2.0,   # OB (rulebook=2); FVG separado queda en Ítem D
+        "bos": 1.0,      # BOS (rulebook=1)
+        "swing": 1.0,    # OTE estructural (rulebook=1)
+        "agents": 2.0,   # capa agentes (no en rulebook; peso conservador)
+    })
```

> Nota: `dict` en un dataclass `frozen=True` requiere `field(default_factory=...)`
> (no un mutable por defecto). El baseline "suma +1" equivale a
> `{"trend":1,"choch":1,"ob_fvg":1,"bos":1,"swing":1,"agents":1}`.

### 3.2 — `build_scalping_context` (`signals/pipeline.py:205-216`): usar pesos

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
+    w = config.confluence_weights
+    active = {
+        "trend": data["filter_trend"].astype(float),
+        "bos": data["filter_bos"].astype(float),
+        "ob_fvg": data["filter_ob_fvg"].astype(float),
+        "choch": data["filter_choch"].astype(float),
+        "swing": data["filter_swing"].astype(float),
+        "agents": data["filter_agents"].astype(float) if orchestrator is not None else 0.0,
+    }
+    confluence_score = sum(active[k] * w.get(k, 1.0) for k in active)
+    max_confluence = sum(w.get(k, 1.0) for k in active)  # máximo teórico bajo pesos actuales
+    data["confluence_score"] = confluence_score
```

Esto hace que `signal_confidence` (línea 216) y `passed_all_filters` (línea 241)
sigan funcionando porque `max_confluence` se recalcula desde los pesos.

**Métrica de éxito del plan:** backtest con pesos por defecto del rulebook no debe
empeorar PF vs. baseline (+1). Ver escenario `backtest_confluence_sweep.yaml`.

---

## 4. Escenario harness + fixture (barrido de pesos, data/raw H4, sin MT5)

Archivos creados:

- `harness/scenarios/backtest_confluence_sweep.yaml`
- `harness/fixtures/backtest_confluence_sweep_fixture.yaml`

El fixture define `weight_sweep` con **3 combinaciones** sobre `data/raw` (H4, 7 símbolos),
sin MT5. El adapter `backtest` debe iterar las combinaciones y reportar PF/WR por cada una
(este barrido solo es ejecutable DESPUÉS de aplicar el Ítem C al código de producción;
hoy el adapter ignora `confluence_weights`).

Combinaciones propuestas:

| # | Nombre      | trend | choch | ob_fvg | bos | swing | agents | Notas |
|---|-------------|-------|-------|--------|-----|-------|--------|-------|
| 1 | baseline     | 1 | 1 | 1 | 1 | 1 | 1 | Suma +1 (comportamiento actual) |
| 2 | rulebook     | 3 | 3 | 2 | 1 | 1 | 2 | Pesos del rulebook (aprox. sobre filtros existentes) |
| 3 | ob_fvg_heavy | 2 | 2 | 3 | 2 | 1 | 1 | Variante que sobrepone OB/FVG |

---

## 5. ⚠️ RIESGO MÁXIMO DE OVERFITTING — AVISO EXPLÍCITO

1. **El barrido de pesos SOLO es válido sobre datos IN-SAMPLE.** Optimizar pesos sobre
   `data/raw` H4 y luego usar esos pesos en producción es **overfitting puro**: el sweep
   selecciona la combinación que mejor se ajusta al ruido histórico, no a la distribución
   futura.

2. **El sweep SOLO es válido TRAS walk-forward OOS (PurgedKFold).** Flujo correcto:
   - Dividir `data/raw` en ventanas temporales purgadas (evitar leakage de barras
     solapadas entre train/val).
   - El sweep de pesos se corre **dentro** de la ventana de entrenamiento de cada fold.
   - La selección de pesos se evalúa **solo** en la ventana OOS (out-of-sample) de ese fold.
   - Reportar PF/WR OOS promedio por combinación; fusionar SOLO si la combinación
     rulebook no empeora el OOS vs. baseline.

3. **No fusionar** ningún peso que mejore solo IN-SAMPLE. El usuario debe ejecutar el
   walk-forward OOS (no este subagente). Los YAML aquí son el *diseño* del experimento.

---

## 6. Rutas de archivos

| Archivo | Estado |
|---------|--------|
| `docs/proposals/item_C.md` | CREADO (este archivo) |
| `harness/scenarios/backtest_confluence_sweep.yaml` | CREADO |
| `harness/fixtures/backtest_confluence_sweep_fixture.yaml` | CREADO |
| `signals/pipeline.py` | NO MODIFICADO (solo diagnóstico, líneas 38-49, 205-216, 219, 241) |

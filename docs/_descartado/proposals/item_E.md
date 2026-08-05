# Ítem E — Invalidación / envejecimiento de detectores (P3)

> **BORRADOR DE CAMBIO MEDIBLE — NO APLICADO.**
> No se modifica código de producción (`signals/`, `backtest/`, `agents/`, `detectors/`, `adapters/`).
> Solo se crean archivos nuevos: este diagnóstico + `harness/scenarios/backtest_detector_invalidation.yaml`
> y su fixture. Cualquier cambio de invalidación/envejecimiento debe validarse con **walk-forward OOS**
> por el usuario antes de fusionar.

---

## 1. Diagnóstico: qué invalidación existe HOY

Los detectores son **detección pura en el bar del evento** (snapshot). Marcan el evento, pero
nunca gestionan su *vida útil*: no lo invalidan si el precio rompe el nivel en sentido contrario,
ni lo envejecen si pasan demasiadas barras. El pipeline luego consume esos flags como si siguieran
"vivos" para siempre.

### 1.1 BOS — `detectors/bos.py`

- **`bos.py:71-84`** — `bos_direction` y `bos_level` se calculan **solo en el bar del break**:
  `bullish_break = close > swing_high.shift(1)` / `bearish_break = close < swing_low.shift(1)`.
  Una vez `bos_direction != 0`, el flag queda "encendido" en ese bar, y el pipeline lo propaga
  con `rolling().max()` (ver abajo). **Nunca se chequea** si luego el precio rompió el nivel en
  sentido contrario (wicky break / no follow-through).
- **Falta:** estado `invalidated` (precio cruza `bos_level` opuesto) y estado `aged` (>N barras
  desde el evento sin confirmación). No existe campo `bos_age` ni `bos_status`.

### 1.2 CHOCH — `detectors/choch.py`

- **`choch.py:10-25`** — `choch_signal` se marca (`CHOCH_BULLISH`/`CHOCH_BEARISH`) en el bar del
  break de `last_swing_high/low`. **No se invalida**: si el precio vuelve dentro de la estructura
  en N barras (failed shift), el flag sigue vigente.
- **Consumo en pipeline:** `pipeline.py:154-155` solo hace `rolling(10).max()` para definir
  "recent" — eso extiende la memoria, no la invalida. Un CHOCH de hace 9 barras cuenta igual que
  uno del bar actual.
- **Falta:** `choch_status` (`active`/`invalidated`) y `choch_age`.

### 1.3 OB — `detectors/ob.py`

- **`ob.py:7-37`** — `ob_bullish`/`ob_bearish` se marcan por `body_ratio > 0.7 & followthrough`
  (`ob.py:18-24`). Solo se guardan `ob_top`/`ob_bottom` y `ob_distance` (`ob.py:26-36`).
  **No hay** seguimiento de si el precio rompió a través del OB (break-through invalidation) ni
  envejecimiento (>20 barras del rulebook, `STRATEGY_IMPROVEMENT_PLAN.md:51`).
- **Falta:** `ob_status` (`active`/`invalidated`/`aged`) y `ob_age`.

### 1.4 FVG — `detectors/fvg.py` (el ÚNICO modelo a seguir)

- **`fvg.py:37`** — `data["fvg_fill_status"] = _track_fvg_fill(data)`.
- **`fvg.py:41-81`** — `_track_fvg_fill` es un **loop estado a estado** que mantiene
  `bull_unfilled`/`bear_unfilled` y marca cada bar como `bullish_unfilled` / `bearish_unfilled` /
  `just_created` / `none`. Este es exactamente el patrón que BOS/CHOCH/OB necesitan.
- **El GAP (ya documentado en STRATEGY_IMPROVEMENT_PLAN.md:50):** el pipeline **NO consume**
  `fvg_fill_status`. En `pipeline.py:137-142` (anchors) y `pipeline.py:176` (`filter_ob_fvg`)
  solo usa `fvg_bullish`/`fvg_bearish` (booleanos de *creación*), no el fill status. O sea:
  FVG tiene el tracking, pero el `confluence_score` ignora si el gap ya fue llenado.

### 1.5 Resumen del GAP (tabla de P3)

| Concepto | Rulebook failure condition | Implementado | Evidencia |
|----------|---------------------------|--------------|-----------|
| BOS | Wicky break / no follow-through → failed | **NO** | `bos.py:71-84` |
| CHOCH | Precio vuelve a estructura en N bars → failed | **NO** | `choch.py:10-25` |
| OB | Rompe a través del OB / >20 bars | **NO** | `ob.py:7-37` |
| FVG | Gap llenado → filled | **PARCIAL** | tracking en `fvg.py:41-81`, no consumido en `pipeline.py:176` |

**Conclusión:** las señales hoy pueden dispararse sobre conceptos ya muertos (BOS de hace 100
barras, OB viejo, FVG ya llenado). El `confluence_score` los trata como vivos perpetuamente.

---

## 2. Propuesta de cambio (diff borrador — SOLO REFERENCIA, no aplicado)

### 2.1 — `detectors/bos.py`: añadir `bos_status` / `bos_age` (patrón `_track_fvg_fill`)

```diff
 def detect_bos(frame: pd.DataFrame, config: BosConfig | None = None) -> pd.DataFrame:
     if config is None:
         config = BosConfig()

     data = frame.copy()
     data["atr"] = _compute_atr(data, config.atr_period)
     data["swing_high"], data["swing_low"] = _swing_points(data, config.swing_lookback)
     data["swing_label"] = _label_swings(data["swing_high"], data["swing_low"])

     # ... (swing/sweep/bos_level sin cambios) ...

     data["bos_direction"] = np.select([bullish_break, bearish_break], [1, -1], default=0)
     data["bos_level"] = np.where(...)

+    # --- Ítem E: invalidación + envejecimiento (patrón _track_fvg_fill) ---
+    data["bos_status"], data["bos_age"] = _track_bos_validity(
+        data, max_age=config.followthrough_bars * 3   # ej. 24 barras; tunear en OOS
+    )
     return data


+def _track_bos_validity(data: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
+    n = len(data)
+    status = pd.Series(["none"] * n, index=data.index)
+    age = pd.Series([0] * n, index=data.index, dtype=int)
+    last_dir = 0
+    last_level = float("nan")
+    last_idx = -1
+    active = False
+    for i in range(1, n):
+        d = int(data["bos_direction"].iloc[i])
+        lvl = data["bos_level"].iloc[i]
+        if d != 0 and pd.notna(lvl):
+            last_dir, last_level, last_idx, active = d, float(lvl), i, True
+        if active:
+            age.iloc[i] = i - last_idx
+            crossed = (
+                (last_dir == 1 and data["low"].iloc[i] < last_level)   # BOS alcista roto por abajo
+                or (last_dir == -1 and data["high"].iloc[i] > last_level)  # BOS bajista roto por arriba
+            )
+            if crossed:
+                status.iloc[i], active = "invalidated", False
+            elif age.iloc[i] > max_age:
+                status.iloc[i], active = "aged", False
+            else:
+                status.iloc[i] = "active"
+    return status, age
```

> Nota: `BosConfig` (`bos.py:9-14`) debe ganar `max_age: int` (o reusar `followthrough_bars`).
> Aquí `max_age` de ejemplo = `followthrough_bars*3` (24 barras); el valor final se elige en OOS.

### 2.2 — `detectors/choch.py`: añadir `choch_status` / `choch_age`

```diff
 def detect_choch(frame: pd.DataFrame) -> pd.DataFrame:
     data = frame.copy().reset_index(drop=True)
     data["choch_signal"] = "NONE"
     # ... swing/context/break sin cambios (líneas 14-24) ...
     data.loc[bearish_context & bullish_break, "choch_signal"] = CHOCH_BULLISH
     data.loc[bullish_context & bearish_break, "choch_signal"] = CHOCH_BEARISH

+    # --- Ítem E: invalidación + envejecimiento ---
+    data["choch_status"], data["choch_age"] = _track_choch_validity(data, max_age=20)
     return data


+def _track_choch_validity(data: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
+    n = len(data)
+    status = pd.Series(["none"] * n, index=data.index)
+    age = pd.Series([0] * n, index=data.index, dtype=int)
+    last_dir = "NONE"
+    last_idx = -1
+    active = False
+    for i in range(1, n):
+        sig = data["choch_signal"].iloc[i]
+        if sig != "NONE":
+            last_dir, last_idx, active = sig, i, True
+        if active:
+            age.iloc[i] = i - last_idx
+            # failed shift: precio vuelve dentro de la estructura opuesta
+            failed = (
+                (last_dir == CHOCH_BULLISH and data["close"].iloc[i] < data["last_swing_low"].iloc[i])
+                or (last_dir == CHOCH_BEARISH and data["close"].iloc[i] > data["last_swing_high"].iloc[i])
+            )
+            if failed:
+                status.iloc[i], active = "invalidated", False
+            elif age.iloc[i] > max_age:
+                status.iloc[i], active = "aged", False
+            else:
+                status.iloc[i] = "active"
+    return status, age
```

### 2.3 — `detectors/ob.py`: añadir `ob_status` / `ob_age`

```diff
 def detect_order_blocks(frame: pd.DataFrame) -> pd.DataFrame:
     # ... cálculo ob_bullish/ob_bearish/ob_top/ob_bottom/ob_distance (líneas 7-36) sin cambios ...
+    data["ob_status"], data["ob_age"] = _track_ob_validity(data, max_age=20)
     return data


+def _track_ob_validity(data: pd.DataFrame, max_age: int) -> tuple[pd.Series, pd.Series]:
+    n = len(data)
+    status = pd.Series(["none"] * n, index=data.index)
+    age = pd.Series([0] * n, index=data.index, dtype=int)
+    last_dir = 0
+    last_top = float("nan")
+    last_bottom = float("nan")
+    last_idx = -1
+    active = False
+    for i in range(1, n):
+        bull = bool(data["ob_bullish"].iloc[i])
+        bear = bool(data["ob_bearish"].iloc[i])
+        if bull or bear:
+            last_dir = 1 if bull else -1
+            last_top = float(data["ob_top"].iloc[i])
+            last_bottom = float(data["ob_bottom"].iloc[i])
+            last_idx, active = i, True
+        if active:
+            age.iloc[i] = i - last_idx
+            # break-through: precio rompe el OB en sentido contrario
+            broke = (
+                (last_dir == 1 and data["close"].iloc[i] < last_bottom)   # OB alcista: cierra debajo
+                or (last_dir == -1 and data["close"].iloc[i] > last_top)  # OB bajista: cierra encima
+            )
+            if broke:
+                status.iloc[i], active = "invalidated", False
+            elif age.iloc[i] > max_age:
+                status.iloc[i], active = "aged", False
+            else:
+                status.iloc[i] = "active"
+    return status, age
```

### 2.4 — `signals/pipeline.py`: consumir estados en `confluence_score` y filtros

El punto clave: **un detector `invalidated` o `aged` NO debe aportar al score ni alimentar
anchors/filtros**. Hoy `filter_ob_fvg` (`pipeline.py:149-152`) y `filter_bos` (`pipeline.py:128-131`)
usan los flags booleanos crudos. Los degradeamos cuando el estado no sea `active`.

```diff
     # --- pipeline.py: ~128 (bos_filter) ---
-    bos_filter = (
-        ((data["macro_direction"] == "BULLISH") & bos_up)
-        | ((data["macro_direction"] == "BEARISH") & bos_down)
-    )
+    bos_alive = data.get("bos_status", pd.Series("active", index=data.index)).isin(["active", "none"])
+    bos_filter = (
+        ((data["macro_direction"] == "BULLISH") & bos_up & bos_alive)
+        | ((data["macro_direction"] == "BEARISH") & bos_down & bos_alive)
+    )

     # ... volume_filter sin cambios ...

     # --- pipeline.py: ~135 (anchors ob/fvg) ---
     bullish_anchor = _last_anchor(
         data["close"],
-        data["fvg_bullish"] | data["ob_bullish"],
+        (data["fvg_bullish"] | data["ob_bullish"])
+        & data.get("ob_status", pd.Series("active", index=data.index)).isin(["active", "none"]),
     )
     bearish_anchor = _last_anchor(
         data["close"],
-        data["fvg_bearish"] | data["ob_bearish"],
+        (data["fvg_bearish"] | data["ob_bearish"])
+        & data.get("ob_status", pd.Series("active", index=data.index)).isin(["active", "none"]),
     )
     # ...
     ob_fvg_filter = ( ... )  # sin cambios estructurales; el anchor ya filtra OBs muertos

     # --- pipeline.py: 154-159 (choch_filter) ---
     recent_bearish_choch = (data["choch_signal"] == CHOCH_BEARISH).rolling(10, min_periods=1).max().astype(bool)
     recent_bullish_choch = (data["choch_signal"] == CHOCH_BULLISH).rolling(10, min_periods=1).max().astype(bool)
+    choch_alive = data.get("choch_status", pd.Series("active", index=data.index)).isin(["active", "none"])
     choch_filter = (
-        ((data["macro_direction"] == "BULLISH") & (~recent_bearish_choch))
-        | ((data["macro_direction"] == "BEARISH") & (~recent_bullish_choch))
+        ((data["macro_direction"] == "BULLISH") & (~recent_bearish_choch) & choch_alive)
+        | ((data["macro_direction"] == "BEARISH") & (~recent_bullish_choch) & choch_alive)
     )

     # --- pipeline.py: 206-214 (confluence_score) ---
     # ADICIONAL: restar penalización por detectores muertos que estén "vivos" solo por el flag crudo.
     max_confluence = 6.0 if orchestrator is not None else 5.0
     confluence_score = (
         data["filter_trend"].astype(int)
         + data["filter_bos"].astype(int)
         + data["filter_ob_fvg"].astype(int)
         + data["filter_choch"].astype(int)
         + data["filter_swing"].astype(int)
         + (data["filter_agents"].astype(int) if orchestrator is not None else 0)
     )
+    # Ítem E: si el detector subyacente está invalidated/aged, el filtro que lo usó
+    # no cuenta. (fvg_fill_status ya existe; extender su consumo aquí)
+    dead = (
+        (~bos_alive if "bos_status" in data else False)
+        | (~choch_alive if "choch_status" in data else False)
+        | (~data.get("ob_status", pd.Series(True, index=data.index)).isin(["active", "none"])
+            if "ob_status" in data else False)
+        # FVG: consumir fvg_fill_status (hoy IGNORADO, ver STRATEGY_IMPROVEMENT_PLAN.md:50)
+        | (data.get("fvg_fill_status", pd.Series("none", index=data.index))
+            .isin(["bullish_unfilled", "bearish_unfilled"]).eq(False)
+            & (data["fvg_bullish"] | data["fvg_bearish"]))
+    )
+    confluence_score = confluence_score.where(~dead, confluence_score - 1).clip(lower=0)
     data["confluence_score"] = confluence_score
```

> **Por qué `data.get(..., default activo)`:** si el Ítem E no está aplicado, los campos
> `*_status` no existen y el comportamiento cae al de hoy (todo cuenta). Esto aisla el cambio y
> permite que el escenario harness compare ON/OFF sin tocar producción.

---

## 3. Escenario harness + fixture (Ítem E)

Archivos creados:

- `harness/scenarios/backtest_detector_invalidation.yaml`
- `harness/fixtures/backtest_detector_invalidation_fixture.yaml`

El fixture define `detector_invalidation` en **ON/OFF** sobre `data/raw` (H4, 8 símbolos, ~81k
barras, 2020→2026), sin MT5. El adapter `backtest` debe correr ambas variantes y reportar
PF/WR/trade-count por cada una (ejecutable SOLO tras aplicar el Ítem E; hoy el adapter ignora
`detector_invalidation`).

| Variante | `detector_invalidation` | Esperado |
|----------|------------------------|----------|
| off | false | Baseline actual (conceptos viven para siempre) |
| on  | true  | BOS/CHOCH/OB invalidados+envejecidos; FVG consome fill status |

**Métrica de éxito del plan:** reducir falsos positivos (trades sobre conceptos muertos) **sin
caer PF > 5%**, y manteniendo `total_trades >= 200` (el engine valida esto en
`backtest/engine.py:545`).

---

## 4. ⚠️ RIESGO: reducción de trade-count por debajo de 200

1. **Envejecer/invalidar BOS/OB/CHOCH mata señales.** Al degradar detectores muertos, el
   `confluence_score` baja y muchas barras dejan de pasar `min_confluence_score` (hoy `2`,
   `pipeline.py:46`). El recuento de trades puede colapsar por debajo del umbral de
   significancia **200** que el propio `backtest/engine.py:545` exige para aceptar la estrategia.
2. **El trade-count actual ya es bajo.** El baseline reportado es ~91 trades in-sample
   (`STRATEGY_IMPROVEMENT_PLAN.md:84`) repartidos en 4 símbolos (~23/símbolo). Añadir
   invalidación sobre H4 (menos barras que M15) puede dejar muestras demasiado pequeñas para
   concluir nada. Por eso el fixture usa **8 símbolos H4** (~81k barras) para maximizar el
   recuento antes de decidir umbrales de `max_age`.
3. **No bajar `min_confluence_score` para compensar** sin re-validar: eso reintroduciría ruido.

**Regla estricta:** cualquier umbral de `max_age` (BOS/CHOCH/OB) y el ON/OFF de invalidación
debe medirse en **walk-forward OOS (PurgedKFold, `ml/stats_validator.py`)** con ventanas
temporales purgadas. El YAML aquí es el *diseño* del experimento, no el cambio.

---

## 5. Rutas de archivos

| Archivo | Estado |
|---------|--------|
| `docs/proposals/item_E.md` | CREADO (este archivo) |
| `harness/scenarios/backtest_detector_invalidation.yaml` | CREADO |
| `harness/fixtures/backtest_detector_invalidation_fixture.yaml` | CREADO |
| `detectors/bos.py` | NO MODIFICADO (solo diagnóstico, líneas 9-14, 71-84) |
| `detectors/choch.py` | NO MODIFICADO (solo diagnóstico, líneas 10-25) |
| `detectors/ob.py` | NO MODIFICADO (solo diagnóstico, líneas 7-37) |
| `detectors/fvg.py` | NO MODIFICADO (referencia de patrón, líneas 37-81) |
| `signals/pipeline.py` | NO MODIFICADO (solo diagnóstico, líneas 128-159, 206-216) |

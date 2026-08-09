# Evidencia de código — Reconciliación Verdad / Autoridad (SDD-00)

**Rama:** `feature/backtest-ict` · **Fecha:** 2026-08-07 · **Método:** lectura estática, sin ejecución
**Criterio de juicio:** Ley arquitectónica de `AGENTS.md` — `engine/` es la única fuente de decisión;
`ict_backtest/` es consumidor puro y desechable; `engine/` nunca importa `ict_backtest/`.

**Estados de claim:** SUPPORTED / CONTRADICTED / STALE / UNVERIFIED / MISSING.

---

## Distinción de gates

### Respuesta corta

`require_pd` y `poi_present` son **DOS GATES DISTINTOS**. No tienen relación de implementación.
`require_pd` es premium/discount. `poi_present` es metadata narrativa que hoy **no veta nada**.
Poner `require_pd=True` **NO** activaría "POI anclado".

### 1. `require_pd` — qué controla exactamente

Firma: `engine/plan.py:371` → `require_pd: bool = True` (dentro de
`top_down_allows_trade`, declarada en `engine/plan.py:364`).

Cuerpo del gate: `engine/plan.py:424-431`.

```
424:    if require_pd:
425:        side = dealing.get("pd_side", "UNKNOWN")
426:        if side == "UNKNOWN":
427:            return False, "pd_unknown"
428:        if direction > 0 and side == "PREMIUM":
429:            return False, "long_in_premium"
430:        if direction < 0 and side == "DISCOUNT":
431:            return False, "short_in_discount"
```

Lee **exclusivamente** `stack["dealing"]["pd_side"]`, poblado en `engine/plan.py:346-355`
a partir de `dealing_range_pd(df, t)` sobre D1/H4 (H4 tiene prioridad, D1 es fallback).

**Veredicto:** `require_pd` gatea **premium/discount del dealing range**, y nada más.
No consulta POI, ni FVG, ni OB, ni BOS/CHOCH padre. **SUPPORTED**.

### 2. `require_pd`: default de firma vs. valor real en el call site

| Ubicación | Valor | Cita |
|---|---|---|
| Default de la firma | `True` | `engine/plan.py:371` |
| Call site real del motor | `False` (explícito) | `engine/sequence.py:479` |

```
476:        if est_htf_ctx_fn is not None and _ctx is not None:
477:            from engine.plan import top_down_allows_trade
478:            _ok, _reason = top_down_allows_trade(
479:                _ctx, target, counter_trend=cfg.counter_trend, require_pd=False,
480:            )
```

Es decir: **en el flujo de producción del motor el filtro premium/discount está APAGADO**.
Solo quedan activos D1 (`require_d1=True`), H4 (`require_h4=True`) y H1 (`require_h1=True`)
por default de firma (`engine/plan.py:368-370`). **SUPPORTED**.

### 3. Origen documentado de la confusión

El comentario que precede al call site **conflaciona los dos conceptos de forma explícita**:

```
engine/sequence.py:474-475
#            comportamiento histórico queda INTACTO. El POI anclado NO es veto
#            (require_pd=False): según auditoría destruye edge; se usa como
```

El comentario afirma que `require_pd=False` significa "el POI anclado no es veto". Eso es
**falso respecto del código**: `require_pd` no toca POI en ninguna línea. La auditoría que
conflacionó ambos gates muy probablemente leyó este comentario y no el cuerpo de
`top_down_allows_trade`. **CONTRADICTED** (el comentario contradice el código que documenta).

### 4. `poi_present` — traza extremo a extremo

| Etapa | Qué ocurre | Cita |
|---|---|---|
| Declaración del campo | `poi_present: Any = None  # ... (bonus, no gate)` | `engine/sequence.py:104` |
| Reset por secuencia | `self.poi_present = None` | `engine/sequence.py:123` |
| Cómputo | `state.poi_present = bool(htf_poi_fn(i, target))` (solo si `htf_poi_fn is not None`) | `engine/sequence.py:502-505` |
| Función que lo produce | `make_htf_poi_fn(...)` / `poi_present(...)` | `engine/poi_anchor.py:86`, `engine/poi_anchor.py:127` |
| Lectura al emitir | `_poi_present = getattr(state, "poi_present", None)` | `engine/sequence.py:611` |
| Emisión en la señal | `"poi_present": _poi_present` | `engine/sequence.py:628` |
| Copia al `ICTSignal` | `poi_present=s.get("poi_present")` | `ict_backtest/canonical.py:373` |
| Campo del dataclass | `poi_present: bool | None = None` | `ict_backtest/engine.py:49` |
| Passthrough semántico | mapeo por `sig_id` | `ict_backtest/semantic_adapter.py:71,122` |

**Búsqueda exhaustiva de ramas que rechacen por `poi_present`:** ninguna. El grep de
`poi_present` en `engine/`, `ict_backtest/`, `scripts/`, `tests/`, `app_observador/` no
devuelve ningún `if ... poi_present ...: continue` ni `return False`. Los únicos consumidores
son asignación, emisión, copia y asserts de test (`tests/test_r10c_adapter.py:245`).

**Veredicto:** `poi_present` es **metadata pura**. Ningún código lo usa para rechazar una señal.
**SUPPORTED**.

### 5. El gate "oculto" que sí existe: `poi_ok` (y por qué tampoco rechaza)

En la MISMA función hay una segunda invocación de `htf_poi_fn`, esta sí con efecto:

```
engine/sequence.py:508-520
508:            poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))
509:            if poi_ok:
510:                _fvg = _latest_fvg_zone(obj, target)
511:                _ob = _latest_ob_zone(obj, target)
...
514:                    state.zone_high, state.zone_low = _fvg
```

Si `poi_ok` es `False`, la zona LTF **no se memoriza**. Pero eso **no descarta la señal**:
al llegar a `BOS_DONE`, el motor sintetiza una zona de reemplazo:

```
engine/sequence.py:588-596
588:                if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
...
594:                    if np.isfinite(atr) and np.isfinite(state.bos_level):
595:                        state.zone_high = state.bos_level + 0.5 * atr
596:                        state.zone_low = state.bos_level - 0.5 * atr
```

**Consecuencia:** `poi_ok=False` degrada la calidad de la zona (pasa de FVG/OB real a
banda sintética alrededor del nivel del BOS) pero **no impide la emisión de la señal**.
No hay veto por POI en ningún punto del motor. **SUPPORTED**.

### 6. ¿Son el mismo gate? ¿`require_pd=True` activaría "POI anclado"?

| Pregunta | Respuesta |
|---|---|
| ¿`require_pd` y `poi_present` son el mismo gate? | **NO.** Son dos gates distintos, en dos módulos distintos, con dos entradas de datos distintas. |
| ¿`require_pd` consulta POI? | **NO.** Solo `stack["dealing"]["pd_side"]` (`engine/plan.py:424-425`). |
| ¿Cambiar `require_pd=False` → `True` impondría "POI anclado"? | **NO.** Impondría el filtro premium/discount de D1/H4. El POI seguiría sin vetar. |
| ¿Existe HOY algún parámetro para hacer de `poi_present` un veto? | **NO.** MISSING: no hay `require_poi`, `as_gate`, ni flag equivalente en `engine/sequence.py` ni en `engine/plan.py`. |

Nota adicional: el comentario de `ict_backtest/canonical.py:233` menciona `as_gate=False`
como si fuese un parámetro real. **No existe** en la firma de `make_htf_poi_fn`
(`engine/poi_anchor.py:86-91`). **STALE**.

### 7. Semántica real de `poi_present`: ¿"POI anclado" o solo "POI"?

Ninguna de las dos. Lo que realmente computa es: **"existe un evento BOS o CHOCH en algún TF
padre (D1/H4/H1), en la misma dirección del setup, con timestamp ya cerrado"**.

```
engine/poi_anchor.py:111-122
111:    def htf_poi_fn(i: int, target) -> bool:
112:        tnum = _direction_to_num(target)
113:        if tnum == 0:
114:            return False
115:        if not by_dir[tnum]:
116:            return True  # sin eventos padre -> no bloquea (comportamiento historico)
117:        if i < 0 or i >= len(ltf_times):
118:            return False
119:        ltf_t = ltf_times.iloc[i]
120:        prior = [e for e in by_dir[tnum] if e.time is not None and e.time <= ltf_t]
121:        prior = prior[-window_n:] if window_n else prior
122:        return bool(prior)
```

Hallazgos precisos:

- **No hay ningún POI en el cálculo.** No se detecta FVG ni OB. Solo `bos_dir` / `choch_dir`
  del TF padre (`engine/poi_anchor.py:71-80`).
- **Condición de anclaje:** existe al menos un evento de estructura padre con
  `direction == target` y `time <= time(vela LTF i)` (`engine/poi_anchor.py:120`).
- **Timeframes padre:** `_HTF_PARENTS = ("D1", "H4", "H1")` (`engine/poi_anchor.py:29`).
  Se tratan como un **conjunto plano**, sin jerarquía y sin exigir el padre inmediato.
- **BOS o CHOCH indistintamente:** ambos se insertan en la misma lista de eventos y se
  consultan sin distinguir `kind` (`engine/poi_anchor.py:75-80`; el campo `_ParentEvent.kind`
  se guarda pero nunca se filtra).
- **Ventana:** `window_n: int = 20` (`engine/poi_anchor.py:90`) recorta a los últimos 20
  eventos previos — es un límite de conteo, **no** de antigüedad temporal.
- **Fail-open:** si no hay eventos padre en esa dirección devuelve `True`
  (`engine/poi_anchor.py:116`). Es decir, ausencia de datos = anclado.
- **Invalidación posterior:** **MISSING.** No hay ningún código que verifique si el BOS/CHOCH
  padre fue invalidado después. El evento vive para siempre en la lista construida una sola
  vez por `build_htf_structure_index` (`engine/poi_anchor.py:49-83`), que se ejecuta al
  inicio y nunca se reevalúa.

**Veredicto sobre la semántica:** `poi_present == True` significa **"hubo estructura padre
en mi dirección"**, no "existe un POI" y mucho menos "existe un POI anclado".
El nombre del campo es engañoso. **CONTRADICTED** respecto de la lectura literal del nombre.

### 8. La otra bandera: `poi["anchored"]` en la narrativa HTF

`engine/htf_narrative.py:149-156` marca el POI real (OB o FVG derivado del último BOS):

```
149:        if poi is not None and htf_poi_fn is not None:
150:            tnum = 1 if direction == BULLISH else (-1 if direction == BEARISH else 0)
151:            try:
152:                poi["anchored"] = bool(htf_poi_fn(len(frame) - 1, tnum))
153:            except Exception:
154:                poi["anchored"] = False
155:        elif poi is not None:
156:            poi["anchored"] = False
```

Aquí **sí** hay un POI concreto (`order_block_for_bos` en `engine/htf_narrative.py:137`,
o `fvg_for_bos` en `:142`), pero el sello `anchored` se calcula con **exactamente la misma
función** `make_htf_poi_fn` — o sea, con el mismo criterio "hubo BOS/CHOCH padre en mi
dirección", evaluado en la **última vela** del frame (`len(frame) - 1`), no en la vela del POI.

Consecuencias:

- No se verifica que el POI provenga del BOS que lo originó. `order_block_for_bos` usa
  `_last_bos_event(frame)` (`engine/htf_narrative.py:124`), del **mismo frame**, no del padre.
- Si `htf_frames` es `None`, `anchored` queda `False` por construcción
  (`engine/htf_narrative.py:128-133, 155-156`) — no por evidencia de mercado.
- El único consumidor de `anchored` es cosmético: el string del resumen
  (`engine/htf_narrative.py:86`, `"anclado HTF" if poi.get("anchored") else "sin anclar"`).
  `narrative_ready_for_trade` (`engine/htf_narrative.py:172-183`) exige que exista `poi`
  pero **NO** exige `poi["anchored"]`. **SUPPORTED**.

### 9. Tercera instancia: `htf_anchored` en el `ICTSignal`

`ict_backtest/canonical.py:375` recalcula el mismo valor por tercera vez, con la función
wrapper del motor:

```
375:            htf_anchored=poi_present(ltf_df, htf_frames, int(s["entry_at"]), direction),
```

Esto reconstruye **todo el índice HTF por cada señal** (`engine/poi_anchor.py:140` llama a
`make_htf_poi_fn`, que llama a `build_htf_structure_index`). Es correcto en cuanto a la Ley
(el backtest consume el motor), pero es O(señales × velas HTF) y además **redundante** con
`s.get("poi_present")` de la línea 373. Tampoco veta nada. **SUPPORTED**.

---

## Contrato faltante de `poi_present`

Preguntas que el autor del spec **debe** responder para convertir `poi_present` en un veto real.
Cada una corresponde a algo que el código **hoy no define**.

### A. Alcance jerárquico

1. ¿El POI debe pertenecer al **TF padre inmediato** del TF de ejecución, o vale cualquier
   TF de `("D1", "H4", "H1")`? Hoy es un conjunto plano sin jerarquía
   (`engine/poi_anchor.py:29`, `:58`).
2. ¿Debe respetarse la **cadena completa** D1→H4→H1 (anclaje en cascada, cada nivel
   confirmando al siguiente) o basta con **un** nivel cualquiera? Hoy basta con uno.
3. Si el LTF de ejecución es M5 o M1, ¿M15 pasa a ser padre válido? Hoy M15 **no** está en
   `_HTF_PARENTS` y por tanto nunca puede anclar.

### B. Definición del ancla

4. ¿Anclaje a **BOS**, a **CHOCH**, o a ambos? Hoy ambos, sin distinción
   (`engine/poi_anchor.py:75-80`; `kind` se guarda pero jamás se lee).
5. ¿El POI debe estar anclado **al BOS específico que creó la zona**, o basta con que exista
   cualquier BOS previo en esa dirección? Hoy es lo segundo — no hay relación de causalidad
   entre el evento padre y la zona LTF.
6. ¿Qué es "POI" en el contrato? Hoy `poi_present` **no mira ningún POI**: solo estructura.
   `_htf_has_poi` (`engine/sequence.py:223-238`) sí mira FVG/OB del HTF, pero **está muerto**:
   no lo llama nadie. **MISSING**: definir si el contrato es estructura, zona, o ambos.

### C. Vigencia e invalidación

7. ¿Qué pasa cuando el BOS/CHOCH padre es **invalidado** posteriormente (el precio rompe el
   swing opuesto)? Hoy no hay reevaluación: el índice se construye una vez y es inmutable
   (`engine/poi_anchor.py:49-83`).
8. ¿Hay **caducidad temporal** del ancla? Hoy solo hay `window_n=20` eventos
   (`engine/poi_anchor.py:90,121`), que es un tope de cantidad, no de antigüedad. Un BOS de
   hace dos años ancla igual que uno de hace dos horas.
9. ¿El POI se consume al ser mitigado (uso único) o puede anclar múltiples entradas?
   No definido en ningún lado.

### D. Semántica de ausencia

10. Si **no hay** eventos padre en esa dirección, ¿el resultado debe ser *fail-open* (`True`,
    conducta actual en `engine/poi_anchor.py:116`) o *fail-closed* (`False`)? Con un veto real,
    el fail-open actual haría que "sin datos" equivalga a "permiso concedido".
11. Si el TF padre **no está cargado** en `htf_frames`, ¿es lo mismo que "sin eventos"?
    Hoy sí (`engine/poi_anchor.py:59-61`, `continue` silencioso).
12. ¿Una zona LTF válida **sin** POI padre debe rechazarse, degradarse a menor confianza, o
    ejecutarse con tamaño reducido? Hoy se degrada implícitamente a banda sintética
    (`engine/sequence.py:588-596`), lo cual nadie especificó.

### E. Multiplicidad y conflicto

13. Si hay **varios** POI padre candidatos (uno en D1 y otro contrario en H1), ¿cuál manda?
    Hoy la pregunta ni se plantea: se consulta solo si existe ≥1 en la dirección deseada.
14. ¿Puede un POI padre en dirección **opuesta** vetar? Hoy no: `by_dir` solo se consulta
    para `tnum` (`engine/poi_anchor.py:115,120`); la dirección contraria se ignora por completo.
15. ¿Cómo se ordena el conflicto entre `poi_present` (estructura) y `poi["anchored"]`
    (zona OB/FVG) y `htf_anchored` (recálculo en `canonical`)? Hoy son **tres cómputos
    del mismo valor** en tres lugares distintos, sin fuente única declarada.

### F. Observabilidad del veto

16. Cuando el veto rechace, ¿qué `reason` debe emitir y dónde se registra? El gate top-down
    ya tiene un vocabulario de razones (`"d1_ranging"`, `"long_in_premium"`, …,
    `engine/plan.py:390-438`); un veto de POI debería sumarse a ese vocabulario o justificar
    por qué no.
17. ¿El veto debe contarse en el embudo `phase_seen` (`engine/sequence.py:435`)? Hoy el embudo
    tiene 4 fases fijas (SWEEP/DISPLACE/BOS/ENTRY) y el contrato de monotonicidad está
    testeado (`tests/test_b2_funnel.py:99-107`); un veto nuevo sin fase propia sería invisible.

---

## Inventario de setups

### Tabla resumen

| Módulo | Decisión de trading | LOC | Equivalente en `engine/` | Tests | ¿Viola la Ley? |
|---|---|---:|---|---|---|
| `ict_backtest/setups/silver_bullet.py` | Valida que sweep y retorno caigan en la MISMA killzone SB (London Open / NY AM); NY PM rechazado | 177 | **AUSENTE** | `tests/test_c2_silver_bullet.py` (11) | **SÍ** — decisión en capa desechable |
| `ict_backtest/setups/turtle_soup.py` | Detecta barrido de PDH/PDL del día previo + reversión con displacement contrario | 207 | **AUSENTE** | `tests/test_c3_turtle_soup.py` (6) | **SÍ** |
| `ict_backtest/setups/ote.py` | Decide si el `entry_price` cae en la banda Fib 62–79 % de la pierna impulsiva | 142 | **PARCIAL** — `engine/dealing_range.py:68-71` computa la banda pero no la valida | `tests/test_d1_ote.py` (10), `tests/test_ote_integration.py` (10) | **SÍ** (duplica geometría del motor) |
| `ict_backtest/setups/breaker_block.py` | Detecta OB fallado que rota de rol tras CHOCH/MSS; invalida tras primera mitigación (MMXM) | 315 | **AUSENTE** (`engine/order_block.py` es OB simple, no breaker) | `tests/test_breaker_block.py` (14) | **SÍ** |
| `ict_backtest/setups/smt_divergence.py` | Detecta divergencia entre par base y correlato en swings (la "mentira" institucional) | 226 | **AUSENTE** | `tests/test_smt_divergence.py` (13) | **SÍ** |
| `ict_backtest/setups/smart_money.py` | Detecta EQH/EQL, sweeps de liquidez y displacement anclado a zona | 463 | **PARCIAL/DUPLICADO** — `engine/liquidity_levels.py` (BSL/SSL) y `engine/sequence.py::_has_sweep/_has_displacement` cubren parte | `tests/test_smart_money.py` (11) | **SÍ** (duplicación directa) |
| `ict_backtest/setups/rr_map.py` | Mapea setup → RR objetivo (SB 1:2, Turtle 1:1.5, OTE 1:3, default 1:3) | 96 | **AUSENTE** (`engine/execution.py:60` acepta `rr` pero no decide el valor) | `tests/test_rr_map.py` (6), `tests/test_rr_applied_to_tp.py` (4) | **SÍ** — política de riesgo por setup es decisión |
| `ict_backtest/setups/__init__.py` | Solo docstring de paquete | 6 | n/a | — | No |

**Conteo: 7 de 7 módulos funcionales violan la Ley.** Los ~1.626 LOC de decisión viven en la
capa desechable y desaparecerían si se borrara `ict_backtest/` según el punto 3 de `AGENTS.md`.

### Análisis de imports (criterio del juicio)

La Ley se aplica preguntando: *¿este módulo consume decisiones del motor, o las produce?*

| Módulo | Imports relevantes | Lectura |
|---|---|---|
| `silver_bullet.py` | `ict_backtest.engine.ICTSignal` (:30), `ict_backtest.rules.killzone_en` (:157) | **Cero imports de `engine/`.** Define su propia noción de killzone válida SB. Productor de decisión. |
| `turtle_soup.py` | solo `numpy`, `pandas` (:27-28) | **Cero imports.** Autocontenido: `_prev_day_ohlc`, `_sweep_broke`, `_has_reversal` son detectores propios. Productor. |
| `ote.py` | `ict_backtest.market_structure.detect_market_structure` (:23) | Usa el detector del **backtest**, no `engine.bos.detect_market_structure`. Duplica `engine/dealing_range.py:68-71`. Productor. |
| `breaker_block.py` | solo `numpy`, `pandas` (:22-23) | **Cero imports.** Detector completo de estructura (rotación de rol, mitigación). Productor. |
| `smt_divergence.py` | solo `numpy`, `pandas` (:24-25) | **Cero imports.** `_swing_highs` / `_swing_lows` propios, en vez de `engine.bias.narrative._swing_points`. Productor + duplicación. |
| `smart_money.py` | solo `numpy`, `pandas` (:79-80) | **Cero imports.** `_detect_sweeps`, `_detect_displacement`, `_find_equal_levels` propios. Duplica lógica de `engine/sequence.py` y `engine/liquidity_levels.py`. Productor. |
| `rr_map.py` | solo `typing` (:29) | **Cero imports.** Tabla de política de riesgo hardcodeada (`rr_map.py:36`). Productor de política. |

**Ningún módulo de `setups/` importa nada de `engine/`.** Ninguno es consumidor puro.
Todos deciden. **SUPPORTED**.

### Atenuante (relevante para el diseño de la migración)

Los siete módulos siguen el llamado "principio Brecha D": **anotan, no vetan**.
`ict_backtest/setups/__init__.py:1-6` lo declara y `ict_backtest/canonical.py:381-403` lo
implementa: los `flag_*` corren como paso POST sobre las señales ya emitidas, envueltos en
`try/except: pass` (`:400-403`).

Esto significa que **hoy no alteran el conteo ni el PnL** — la violación es estructural
(código de decisión en la capa equivocada), no funcional. El único que sí influye en el
resultado es `rr_map.rr_for`, importado directamente por el orquestador
(`ict_backtest/canonical.py:40`) y aplicado al TP vía `_rr_for_raw_signal`
(`ict_backtest/canonical.py:276,285,297`). **SUPPORTED**.

### Baseline de caracterización (qué fija cada suite de tests)

Estas son las decisiones observables que una migración a `engine/` debe preservar bit a bit.

**`tests/test_c2_silver_bullet.py` — 11 tests**

- `test_is_silver_bullet_london_open` (:115) / `test_is_silver_bullet_ny_am` (:124):
  sweep y retorno dentro de la misma killzone → `True`, y `meta` reporta `'L'` / `'NY_AM'`.
- `test_is_silver_bullet_return_outside_window` (:133): retorno fuera de la ventana → `False`.
- `test_is_silver_bullet_different_killzone` (:142): sweep en London y retorno en NY → `False`
  (fija que la killzone debe ser la **misma**, no solo "alguna válida").
- `test_is_silver_bullet_ny_pm_rejected` (:151): NY PM **no** es killzone SB. Regla dura.
- `test_is_silver_bullet_return_before_sweep_rejected` (:160): `return_ts < sweep_ts` → `False`
  (anti look-ahead a nivel de contrato).
- `test_flag_silver_bullet_annotates_confirmed` (:175) / `_rejected` (:187): la anotación
  escribe `sb_confirmed` y `sb_killzone` por `setattr`.
- `test_flag_silver_bullet_no_hard_filter` (:199): **la lista de señales no cambia de longitud**.
  Este es el test que congela "anota, no veta".
- `test_call_site_real_silver_bullet` (:213) / `_outside_window` (:236): verifican el cableado
  real a través de `evaluate_signals`.

**`tests/test_c3_turtle_soup.py` — 6 tests**

- `test_is_turtle_soup_long_detects_pdl_sweep_and_reversal` (:143): LONG requiere romper el
  **low del día previo** y luego displacement alcista.
- `..._short_detects_pdh_sweep_and_reversal` (:153): espejo con PDH.
- `test_is_turtle_soup_false_when_no_prev_day` (:181): sin día previo en los frames → `False`
  (no inventa).
- `test_is_turtle_soup_false_when_no_reversal` (:193): sweep sin reversión → `False`.
  Fija que el sweep **solo** no basta.
- `test_call_site_flags_turtle_soup_on_real_signals` (:209) / `_does_not_flag_non_turtle` (:231):
  cableado real y ausencia de falsos positivos.

**`tests/test_d1_ote.py` — 10 tests**

- `test_ote_zone_returns_fib_62_79_of_leg` (:119): la banda es exactamente 0.618–0.786 del rango.
- `test_is_ote_entry_long_inside_band` (:129) / `_outside_band` (:139) / `_short_mirror` (:147):
  simetría long/short y bordes de la banda.
- `test_is_ote_entry_rejects_nonpositive_leg` (:155): rango ≤ 0 → `False` sin excepción.
- `test_flag_ote_long_entry_in_ote_band` (:162) / `_short_` (:190) / `_outside_` (:213):
  anotación `ote_confirmed`.
- `test_flag_ote_no_swing_returns_false` (:235): sin swing detectable → `False`, no error.
- `test_flag_ote_empty_signals_returns_empty` (:257): lista vacía → lista vacía.

**`tests/test_ote_integration.py` — 10 tests.** Añade el contrato de no-invasión:
`test_orchestrator_ote_false_does_not_drop_signal` (:253) fija que un OTE negativo **no**
descarta la señal, y `test_rr_target_precedence_ote_sb_default` (:298) fija la precedencia
Silver Bullet > OTE > default en la resolución del RR.

**`tests/test_breaker_block.py` — 14 tests.** Lo más relevante para migrar:
`test_bullish_breaker_from_bearish_ob` (:127) y su espejo (:139) fijan la rotación de rol;
`test_breaker_disappears_after_mitigation` (:176) fija el MMXM de uso único;
`test_no_false_breaker_before_rotation` (:184) fija que el OB debe romperse **antes** de contar;
`test_no_breaker_when_close_inside_ob` (:165) fija el criterio de ruptura por cierre.

**`tests/test_smt_divergence.py` — 13 tests.** `test_divergence_short_base_rises_correlate_falls`
(:89) y su espejo (:106) fijan la dirección resultante; `test_flag_no_lookahead` (:206) fija que
solo se comparan barras cerradas; `test_strength_is_bounded` (:143) fija `strength ∈ [0,1]`.

**`tests/test_smart_money.py` — 11 tests.** `test_eqh_zones_detected` (:124) / `_eql_` (:136)
fijan la detección de niveles iguales por tolerancia relativa (sin ATR);
`test_sweep_down_then_bullish_rebound_detected` (:147) y espejo (:154) fijan el par
sweep+rebote; `test_no_zones_on_trending_data` (:116) fija ausencia de falsos positivos en
tendencia; `test_missing_columns_returns_error` (:101) fija degradación explícita.

**`tests/test_rr_map.py` — 6 tests.** `test_rr_for_known_setups` (:113) congela la tabla
SB 2.0 / Turtle 1.5 / OTE 3.0; `test_flag_rr_precedence_sb_over_ote` (:141) congela la
precedencia. **`tests/test_rr_applied_to_tp.py`** (4 tests, :46-61) es el único que prueba que
el RR **sí afecta el TP** — es decir, el único punto donde `setups/` cambia el resultado.

### `engine/sequence.py` y el parámetro `setup=`

**MISSING.** No existe. Las tres firmas públicas del motor de secuencia son:

- `_run_sequence_impl(...)` — `engine/sequence.py:390-394`
- `run_sequence(...)` — `engine/sequence.py:641-645`
- `run_sequence_traced(...)` — `engine/sequence.py:660-664`

Ninguna acepta `setup`. El grep de `setup` sobre `engine/*.py` devuelve **solo comentarios y
docstrings** (`engine/execution.py:16`, `engine/htf_narrative.py:148`, `engine/invalidation.py:17,43`,
`engine/poi_anchor.py:4`, `engine/sequence.py:9,158,171,174,206,224,242,483`). Cero
declaraciones de parámetro, cero ramas.

El motor **no tiene noción de "setup"**: solo conoce la secuencia canónica única
sweep → displace → BOS → retorno. La diferenciación por setup existe únicamente como
anotación posterior en `ict_backtest/canonical.py:381-403`.

El propio `docs/tesis/SDD_LTF_ENTRY_LAYER.md:106-107` propone añadir un modo
`style="silver_bullet"` — es decir, reconoce que **hoy no existe**. **MISSING**, confirmado.

### `tests/test_engine_no_backtest_import.py` — invariante exacta

Archivo de 38 líneas. Un único test: `test_engine_does_not_import_ict_backtest` (:29).

Mecanismo (`:15-26`): parsea con `ast.parse` **todos** los `engine/**/*.py` (`:31`) y recorre
el AST buscando nodos `ast.Import` y `ast.ImportFrom` cuyo módulo raíz (`split(".")[0]`) sea
`ict_backtest`. Falla si encuentra alguno.

Invariante enforced: **`engine/` no contiene ningún import real de `ict_backtest`.**

Alcance y límites, explícitos para el autor del spec:

- ✅ Detecta imports a nivel de módulo **y** dentro de funciones (usa `ast.walk`, no solo el
  cuerpo top-level).
- ✅ Ignora menciones en docstrings y strings (`:3-4`, decisión deliberada).
- ❌ **No** detecta imports dinámicos (`importlib.import_module("ict_backtest.x")`).
- ❌ **No** verifica la dirección inversa: `ict_backtest/` importando `engine/` está permitido
  y es lo correcto (`ict_backtest/canonical.py:42,46`).
- ❌ **No** verifica el punto 2 de la Ley (ausencia de lógica de decisión en `ict_backtest/`).
  Por eso los 7 módulos de `setups/` pasan este test sin problema: la Ley que violan
  **no tiene guardia automatizada**.

**SUPPORTED**, con la salvedad de que cubre solo una de las dos mitades de la Ley.

---

## Trade management

### 1. Dónde está implementado

**Ubicación única: `ict_backtest/trade_mgmt.py`** (204 líneas), capa desechable.

| Capacidad | Función | Cita |
|---|---|---|
| Break-even | `to_breakeven(entry, sl, direction, current_price, be_trigger_r=1.0)` | `ict_backtest/trade_mgmt.py:20-40` |
| Parcial | `partial_exit(entry, tp1, direction, current_price, pct=0.5)` | `ict_backtest/trade_mgmt.py:43-60` |
| Trailing | `trailing_stop(entry, sl, direction, current_price, step_r=1.0)` | `ict_backtest/trade_mgmt.py:63-89` |
| Orquestación + cierre | `apply_trade_management(entry, sl, tp, direction, df, ...)` | `ict_backtest/trade_mgmt.py:92-186` |

`apply_trade_management` aplica, en orden por vela (`:145-182`): (1) parcial + BE al tocar
`tp1` por `high`/`low` (`:151-160`), (2) trailing tras el parcial (`:163-168`),
(3) cierre por TP / SL / BE / trailing (`:171-182`), y devuelve
`{exit_reason, exit_price, pnl_r, partial_done, risk}` (`:198-204`).

Consumidor real: `ict_backtest/bar_by_bar_engine.py:15` (import) y `:295` (llamada).

### 2. ¿`engine/` tiene alguna capacidad de gestión post-entrada?

**NO.** **MISSING**, con cita:

- `engine/execution.py` tiene una sola función pública, `fine_execution`
  (`engine/execution.py:54-175`). Devuelve `{ok, exec_tf, entry, sl, tp, tp_ext, rng_exec, rr, reason}`
  (`:165-175`) — es un cálculo **de un solo disparo, en el momento de la entrada**.
- No existe `manage_trade`, ni `move_be`, ni `partial`, ni `trailing` en ningún archivo de
  `engine/` (grep de `trade_mgmt|apply_trade_management` sobre el repo: cero hits en `engine/`).
- El propio SDD lo reconoce: `docs/tesis/SDD_LTF_ENTRY_LAYER.md:29` marca el ítem 22
  (Trade Management BE/parciales) como **"NO EXISTE"**, y `:82-83` propone crear
  `engine/execution.py::manage_trade(position, ms, t, cfg)` como trabajo de Fase 2 pendiente.

**El motor no puede responder hoy "tengo una posición, ¿qué hago ahora?".**

### 3. ¿Es lógica de decisión (violación) o medición pura?

**Es lógica de decisión. VIOLACIÓN DE LA LEY. SUPPORTED.**

Justificación por evidencia, no por opinión:

- **Contiene umbrales de política, no de medición.** `be_trigger_r: float = 1.0` (`:25`),
  `pct: float = 0.5` (`:48`), `step_r: float = 1.0` (`:68`), `tp1_r: float = 1.0` (`:100`).
  "Mover el SL a BE a 1R" y "cerrar el 50 % en el primer objetivo" son **decisiones de
  trading del humano**, exactamente lo que la Ley reserva al motor.
- **Emite acciones, no métricas.** `to_breakeven` devuelve *el nuevo SL* o `None` = "no mover"
  (`:39-40`). Eso es una orden.
- **Prueba por contradicción:** si mañana se borra `ict_backtest/` (punto 3 de `AGENTS.md`),
  el motor **pierde** break-even, parciales y trailing. Un operador en vivo quedaría sin
  gestión. Por definición de la Ley, eso significa que la capacidad estaba en el lugar
  equivocado.
- **Confirmación documental independiente:** `docs/tesis/SDD_LTF_ENTRY_LAYER.md:82-88`
  planifica mover esta lógica a `engine/execution.py::manage_trade`, con el backtest
  consumiéndola vela a vela. El diseño previsto coincide con este diagnóstico.

Matiz honesto: `apply_trade_management` **es pura en el sentido funcional** (no muta `df`,
no toca estado global — `:121`). Pureza funcional ≠ ausencia de decisión. La Ley habla de
*dónde vive la decisión*, no de efectos secundarios.

### 4. Acoplamiento entre "¿entro?" y "tengo posición, ¿qué hago?"

**Ya están separados.** Es la mejor noticia de esta sección.

| Fase | Módulo | Entrada | Salida |
|---|---|---|---|
| ¿Entro? | `engine/sequence.py::_run_sequence_impl` (:390) | velas LTF + contexto HTF | lista de señales (`:618-634`) |
| ¿Dónde? | `engine/execution.py::fine_execution` (:54) | `ms`, `t`, `direction`, `sweep_ts` | `entry`/`sl`/`tp` (`:165-175`) |
| Tengo posición, ¿qué hago? | `ict_backtest/trade_mgmt.py::apply_trade_management` (:92) | `entry`, `sl`, `tp`, `direction`, `df` **post-entrada** | `exit_reason`, `pnl_r` (`:198-204`) |

Evidencia del desacoplamiento:

- `apply_trade_management` trabaja con **primitivos** (`entry`, `sl`, `tp`, `direction`), no con
  `ICTSignal`. Está documentado como decisión deliberada: *"aqui trabajamos con primitivos
  (entry/sl/tp/direction/current_price) para maxima pureza y testeo"*
  (`ict_backtest/trade_mgmt.py:6-7`).
- No importa `canonical`, ni `sequence`, ni `engine` (`:11-13`: solo `pandas`).
- El único punto de unión es `ict_backtest/bar_by_bar_engine.py:295`, un call site explícito
  posterior al fill.
- `tests/test_e1_trade_mgmt.py` (19 tests) y `tests/test_e1_applied_trade_mgmt.py` (3 tests)
  ejercen la gestión **sin generar ni una sola señal**.

**Implicación para el diseño:** la migración a `engine/` es un traslado casi mecánico. No hay
que desenredar nada; hay que mover el archivo, invertir el sentido del import y darle al motor
la firma de posición que hoy no tiene. Riesgo bajo. **SUPPORTED**.

Nota de deuda: existe `tests/_broken/test_fase1_2_trade_mgmt_wiring.py`, que espera
`apply_trade_management` importable desde `ict_backtest.engine` (`:18`) y un parámetro
`trade_mgmt=True/False` en `simulate_trade` (`:60,75`). Está en `_broken/`, lo que sugiere un
cableado abandonado. **STALE**.

---

## Mapa LTF

### 1. Contrato completo de `fine_execution`

`engine/execution.py:54-62`:

```
def fine_execution(
    ms: dict[str, pd.DataFrame],
    t: Any,
    direction: int,
    *,
    exec_tf: str = "M5",
    rr: float = 3.0,
    sweep_ts: Any | None = None,
) -> dict[str, Any]:
```

**Entradas**

| Parámetro | Significado | Cita |
|---|---|---|
| `ms` | frames por TF; debe incluir `exec_tf`, con fallback a `M15` | `:66`, `:79-81` |
| `t` | tiempo de la vela LTF ya cerrada (ancla anti look-ahead) | `:67`, `:85` |
| `direction` | `+1` long / `-1` short | `:68` |
| `exec_tf` | TF de ejecución fina; default `"M5"`, `"M1"` permitido | `:59`, `:69` |
| `rr` | ratio TP/SL; default `3.0` | `:60` |
| `sweep_ts` | tiempo del sweep en el LTF; si se da, ancla el SL a la mecha del sweep del exec TF | `:61`, `:70-73` |

**Salidas** (`:165-175` en éxito): `ok`, `exec_tf`, `entry`, `sl`, `tp`, `tp_ext`, `rng_exec`,
`rr`, `reason="fine_exec_structural"`. Precios redondeados a 5 decimales (`:168-171`).

**Qué decide**

1. **Entry** = último swing high (long, `:117`) o swing low (short, `:148`) del exec TF; si no
   hay swings, el `close` de la última vela cerrada (`:115`, `:146`).
2. **SL** = mecha del sweep del exec TF ± buffer (`:111`, `:144`), donde
   `buf = STRUCT_SL_BUFFER_RANGE * rng_exec` = `0.3 × rango medio` (`:32`, `:99`).
   Fallback estructural si el SL queda inválido: reanclar al último swing opuesto
   (`:121-125`, `:151-155`).
3. **TP** = `entry ± rr × risk` (`:133`, `:163`).
4. **`tp_ext`** = máximo `high` / mínimo `low` del exec TF cerrado — liquidez externa (`:134`, `:164`).
5. **`rng_exec`** = media de `high - low` de las últimas 50 velas del exec TF (`:95-96`).
   Matemática pura, sin ATR.

**Timeframes que asume**: cualquiera presente en `ms`; default `M5`, fallback `M15` (`:79-81`).
La ley se cumple: solo importa `engine.bias.narrative._swing_points` (`:27`).

**Lo que NO decide:** dirección, si entrar, killzone, tamaño de posición, gestión post-entrada.
Es una función de reanclaje geométrico.

### 2. Diagnóstico de la discrepancia `evaluate_signals` ≈ 10 vs. `run_backtest --exec-tf M5` = 0

Cadena real de llamadas:

```
CLI main()                       ict_backtest/run_backtest.py:440-511
  └─ run_sequence_backtest(...)  ict_backtest/run_backtest.py:193-206
       └─ generate_sequence_signals(...)  ict_backtest/run_backtest.py:102-142  (wrapper delgado)
            └─ evaluate_signals(...)      ict_backtest/canonical.py:143-407
                 ├─ run_sequence(...)     engine/sequence.py:641  (detección — devuelve raw_sigs)
                 └─ fine_execution(...)   engine/execution.py:54  (reanclaje — solo si use_exec)
```

**Inventario COMPLETO de puntos donde una señal puede caer** (en orden de ejecución):

| # | Punto de caída | Cita | ¿Depende de `exec_tf`? |
|---|---|---|---|
| D0a | Ventana BOS más corta reduce ENTRY en el motor | `engine/sequence.py:566`, `:601` vía `_effective_bos_gap` (`:376-387`) | No — depende de `bos_gap` |
| D0b | Gate top-down D1/H4/H1 veta la dirección | `engine/sequence.py:481-487` | No |
| D0c | Sesgo `RANGING` reinicia la secuencia | `engine/sequence.py:459-461` | No |
| D1 | `fill_entry_price` lanza `ValueError` (no hay barra siguiente para `next_open`) | `ict_backtest/canonical.py:257-259` | No |
| D2 | Rango medio del LTF no positivo | `ict_backtest/canonical.py:261-263` | No |
| D3 | **Killzone**: se descarta si no es London Open / NY AM / NY PM | `ict_backtest/canonical.py:264-266` | No — se evalúa sobre el LTF, **antes** del reanclaje |
| D4 | `calc_structural_sl` devuelve `None` | `ict_backtest/canonical.py:268-270` | No |
| D5 | `risk <= 0` o `risk > 6.0 × rng_LTF` (`STRUCT_SL_MAX_RANGE`, `ict_backtest/engine.py:361`) | `ict_backtest/canonical.py:271-273` | No |
| **D6** | **`fine_execution` devuelve `ok=False` → `continue`** | `ict_backtest/canonical.py:303-306` | **SÍ** |
| **D7** | **`risk > 6.0 × rng_exec` recalculado con el SL del exec TF → `continue`** | `ict_backtest/canonical.py:318-322` | **SÍ** |

Sub-razones de D6, todas dentro de `engine/execution.py`:

| `reason` | Condición | Cita |
|---|---|---|
| `no_exec_tf_data` | `ms[exec_tf]` ausente y sin fallback M15 | `:82-83` |
| `not_enough_bars` | menos de 5 velas cerradas ≤ `t` | `:86-87` |
| `zero_range` | rango medio del exec TF ≤ 0 | `:97-98` |
| `no_sweep_bar` | ninguna vela del exec TF cerrada ≤ `sweep_ts` | `:105-106`, `:138-139` |
| `sl_invalid_long` / `sl_invalid_short` | SL cruzado tras el fallback estructural | `:122-123`, `:131-132`, `:152-153`, `:161-162` |
| `no_swings` | sin swings en el exec TF (rama sin `sweep_ts`) | `:127-128`, `:157-158` |

**Punto de caída más probable (nº 1): D0a — divergencia de `bos_gap` entre entry points.**

```
ict_backtest/canonical.py:153     bos_gap: int | None = None      # evaluate_signals → DINÁMICO
ict_backtest/run_backtest.py:196  bos_gap: int | None = 10        # run_sequence_backtest → FIJO 10
ict_backtest/run_backtest.py:463  ap.add_argument("--bos-gap", type=int, default=10)
```

Con `bos_gap=None`, `_effective_bos_gap` (`engine/sequence.py:376-387`) llama a
`confirmation_window`, cuyo fallback determinista es **40** velas (`engine/sequence.py:354`,
`:361`, `:369`, `:373`). Con `bos_gap=10` la ventana es **fija 10**.

Esa ventana se aplica **dos veces** en el motor:
`DISPLACE → BOS` (`engine/sequence.py:566`) y `BOS → ENTRY` (`engine/sequence.py:601`).
En ambos casos, exceder la ventana ejecuta `state.reset(); continue`.

Reducir de 40 a 10 en dos etapas encadenadas colapsa el embudo de forma multiplicativa.
**Esta caída ocurre ANTES de que `exec_tf` se toque siquiera**, y explica que el backtest
CLI dé 0 mientras `evaluate_signals` (llamado con sus defaults) dé ~10.
La hipótesis del SDD (`docs/tesis/SDD_LTF_ENTRY_LAYER.md:63-65`) — *"`run_backtest` no pasa el
`sweep_ts`"* — es **CONTRADICTED**: `ict_backtest/canonical.py:298` sí lo pasa, y el flujo es
compartido por ambos entry points.

**Punto de caída nº 2: D7 — desajuste de escala en el filtro de riesgo.**

```
ict_backtest/canonical.py:318-322
318:            risk = abs(entry - sl)
319:            rng_exec = fine.get("rng_exec") or rng
320:            if rng_exec and risk > STRUCT_SL_MAX_RANGE * rng_exec:
321:                continue
```

`rng_exec` es el rango medio de **M5** (`engine/execution.py:95-96`), típicamente ~3× menor que
el de M15. Pero el `risk` se mide entre el `entry` (swing high de M5 **en el momento del toque**)
y el `sl` (mecha del sweep de M5 **en el momento del sweep**), instantes que pueden estar
separados por muchas velas. El numerador conserva escala de M15 mientras el denominador baja a
escala de M5: el cociente se infla ~3× contra un techo constante de 6.0
(`ict_backtest/engine.py:361`). Filtro estructuralmente más duro con `exec_tf=M5` que sin él.

Los tests sintéticos no lo detectan porque usan precio **plano** a propósito —
`tests/test_b2_exec_tf.py:46-50` documenta que si el precio derivara, *"el risk romperia el
filtro STRUCT_SL_MAX_RANGE"*. El artefacto que el test evita es exactamente el fallo en datos
reales. **SUPPORTED**.

**Punto de caída nº 3: D6/`no_sweep_bar` y `not_enough_bars` por recorte de ventana.**
Con `--window-months 1`, `load_frames` recorta **todos** los TF al mismo `start`
(`ict_backtest/run_backtest.py:244-246`). Si el `sweep_ts` de una señal cae cerca del borde
izquierdo, puede no haber 5 velas M5 cerradas previas (`engine/execution.py:86-87`) o ninguna
vela M5 ≤ `sweep_ts` (`:105-106`). Afecta al principio de la ventana. **UNVERIFIED** (no se
ejecutó nada).

**Hallazgo colateral: `enable_pd_index` es un parámetro muerto.**
Declarado en `ict_backtest/canonical.py:157` y documentado en `:166-169`, pero **nunca leído en
el cuerpo** de `evaluate_signals`. Los únicos hits del grep son la firma, el docstring y una
llamada externa (`:424`). El CLI lo pasa como `True` (`ict_backtest/run_backtest.py:505`)
creyendo activar la Fase C. No tiene efecto. **CONTRADICTED**.

**Descartado como causa:** la killzone (D3) se evalúa sobre la vela **LTF** en
`ict_backtest/canonical.py:264-266`, antes del bloque `use_exec`. El recálculo sobre el exec TF
(`:313-317`) solo reescribe la variable `kz` para metadata; no hay un segundo `continue`.
`exec_tf` **no** puede provocar caídas por killzone.

**Descartado como causa:** el cableado del parámetro. `tests/test_b2_exec_tf_wiring.py` (4 tests,
:48-73) prueba que `exec_tf` se propaga por `run()`, `generate_sequence_signals` y
`run_sequence_backtest`. La propagación funciona.

### 3. Qué especifica ya `docs/tesis/SDD_LTF_ENTRY_LAYER.md`

Documento de 159 líneas, fechado 2026-08-06, estado *"Fase 1 en ejecución; Fases 2-5 pendientes"*.

**Ya cubierto — no duplicar:**

| Tema | Contenido | Cita |
|---|---|---|
| Ley y alcance | HTF cerrado; este SDD cubre solo LTF; todo va al motor | `:7-16` |
| Tabla de gaps | Ítems 11/15/16/18/19/22/23/24 con estado y hueco | `:22-31` |
| Fase 1 — exec fino | Contrato de `fine_execution` ya escrito; `canonical` ya pasa `sweep_ts` (~l298) | `:45-59` |
| Diagnóstico pendiente | Reconoce explícitamente el 10 vs 0 y lo asigna a Fase 1 | `:56-59`, `:62-65` |
| Fase 2 — gestión | Diseño de `engine/execution.py::manage_trade`; BE al 50 % del recorrido; parcial 50 % en liquidez interna | `:76-94` |
| Fase 3 — SB/PO3 | Propone `style="silver_bullet"` en el motor y cablear `signals/po3.py` | `:96-117` |
| Fase 4 — OTE | Propone `_ote_zone(sweep, bos)` y `require_ote=True` en `fine_execution` | `:119-129` |
| Fase 5 — killzone | Centralizar `KILLZONES_UTC` en un módulo único | `:131-142` |
| Verificación | Tests nuevos, backtest 1 mes con runner_monitor, no romper 123 tests | `:144-150` |
| Riesgos | Divergencia `run_backtest` vs `evaluate_signals`; SB depende de calibrar displacement; RAM de M1/M5 | `:152-159` |

**Lo que el SDD deja SIN definir** (huecos legítimos para el spec nuevo):

1. **Autoridad de timeframe.** No dice qué TF **emite** el `Signal` final ni cómo se resuelve
   un conflicto M5 vs M1. Habla de "entrada fina" sin declarar propietario de la decisión.
2. **El rol de M1.** El título de la tesis sugiere M1 = confirmación, pero el SDD trata M5 y M1
   como intercambiables vía `exec_tf` (`:48`). No hay contrato de confirmación M1.
3. **Diagnóstico correcto del 10 vs 0.** La hipótesis de `:63-65` (`sweep_ts` no pasado) es
   incorrecta; la divergencia de `bos_gap` no se menciona.
4. **Contrato de `poi_present`.** Da el POI anclado por cerrado (`:9-11`) sin notar que hoy no
   veta y que su semántica no es la de un POI.
5. **Migración de `setups/`.** Los 7 módulos que ya existen en la capa desechable no aparecen;
   la Fase 3 habla de "crear" Silver Bullet cuando hay 177 líneas y 11 tests escritos.
6. **Trade management existente.** `:29` dice "NO EXISTE", pero
   `ict_backtest/trade_mgmt.py` tiene 204 líneas y 22 tests. La Fase 2 debería ser una
   **migración**, no una creación. **STALE**.
7. **Estado real de la killzone.** `:134` afirma que `detectors/killzones.py` usa horas
   locales. Es incorrecto (ver §5). **STALE**.

### 4. Soporte de OTE

**El cálculo existe en el motor. La validación NO. SUPPORTED / MISSING respectivamente.**

`engine/dealing_range.py:68-71` — verificado literalmente:

```
68:    data["ote_long_min"] = range_low + config.ote_min_retrace * span
69:    data["ote_long_max"] = range_low + config.ote_max_retrace * span
70:    data["ote_short_min"] = range_high - config.ote_max_retrace * span
71:    data["ote_short_max"] = range_high - config.ote_min_retrace * span
```

Constantes: `OTE_MIN_RETRACE = 0.62` (`:26`), `OTE_MAX_RETRACE = 0.79` (`:27`), configurables
vía dataclass (`:37-38`). Se clasifica la zona en `OTE_LONG` / `OTE_SHORT` / `DISCOUNT` /
`PREMIUM` / `OTE_NONE` (`:79-90`), y `is_favorable` acepta `OTE_LONG` en discount y `OTE_SHORT`
en premium (`:106-108`).

**¿`fine_execution` aplica OTE?** **NO.** El texto completo de `engine/execution.py` (175 líneas)
no contiene ninguna referencia a OTE, ni importa `engine.dealing_range`. El entry se decide por
breakout de swing (`:117`, `:148`), sin banda de retroceso.

**¿Existe `require_ote` en algún lugar?** **MISSING.** El grep de `require_ote` sobre
`engine/`, `ict_backtest/`, `scripts/`, `tests/` y `detectors/` devuelve **cero** resultados.
Solo aparece como propuesta futura en `docs/tesis/SDD_LTF_ENTRY_LAYER.md:127`.

**Estado real: hay TRES implementaciones desconectadas de OTE**, ninguna en el camino de decisión:

| Implementación | Rol actual | Cita |
|---|---|---|
| `engine/dealing_range.py:68-71` | columnas + clasificación de zona; nadie las lee para vetar | motor |
| `ict_backtest/setups/ote.py::is_ote_entry` (:44) | valida el precio en la banda; **solo anota** `ote_confirmed` | backtest |
| `ict_backtest/setups/rr_map.py:36` | usa `ote_confirmed` para elegir RR 3.0 | backtest |

### 5. Killzones — el claim reportado es incorrecto

**Claim:** *"`detectors/killzones.py` usa horas LOCALES en vez de UTC centralizado."*
**Estado: CONTRADICTED.**

`detectors/killzones.py:12-15` declara lo contrario, y el código lo cumple:

```
12: PRINCIPIO DE ZONA HORARIA (MDS_KILLZONES / DEC-009i, bug KZ-2): la hora la da el
13: SERVIDOR (broker MT5). Se CONVIERTE a UTC canonico via ZoneInfo (DST automatico)
14: y recien ahi se evaluan las bandas ICT. NUNCA offset fijo hardcodeado.
```

- Bandas declaradas en ET / Tokyo (`:30-35`), convertidas a UTC **por día** vía `ZoneInfo`
  (`:40-52`), con DST automático.
- `_session_window_utc` usa `_et_band_to_utc` para LDN/NY y `ZoneInfo("Asia/Tokyo")` para ASIA
  (`:37`, `:46-52`).
- `detect_killzones` acepta `broker_tz` y convierte servidor → UTC vía `server_to_utc`
  (`:55-69`); sin `broker_tz` asume que `time` ya viene en UTC (convención del proyecto, `:15`).

El claim proviene de `docs/tesis/SDD_LTF_ENTRY_LAYER.md:134`, que quedó **STALE** tras el fix KZ-2.

**El problema real es otro, y sí existe: fragmentación de la fuente.**

| Consumidor | Fuente de killzone | Bandas | Cita |
|---|---|---|---|
| `detectors/killzones.py` | `ict_backtest.rules.server_to_utc` / `_et_band_to_utc` | LDN_OPEN 02–05 ET, NY_AM 10–12 ET, NY_PM 14–17 ET, ASIA 10–14 Tokyo | `detectors/killzones.py:25,30-35` |
| `ict_backtest/canonical.py` | `ict_backtest.rules.killzone_en` | acepta `"London Open"`, `"New York AM"`, `"New York PM"` | `ict_backtest/canonical.py:38,264-266` |
| `ict_backtest/setups/silver_bullet.py` | `ict_backtest.rules.killzone_en` (import diferido) | solo London Open + NY AM; **NY PM rechazado** | `ict_backtest/setups/silver_bullet.py:157`; docstring `:5-11` |

**¿`engine/` tiene killzone propia? NO. MISSING.** El grep de `killzone` sobre `engine/**/*.py`
devuelve **cero** resultados. No existe `engine/killzones.py`.

Consecuencias para la Ley:

- El filtro de killzone es una **decisión de trading** ("no opero fuera de la killzone") que hoy
  vive íntegramente en `ict_backtest/canonical.py:264-266`. **VIOLACIÓN.**
- `detectors/killzones.py:25` importa de `ict_backtest.rules`. `detectors/` no es `engine/`, así
  que no rompe el test AST — pero acopla un detector compartido a la capa desechable.
- Si `ict_backtest/` se borrara, el motor **no sabría qué es una killzone**.
- Las dos definiciones divergen: NY PM es válida para el motor de secuencia y no para
  Silver Bullet. Ninguna está declarada como canónica.

### 6. Verificación puntual: `sweep_ts` sí se pasa

`ict_backtest/canonical.py:295-302`:

```
295:        if use_exec:
296:            entry_ts = ltf_df.iloc[entry_at]["time"]
297:            _rr_exec = _rr_for_raw_signal(s, ltf_df, direction, ltf)
298:            sweep_ts = ltf_df.iloc[s["sweep_at"]]["time"]
299:            fine = fine_execution(
300:                ms, entry_ts, direction,
301:                exec_tf=exec_tf, rr=_rr_exec, sweep_ts=sweep_ts,
302:            )
```

**SUPPORTED.** Como `run_backtest` delega en `evaluate_signals`, esta línea es común a ambos
entry points. La hipótesis del SDD queda descartada.

### 7. Qué afirman hoy `test_b2_exec_tf.py` y `test_b2_funnel.py`

**`tests/test_b2_exec_tf.py` — 4 tests. Contrato declarado en `:13-18`.**

| Test | Afirmación | Cita |
|---|---|---|
| `test_exec_tf_kwarg_anchors_sl_to_exec_tf` | con `exec_tf="M5"` el SL cae en `(1.0975, 1.0990)` → viene de la mecha M5 (1.0980), no de la M15 (1.0990) ni de la M1 (1.0975) | `:137-155` |
| `test_exec_tf_none_is_identical_to_ltf` | `exec_tf=None` produce **exactamente** el mismo `stop_loss` que `exec_tf="M15"` (regresión cero) | `:158-178` |
| `test_exec_tf_m1_uses_m1_sweep` | con `exec_tf="M1"` el SL cae en `(1.0970, 1.0975)` → mecha M1 | `:181-195` |
| `test_call_site_uses_exec_tf_for_po3_config` | `Po3MotorConfig` recibe `exec_tf="M5"` (cableado) | `:198-223` |

**Limitación crítica del baseline:** los tres primeros **evitan la detección por completo**.
`_inject_signal` (`:106-133`) monkeypatchea `run_sequence` en `ict_backtest.sequence` **y** en
`ict_backtest.canonical` para devolver una señal cruda fabricada (`:116-127`). Es decir:
**estos tests nunca ejercen el motor de secuencia**. Solo prueban el reanclaje de
`ict_backtest/canonical.py:295-322`.

Además, los datos son **precio plano** por diseño explícito (`:46-50`), justamente para que
el `risk` no dispare el filtro `STRUCT_SL_MAX_RANGE`. **Ninguno de estos tests puede detectar
el modo de falla D7**, que es la caída candidata nº 2. **SUPPORTED** (que pasan) pero
**UNVERIFIED** como cobertura del bug real.

**`tests/test_b2_funnel.py` — 6 tests. Contrato declarado en `:10-12`.**

| Test | Afirmación | Cita |
|---|---|---|
| `test_run_sequence_returns_2tuple_with_funnel` | `run_sequence` devuelve `(signals, phase_seen)` | `:78-87` |
| `test_funnel_has_four_keys_and_is_monotonic` | claves exactas `{SWEEP, DISPLACE, BOS, ENTRY}` y `SWEEP >= DISPLACE >= BOS >= ENTRY` (Ley 11) | `:89-107` |
| `test_evaluate_signals_default_returns_list` | sin `return_phase_seen` devuelve **lista** (regresión cero) | `:111-121` |
| `test_evaluate_signals_return_phase_seen_includes_funnel` | con el flag devuelve `(signals, funnel)` monotónico | `:124-135` |
| `test_generate_sequence_signals_default_returns_list` | mismo contrato en el wrapper | `:138-147` |
| `test_generate_sequence_signals_return_phase_seen_includes_funnel` | mismo contrato con flag | `:150-162` |

**No dicen nada sobre `exec_tf`.** El embudo pasa por
`run_sequence` → `evaluate_signals` → `generate_sequence_signals`, pero nunca se ejercita
`run_sequence_backtest` con `exec_tf`. Además usan precio plano (`:32-53`), así que el embudo
observado es trivialmente `{0,0,0,0}` o casi. El invariante de monotonicidad se cumple de forma
vacua. **La discrepancia 10 vs 0 no está cubierta por ningún test. MISSING.**

---

## Autoridad de timeframe

### ¿Quién emite hoy el `Signal` final?

**Dos autoridades encadenadas, sin propietario declarado.**

**Autoridad 1 — QUÉ y CUÁNDO: el LTF (M15 por defecto).**

`engine/sequence.py:618-634` es el único lugar del motor donde nace una señal:

```
618:                signals.append({
619:                    "time": str(obj.meta.get("time")),
620:                    "direction": target,
621:                    "entry": float(obj.meta.get("close")),
...
626:                    "entry_at": i,
```

Se dispara en `engine/sequence.py:607` (`_touches_zone`), sobre la vela `obj = objs[i]` del
**LTF**, construida por `_candle_objects(ltf_df, ltf_tf)` (`:133-150`, invocado en `:428`).
`ltf_tf` default `"M15"` (`:392`, `:642`). El `entry` inicial es el `close` del LTF.

**Autoridad 2 — DÓNDE: el exec TF (M5/M1), condicional.**

`ict_backtest/canonical.py:307-309` sobrescribe `entry`, `sl` y `tp` con la salida de
`fine_execution`, pero **solo si `use_exec`** (`:249`), y `fine_execution` puede rechazar
(`:303-306`). El objeto `ICTSignal` definitivo se construye en `ict_backtest/canonical.py:360-379`
— es decir, **en la capa desechable**.

### Observación de arquitectura para el autor del spec

**El motor NUNCA emite un objeto `Signal`.** `run_sequence` devuelve `list[dict]`
(`engine/sequence.py:395`, `:433`). El tipo `ICTSignal` está definido en `ict_backtest/engine.py`
(campos en `:43`, `:49`) y se instancia en `ict_backtest/canonical.py:361`.

Consecuencia directa sobre la Ley: **la construcción del objeto de decisión final vive en la
capa que debe poder borrarse.** Si `ict_backtest/` desapareciera, el motor devolvería
diccionarios sin contrato de tipo, sin `symbol`, sin `stop_loss`, sin `take_profit` y sin
killzone aplicada. `ict_backtest/canonical.py:143-407` **no es un consumidor puro**: es el
ensamblador de la señal.

### Ambigüedades sobre la cadena D1/H4/H1 → M15 → M5 → M1

| # | Ambigüedad | Evidencia |
|---|---|---|
| 1 | **M15 tiene doble rol** (contexto y ejecución) sin distinción formal. Está en `build_context_stack` (`engine/plan.py:317`), es el LTF de detección (`engine/sequence.py:642`) y es el fallback de ejecución (`engine/execution.py:80-81`). |
| 2 | **M5 y M1 son intercambiables.** `exec_tf` acepta cualquiera de los dos (`engine/execution.py:59`; CLI `choices=[None,"M5","M1"]`, `ict_backtest/run_backtest.py:473`). No hay contrato que diga "M5 decide el setup, M1 confirma". |
| 3 | **No existe capa de confirmación M1.** `fine_execution` con `exec_tf="M1"` **reemplaza** a M5, no lo confirma. Ningún código encadena M5 → M1. **MISSING**. |
| 4 | **`require_ltf` está apagado.** `engine/plan.py:373` lo define con default `False`, y el call site del motor (`engine/sequence.py:478-480`) no lo pasa. Por tanto `ltf_confirms` (`engine/plan.py:433-438`) **nunca corre en producción**. La confirmación M5/M1 existe y está desactivada. |
| 5 | **M5/M1 no pueden vetar, por diseño declarado.** `engine/plan.py:377-381`: *"M5/M1 NO redefinen el sesgo mayor: por eso solo pueden pedir confirmacion a favor y NUNCA vetan"*. Coherente con la tesis, pero implica que la "autoridad" de M1 es nula. |
| 6 | **El POI no está atado a M15.** `_HTF_PARENTS = ("D1","H4","H1")` (`engine/poi_anchor.py:29`) excluye M15, así que la capa de contexto/POI que el título de la cadena atribuye a M15 no existe como tal. |
| 7 | **El sesgo se lee de UN solo TF.** `extract_htf_layer(_ctx, htf)` (`engine/sequence.py:453`) reduce el `MultiTFContext` de 6 TF a **una** capa. El propio docstring lo admite: *"Los otros 5 TF viajan disponibles en el contexto pero aún no influyen en la lógica"* (`:410-412`). |

**Respuesta directa a la pregunta de autoridad:** hoy **M15 decide** (emite la señal en
`engine/sequence.py:618`) y **M5/M1 solo reanclan precios** cuando se los pide explícitamente
(`ict_backtest/canonical.py:295-322`). La cadena D1/H4/H1 actúa como **filtro de dirección**
(`engine/sequence.py:476-487`), no como emisor. M1 no tiene rol de confirmación alguno.

---

## Tabla de claims

| # | Claim | Origen | Evidencia (`file:line`) | Estado |
|---|---|---|---|---|
| 1 | `require_pd` gatea premium/discount | Tarea D | `engine/plan.py:371,424-431` | SUPPORTED |
| 2 | El call site pasa `require_pd=False` (contradice el default `True`) | Tarea D | `engine/plan.py:371` vs `engine/sequence.py:479` | SUPPORTED |
| 3 | El comentario de `sequence.py` conflaciona `require_pd` con "POI anclado" | Tarea D | `engine/sequence.py:474-475` vs `engine/plan.py:424-431` | CONTRADICTED |
| 4 | `poi_present` es campo de estado marcado "bonus, no gate" | Tarea D | `engine/sequence.py:104` | SUPPORTED |
| 5 | Ningún código rechaza una señal por `poi_present` | Tarea D | grep completo; consumidores en `engine/sequence.py:611,628`, `ict_backtest/canonical.py:373`, `ict_backtest/semantic_adapter.py:122` | SUPPORTED |
| 6 | `poi_ok` sí condiciona el trazado de la zona | Tarea D | `engine/sequence.py:508-520` | SUPPORTED |
| 7 | …pero no descarta la señal: hay zona sintética de fallback | Tarea D | `engine/sequence.py:588-596` | SUPPORTED |
| 8 | `require_pd` y `poi_present` son gates DIFERENTES | Tarea D | `engine/plan.py:424-431` vs `engine/poi_anchor.py:111-122` | SUPPORTED |
| 9 | `require_pd=True` NO impondría "POI anclado" | Tarea D | `engine/plan.py:424-431` (solo lee `dealing.pd_side`) | SUPPORTED |
| 10 | `poi_present==True` significa "existe BOS/CHOCH padre en mi dirección", no "existe POI" | Tarea D | `engine/poi_anchor.py:71-80,111-122` | CONTRADICTED (vs. el nombre) |
| 11 | El anclaje usa D1/H4/H1 como conjunto plano, sin padre inmediato | Tarea D | `engine/poi_anchor.py:29,58` | SUPPORTED |
| 12 | BOS y CHOCH se tratan igual (`kind` nunca se filtra) | Tarea D | `engine/poi_anchor.py:75-80` | SUPPORTED |
| 13 | Fail-open: sin eventos padre devuelve `True` | Tarea D | `engine/poi_anchor.py:115-116` | SUPPORTED |
| 14 | No hay reevaluación si el BOS padre se invalida | Tarea D | `engine/poi_anchor.py:49-83` (índice inmutable) | MISSING |
| 15 | `poi["anchored"]` se evalúa en la última vela, no en la del POI | Tarea D | `engine/htf_narrative.py:152` (`len(frame)-1`) | SUPPORTED |
| 16 | `narrative_ready_for_trade` no exige `anchored` | Tarea D | `engine/htf_narrative.py:172-183` | SUPPORTED |
| 17 | `as_gate=False` mencionado en `canonical` no existe en la firma | Tarea D | `ict_backtest/canonical.py:233` vs `engine/poi_anchor.py:86-91` | STALE |
| 18 | `htf_anchored` recalcula el mismo valor por señal | Tarea D | `ict_backtest/canonical.py:373` y `:375` | SUPPORTED |
| 19 | Los 7 setups funcionales viven en la capa desechable | Tarea E | `ict_backtest/setups/*.py` | SUPPORTED |
| 20 | Ningún setup importa de `engine/` | Tarea E | imports en `:22-30` de cada módulo | SUPPORTED |
| 21 | Los setups anotan y no vetan (violación estructural, no funcional) | Tarea E | `ict_backtest/setups/__init__.py:1-6`; `ict_backtest/canonical.py:381-403` | SUPPORTED |
| 22 | Excepción: `rr_map` sí afecta el TP | Tarea E | `ict_backtest/canonical.py:40,276,285,297`; `tests/test_rr_applied_to_tp.py:46-61` | SUPPORTED |
| 23 | Silver Bullet / Turtle Soup / Breaker / SMT no tienen equivalente en `engine/` | Tarea E | `engine/` (16 archivos) — sin módulos correspondientes | MISSING |
| 24 | OTE está duplicado: motor calcula, backtest valida | Tarea E/G | `engine/dealing_range.py:68-71` vs `ict_backtest/setups/ote.py:44` | SUPPORTED |
| 25 | `engine/sequence.py` NO tiene parámetro `setup=` | Tarea E | `engine/sequence.py:390-394,641-645,660-664` | MISSING |
| 26 | `test_engine_no_backtest_import` hace AST-scan e ignora docstrings | Tarea E | `tests/test_engine_no_backtest_import.py:15-26,29-38` | SUPPORTED |
| 27 | Ese test no cubre la segunda mitad de la Ley (lógica en el backtest) | Tarea E | mismo archivo, alcance | SUPPORTED |
| 28 | Trade management vive solo en `ict_backtest/trade_mgmt.py` | Tarea F | `ict_backtest/trade_mgmt.py:20,43,63,92` | SUPPORTED |
| 29 | `engine/` no tiene gestión post-entrada | Tarea F | `engine/execution.py` (única función `fine_execution`, `:54`) | MISSING |
| 30 | Es decisión (umbrales de política), no medición | Tarea F | `ict_backtest/trade_mgmt.py:25,48,68,100` | SUPPORTED |
| 31 | Entrada y gestión ya están desacopladas | Tarea F | `ict_backtest/trade_mgmt.py:6-7,11-13`; único call site `ict_backtest/bar_by_bar_engine.py:295` | SUPPORTED |
| 32 | El SDD dice "Trade Management NO EXISTE" | Tarea F | `docs/tesis/SDD_LTF_ENTRY_LAYER.md:29` vs `ict_backtest/trade_mgmt.py` | STALE |
| 33 | `fine_execution`: entry por breakout de swing, SL en mecha de sweep, TP por RR | Tarea G | `engine/execution.py:111,117,133,144,148,163` | SUPPORTED |
| 34 | Causa nº 1 del 10 vs 0: `bos_gap` 10 (fijo) vs `None` (dinámico → 40) | Tarea G | `ict_backtest/run_backtest.py:196,463` vs `ict_backtest/canonical.py:153`; `engine/sequence.py:354,373,566,601` | SUPPORTED |
| 35 | Causa nº 2: filtro de riesgo con `rng_exec` de M5 y `risk` de escala M15 | Tarea G | `ict_backtest/canonical.py:318-322`; `engine/execution.py:95-96`; `ict_backtest/engine.py:361` | SUPPORTED |
| 36 | Causa nº 3: `no_sweep_bar` / `not_enough_bars` en el borde de la ventana | Tarea G | `engine/execution.py:86-87,105-106`; `ict_backtest/run_backtest.py:244-246` | UNVERIFIED |
| 37 | La hipótesis del SDD (`sweep_ts` no pasado) es falsa | Tarea G | `ict_backtest/canonical.py:298` vs `docs/tesis/SDD_LTF_ENTRY_LAYER.md:63-65` | CONTRADICTED |
| 38 | `enable_pd_index` es parámetro muerto en `evaluate_signals` | Tarea G | `ict_backtest/canonical.py:157,166-169` (nunca leído); CLI lo pasa `True` en `ict_backtest/run_backtest.py:505` | CONTRADICTED |
| 39 | La killzone no puede causar caídas por `exec_tf` | Tarea G | `ict_backtest/canonical.py:264-266` (antes de `use_exec`) vs `:313-317` (solo metadata) | SUPPORTED |
| 40 | El cableado de `exec_tf` funciona | Tarea G | `tests/test_b2_exec_tf_wiring.py:48-73` | SUPPORTED |
| 41 | `engine/dealing_range.py` computa las bandas OTE 0.62–0.79 | Tarea G | `engine/dealing_range.py:26-27,68-71` | SUPPORTED |
| 42 | `fine_execution` NO aplica OTE | Tarea G | `engine/execution.py` completo — sin referencia ni import | SUPPORTED |
| 43 | `require_ote` no existe en ninguna parte | Tarea G | grep global: 0 hits; solo propuesto en `docs/tesis/SDD_LTF_ENTRY_LAYER.md:127` | MISSING |
| 44 | `detectors/killzones.py` usa horas LOCALES | Tarea G (claim reportado) | `detectors/killzones.py:12-15,30-35,40-52` — usa ZoneInfo ET/Tokyo → UTC con DST | CONTRADICTED |
| 45 | El problema real de killzone es la fragmentación de la fuente | Tarea G | `detectors/killzones.py:25`; `ict_backtest/canonical.py:38,264-266`; `ict_backtest/setups/silver_bullet.py:157` | SUPPORTED |
| 46 | `engine/` no tiene lógica de killzone propia | Tarea G | grep `killzone` en `engine/**/*.py`: 0 hits | MISSING |
| 47 | La señal final la emite el LTF (M15) en el motor | Tarea G | `engine/sequence.py:607,618-634` | SUPPORTED |
| 48 | El objeto `ICTSignal` se ensambla en la capa desechable | Tarea G | `ict_backtest/canonical.py:360-379`; tipo en `ict_backtest/engine.py:43,49` | SUPPORTED |
| 49 | `require_ltf` existe pero nunca se activa en producción | Tarea G | `engine/plan.py:373,433-438` vs `engine/sequence.py:478-480` | SUPPORTED |
| 50 | No hay capa de confirmación M1 encadenada a M5 | Tarea G | `engine/execution.py:59,79-81` (M5 y M1 mutuamente excluyentes) | MISSING |
| 51 | El `MultiTFContext` carga 6 TF pero solo 1 influye | Tarea G | `engine/sequence.py:410-412,453` | SUPPORTED |
| 52 | `ict_backtest/sequence.py` es un shim sin lógica (cumple la Ley) | Tarea E | `ict_backtest/sequence.py:1-28` | SUPPORTED |
| 53 | `_htf_has_poi` está definido pero muerto | Tarea D | `engine/sequence.py:223-238` — sin call sites | SUPPORTED |
| 54 | Los tests B2 evitan la detección (monkeypatch de `run_sequence`) | Tarea G | `tests/test_b2_exec_tf.py:106-133` | SUPPORTED |
| 55 | Los tests B2 usan precio plano para eludir `STRUCT_SL_MAX_RANGE` | Tarea G | `tests/test_b2_exec_tf.py:46-50` | SUPPORTED |
| 56 | Ningún test cubre la discrepancia 10 vs 0 | Tarea G | `tests/test_b2_funnel.py` (no ejercita `run_sequence_backtest` con `exec_tf`) | MISSING |

---

## Preguntas abiertas para el autor del spec

### Bloque 1 — Autoridad y contrato de la señal (el más urgente)

1. **¿Quién es dueño del objeto `Signal`?** Hoy el motor devuelve `list[dict]`
   (`engine/sequence.py:395`) y el backtest construye `ICTSignal`
   (`ict_backtest/canonical.py:361`). ¿El spec exige que `engine/` emita un tipo propio?
   Sin eso, borrar `ict_backtest/` deja al motor sin contrato de salida.
2. **¿Qué timeframe tiene la autoridad final?** Declarar explícitamente el rol de cada nivel:
   D1/H4/H1 = dirección, M15 = ¿contexto o ejecución?, M5 = ¿setup?, M1 = ¿confirmación?
   El código actual no lo distingue (ver §Autoridad, ambigüedades 1-3).
3. **¿M1 confirma o reemplaza a M5?** Hoy son excluyentes (`engine/execution.py:59`).
   Si la tesis pide encadenamiento, hay que diseñarlo desde cero.
4. **¿Se reactiva `require_ltf`?** Existe e implementa confirmación M5/M1
   (`engine/plan.py:373,433-438`) pero nunca se pasa. ¿Es deuda o decisión?

### Bloque 2 — `poi_present` como veto real

5. Las 17 preguntas de la sección **Contrato faltante de `poi_present`** (alcance jerárquico,
   definición del ancla, vigencia, semántica de ausencia, multiplicidad, observabilidad).
6. **¿Se unifican los tres cómputos?** `poi_present` (estado), `poi["anchored"]` (narrativa) y
   `htf_anchored` (`ICTSignal`) calculan lo mismo en tres lugares. ¿Cuál es la fuente única?
7. **¿Se corrige el nombre?** El campo no mide un POI. Renombrarlo a algo como
   `htf_structure_aligned` evitaría que la próxima auditoría repita la confusión.
8. **¿Qué pasa con `_htf_has_poi`?** (`engine/sequence.py:223-238`) sí mira FVG/OB del HTF y
   está muerto. ¿Es la base del contrato real o se elimina?

### Bloque 3 — Migración de `setups/` al motor

9. **¿Migración total o selectiva?** Son 7 módulos, ~1.626 LOC y ~69 tests. ¿Todos, o solo los
   que la tesis exige (Silver Bullet, Turtle Soup, OTE)?
10. **¿Cómo los invoca el motor?** No hay parámetro `setup=` (`engine/sequence.py:390-394`).
    ¿Se añade un `style=`/`setup=` como propone `SDD_LTF_ENTRY_LAYER.md:106`, o se resuelve con
    composición de estrategias?
11. **¿Se mantiene "anota, no veta"?** `tests/test_c2_silver_bullet.py:199` congela ese contrato.
    Si en el motor pasan a vetar, ese test debe reescribirse **deliberadamente**.
12. **¿Qué pasa con `rr_map`?** Es el único que ya afecta el resultado
    (`ict_backtest/canonical.py:276`). Migrarlo cambia el PnL. ¿Se acepta esa ruptura?
13. **¿Se deduplica OTE?** Hay tres implementaciones (motor, setup, rr_map). ¿La banda del motor
    (`engine/dealing_range.py:68-71`) es la canónica?
14. **¿Se añade una guardia automática para la segunda mitad de la Ley?**
    `test_engine_no_backtest_import.py` cubre la dirección de imports pero no detecta lógica de
    decisión en `ict_backtest/`. Sin guardia, la violación se repetirá.

### Bloque 4 — Trade management

15. **¿Migración o reescritura?** `ict_backtest/trade_mgmt.py` funciona y tiene 22 tests.
    `SDD_LTF_ENTRY_LAYER.md:82-83` propone una API distinta
    (`manage_trade(position, ms, t, cfg)` → `{"move_be", "partial"}`). ¿Se conserva el
    comportamiento existente o se rediseña?
16. **¿Cuál es el tipo `position`?** No existe en el repo. Hay que definirlo antes de escribir
    `manage_trade`.
17. **¿Los umbrales de política son configurables o son doctrina?**
    BE a 1R (`:25`) vs. "50 % del recorrido entry→TP" (`SDD:84-85`) son reglas distintas.
    ¿Cuál manda?
18. **¿La gestión decide vela a vela o por evento?** El backtest itera por vela
    (`ict_backtest/trade_mgmt.py:145`). En vivo el motor recibe ticks. ¿Mismo contrato?

### Bloque 5 — Capa LTF y el bug `exec_tf`

19. **¿Se unifican `run_sequence_backtest` y `evaluate_signals` en un solo defaults set?**
    La divergencia de `bos_gap` (10 vs `None`) es la causa nº 1 candidata. Cualquier
    parámetro con dos defaults distintos volverá a producir este tipo de discrepancia.
20. **¿Cuál es el default canónico de `bos_gap`?** ¿Fijo 10, dinámico por tabla empírica, o
    dinámico con otro fallback? Hoy el fallback duro es 40 (`engine/sequence.py:354`).
21. **¿El filtro `STRUCT_SL_MAX_RANGE` debe escalar con el exec TF?** Aplicar el mismo múltiplo
    6.0 sobre el rango M5 cuando el `risk` conserva escala M15 es incoherente
    (`ict_backtest/canonical.py:318-322`).
22. **¿`enable_pd_index` se elimina o se implementa?** Hoy es parámetro muerto que el CLI pasa
    como `True` creyendo activar algo (`ict_backtest/run_backtest.py:505`).
23. **¿Dónde viven las killzones?** No existen en `engine/`. ¿Se crea `engine/killzones.py` como
    propone `SDD:138`, y qué se hace con la divergencia NY PM (válida para el motor de
    secuencia, inválida para Silver Bullet)?
24. **¿Se añade un test de integración que ejercite `run_sequence_backtest` con `exec_tf` sobre
    datos con movimiento real?** Los tests B2 actuales no pueden detectar el fallo
    (`tests/test_b2_exec_tf.py:46-50,106-133`).

### Bloque 6 — Alcance y secuencia

25. **¿Qué se cierra primero?** El diagnóstico sugiere este orden por dependencia:
    (a) unificar defaults de entry points → recupera señales;
    (b) migrar trade management → bajo riesgo, alto valor, ya desacoplado;
    (c) definir el contrato de `poi_present` → habilita el veto;
    (d) migrar `setups/` → el más grande, y el que rompe PnL vía `rr_map`.
26. **¿Se acepta romper la "regresión cero"?** Varias correcciones (activar `require_pd`,
    convertir `poi_present` en veto, migrar `rr_map`) cambiarán los números de
    `docs/METRICS_CANON.md`. ¿Hay presupuesto para re-medir?

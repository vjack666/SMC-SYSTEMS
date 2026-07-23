# SDD — Cierre del Setup Operacional (Dashboard SMC-SYSTEMS)

> **Propósito:** terminar la herramienta EN PRODUCCIÓN (app_observador / loop de
> análisis 24/7) para que arme un setup ICT **como un humano**, cerrando 4 huecos
> de profundidad. NO es un rewrite: la arquitectura de 3 capas (HTF→ITF→exec TF) ya
> existe y es correcta. Se mete PROFUNDIDAD en Stage 4/5 y se afianza el ciclo vivo.
>
> **Fecha:** 2026-07-23 · **Autor:** agente (diseño) + sub-agentes (secciones 5A/5B/5C)
> **Fuente de verdad:** `docs/ict/20_TESIS_ICT.md`, `app_observador/core/pipeline.py`,
> `app_observador/core/engine.py`, `docs/plan/DASHBOARD_OPERACIONAL_PLAN.md`
> **Gobernanza (Ruben):** diseño + estructuras + tests sintéticos ANTES de implementar
> y antes de tocar datos reales. Demo sin contexts reales primero.

---

## 0. Alcance

Herramienta en producción hoy: el **Dashboard Operacional** (observador FundedNext,
modo SIN BOT). El backtest queda FUERA de alcance (laboratorio).

Lo que ya está BIEN (no tocar): `run_pipeline` ya refleja las 3 capas del humano —
BiasEngine(D1) → ContextEngine(H4) → IntradayEngine(H1) → POIEngine(M15) →
TriggerEngine(M5) → RiskEngine → ExecutionPlan. El veredicto ya es jerárquico
(`context_alignment`), no votación.

Lo que FALTA TERMINAR (4 huecos, detallados en §2 y diseñados en §5):

| # | Hueco | Por qué el humano lo hace y el dashboard NO | Sección |
|---|--------|----------------------------------------------|---------|
| 1 | Trigger de ENTRADA real | Humano espera el **retroceso a la zona POI + reacción** (libro 15 §6, paso 5). Dashboard solo confirma geometría (sweep+bos+fvg). | 5A |
| 2 | POI anclado y rankeado | Humano exige POI = PD Array en discount/premium + sesgo HTF + desplazamiento + tier + stacking (libro 21). Dashboard cuenta cualquier FVG/OB suelto. | 5B |
| 3 | Plan concreto vivo (entry/SL/TP) | Stage 7 (canonical R7) se **cuelga** en `run_cycle` → el operador nunca ve entry/SL/TP. | 5C |
| 4 | Gate de sesión en el trigger | Humano solo dispara en London/NY. El trigger no filtra por killzone. | 5A |

---

## 1. Estado actual (resumen verificado)

- `pipeline.run_pipeline(d1,h4,h1,m15, m5=None, smt_a=None, smt_b=None)` → `dict`
  con `bias`, `context_alignment`, `votes` (LEGADO), `reasons`, `poi`, `trigger`, `smt`.
- `trigger_engine(m5)` hoy: `valid = sweep and bos and fvg` (geometría plana). No sabe
  si el precio está EN la zona ni si reaccionó. No recibe zona POI ni sesión.
- `poi_engine(m15, d1)` hoy: `valid = (ob or fvg) and ote`; bonus si cae en discount.
  No chequea desplazamiento, no rankea tier, no hace stacking, no ancla a narrativa HTF.
- `engine.run_cycle` escribe `last_cycle.json` ANTES del paso 6, pero el paso 6
  (`_canonical_plan`) se cuelga en este entorno → proceso muerto → cache viejo.

---

## 2. Los 4 huecos (cómo los cierra cada sección)

1. **Trigger real (5A):** máquina de estados
   `STRUCTURE_READY → WAITING_PULLBACK → TRIGGER_READY`, donde el salto
   WAITING→READY exige "precio dentro de la zona POI + rechazo" y dentro de killzone.
2. **POI libro 21 (5B):** `tier` (T1 BPR / T2 OB·FVG / T3 rejection / SKIP),
   `anchored` (ancla a BOS/CHOCH HTF), `stacked` (multi-TF), `quality_bonus`
   sumado a `confidence` como BONUS (NUNCA filtro duro — tesis probó PF 0.900 duro).
3. **Resiliencia run_cycle (5C):** el cache se escribe SIEMPRE; el paso 6 aislado en
   tiempo (timeout-bound) para que nunca bloquee el ciclo ni deje el dashboard mudo.
4. **Gate de sesión (5A):** reutilizar la killzone existente; el trigger solo marca
   READY dentro de London/NY (y NY PM si se cablea).

---

## 3. Principios de diseño (OBLIGATORIOS)

- **Funciones puras:** `stage(tf_data) -> dict`. Sin estado global.
- **Reutilizar, no duplicar:** `analyze_timeframe` ya devuelve
  `sweep_up/down, bos_dir, bos_status, fvg_state, ob_dir, ote_long/short,
  zone_low/zone_high`. Los detectores viven en `detectors/` y `liquidity_context`.
- **No inventar datos:** campo ausente → `"EN CONSTRUCCIÓN"` / `"PENDING"` honesto.
- **Separación backtest≠dashboard:** `run_cycle` puede importar `ict_backtest` para el
  canonical, pero el pipeline de decisión NO depende del motor de backtest.
- **Sin dependencia MT5 en el pipeline:** lee parquet vía `rutina_eurusd._load`.
- **No romper la UI:** `context_alignment` y `votes` siguen siendo leídos. Se AÑADEN
  campos, no se borran.
- **POI = bonus de calidad, NUNCA filtro duro** (tesis: duro = PF 0.900).
- **TDD / harness-first:** tests sintéticos GREEN antes de datos reales.

---

## 4. Contrato de integración en `run_pipeline`

Firma propuesta (compatible con la UI actual):

```python
def run_pipeline(d1, h4, h1, m15,
                 m5=None, smt_a=None, smt_b=None,
                 session=None) -> dict:
    ...
```

Cambios mínimos (detallados en §5):
- `poi = poi_engine(m15, d1, h1=h1, h4=h4)` → añade `tier, anchored, stacked,
  quality_bonus` a `poi` y a `context_alignment["poi"]`.
- `trig = trigger_engine(m5, poi_zone=..., session=session)` → añade máquina de
  estados y `in_zone / reaction` a `trigger` y a `context_alignment["trigger"]`.
- `confidence` suma `poi["quality_bonus"]` (cap 20) y descuenta si trigger fuera de
  killzone.
- `engine.run_cycle` aísla el paso 6 (ver 5C) → `result["canonical"]` siempre poblado
  o `"EN CONSTRUCCIÓN"`.

Nuevos campos en `context_alignment` (el string legado `trigger`/`poi` se conserva
intacto; el detalle fino va en claves hermanas para no romper la UI):
- `poi`: además del string `VALID/INVALID` → `poi_tier` (T1/T2/T3/SKIP/PENDING),
  `poi_anchored` (bool), `poi_stacked` (bool), `poi_quality_bonus` (int 0–20).
- `trigger`: además del string `PENDING/VALID` → `trigger_machine` con
  `STRUCTURE_READY` / `WAITING_PULLBACK` / `TRIGGER_READY` / `TRIGGER_READY_OFF_SESSION`
  / `PENDING`, y `in_zone` (bool), `reaction` (bool), `in_killzone` (bool).
- `canonical` (en `result`, no en context_alignment): 3 estados — `"EN CONSTRUCCIÓN"`
  (str) / `None` (corrió, sin plan vigente) / `dict` poblado (Entry/SL/TP vivos).

---

## 5. SECCIONES POR COMPONENTE

> Las subsecciones 5A, 5B y 5C se completan con el diseño de los sub-agentes
> (ver historial de la sesión). Cada una entrega: objetivo, responsabilidad, contrato
> de función, estructuras de datos, reutilización, lógica (pseudocódigo), casos,
> regla EN CONSTRUCCIÓN, tests sintéticos, riesgos y asunciones.

### 5A Stage 5 — Trigger de entrada real + Gate de sesión

> Diseñado por sub-agente (leaf). Hallazgo clave: `core/timezone.py` YA tiene
> `KILLZONES_UTC` (London 07–10, NY AM 12:30–15, NY PM 17–20 UTC) y
> resuelve el ⚠TZ de la tesis §11; solo falta enchufar `killzone_en(dt)` al
> pipeline y actualizar el mapa §11 (London + NY PM YA cableados, no "no cableados").

**Objetivo**
Que `M5_TRIGGER` deje de validarse en el close de la vela del BOS (paso 3 tesis §6)
y solo pase a `TRIGGER_READY` cuando el precio **retrocedió a la zona POI** (FVG/OB
que dejó el displacement) **y reaccionó** (paso 5), y que ese disparo **solo cuente
dentro de una killzone** (London / NY AM / NY PM, §9).

**Responsabilidad única**
El trigger sigue siendo un **reportero de ambos lados**: para LONG y SHORT informa
checks (`sweep/bos/fvg/pullback/reaction/session`) y un estado de máquina. NO elige
lado, NO calcula confianza, NO opera contra el macro (eso sigue en el VerdictBuilder).

**Contrato de función (firma EXACTA)**
```python
def trigger_engine(
    m5: dict | None = None,          # salida de analyze_timeframe(df_m5, "M5") — sin cambio
    poi: dict | None = None,         # salida de poi_engine (zone M15: invalidation/target, has_fvg/ob)
    now_utc: datetime | None = None, # instante de evaluación; run_pipeline lo inyecta (utc_now() o time de la vela)
) -> dict:
```
- `m5`: igual que hoy. Se usan además `close`, `atr`, `ob_top/ob_bottom`, `fvg_state`,
  `ote_long/ote_short`, `time` — todos YA en `analyze_timeframe`, cero detectores nuevos.
- `poi`: la zona M15 del libro 15. Si `poi=None` o `valid=False` → el pullback usa la
  zona LTF propia de M5 (FVG/OB de la ruptura); si tampoco hay → `PENDING`.
- `now_utc`: hace el gate de sesión **puro y testeable**. Nunca `datetime.now()` dentro
  del stage; `run_pipeline` inyecta `utc_now()` (live) o el `time` de la última vela.
  `None` → `session="UNKNOWN"` (regla EN CONSTRUCCIÓN).

**Salida** (aditiva, no rompe):
```python
{
  "side": None, "valid": False, "state": "PENDING",   # legado, intacto
  "checks": {"sweep","bos","fvg","pullback","reaction","session"},  # 3 claves NUEVAS
  "session": {"in_killzone": bool|None, "name": str, "state": "OPEN|CLOSED|UNKNOWN"},
  "long":  {... ampliado con "machine_state", "entry_zone": (lo,hi)},
  "short": {...},
}
```
Y `context_alignment['trigger']` pasa de `VALID|PENDING` a uno de:
`"STRUCTURE_READY" | "WAITING_PULLBACK" | "TRIGGER_READY" | "TRIGGER_READY_OFF_SESSION" | "PENDING"`.
Para no romper lecturas existentes, el string clásico `trigger` conserva `"VALID"/"PENDING"`
y el detalle fino va en `context_alignment['trigger_machine']`.

**Máquina de estados**
```
PENDING ──(sweep+bos+fvg del lado)──▶ STRUCTURE_READY
STRUCTURE_READY ──(close entra en entry_zone)──▶ WAITING_PULLBACK
WAITING_PULLBACK ──(precio tocó zona + reacción a favor)──▶ TRIGGER_READY        (si in_killzone)
                                                            └─▶ TRIGGER_READY_OFF_SESSION (si fuera de killzone)
cualquier estado ──(falta dato: sin M5 / sin zona / sin reloj)──▶ PENDING
```
`valid=True` **solo** en `TRIGGER_READY`. Consumo en VerdictBuilder: sigue eligiendo
`trig[derived_bias.lower()]` y `trigger_valid = cand["valid"]` (separación intacta).
`TRIGGER_READY_OFF_SESSION` NO es válido pero se muestra como "⏳ setup listo, fuera de killzone".

**Reutilización**
- **Killzone**: `core/timezone.py` ya tiene `KILLZONES_UTC` y `killzone_activa_ahora()`.
  Solo añadir `killzone_en(dt_utc) -> str` (misma tabla, recibe datetime) y que
  `killzone_activa_ahora()` = `killzone_en(utc_now())`. Cero duplicación.
- **Zona POI**: `poi_engine` ya devuelve `invalidation/target`; `analyze_timeframe` M5 ya da
  `ob_top/ob_bottom` y `ote_long/ote_short`. La `entry_zone` se arma con esos campos.
- **Reacción**: se infiere de `close` vs zona + `atr` como buffer, sin nuevo cálculo.

**Lógica propuesta (pseudocódigo)**
```python
def _entry_zone(m5, poi, side):
    if side=="LONG" and m5.ob_dir=="bullish": return (m5.ob_bottom, m5.ob_top)
    if side=="SHORT" and m5.ob_dir=="bearish": return (m5.ob_bottom, m5.ob_top)
    if poi and poi["valid"]: return orden(poi["invalidation"], poi["target"])  # zona M15
    return None                                            # -> PENDING pullback

def _eval_side(m5, side, poi, session):
    sweep, bos, fvg = (como hoy)
    structure = sweep and bos and fvg
    if not structure: return PENDING
    zone = _entry_zone(m5, poi, side)
    if zone is None: return machine_state="STRUCTURE_READY", pullback=None (EN CONSTRUCCIÓN)
    lo, hi = zone; px = m5["close"]; buf = 0.10 * m5["atr"]
    pullback = (lo - buf) <= px <= (hi + buf)
    reaction = pullback and (px >= lo if side=="LONG" else px <= hi) \
               and (m5["bos_status"]=="active")
    if not pullback: return "WAITING_PULLBACK"
    if not reaction:  return "WAITING_PULLBACK" (nota: "en zona, sin reacción")
    if session["state"]=="UNKNOWN": return "WAITING_PULLBACK" + checks.session=None
    return "TRIGGER_READY" if session["in_killzone"] else "TRIGGER_READY_OFF_SESSION"
```
Gate de sesión: `name = killzone_en(now_utc)`; `in_killzone = bool(name)`;
`state = "OPEN" if name else "CLOSED"`; `now_utc=None → "UNKNOWN"`.
**Dependencia de datos**: el último precio M5 ya viene en `m5["close"]` (parquet vía
`rutina_eurusd._load`, sin MT5). El reloj se inyecta desde `run_pipeline` → stage puro.

*Limitación honesta (declarada)*: con snapshot de 1 vela, "reacción" es heurística
(precio en zona + estructura activa + close del lado correcto). Detectar mecha de rechazo
multi-vela requiere serie → fase futura Stage 5b. No se finge.

**Casos**
| Caso | Resultado |
|---|---|
| Feliz: sweep+bos+fvg LONG, close en zona, bos_status active, 13:00 UTC (NY AM) | `long TRIGGER_READY`, valid=True |
| Sweep falla | PENDING, `checks.sweep=False`, "Esperando sweep" |
| Sin M5 | PENDING honesto ambos lados; `session` se reporta igual |
| Sesgo opuesto: short READY pero bias LONG | trigger lo reporta; VerdictBuilder NO lo elige → `trigger_valid=False` |
| Fuera de killzone (05:00 UTC) | `TRIGGER_READY_OFF_SESSION`, valid=False, sin los 10 pts |
| Estructura lista, precio lejos | `WAITING_PULLBACK` (estado que hoy contaba mal como VALID) |

**Regla 'EN CONSTRUCCIÓN'**
- Sin M5 → PENDING.
- Estructura OK pero sin zona calculable → `STRUCTURE_READY`, `pullback=None`, nota honesta.
- `now_utc=None` → `session.state="UNKNOWN"`, nunca asume killzone abierta.
- `atr` NaN → buffer=0, no se aborta.

**Tests sintéticos (GREEN esperados)**
1. `test_trigger_ready_long`: m5 LONG completo, close en zona, now=13:00 UTC → READY.
2. `test_waiting_pullback`: close fuera de zona → WAITING_PULLBACK, valid=False.
3. `test_off_session`: now=05:00 UTC → TRIGGER_READY_OFF_SESSION.
4. `test_session_boundaries`: 06:59→CLOSED, 07:00→London, 12:30→NY AM, 15:00→CLOSED, 17:00→NY PM, 20:00→CLOSED.
5. `test_no_m5_pending`: m5=None → PENDING, checks nuevos presentes.
6. `test_no_zone_en_construccion`: estructura OK, ob_dir='-', poi inválido → STRUCTURE_READY.
7. `test_no_clock_unknown`: now_utc=None → nunca TRIGGER_READY.
8. `test_verdictbuilder_ignores_opposite`: short READY + bias LONG → trigger_valid=False.
9. `test_ui_contract`: `context_alignment` conserva `trigger`/`votes`/`stages`.
10. `test_purity`: 2 llamadas mismos args → dicts idénticos (sin estado global).

**Riesgos y mitigaciones**
- Reacción en 1 vela es débil → heurística v1 + buffer ATR + `bos_status=active`; Stage 5b futuro.
- Zona M15 vs M5 pueden discrepar → prioridad documentada (OB M5 > POI M15).
- Confianza baja de noche (trigger nunca aporta 10 pts) → comportamiento correcto de tesis.
- Cambio de firma → args nuevos con default `None`; llamada vieja `trigger_engine(m5)` sigue.
- Backtest vs live desalineados en reloj → `now_utc` inyectado.

---

### 5B Stage 4 — POI anclado y rankeado (libro 21)

> Diseñado por sub-agente (leaf). POI = BONUS de calidad (cap 20), NUNCA filtro duro
> (tesis probó: duro = A'' PF 0.900 vs A' PF 1.511).

**Objetivo**
Convertir `poi_engine` de "cualquier OB/FVG + OTE = POI" a un POI ICT real (libro 21):
PD Array en la zona premium/discount correcta del dealing range D1, alineado al sesgo HTF,
respaldado por desplazamiento institucional (BOS activo en su TF), rankeado por tier
(T1 BPR > T2 OB/FVG standalone > T3 rejection), anclado a narrativa HTF y elevado por
stacking multi-TF (OB M15 dentro de FVG H1). Traducido en **bonus acotado (≤20)** que
suma a `confidence` — jamás gate que anule la señal.

**Responsabilidad única**
Clasificar y puntuar la zona de interés M15. NO decide el veredicto, NO bloquea el
trigger, NO detecta estructuras nuevas (reutiliza campos de `analyze_timeframe`).

**Contrato de función (firma EXACTA)**
```python
def poi_engine(
    m15: dict,
    d1: dict | None = None,
    h4: dict | None = None,   # NUEVO: ancla narrativa HTF (bos_dir/bos_status)
    h1: dict | None = None,   # NUEVO: stacking (fvg_state/ob_dir/zone H1)
    bias_side: str | None = None,  # NUEVO: sesgo derivado ("LONG"/"SHORT"/None)
) -> dict
```
- Necesita H1 y H4 (ambos ya existen en `run_pipeline`, costo cero).
- `bias_side` lo pasa `run_pipeline` (mover el cálculo de `derived_bias` arriba de la
  llamada; es puro, sin dependencia circular).
- Función pura: sin I/O, sin estado.

**Salida** (campos existentes intactos):
| Campo | Tipo | Semántica |
|---|---|---|
| `valid` | bool | **SIN CAMBIOS** (has_ob∨has_fvg) ∧ has_ote |
| `has_ob/has_fvg/has_ote/premium_discount/pd_aligned/invalidation/target/note` | — | como hoy |
| `tier` | str | `"T1"`/`"T2"`/`"T3"`/`"SKIP"`/`"PENDING"` |
| `anchored` | bool | BOS/CHOCH H4 activo en dirección del POI |
| `stacked` | bool | PD Array M15 dentro de zona H1 misma dirección |
| `displacement` | bool | BOS M15 activo en dirección del PD Array |
| `quality_bonus` | int | 0–20; suma a confidence en run_pipeline |
| `tier_note` | str | explicación humana |

Integración: `confidence = _confidence(...) + smt_conf + pd_bonus + poi["quality_bonus"]`
(el `pd_bonus` actual de +5 se **absorbe** dentro de `quality_bonus` para no doble-contar).

**Nuevos campos en `context_alignment['poi']`** (string `"VALID"/"INVALID"` se mantiene;
se añaden hermanos): `poi_tier`, `poi_anchored`, `poi_stacked`, `poi_quality_bonus`.
`stages["M15_POI"]` pasa a `✔ T1 BPR apilado` / `✔ T2 sin ancla` / `□ sin POI`.

**Reutilización (campos de analyze_timeframe por condición libro 21)**
| Condición | Campo | TF |
|---|---|---|
| (1) Zona premium/discount | `zone_low/zone_high` D1 (mid=EQ) vs mid M15 | D1+M15 |
| (2) Sesgo HTF | `bias_side` (derived_bias ya calculado) | D1/H1 |
| (3) Desplazamiento | `bos_dir`+`bos_status=="active"` M15 misma dirección | M15 |
| Ancla narrativa | `bos_dir`/`bos_status` H4 en dirección del POI | H4 |
| Tier T1 (BPR) | `has_ob ∧ has_fvg` mismo `zone_low..zone_high` M15 | M15 |
| Stacking | mid zona M15 ∈ [h1.zone_low, h1.zone_high] + dirección H1 | M15+H1 |

**Lógica propuesta (pseudocódigo)**
```python
side_poi = "LONG" si ob_dir M15=="LONG"/bos_dir==1, "SHORT" análogo, ambiguo→bias_side
cond_zona   = (premium_discount=="DISCOUNT" ∧ side_poi=="LONG") ∨ ("PREMIUM" ∧ "SHORT")  # PENDING si sin D1
cond_sesgo  = bias_side in ("LONG","SHORT") ∧ side_poi == bias_side
displacement = m15.bos_status=="active" ∧ bos_dir apunta a side_poi
anchored    = h4 dado ∧ h4.bos_status=="active" ∧ h4.bos_dir apunta a side_poi
stacked     = h1 dado ∧ zona H1 existe ∧ mid_zona_M15 ∈ [h1.zone_low, h1.zone_high] ∧ dir H1==side_poi

si no valid                    → tier = "PENDING"
si cond_zona==False (con D1)  → tier = "SKIP"     # wrong-side: diagnóstico, NO anula valid
si has_ob ∧ has_fvg ∧ displacement → tier = "T1"    # BPR proxy
si (has_ob ⊕ has_fvg) ∧ displacement → tier = "T2"
si (has_ob ∨ has_fvg) sin displacement → tier = "T3"
si stacked ∧ tier=="T2"       → tier = "T1"
si stacked ∧ tier=="T3"       → tier = "T2"

bonus = 0
si valid ∧ tier=="T1": bonus += 10  | "T2": +7 | "T3": +4 | SKIP/PENDING: +0
si cond_zona ∧ cond_sesgo: bonus += 5     # absorbe el pd_bonus actual
si anchored: bonus += 5
quality_bonus = min(bonus, 20)
```
En `run_pipeline`: eliminar el `pd_bonus` suelto (absorbido), sumar `poi["quality_bonus"]`
a confidence. `valid` sigue alimentando `_confidence` → **ninguna señal actual desaparece**.

**Casos**
- Feliz T1 anclado: OB+FVG M15 en DISCOUNT, bias LONG, BOS M15/H4 activos, zona M15 en FVG H1 → T1, anchored, stacked, bonus=20.
- POI suelto sin ancla: FVG M15 con displacement pero sin BOS H4 → T2, anchored=False, bonus=12.
- Wrong-side (SKIP): OB bullish en PREMIUM con bias LONG → SKIP, bonus=0, `valid` intacto (no anula).
- Sin D1: `premium_discount="PENDING"`, sin SKIP posible, sin +5 de zona.
- Sin M15: valid=False, tier="PENDING", bonus=0, nota honesta.

**Regla 'EN CONSTRUCCIÓN'**
Mientras falten insumos (H4/H1 no pasados, o campos PENDING), la UI muestra tier como
`"PENDING (en construcción)"` y `quality_bonus` computa solo con lo disponible. El string
legado `context_alignment["poi"]` NO cambia de semántica hasta que la UI migre.

**Tests sintéticos (GREEN primero)**
1. `test_t1_apilado_anclado`: OB+FVG M15 LONG, BOS activos M15/H4, zona M15 en H1, D1 discount, bias LONG → T1/anchored/stacked/bonus=20.
2. `test_sin_ancla_es_t2`: sin BOS H4 → anchored False, valid True, bonus=12.
3. `test_wrong_side_skip_no_gate`: OB LONG en premium, bias LONG → SKIP, bonus 0, valid True (guardia anti-filtro-duro).
4. `test_sin_d1_pending`: d1=None → premium_discount PENDING, sin SKIP, sin +5.
5. `test_sin_m15_pending`: m15 campos "-" → valid False, tier PENDING, bonus 0.
6. `test_stacking_eleva_tier`: T2 + zona en H1 misma dir → T1.
7. `test_confidence_suma_bonus_y_no_doble_pd`: run_pipeline con bonus 20 → confidence = base + smt + 20 (pd_bonus viejo eliminado).
8. Regresión: todos los tests existentes de `poi_engine` siguen GREEN.

**Riesgos y mitigaciones**
- BPR proxy impreciso (has_ob∧has_fvg no garantiza solapamiento real): mitigar exigiendo
  mismo rango `zone_low..zone_high` M15; refinar cuando analyze_timeframe exponga zonas por tipo.
- Doble conteo de pd_bonus: eliminado explícitamente; test 7 lo asegura.
- Cambio de firma → defaults `None` → retrocompatible.
- Tentación de gate: el contrato prohíbe tocar `valid`; test 3 es guardia anti A'' PF 0.900.
- Reordenar derived_bias antes de poi_engine: cálculo puro sin dependencias del poi.

---

### 5C Resiliencia de run_cycle (cerrar Bloqueo A)

> Diseñado por sub-agente (leaf). Recomienda un ticket hermano **5D** (latencia M5/SMT
> aparte) — ver §8. Este 5C cierra el Bloqueo A (canonical R7) y la Fase C del plan.

**Objetivo**
Garantizar que `last_cycle.json` se escriba **siempre completo** con el veredicto honesto
(pasos 1-5), sin que el paso 6 (canonical R7 / `_canonical_plan`) pueda colgar, matar
por timeout el proceso background, ni dejar el cache viejo/mudo. El canonical se vuelve un
enriquecimiento **best-effort acotado en tiempo**.

**Responsabilidad única**
`run_cycle` orquesta el ciclo y **es dueño de la escritura atómica del cache tras pasos
1-5**. El plan canónico R7 es señal opcional que se intenta *dentro de un presupuesto de
tiempo estricto*; su ausencia = estado honesto `'EN CONSTRUCCIÓN'`, no fallo del ciclo.

**Contrato / cambios en run_cycle**
- **Firma intacta:** `run_cycle(force_fetch: bool = False) -> dict`. UI y `load_cached()` no cambian.
- El cache se escribe con veredicto ya honesto (como hoy, líns 224-230) — se conserva.
- El paso 6 se envuelve en una **llamada acotada por timeout** (`_canonical_plan_bounded`).
  Nueva constante `CANONICAL_TIMEOUT_S` (p.ej. 12s).
- Nuevo helper `_canonical_plan_bounded(symbol, timeout_s) -> dict | None` aísla `_canonical_plan`
  en un worker con timeout. `_canonical_plan` **no se modifica** (mantiene límite backtest≠dashboard).
- Re-escritura del cache tras poblar canonical = **atómica** (tmp + `os.replace`).

**Estrategia elegida: `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=...)`**
| Opción | Veredicto |
|---|---|
| **ThreadPoolExecutor + result(timeout)** ✅ | Sin overhead de intérprete, comparte proceso, `TimeoutError` limpio, run_cycle sigue con `'EN CONSTRUCCIÓN'`. Determinista y trivial de testear (mock con `sleep`). |
| subprocess (job aparte) | Aísla mejor cuelgue nativo C/IO, pero pesado (arrancar intérprete + serializar frames + IPC). Overkill. |
| Job/cron aparte | Ideal a futuro, pero introduce 2 escritores sobre el mismo archivo (más race). No para este sprint. |

*Caveat honesto:* un thread **no se puede matar**; si `_canonical_plan` se cuelga en I/O
nativo bloqueante, el `future` queda huérfano (thread zombie) aunque `run_cycle` ya haya
retornado con cache escrito. **Aceptable** porque el objetivo es que el cache y el dashboard
no se queden mudos. Para blindaje total → promover a `subprocess` después.

**Estructuras de datos / estados de cache**
`result["canonical"]` tiene exactamente **tres estados**:
1. `"EN CONSTRUCCIÓN"` (str) → no disponible (timeout/excepción/aún corriendo). Honesto.
2. `None` → `_canonical_plan` corrió OK pero no hay plan vigente (`max_age_bars` vencido).
3. `dict` poblado → `{side, entry, sl, tp, rr, engine}` + overlay en `result["veredicto"]`.

El **veredicto (votos D1/H4/M15) NUNCA se reescribe** con canonical (se conserva nota Fase C).
El cache siempre contiene: `semaforo, bias, veredicto, noticias, mapas, wyckoff, estructura,
errores` + `canonical` en uno de los 3 estados.

**Reutilización**
- `_canonical_plan(symbol)` **se mantiene idéntico** (líns 278-299): sigue importando
  `ict_backtest.*` y el cap de 2500 barras. El límite backtest≠dashboard se respeta.
- Solo se **envuelve** en `_canonical_plan_bounded`. Cero duplicación.
- La escritura de cache se factoriza en `_write_cache_atomic(result)` reutilizada por paso 5 y paso 6.

**Lógica propuesta (pseudocódigo)**
```python
def _write_cache_atomic(result):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, CACHE_PATH)          # atómico: nunca JSON a medias

def _canonical_plan_bounded(symbol, timeout_s):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_canonical_plan, symbol)
        try:
            return ("OK", fut.result(timeout=timeout_s))   # dict o None
        except FutureTimeoutError:
            return ("TIMEOUT", None)
        except Exception as e:
            return ("ERROR", e)
        # __exit__ hace shutdown(wait=False)

def run_cycle(force_fetch=False):
    ... pasos 1-5 (sin cambios) ...
    result["canonical"] = "EN CONSTRUCCIÓN"
    try: _write_cache_atomic(result)      # <-- garantía de no-silencio
    except Exception as e: log_error("engine","cache_write",e,symbol=SYMBOL)
    status, payload = _canonical_plan_bounded(SYMBOL, CANONICAL_TIMEOUT_S)
    if status == "OK" and payload:
        result["canonical"] = payload
        verd = dict(result.get("veredicto") or {})
        verd.update(invalidation=payload["sl"], target=payload["tp"],
                    canonical_entry=payload["entry"], canonical_side=payload["side"],
                    canonical_rr=payload["rr"], engine=payload["engine"])
        result["veredicto"] = verd
        log_event("engine","canonical_plan",...)
        try: _write_cache_atomic(result)
        except Exception as e: log_error(...)
    elif status == "OK":
        result["canonical"] = None
        log_event("engine","canonical_plan_empty",...)
    elif status == "TIMEOUT":
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append("canonical: timeout")
        log_error("engine","canonical_timeout",...,symbol=SYMBOL)
    else:
        result["canonical"] = "EN CONSTRUCCIÓN"
        result["errores"].append(f"canonical: {payload}")
        log_error("engine","canonical_plan_fallo",payload,symbol=SYMBOL)
    return result
```
Punto crítico: el cache se escribe **antes** del paso 6 y el paso 6 nunca tarda más de
`CANONICAL_TIMEOUT_S`. Si el canonical llega dentro del presupuesto, se re-escribe atómicamente.

**Casos**
| Caso | `canonical` en cache | Cache escrito | Notas |
|---|---|---|---|
| Ciclo OK + canonical OK | `dict` poblado | 2 veces (pre + enriquecido) | veredicto con overlay, votos intactos |
| Ciclo OK + canonical vigente=None | `None` | 1 vez | honesto: no hay plan fresco |
| Ciclo OK + canonical tarda >timeout | `"EN CONSTRUCCIÓN"` | 1 vez (pre-paso6) | thread huérfano, run_cycle retorna |
| Ciclo OK + canonical lanza excepción | `"EN CONSTRUCCIÓN"` | 1 vez | error en `errores` |
| Ciclo parcial (un TF de contexto falla) | — | 0 (return temprano lín 83) | sin contexto no hay veredicto; comportamiento actual conservado |

**Regla 'EN CONSTRUCCIÓN'**
`canonical` = `"EN CONSTRUCCIÓN"` **siempre que el plan no se pudo obtener por tiempo o
error**, nunca plan inventado ni último plan viejo. `None` = "corrió limpio pero no hay señal
vigente". La UI distingue: `"EN CONSTRUCCIÓN"` = chip gris "calculando"; `None` = chip
"sin plan vigente"; `dict` = chip con Entry/SL/TP. Honestidad = el estado refleja la realidad.

**Tests sintéticos (TDD — GREEN)**
Mockeando `engine._canonical_plan` (monkeypatch), `CACHE_PATH` → `tmp_path`:
1. `test_canonical_lento_no_bloquea_cache`: mock `sleep(30)`, `CANONICAL_TIMEOUT_S=1` → retorna ~1s, cache existe, veredicto poblado, `canonical=="EN CONSTRUCCIÓN"`, error registrado.
2. `test_canonical_excepcion_deja_en_construccion`: mock `raise RuntimeError` → cache presente, canonical EN CONSTRUCCIÓN, veredicto intacto.
3. `test_canonical_ok_enriquece`: mock devuelve plan fake → `canonical==dict`, `veredicto["invalidation"]==plan["sl"]`, votos sin cambios.
4. `test_canonical_none_honesto`: mock devuelve None → `canonical is None`.
5. `test_cache_siempre_presente`: parametrizado {lento, excepción, None, ok} → siempre `CACHE_PATH.exists()` y JSON parseable con clave `veredicto`.
6. `test_write_atomico_sin_json_parcial`: nunca queda `.json.tmp` y el JSON final siempre parsea.

**Riesgos y mitigaciones**
- Thread zombie (cuelgue nativo I/O): `shutdown(wait=False)` para no esperar; el thread muere solo. Si recurrente → promover a `subprocess` (misma interfaz `_canonical_plan_bounded`).
- Race al re-escribir cache: resuelta con `tmp + os.replace` — un lector nunca ve JSON parcial.
- Acumulación de threads si run_cycle se llama en loop rápido: `max_workers=1` + `with` context; un cuelgue previo no impide el siguiente. Aceptable (run_cycle es periódico).
- Doble escritura de cache (2 writes en OK): costo trivial, atómico, sin corrupción.

**Asunciones**
1. `os`, `json`, `concurrent.futures` importables; `CACHE_PATH` es `Path`.
2. La lentitud de `analyze_timeframe` (M5/SMT) NO se resuelve aquí → ver ticket 5D (§8).
3. `_canonical_plan` es idempotente y sin efectos secundarios → seguro en thread.

---

### 5D Two-pass en run_cycle (latencia M5/SMT aparte) — CERRADO 2026-07-23

> Ticket hermano recomendado por 5C. NO toca el diseño de 5C: mantiene intactos
> `_write_cache_atomic`, `_canonical_plan_bounded`, `_canonical_plan` y la firma
> `run_cycle(force_fetch=False)`. Solo mueve la PRIMERA escritura de cache a ANTES
> de cargar M5/SMT.

**Objetivo**
El dashboard debe ver el veredicto CORE (sesgo + POI + trigger) en minutos, sin
esperar a que `analyze_timeframe` de M5/SMT (lentos en este entorno: M5 ~194 s,
par SMT ~53 s) termine, ni al canonical.

**Qué hace (two-pass)**
- **PASS 1 (core, rápido):** analiza D1/H4/H1/M15 (TIMEFRAMES), llama
  `run_pipeline(..., m5=None, smt_a=None, smt_b=None)` → veredicto honesto (trigger
  PENDING si falta M5, SMT PENDING sin el par). Escribe `estructura` y hace la
  **escritura atómica INMEDIATA** del cache (con `canonical` aún sin poblar).
- **PASS 2 (enriquecimiento, best-effort):** carga M5 (`SYMBOL M5`) y SMT
  (`SYMBOL_PAIR H1`) APARTE; si cargó algo, re-llama
  `run_pipeline(..., m5=m5_info, smt_a=h1, smt_b=smt_b_info)` → veredicto
  ENRIQUECIDO y **re-escribe** el cache. Si M5/SMT fallan, el veredicto final =
  el core (nunca vacío, nunca se inventa M5/SMT).
- Luego sigue el flujo 5C intacto: noticias/semáforo/mapas/wyckoff + paso 6
  canonical acotado (`'EN CONSTRUCCIÓN'` + re-escritura best-effort).

**Escrituras de cache (máximo, todas atómicas)**
1. pass 1 (veredicto core) — NUEVA, inmediata.
2. pass 2 (veredicto enriquecido con M5/SMT) — si M5/SMT cargaron.
3. paso 6 canonical (`'EN CONSTRUCCIÓN'` y luego dict si llega) — lógica 5C.

**Contrato conservado**
- Firma `run_cycle` y `load_cached()` intactas; campos de `result`/`context_alignment`
  sin cambios de semántica (solo se escriben antes).
- Return temprano si falta D1/H4/H1/M15 (comportamiento 5C) sin cambios.
- `_canonical_plan_bounded`, `_write_cache_atomic` y `run_pipeline` NO se modifican.

**Suite:** `tests/test_run_cycle_twopass.py` (8 tests: pass1 sin M5, enriquecimiento
re-escribe, cache siempre presente parametrizado, pass1 no espera canonical,
regresión 5C, return temprano sin datos core). Regresión 5A/5B/5C/UI GREEN.

---

## 6. Orden de implementación por fases (gobernanza Ruben)

Cada fase: demo sintética → tests GREEN → datos reales → evidencia en vivo → doc al día.

1. **Fase 1 — 5C (resiliencia run_cycle):** primero que nada, el cache vivo debe
   escribirse siempre. Sin esto no hay evidencia de nada. (Desbloquea Fase C del plan.)
2. **Fase 2 — 5B (POI libro 21):** enriquece `context_alignment["poi"]` como bonus.
   No cambia el flujo de decisión, solo sube `confidence` cuando hay POI de verdad.
3. **Fase 3 — 5A (trigger real + sesión):** añade la máquina de estados al trigger y
   el gate de killzone. Es el salto de "análisis listo" a "setup armable".
4. **Fase 4 — Integración y evidencia viva:** `run_pipeline` con los 3 cambios en
   EURUSD real; capturar `last_cycle.json` con trigger READY + POI tier + canonical vivo.

---

## 7. Definición de terminado

Un componente está terminado cuando:
✓ el motor produce el dato · ✓ la UI lo consume · ✓ el usuario lo ve ·
✓ existe evidencia de lectura en vivo · ✓ está documentado · ✓ quedó en el roadmap.

Cierre total del SDD cuando los 4 huecos tengan evidencia viva en `last_cycle.json`
y la UI muestre: sesgo → POI tier → trigger READY en killzone → entry/SL/TP vivos,
sin que `run_cycle` se quede mudo.

**Estado (2026-07-23):** los 4 huecos tienen **implementación + tests GREEN**
(5C: 9 tests · 5B: 9 tests · 5A: 16 tests — 34 passed en una sola corrida) y
evidencia viva con EURUSD real vía parquet en
`docs/evidence/fase4_last_cycle_probe.json` (ver §9). El estado READY del trigger
depende del mercado del momento (la sonda mostró honestamente PENDING con la
última vela disponible); la máquina de estados y el gate de killzone están
cableados y testeados.

---

## 8. Tickets resumidos + índice

### Tickets (orden de ejecución)
| ID | Componente | Cierra | Entrega | Depende de |
|----|-------------|--------|----------|------------|
| **5C** | Resiliencia `run_cycle` (canonical acotado en tiempo + cache atómico) | Bloqueo A + Fase C del plan | sección §5C | — (primero) |
| **5B** | POI anclado y rankeado (libro 21) como bonus ≤20 | Hueco 2 | sección §5B | — |
| **5A** | Trigger real de entrada + gate de sesión (killzone) | Huecos 1 y 4 | sección §5A | 5B (consume `poi`) |
| **5D** | Latencia M5/SMT aparte (two-pass: cache core primero, M5/SMT/canonical como enriquecimiento) | Deuda de lentitud de `analyze_timeframe` | fuera de este SDD (recomendado por 5C) | 5C |
| **Fase 4** | Integración + evidencia viva EURUSD | cierre total | §6 paso 4 | 5A+5B+5C |

### Índice de secciones
- §0 Alcance · §1 Estado actual · §2 Los 4 huecos · §3 Principios de diseño
- §4 Contrato de integración en `run_pipeline` · §5 Secciones por componente
- §5A Trigger real + sesión · §5B POI libro 21 · §5C Resiliencia run_cycle
- §6 Orden de fases · §7 Definición de terminado · §8 Tickets + índice

### Notas de los sub-agentes (hallazgos verificables)
- **5A**: `core/timezone.py` YA tiene `KILLZONES_UTC` (London 07–10, NY AM 12:30–15,
  NY PM 17–20 UTC) y resuelve el ⚠TZ de la tesis §11. London + NY PM NO están
  "no cableados" — solo falta enchufar `killzone_en(dt)` al pipeline y actualizar el mapa §11.
- **5C**: el cuelgue del canonical es best-effort acotado con `ThreadPoolExecutor` +
  `result(timeout)`; caveeat honesto: thread zombie si el cuelgue es I/O nativo (aceptable
  para el objetivo; promover a `subprocess` si recurre). Recomienda 5D para M5/SMT.
- **5B**: POI como bonus (cap 20), NUNCA filtro duro (guardia anti A'' PF 0.900 en test 3).
  `valid` no se toca; solo sube `confidence` cuando hay POI de verdad.

---

## 9. Estado de ejecución (2026-07-23)

| Ticket | Estado | Tests | Suite |
|--------|--------|-------|-------|
| **5C** Resiliencia `run_cycle` (canonical acotado + cache atómico) | ✅ IMPLEMENTADO | 9 passed | `tests/test_run_cycle_resilient.py` |
| **5D** Two-pass `run_cycle` (cache core inmediato + enriquecimiento M5/SMT/canonical aparte) | ✅ IMPLEMENTADO | 8 passed | `tests/test_run_cycle_twopass.py` |
| **5B** POI libro 21 (tier/anchored/stacked/quality_bonus) | ✅ IMPLEMENTADO | 9 passed | `tests/test_poi_engine_book21.py` |
| **5A** Trigger real (máquina de estados) + gate de killzone | ✅ IMPLEMENTADO | 16 passed | `tests/test_trigger_engine_session.py` |
| **Fase 4** Integración + evidencia viva EURUSD | ✅ EVIDENCIA GENERADA | — | `docs/evidence/fase4_last_cycle_probe.json` (sonda: `tests/_probe_fase4_evidence.py`) |

Comandos exactos que pasaron (2026-07-23):

```bash
python -m pytest tests/test_run_cycle_resilient.py tests/test_poi_engine_book21.py tests/test_trigger_engine_session.py -q
# -> 34 passed

python -m pytest tests/test_run_cycle_resilient.py -q   # 9 passed
python -m pytest tests/test_poi_engine_book21.py -q     # 9 passed
python -m pytest tests/test_trigger_engine_session.py -q  # 16 passed
```

Evidencia viva (EURUSD real, parquet `data/raw/`, SIN MT5; los 5 TF D1/H4/H1/M15/M5
disponibles y frescos):

- `context_alignment` ahora incluye: `poi_tier` (la sonda mostró `SKIP wrong-side`
  — POI válido pero del lado equivocado del dealing range, diagnóstico honesto,
  NO anula `valid`), `poi_anchored`/`poi_stacked`/`poi_quality_bonus`, y
  `trigger_machine` (`PENDING` con la última vela — sin estructura M5 completa en
  ese instante; la máquina de estados y el gate de killzone están cableados).
- `run_cycle(force_fetch=False)` escribe el cache SIEMPRE (atómico) y `canonical`
  queda en uno de los 3 estados honestos (`"EN CONSTRUCCIÓN"` / `None` / dict);
  detalle en el JSON de evidencia.
- Deuda conocida (ticket 5D, fuera de este SDD): `analyze_timeframe` sigue lento
  en este entorno (M5 ~194 s, M15 ~53 s) — no bloquea el cache gracias a 5C.

Pendiente para cierre TOTAL (§7): validación visual en la UI con display
(chips POI tier / trigger machine / canonical) — el motor ya produce los datos.

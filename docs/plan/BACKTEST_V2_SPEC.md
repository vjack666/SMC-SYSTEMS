# Backtest v2 — Architecture Specification

| Campo | Valor |
|-------|-------|
| **ID** | `BACKTEST_V2_SPEC` |
| **Versión** | **1.1 (Architecture Approved + ops)** |
| **Fecha** | 2026-07-16 |
| **Estado** | **ARCHITECTURE APPROVED** — congela la **arquitectura**; **no** congela la implementación |
| **Ops** | Ejecución de corridas: `docs/plan/RUNNER_MONITOR.md` (CPU/RAM, ventanas, multi-par) |
| **Aprobación** | Arquitectura aceptada como especificación oficial de diseño (revisión Ruben / feedback integrado) |
| **Autoridad** | Referencia para Backtest v2 y evaluación de cobertura de la estrategia ICT |
| **No sustituye** | `CRONOGRAMA_Y_ROADMAP.md`, `PLAN_BACKTEST_PROFESIONAL.md` (R6 reloj/fill/costos) |
| **Se apoya en** | `20_TESIS_ICT.md`, `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`, `21_POI.md`, `13_BACKTEST_PROFESIONAL/`, auditorías Strategy vs Sim |
| **Prohibido hasta auth de implementación** | Programar multi-TF, tocar edge con Optuna, mezclar strategy en el simulador |

### Qué congela v1.0 (y qué no)

| Congela (arquitectura) | No congela (implementación) |
|------------------------|-----------------------------|
| Separación Strategy / TradingPlan / Orders / Simulator | APIs Python concretas, nombres de archivos |
| Cadena multi-TF y roles por TF | Algoritmos exactos de un detector |
| FSM de plan entre capas | Optimizaciones de performance |
| Catálogo de eventos + event log obligatorio | Formato binario del log |
| Coverage Matrix C0x + reporte automático | Umbrales numéricos de edge |
| Roadmap de fases F0–F7 y DoD tipo | Orden interno de tareas dentro de una fase si la evidencia lo exige |
| Política de ejecución de corridas (ventana visible, recursos, multi-par) | Código exacto del launcher multi-symbol |

**Cláusula de evolución:** cada fase (F0–F6) **podrá ajustarse** durante el desarrollo si auditorías o evidencia empírica muestran una mejor solución, **siempre respetando los principios** de esta especificación (separación Strategy/Sim, cobertura medible, reloj causal, no declarar edge de “tesis completa” sin cobertura).

---

## 0. Pregunta que responde este documento

> **¿Cómo debe trabajar el backtest para reproducir el proceso mental del trader ICT — desde que abre el gráfico hasta que cierra la operación — sin confundir decisión con simulación de broker?**

### 0.1 Diagnóstico que motiva v2 (hechos ya auditados)

| Hecho | Implicación |
|-------|-------------|
| Path prod actual ≈ **H4 bias + M15 sequence** + KZ + SL/TP parciales + fill/costos | Evalúa un **subset** de la tesis |
| D1 a menudo se **carga** pero no decide si `htf ≠ D1` | Contexto macro ausente en la decisión |
| H1 / M5 / M1 **no** están en el generador canónico | No hay 3 capas reales ni entry fino |
| POI / P-D / stacking / narrativa **no** (o desactivados) | Filtros de calidad del humano no se prueban |
| R6.4 M2: resultado pobre en EURUSD M15 | Valida **esta implementación**, no “toda la estrategia ICT del doc” |

### 0.2 Regla científica (no negociable)

```text
Conclusión de rentabilidad  ≡  conclusión sobre la COBERTURA implementada bajo prueba.
Cobertura parcial          ⇒  no se declara “la tesis ICT no tiene edge”.
```

**Lenguaje oficial (reemplaza estimaciones vagas):**

> La cobertura funcional actual es **parcial** y **deberá cuantificarse** mediante la Coverage Matrix (C0x) y el **Coverage Report automático** antes de interpretar los resultados como representativos de la estrategia completa.

No se usarán frases del tipo “un tercio / la mitad” como cifra oficial sin reporte C0x.

### 0.3 Principio de separación (v1.0)

```text
Strategy
    ↓
TradingPlan          ← contexto, narrativa, zonas, score, invalidaciones, 0..n intents
    ↓
Orders[]             ← órdenes listas para broker simulado
    ↓
Simulator            ← fill, fricción, path OHLC, exit, PnL
    ↓
TradeResult + EventLog + CoverageReport
```

**Backtest v2** = orquestación que:

1. Corre la **Strategy multi-TF** (proceso mental ICT) y materializa un **TradingPlan**.  
2. Deriva **Orders** del plan (puede haber 0, 1 o N).  
3. Pasa cada Order al **Simulator** (R6: fill/costos/reloj).  
4. Emite **EventLog** + **explicación por trade** (observabilidad).  
5. **Nunca** re-decide bias/POI/KZ/SL/TP dentro del simulador.

---

## 1. Flujo temporal completo (recorrido del reloj mental)

El trader ICT **no** opera un solo TF. Lee en cascada (top-down). El backtest v2 debe recorrer la **misma cascada** en cada instante de decisión del exec TF.

### 1.1 Cadena canónica de timeframes

```text
D1   →  contexto macro / rango / liquidez de día-semana
 ↓
H4   →  bias y narrativa de sesión multi-día / POI de contexto
 ↓
H1   →  confirmación estructural intermedia (ITF intradía)
 ↓
M15  →  manipulación + displacement + BOS/CHOCH de setup
 ↓
M5   →  refinamiento / mitigación de zona
 ↓
M1   →  entrada fina (solo modelos scalping avanzados; opcional)
```

### 1.2 Qué aporta cada TF

| TF | Rol mental del trader | Información que debe producir | Qué **no** debe hacer |
|----|----------------------|-------------------------------|------------------------|
| **D1** | Historia de más alto nivel | Dealing range, premium/discount, liquidez macro, bias de contexto, régimen grueso | Entry/SL/TP de scalping |
| **H4** | Flujo institucional del horizonte intradía | Bias H4, BOS/CHOCH H4, sweeps H4, POI de contexto, narrativa | Disparar entry M1 |
| **H1** | ¿El plan H4 sigue vivo? | Validación POI, FVG/OB de zona, invalidación temprana | Costos de broker |
| **M15** | Manipulación y confirmación de setup | Sweep, displacement, BOS/CHOCH, cuadro mitigation, fase de setup | Inventar bias D1 |
| **M5** | Precisión de mitigación / exec SB | Toque de zona, micro-confirmación, entry/SL/TP si exec=M5 | Redefinir sesgo H4 sin invalidación formal |
| **M1** | Entry de mínimo riesgo estructural | Entry, SL, TP inmediatos si el modelo lo exige | Obligatorio en intradía M15-exec |

### 1.3 Perfiles de modelo

| Modelo | Bias HTF | Zona ITF | Exec TF | M1 |
|--------|----------|----------|---------|-----|
| **Intradía / PO3-Turtle (default tesis 18)** | D1 + H4 | H1 + M15 | **M15** | No |
| **Silver Bullet estándar** | H4 o H1 | M15 + M5 | **M5** | No |
| **Silver Bullet fino** | H4 o H1 | M15 + M5 | **M1** | Sí |
| **Swing (futuro)** | W1/D1 | H4 | H1 | No |

> **Regla dura (tesis 18):** SL y entry **siempre** en el **exec TF** del modelo activo.

### 1.4 Reloj y causalidad multi-TF (R6 se reutiliza)

En cada barra del **exec TF** con timestamp `t`:

1. Solo barras HTF/ITF con **cierre ≤ t**.  
2. Sin OHLC futuro.  
3. Fill default: **next_open** del exec TF (G2).  
4. Costos ON en producción (G3).

---

## 2. Máquina de estados entre timeframes

La FSM **dentro de M15** (`IDLE → SWEEP → DISPLACE → BOS → ENTRY`) se conserva como **submáquina de setup**.  
v2 añade la FSM **de plan** entre capas:

```text
NO_TRADE → CONTEXT_OK → ZONE_ARMED → SETUP_LIVE → STRUCTURE_OK
         → ENTRY_READY → IN_TRADE → CLOSED
```

| Desde | Hacia | Condición | Capa |
|-------|-------|-----------|------|
| NO_TRADE | CONTEXT_OK | Bias D1/H4 usable; régimen operable | D1+H4 |
| CONTEXT_OK | ZONE_ARMED | POI/zona alineada a bias y P/D | H4+H1 |
| ZONE_ARMED | SETUP_LIVE | Sweep de liquidez opuesta al setup | M15 |
| SETUP_LIVE | STRUCTURE_OK | Displace (si aplica) + BOS/CHOCH según modelo | M15 |
| STRUCTURE_OK | ENTRY_READY | Mitigación en exec TF + gates de sesión | Exec |
| ENTRY_READY | IN_TRADE | Simulator llena Order | Sim |
| IN_TRADE | CLOSED | SL/TP/hold/gestión/invalidación | Strategy rules + Sim path |
| * | NO_TRADE | Invalidación de plan | Multi-TF |

Sin `CONTEXT_OK` y `ZONE_ARMED`, la submáquina M15 **no arma** trades en modo v2 full (salvo `legacy_subset=true`).

### 2.1 Proceso mental del trader (= especificación)

```text
1. D1: rango, P/D, liquidez macro
2. H4: bias y POI de historia
3. H1: ¿zona sigue válida?
4. Killzone
5. M15: sweep → displace → BOS/CHOCH
6. Cuadro FVG/OB; esperar retorno (no chase BOS close)
7. Exec TF: mitigation / entry
8. SL estructural exec TF
9. TP liquidez cercana; RR mínimo o no-trade
10. Gestión hasta exit
```

---

## 3. Decisiones por timeframe

(Resumen; detalle de tablas D1…M1 sin cambio de intención respecto al diseño 0.1.)

| TF | Decide | No decide |
|----|--------|-----------|
| D1 | Contexto, dealing range, P/D, liquidez macro, bias contexto | Entry/SL/TP |
| H4 | Bias plan, BOS/CHOCH contexto, POI candidatos, CT permitido | Entry M1 |
| H1 | POI vigente, FVG/OB zona, invalidación | Costos |
| M15 | Sweep, displace, BOS/CHOCH setup, mitigation box | Spread broker |
| M5 | Mitigación fina / exec SB | Bias D1 |
| M1 | Entry fino opcional | Contexto D1 |

---

## 4. Herencia de capas → TradingPlan → Orders

```text
D1  → ContextSnapshot
H4  → PlanSnapshot   (hereda Context)
H1  → ZoneSnapshot   (hereda Plan)
M15 → SetupSnapshot  (hereda Zone+Plan)
Exec→ EntryIntent(s)
        ↓
   TradingPlan  (agrega todo lo anterior + score + invalidaciones + event trail)
        ↓
   Orders[]
        ↓
   Simulator
```

### 4.1 `TradingPlan` (contrato mínimo)

Un plan **no es** solo una orden. Contiene la decisión completa del trader en `t`:

```text
TradingPlan:
  plan_id: str
  symbol: str
  model_id: str
  state: NO_TRADE | CONTEXT_OK | ... | ENTRY_READY | IN_TRADE | CLOSED
  coverage_mode: "legacy_subset" | "v2_full" | "v2_partial:<tag>"

  context: ContextSnapshot      # D1...
  narrative: PlanSnapshot       # H4...
  zone: ZoneSnapshot | null     # H1...
  setup: SetupSnapshot | null   # M15...

  quality_score: float | null   # POI bonus, confluencias, etc.
  invalidation_rules: list      # qué mataría este plan
  event_ids: list[str]          # punteros al EventLog

  orders: list[Order]           # 0..n órdenes listas (puede ser vacío)
  explanation: TradeExplanation # ver §9 observabilidad
```

### 4.2 `Order` (mínimo)

```text
Order:
  order_id, plan_id, symbol, model_id
  direction: +1 | -1
  signal_time: timestamp
  stop_loss: float
  take_profit: float
  max_hold_bars: int
  meta: dict   # opaque para el sim
```

### 4.3 Reglas de herencia

1. Un hijo no inventa bias: lo hereda o invalida.  
2. POI LTF sin ancla de Zone/Plan no es POI.  
3. Simulador no interpreta `meta` ni snapshots.  
4. TF requerido ausente → `DATA_INCOMPLETE` / NO_TRADE (no fallback silencioso salvo `legacy_subset`).

### 4.4 Modo `legacy_subset`

```text
legacy_subset=true  →  H4+M15 (+ filtros v1); para comparación R6.4
legacy_subset=false →  cadena del modelo (default v2)
```

Toda métrica en METRICS_CANON debe llevar `coverage_mode` + **Coverage Report**.

---

## 5. Eventos y Event Log canónico

### 5.1 Eventos de Strategy (decisión)

```text
BiasFormed, DealingRangeDefined, PremiumDiscountLabeled,
POIIdentified, POIValidated, POIInvalidated,
LiquidityMapped, SweepTaken, DisplacementPrinted,
CHOCHPrinted, BOSPrinted, MSSAccepted,
MitigationBoxDrawn, ZoneTouched,
KillzoneOpen, KillzoneClosed,
PlanFormed, PlanInvalidated,
OrderIntentEmitted,
ManageScaleOut, ManageBreakEven, ManageTrail,
ExitIntent
```

### 5.2 Eventos de Simulator (broker)

```text
OrderAccepted, EntryFilled, BarPathProgress,
StopHit, TargetHit, HoldExpired, GapThrough,
ExitFilled, CostsApplied, TradeClosed
```

### 5.3 Event Log obligatorio (canonical)

**Requisito de arquitectura:** todo evento de §5.1 y §5.2 que ocurra en una corrida **debe persistirse** en un log ordenado por tiempo (y desempate estable).

```text
EventLogRecord:
  ts: timestamp          # tiempo de mercado o de barra
  seq: int               # orden estable
  kind: event_name
  plan_id: str | null
  order_id: str | null
  trade_id: str | null
  tf: str | null         # D1|H4|H1|M15|M5|M1
  payload: dict          # datos mínimos reproducibles (niveles, ids de objetos)
```

Ejemplo de reproducción de un trade:

```text
09:15  BiasFormed           tf=H4   payload={bias:BULLISH}
09:20  DealingRangeDefined  tf=D1   payload={pd:DISCOUNT}
09:30  POIValidated         tf=H1   payload={poi_id:...}
09:45  SweepTaken           tf=M15
10:00  BOSPrinted           tf=M15
10:15  ZoneTouched          tf=M15
10:15  OrderIntentEmitted
10:15  EntryFilled          (sim)
10:45  TargetHit
10:45  TradeClosed
```

**DoD de log:** dado un `trade_id`, se puede reconstruir la cadena de eventos **sin** releer el código de strategy a mano.

Formato de archivo (JSONL / parquet) se elige en implementación; el **contrato de campos** queda congelado aquí.

---

## 6. Qué queda en Strategy

Todo lo que responde “**¿operamos y con qué plan?**”:

| Dominio | Responsabilidades |
|---------|-------------------|
| Contexto | Bias D1/H4, ranging/no-trade, régimen |
| Rango | Dealing range, EQ, premium/discount |
| Liquidez | BSL/SSL, sweeps válidos |
| POI | Ancla, tiers, stacking, bonus (no gate duro por defecto) |
| Estructura | BOS, CHOCH, MSS, displacement |
| Secuencia setup | sweep→…→mitigation |
| Sesión | Killzones, (futuro) news |
| Modelo | PO3 / Turtle / SB + mapa TF |
| Entry / SL / TP / RR | Construcción de Order dentro del plan |
| Gestión | max_hold, BE, parciales, trail, ExitIntent |
| Invalidación | Por evento y por ruptura de narrativa |
| **TradingPlan** | Empaquetado de contexto + narrativa + orders + explanation |
| **Eventos de decisión** | Append al EventLog |

Strategy **no** calcula half-spread fill ni path OHLC post-orden (salvo emitir ExitIntent / update de niveles).

---

## 7. Qué queda en Simulation

```text
Order
  → validación numérica mínima
  → fill (next_open / signal_close)
  → spread / slip / commission
  → path OHLC (SL/TP/hold/gaps)
  → exit
  → PnL (R / $)
  → eventos de broker en EventLog
  → TradeResult
```

### 7.1 Invariante de pureza

El simulador **no** lee columnas ICT para decidir, no aplica KZ, no elige SL/TP, no filtra P/D.

### 7.2 Reutilización v1

| v1 | Rol v2 |
|----|--------|
| `simulate_trade`, `fill_entry_price`, `costs`, `_util` closed HTF, `_metrics` | **Simulator** |
| `run_sequence`, `generate_sequence_signals`, `calc_structural_sl`, `_tp_liquidity` | **Strategy** (plan/orders) |

---

## 8. Coverage Matrix y Coverage Report **automático**

### 8.1 Capacidades (C0x) — fuente de verdad de cobertura

| ID | Capacidad | required_for_full_thesis |
|----|-----------|--------------------------|
| C01 | Bias HTF (≥1 TF) | sí |
| C02 | Contexto D1 en decisión | sí |
| C03 | Dealing range + Premium/Discount | sí |
| C04 | H1 validación de zona | sí |
| C05 | POI anclado a narrativa | sí |
| C06 | Stacking multi-TF POI | sí |
| C07 | Secuencia Sweep→BOS→mitigation | sí |
| C08 | Killzone | sí |
| C09 | SL estructural en exec TF | sí |
| C10 | TP liquidez cercana (no solo cluster ciego) | sí |
| C11 | RR mínimo 1:3 como gate de calidad | sí |
| C12 | Confirmación M5 (según modelo) | condicional |
| C13 | Entry M1 (según modelo) | condicional |
| C14 | Invalidación narrativa por evento | sí |
| C15 | Trade management (BE/parciales/trail) | sí |
| C16 | Fill realista | sí (sim) |
| C17 | Costos reales | sí (sim) |
| C18 | Reloj HTF closed-only | sí (sim) |
| C19 | Métricas etiquetadas por cobertura | sí (harness) |
| C20 | Separación Strategy/Sim/Plan | sí (harness) |

Estados por capacidad: `implemented | partial | missing | n/a_model`.

### 8.2 Coverage Report (salida obligatoria de cada corrida v2)

No se discute “a ojo”. Cada run debe emitir (estructura lógica):

```text
Coverage Report
───────────────
model_id: ...
coverage_mode: legacy_subset | v2_full | v2_partial:...

required:     N     # C0x con required_for_full_thesis=yes (o aplicables al model)
implemented:  K     # estado == implemented
partial:      P
missing:      M

coverage_pct:  100 * (implemented + 0.5*partial) / required
              # fórmula fija; no se inventan % en chat

per_capability:
  C01: implemented
  C02: missing
  ...
```

**Regla:**  
`coverage_pct` y el detalle C0x se generan por **código de reporte** (Fase 0), no por estimación en documentos sueltos.

Hasta que exista el reporter automático, en docs solo se dice **“cobertura parcial — pendiente cuantificar con Coverage Report”**.

### 8.3 Interpretación de métricas

```text
if coverage_mode != v2_full OR coverage_pct < umbral_acordado:
    veredicto = "resultado de implementación parcial"
else:
    veredicto = "candidato a edge de estrategia objetivo (aún sujeto a OOS/WF)"
```

Umbral numérico de “full thesis” se fija al cerrar F0 (propuesta de trabajo: required C01–C11 + C14 + C16–C20 en `implemented`; C12–C13 según model_id).

---

## 9. Observabilidad (capa obligatoria)

No basta con `BUY` / `SELL`.

### 9.1 `TradeExplanation` (por trade)

```text
TradeExplanation:
  trade_id, plan_id, order_id
  result: TP | SL | HOLD | ...
  layers:
    D1: { bias, pd_side, dealing_range_summary }
    H4: { bias, bos/choch, narrative }
    H1: { poi_valid, zone }
    M15: { sweep, displace, bos, mitigation }
    exec: { tf, entry, sl, tp }
  quality_score: ...
  event_log_slice: [event_ids...]   # para abrir el log canónico
```

Ejemplo de vista humana:

```text
Trade 241  Result: TP
  D1:  Discount | context bias bullish
  H4:  Bullish BOS | plan alive
  H1:  POI valid
  M15: Sweep → Displacement → BOS → Mitigation
  Entry: ...  SL: ...  TP: ...
```

### 9.2 Usos

- Depuración de “por qué entró”.  
- Auditoría vs tesis.  
- Comparar legacy_subset vs v2_full en el mismo día de mercado.

La explicación la **construye Strategy/Plan** (conoce la narrativa); el Simulator solo aporta fills y `exit_reason`.

---

## 10. API lógica v1.0

```text
context = build_market_context(frames, t)           # joins closed-only
plan    = Strategy.evaluate(context, model_config)  # → TradingPlan + events
orders  = plan.orders
results = []
for o in orders:
    tr, sim_events = Simulator.run(o, frames[exec_tf], costs)
    results.append(tr)
    EventLog.append(sim_events)
report = Metrics.aggregate(results)
cover  = CoverageReport.from_registry(model_config, impl_registry)
# artifacts: EventLog, TradeExplanations, cover, report
```

---

## 11. Roadmap de fases + Definition of Done

### Plantilla DoD (toda fase F0–F7)

Cada fase **no está done** sin:

```text
DoD (plantilla)
───────────────
[ ] Objetivo de arquitectura de la fase cumplido (checklist de la fase)
[ ] Tests (sintéticos y/o regresión legacy_subset según fase)
[ ] Documentación actualizada (spec anexo o avances)
[ ] Coverage registry C0x actualizado (estados implemented/partial/missing)
[ ] Coverage Report generable en corrida de humo
[ ] Comparación legacy (si aplica): misma muestra, métricas etiquetadas
[ ] EventLog emite eventos nuevos de la fase (si la fase introduce eventos)
[ ] Ningún if ICT nuevo dentro del Simulator
[ ] Auth de merge según reglas del repo
```

---

### Fase 0 — Frontera, cobertura, observabilidad mínima

**Objetivo:** congelar borde Plan/Order/Sim; reporter C0x; log de eventos skeleton.

**Estado (2026-07-16):** ✅ **código F0 entregado** — `ict_backtest/v2/`, tests `tests/test_backtest_v2_f0.py`, avance `docs/avances/BACKTEST_V2_F0.md`.

**DoD específico + plantilla:**

- [x] Contratos TradingPlan / Order / TradeResult / EventLogRecord documentados e implementables  
- [x] Registry C0x versionado (`ict_backtest/v2/coverage.py`)  
- [x] Coverage Report se genera aunque casi todo esté `missing`/`partial`  
- [x] Corrida `legacy_subset` etiqueta `coverage_mode` y no llama “tesis full”  
- [x] Simulator sin nuevas dependencias ICT (`v2/simulator.py` solo OHLC + Order)  
- [x] EventLog + TradeExplanation en corrida  
- [x] CLI `python -m ict_backtest.v2.run_v2` + ops runner_monitor  
- [ ] Auth de merge / commit (operador)

---

### Fase 1 — D1 vivo en decisión

**Objetivo:** ContextSnapshot desde D1 closed-only en el plan.

**DoD específico:**

- [ ] C02 → `implemented` o justificación `partial` con test  
- [ ] Tests: D1 ranging vs trending cambia `TradingPlan.state` / orders  
- [ ] Eventos: `BiasFormed` / contexto D1 en EventLog  
- [ ] Explanation muestra capa D1  
- [ ] Plantilla DoD §11  

---

### Fase 2 — H1 en la cadena

**Objetivo:** ZoneSnapshot; invalidación H1 cancela setups que legacy pasaría.

**DoD específico:**

- [ ] C04 implemented/partial medible  
- [ ] Test de invalidación H1  
- [ ] Eventos POI/zone en log  
- [ ] Plantilla DoD  

---

### Fase 3 — POI anclado (bonus por defecto)

**Objetivo:** POI con ancla narrativa + P/D; no gate duro ciego.

**DoD específico:**

- [ ] C05 (y camino a C06) actualizados en registry  
- [ ] Tests anti-regresión del error A'' (filtro duro ciego documentado como prohibido)  
- [ ] quality_score visible en TradingPlan + Explanation  
- [ ] Documentación tesis 21 alineada  
- [ ] Plantilla DoD  

---

### Fase 4 — Premium/Discount + dealing range

**DoD específico:**

- [ ] C03 implemented  
- [ ] Tests wrong-side (long en premium indebido según regla de modelo)  
- [ ] Eventos DealingRange / P-D en log  
- [ ] Plantilla DoD  

---

### Fase 5 — Multi-TF de ejecución (M15/M5/M1 según modelo)

**DoD específico:**

- [ ] C09–C11 (y C12/C13 si model lo requiere)  
- [ ] Entry/SL/TP solo en exec TF (tests)  
- [ ] TP cercana vs cluster: comportamiento documentado y testeado  
- [ ] Plantilla DoD  

---

### Fase 6 — Narrativa + trade management

**DoD específico:**

- [ ] C14–C15  
- [ ] Invalidación por evento sin reloj disfrazado como única fuente (o deuda explícita)  
- [ ] BE/parciales como updates de plan/order; sim solo aplica niveles  
- [ ] Plantilla DoD  

---

### Fase 7 — Re-medición científica

**DoD específico:**

- [ ] Ablation de **cobertura** (legacy vs +D1 vs +H1 vs +POI vs full)  
- [ ] METRICS_CANON actualizado **solo** con modos etiquetados + Coverage Report adjunto  
- [ ] Ningún claim de “tesis completa” si report &lt; umbral  
- [ ] Plantilla DoD  

---

## 12. Anti-patrones

| Anti-patrón | Por qué |
|-------------|---------|
| ICT dentro de `simulate_trade` | Rompe separación |
| Optuna sobre legacy vendido como tesis full | Fraude de cobertura |
| POI filtro duro ciego | Empíricamente invalidado |
| % de cobertura inventado en chat | Debe salir del Coverage Report |
| Order sin TradingPlan/Explanation en v2 full | Pierde observabilidad |
| Eventos no logueados | No hay auditoría reproducible |
| Un solo PR monstruo F1–F6 | No se mide delta |

---

## 13. Relación con R6 / R7 / R10.C / tesis

| Iniciativa | Rol |
|------------|-----|
| R6 | Cimientos del **Simulator** |
| R7 | Strategy v2 = candidata a única evaluación ICT |
| R9 MarketObject | Payload de eventos / zonas / POI |
| R10.C | Candidato a invalidación narrativa (F3–F6) |
| Tesis 18/20/21 | Requisitos de Strategy |
| Libro 13 | Veracidad del Simulator + OOS |

---

## 14. Criterio para hablar de edge de la estrategia objetivo

1. Strategy / TradingPlan / Simulator separados por contrato.  
2. Coverage Report automático en cada corrida de referencia.  
3. Capacidades required del model en estado aceptable (umbrales F0).  
4. EventLog + TradeExplanation para muestra de trades.  
5. Ablation de cobertura documentada en METRICS_CANON.

Hasta entonces el lenguaje es:

> **“Resultados de implementación con cobertura parcial (ver Coverage Report)”**,  
> no **“la estrategia ICT no funciona”**.

---

## 15. Ejecución de corridas (ops) — CPU, RAM, ventanas, multi-par

Esta sección es **parte de la arquitectura operativa** de Backtest v2.  
Detalle de herramienta: [`RUNNER_MONITOR.md`](RUNNER_MONITOR.md) · launcher: `scripts/runner_monitor.py`.

### 15.1 Host de referencia (operador)

| Recurso | Spec de trabajo (conservador) |
|---------|--------------------------------|
| CPU | Intel i9-13900H (u host similar multi-core) |
| RAM | 16 GB — no saturar: objetivo **≤ ~10–12 GB** de uso total del sistema durante corridas |
| Workers | **~70–80%** de hilos lógicos (`HERMES_WORKERS`, default ~75% en runner_monitor) |
| Prioridad Windows | **Above Normal** (nunca High / Realtime) |
| Headroom | Dejar ~20% CPU libre para Windows, VS Code, agente |

Si RAM del sistema **≥ 80%**: bajar paralelismo (menos pares concurrentes y/o menos workers), no empujar al 100%.

### 15.2 Cómo se lanza un backtest (agente y humano)

**Regla:** toda corrida de backtest / ablation / WF / multi-TF que pueda superar **60 s**:

```bat
python scripts\runner_monitor.py --window --title "bt-EURUSD-v2" -- <comando_backtest>
```

| Obligatorio | Prohibido |
|-------------|-----------|
| **`--window`**: consola **nueva y visible** para que el operador vea progreso | Background oculto / detached sin ventana |
| Una espera bloqueante al proceso (exit del SO) | Spam en chat: “sigo esperando…”, “vivo (73s)…” |
| Silencio en el chat del agente hasta el exit | Polling cada N segundos al usuario |
| Al terminar: leer exit + `results/runner_monitor_last.json` + outputs | % de progreso inventados |

**Alternativa explícita al operador:** el agente puede **indicar el comando** para que el usuario lo ejecute en una ventana aparte; no debe fingir “corrida en background invisible” sin que nadie vea el monitor.

Jobs **&lt; 60 s**: terminal principal OK.

### 15.3 Varios pares al mismo tiempo (paralelismo multi-symbol)

**Sí se puede y se recomienda** para ahorrar tiempo de pared (wall-clock), con límites de RAM.

```text
Objetivo: N símbolos terminan en ~max(t_i) en lugar de sum(t_i)

Ejemplo 4 pares ~15 min c/u:
  secuencial  ≈ 60 min
  paralelo 2  ≈ 30 min
  paralelo 3–4≈ 15–20 min  (si RAM aguanta)
```

#### Política v2 (diseño)

| Parámetro | Valor guía (16 GB) |
|-----------|---------------------|
| **Máx. símbolos concurrentes** | **2 por defecto**; **3** solo si RAM estable &lt; 80%; **4** solo smoke/corto |
| **1 ventana monitor por símbolo** | `--window --title "bt-EURUSD"` … `"bt-XAUUSD"` |
| **Workers por proceso** | repartir el presupuesto global: p.ej. total ~75% CPUs **entre** los jobs (no 75% × N) |
| **Afinidad** | opcional en impl; no es requisito de F0 |
| **Agregación** | al final, un **Coverage Report + métricas por símbolo** y un resumen combinado etiquetado |

```text
Lanzamiento conceptual (paralelo acotado):

  for symbol in batch (size <= max_concurrent):
      start runner_monitor --window --title "bt-{symbol}" -- backtest --symbol {symbol}
  wait all in batch
  next batch if more symbols
```

#### Restricciones

1. **No** lanzar 8 símbolos × full multi-TF a la vez en 16 GB (OOM / thrashing).  
2. Cada par es un **proceso aislado** (mismo código, distinto `symbol` / output dir).  
3. El “mismo tiempo” es **aproximado**: el par más lento manda el reloj del batch.  
4. Si un par OOM: bajar `max_concurrent` a 1 y reintentar ese par solo.  
5. Resultados por símbolo en rutas separadas (`results/bt_v2/{symbol}/…`) para no pisarse.

#### Qué gana el proyecto

- Ablation multi-símbolo más rápida.  
- Comparación EURUSD vs XAUUSD “en la misma tarde”.  
- El operador **ve** N monitores (uno por par), no un chat con polls.

### 15.4 Relación con fases de implementación

| Fase | Ops |
|------|-----|
| F0 | Documentar + usar runner_monitor en cualquier smoke largo |
| F1+ | Toda medición oficial multi-símbolo sigue §15 |
| F7 | Ablation de cobertura multi-par con batches concurrentes acotados |

---

## 16. Resumen ejecutivo

| Tema | Decisión de arquitectura |
|------|---------------------------|
| Objetivo del BT | Reproducir el **proceso de decisión** del trader ICT, no solo H4→M15 |
| Pipeline | Strategy → **TradingPlan** → Orders → Simulator |
| Cobertura | Matrix C0x + **Coverage Report automático** (sin % narrativos) |
| Observabilidad | EventLog canónico + TradeExplanation por trade |
| Roadmap | F0–F7 con **DoD plantilla + DoD por fase** |
| **Ejecución** | **runner_monitor --window**, CPU ~70–80%, RAM headroom 16 GB |
| **Multi-par** | **Sí, en paralelo acotado** (default 2 concurrentes) para ahorrar wall-time |
| Aprobación | **Architecture Approved** — implementación flexible bajo principios |

---

*Backtest v2 Architecture Specification **v1.1 (Architecture Approved + ops)** — 2026-07-16.  
Congela arquitectura; no congela implementación.  
v1.1: política de ejecución (CPU/RAM), ventanas visibles, multi-symbol paralelo.*

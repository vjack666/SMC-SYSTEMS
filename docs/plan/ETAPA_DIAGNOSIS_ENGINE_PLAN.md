# FASE D — DIAGNOSIS ENGINE (Infraestructura de autoexplicación)

**Fecha:** 2026-07-18
**Origen:** Auditoría de producción de Fase C + giro de enfoque acordado con Ruben.
**Estado:** DISEÑO APROBADO (no implementado salvo Paso 1 cableo Fase C en backtests).

---

## 0. POR QUÉ EXISTE ESTA FASE

Fase C cerró la capa de *percepción* (autoridad de zonas HTF). Pero el sistema
todavía termina un backtest diciendo solo:

```
PF = 0.91
WR = 42%
```

Eso NO permite evolucionar. El objetivo de la Fase D NO es mejorar el Profit
Factor automáticamente. El objetivo es que **el sistema pueda explicarse a sí
mismo cuando el rendimiento no alcanza el objetivo**.

Convertir cada backtest en una *fuente de conocimiento* sobre el comportamiento
del sistema, no solo en una cifra de rendimiento.

---

## 1. PRINCIPIO RECTOR (de hierro)

> El DiagnosisEngine NUNCA dice "agregá este filtro".
> Dice: "existe evidencia de que el filtro X podría explicar parte de la
> degradación".

Diferencia crítica:
- NO recomienda cambiar parámetros.
- NO es un optimizador (Optuna ya existe en Fase R6/optimize.py).
- SI genera **hipótesis** rankeadas por confianza, con evidencia.

Esto evita el sobreajuste: si no hay evidencia dominante, el reporte dice
"no hay evidencia suficiente para modificar un filtro" (ver ejemplo §7).

---

## 2. CADENA DE PROCESAMIENTO (el "médico" del sistema)

```
BACKTEST (sequence / v2 / optimize)
        │  produce lista de TradeResult + meta
        ▼
TradeContext          ← CONGELADO una sola vez (Fase D, Paso 2)
        │  {trade_id, signal_id, context_version,
        │   htf_bias, zone_authority, structure_quality,
        │   phase_log, exit_diag}
        │  INMUTABLE: nunca se modifica ni recalcula tras conocer el resultado
        ▼
Statistics Engine     ← métricas agregadas + cohortes
        │
        ▼
Correlation Engine    ← ¿qué variables se asocian a pérdidas/ganancias?
        │   fuerza/dirección, colinealidad, tamaño de muestra
        ▼
Hypothesis Generator ← SOLO AQUÍ se proponen hipótesis,
        │   apoyadas en las correlaciones previas
        │   (p.ej. "73% de pérdidas sin autoridad HTF")
        ▼
Evidence Ranking     ← confianza de cada hipótesis (boot/freq)
        │
        ▼
Final Report         ← texto para humano Y para el agente (chat_context)
```

### Contrato de inmutabilidad (anti look-ahead / sesgo de retrospectiva)
`TradeContext` es un **frozen dataclass**. Se construye UNA SOLA VEZ a partir
de `Signal` + `Trade` + `meta` en el momento de la simulación. Después:
- NUNCA se modifica.
- NUNCA se recalcula.
- NUNCA se "arregla" tras conocer el PnL.

Así el Diagnosis Engine solo LEe contexto histórico; no puede contaminarse
con el resultado (el mismo peligro que el look-ahead cross-timeframe de R4).

### Identificadores persistentes
Cada `TradeContext` lleva:
- `trade_id`: UUID del trade (estable a lo largo del reporte).
- `signal_id`: referencia a la señal que lo originó (trazabilidad a R7).
- `context_version`: versión del esquema TradeContext (para reconstruir
  exactamente qué contexto tuvo un trade años después, aunque la estrategia
  evolucione).

### Contrato del reporte (6 preguntas + "no lo sé")
El `Final Report` debe responder explícitamente:
1. **¿Qué ocurrió?** → PF, WR, DD, Expectancy.
2. **¿Dónde ocurrió?** → símbolos, sesiones, ventanas temporales, TF.
3. **¿Por qué ocurrió?** → hipótesis respaldadas por evidencia.
4. **¿Qué evidencia respalda eso?** → porcentajes, correlaciones, cohortes,
   distribuciones.
5. **¿Qué tan confiable es?** → nivel de confianza, tamaño de muestra,
   consistencia estadística.
6. **¿Qué NO puede concluir todavía?** → variables sin evidencia,
   muestra insuficiente, resultados ambiguos.

El punto 6 es OBLIGATORIO: un buen diagnóstico debe poder decir
**"no lo sé"** cuando la evidencia no alcanza. Evita conclusiones forzadas
y sobreajuste.

Cada etapa es un módulo puro en `ict_backtest/diagnostics/`. Ninguno toca
R7 (motor de decisión) ni altera PnL.

---

## 3. QUÉ INFORMACIÓN SE PIERDE HOY (auditado en los flujos reales)

`engine.simulate_trade` (engine.py:73) devuelve:
- `ICTTrade`: symbol, entry_time, exit_time, direction, entry, exit, pnl_r
- `meta`: exit_reason (SL/TP/hold_limit), mfe_r, mae_r, hold_bars

La **señal original** (sweep_at, bos_at, entry_at, ATR, y en producción
`zone_authority`) SE PIERDE al simular. Del trade solo queda pnl_r + exit_reason.

Por flujo (auditado 2026-07-18):
- `run_backtest.py` CLI: imprime _metrics + dict exits. No archiva JSON, no hay
  por-trade, no hay estructura, no hay autoridad.
- `optimize.py`: PF in/out-sample por fold + veredicto de robustez. Agrega por
  fold, no desglose por-trade del por qué cayó un fold.
- `plot_equity_curve.py`: curva + puntos verde/rojo. No el motivo.
- `v2/orchestrator`: YA esqueleto de diagnóstico (TradeExplanation, EventLog,
  explanations.jsonl, live_structure.csv, contracts.py con quality_score/zone/
  narrative/layers). PERO `explanation_mtf`/`legacy` se arman a MANO con
  strings fijos; `generate_*_signals` se llaman SIN `enable_pd_index` ⇒
  `zone_authority` va None ⇒ `zone` y `quality_score` quedan vacíos.

Conclusión: el andamiaje de diagnóstico YA EXISTE en v2, pero está
desconectado de la información real.

---

## 4. CONTRATO DE DATOS: TradeContext (por trade)

```python
@dataclass(frozen=True)  # INMUTABLE: 1 vez, nunca post-outcome
class TradeContext:
    # --- identificadores persistentes ---
    trade_id: str            # UUID estable en todo el reporte
    signal_id: str           # trazabilidad a la señal R7
    context_version: str     # p.ej. "ctx-1.0" (reconstrucción futura)
    # --- identidad ---
    symbol: str
    time: str
    direction: int
    # entry context
    htf_trend: str
    sweep_up: bool
    sweep_down: bool
    htf_bias: str
    # FASE C (metadata, nunca input de decisión)
    zone_authority: dict | None   # {has_htf_anchor, tier, stacking_level,
                                  #  confidence_weight, level}
    # structure quality (deuda R7/sequence, NO Fase C)
    displacement_gap: int
    bos_gap: int
    atr_z: float
    sl_is_structural: bool
    dist_entry_to_sl_r: float
    phase_log: tuple[str, ...]     # sweep -> displace -> BOS -> return (inmutable)
    # exit diagnostics
    exit_reason: str
    mfe_r: float
    mae_r: float
    hold_bars: int
    adverse_excursion_at_exit: float
    time_in_drawdown: float
    # regime (HOY NO EXISTE; si se agrega en otra fase, se consume)
    regime_tag: str | None
    htf_bias_at_exit: str | None
```

**Regla de hierro:** una vez construido, `TradeContext` es de solo lectura.
El Diagnosis Engine lo consume; no lo muta. (Ver §2 Contrato de
inmutabilidad — anti sesgo de retrospectiva, mismo peligro que el
look-ahead cross-timeframe de R4.)

---

## 5. ORDEN DE IMPLEMENTACIÓN (aprobado por Ruben 2026-07-18)

Respeta la arquitectura: primero existan los datos, luego se almacenen,
después se analicen, al final se presenten.

### Paso 1 — Fase C viaja a todos los backtests (RIESGO BAJO) ✅ EN CURSO
- `run_backtest.run_sequence_backtest`: agregar `enable_pd_index` y pasarlo a
  `generate_sequence_signals` (hoy lo omite).
- `run_backtest.main`: pasar `enable_pd_index=True` (o flag CLI `--pd-index`).
- `v2/orchestrator.run_sequence_parity` + `run_mtf_intraday`: pasar
  `enable_pd_index=True` a `generate_*_signals`.
- `optimize.py`: QUEDA FUERA del Paso 1 (usa `run_sequence` directo; costo de
  construir HtfPdIndex N trials veces; backtests de rendimiento suspendidos
  hasta Fase G por regla del roadmap). Pendiente documentado.
- Contrato: `zone_authority` es METADATA del trade, nunca input que altere PnL.
  R1 (conteo igual con/sin C) se preserva.

### Paso 2 — Conservar TradeContext (deuda R7/sequence, NO Fase C)
**DECISIÓN DE ARQUITECTURA (Ruben 2026-07-18):** `simulate_trade` NO construye
el TradeContext. `simulate_trade` SIMULA (su única responsabilidad). Un
`TradeContextBuilder` puro en `ict_backtest/diagnostics/` es quien CONGELA.

Concretamente:
- `engine.simulate_trade` queda IGUAL (no se toca → R1 de Paso 2: PnL idéntico).
- `engine.simulate_trade_with_context` EMITE `RawDiagnosticData` (trade + meta +
  row LTF + htf_context). NO conoce el esquema de diagnóstico.
- `diagnostics/context_builder.build_trade_context(raw) -> TradeContext`
  función PURA que CONGELA (frozen dataclass). Así `engine.py` queda limpio y
  Fase D crece (noticias, vol, sesión, régimen, liquidez, spreads...) SIN tocar
  la lógica de ejecución: solo se amplía el builder / RawDiagnosticData.
- Call site `run_backtest.run_sequence_backtest` acumula `RawDiagnosticData` en
  `m["contexts"]` + `m["backtest_id"]` (en memoria; el congelado lo hace Paso 3).

Campos: `backtest_id`+`trade_id`+`signal_id`+`context_version`+`context_created_at`,
zone_authority (Fase C como METADATA), phase_log, sl_is_structural, dist_entry_to_sl_r,
atr_z, exit diagnostics. Sin tocar decisión ni PnL.

**ESTADO: ✅ IMPLEMENTADO 2026-07-18** — `simulate_trade_with_context` +
`diagnostics/trade_context.py` (TradeContext @frozen) +
`diagnostics/context_builder.py` (build_trade_context puro). 5 tests verdes
(inmutabilidad, R1 PnL idéntico, ids, Fase C viaja como metadata, call site
`run_backtest` emite `contexts`+`backtest_id`).

### Paso 3 — NUEVA CAPA `ict_backtest/diagnostics/`
- `backtest_report.py`: `BacktestReport.build(contexts)` → consume `m["contexts"]`
  (RawDiagnosticData), congela cada uno vía `build_trade_context`, arma cohortes
  por autoridad/bias/tier + rolling PF (dónde se degradó) + `explain()` (texto).
- Hook en `run_backtest.py` / `v2`: al final, construir reporte y escribir
  `results/diagnostics/<symbol>_<engine>_<fecha>.json` + `.md`.
- Statistics Engine + Correlation Engine + Hypothesis Generator + Evidence Ranking
  (LOS MÓDULOS DEL DIAGNÓSTICO, no del backtest).

### Paso 4 — Alimentar v2 con datos reales
- `v2/orchestrator`: llenar `explanation.layers["PD"]` y `quality_score` con
  `zone_authority` real (hoy van vacíos/None). El andamiaje ya existe.

---

## 6. QUÉ PERTENECE A QUÉ

- **Fase C (hecha):** `zone_authority` existe y funciona. Paso 1 solo lo
  cablea en backtests (mismo patch que hice para el observador).
- **R7 / sequence (otra fase):** phase_log, sl_is_structural,
  dist_entry_to_sl_r, atr_z, htf_bias_entry/exit. Hoy no se serializan.
  Deuda del motor de simulación, no de Fase C.
- **Fase D / NUEVA CAPA (lo que se diseña acá):** `diagnostics/*`,
  hook de reporte. Consumidor de metadata, no productor. NO optimiza params.
- **FUERA DE ALCANCE:** `regime_tag` (no existe filtro de régimen hoy).
  Si se agrega en otra fase, el diagnóstico lo consumiría.

---

## 7. EJEMPLOS DE SALIDA (lo que el operador leería)

### Edge detectado (por qué GANÓ)
```
EDGE DETECTADO
Las operaciones ganadoras compartieron:
  ✔ Autoridad HTF Alta (94%)
  ✔ BOS fuerte
  ✔ Displacement > 1.3 ATR
  ✔ Entrada en descuento
  ✔ Stacking H4 + D1
Confianza: 91%
Conclusión: el edge se concentra en estructuras con fuerte alineación HTF.
```

### Diagnóstico de pérdida (hipótesis rankeada)
```
PF = 0.82
Diagnóstico:
  ✔ BOS correcto
  ✔ Sweep correcto
  ✔ Entrada correcta
Pero:
  73% de las operaciones perdedoras carecían de autoridad HTF.
Hipótesis principal: la estructura local funciona, pero el contexto
  superior no acompaña.
Confianza: 88%
```

### Sin causa dominante (anti-sobreajuste)
```
No existe una causa dominante.
Las pérdidas se distribuyen entre:
  29% baja autoridad
  31% sesiones lentas
  18% SL arbitrario
  22% baja volatilidad
No hay evidencia suficiente para modificar un filtro.
```

---

## 8. ESTADO Y GOVERNANZA

- Paso 1: ✅ DONE (Fase C cableada en backtests como METADATA, R1 OK).
- Paso 2: ✅ DONE 2026-07-18 (TradeContext emitido+congelado; R1 PnL idéntico;
  inmutable; ids persistentes; call site `run_backtest` emite `contexts`+
  `backtest_id`). Arquitectura: `simulate_trade` SIMULA →
  `simulate_trade_with_context` EMITE → `context_builder` CONGELA.
- Paso 3/4: pendientes, por TDD, UNA tarea a la vez.
- NO pushear sin OK expreso + cronograma al día en el mismo commit.
- Fase C sigue marcada ✅ Cerrado en CRONOGRAMA_Y_ROADMAP.md (línea ~108).
  Esta Fase D es NUEVA y se agrega como entrada aparte.

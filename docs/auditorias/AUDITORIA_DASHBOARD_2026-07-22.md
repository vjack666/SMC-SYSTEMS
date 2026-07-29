# AUDITORÍA DASHBOARD (monitoring) — 2026-07-22

Auditoría de código, SIN modificaciones. Objetivo: mapear `monitoring/`, su
alineación con el pipeline real de backtest, y detectar componentes muertos /
desacoplados / duplicados.

Método: lectura de `monitoring/*.py`, `legacy/monitoring/harness_adapter.py`,
`paper_trading/runner.py`, `ict_backtest/run_backtest.py`, `ict_backtest/engine.py`,
`ict_backtest/diagnostics/statistics_engine.py`, `ict_backtest/plot_equity_curve.py`,
y grep de `generate_dashboard` / `MonitoringHarnessAdapter` / `from monitoring` / `import monitoring`
en todo el repo.

---

## PARTE 1 — Estado actual

El "Dashboard" NO es una UI web ni un panel gráfico. Es una función
`generate_dashboard(equity, tracker=None, drift=None) -> dict` en
`monitoring/dashboard.py` que ensambla un diccionario JSON con: `timestamp`,
`alerts` (siempre `[]`), `drawdown`, `performance`, y opcionalmente `trades` y
`drift`.

Es parte del subsistema de **MONITOREO EN VIVO** (paper trading / live), NO del
pipeline de backtest. El backtest (`run_backtest.py`) no importa nada de
`monitoring`. Por lo tanto, el dashboard hoy solo se alimenta de un feed de
equity/trades EN VIVO, no de resultados de backtest.

Estado de implementación: funcional pero **desacoplado del backtest** y con
**componentes muertos** (alertas, PSI en dashboard).

---

## PARTE 2 — Arquitectura del Dashboard

### Módulos de `monitoring/`

| Archivo | Propósito | Responsabilidades | Inputs | Outputs | Dependencias | Quién lo usa | Quién debería usarlo |
|---|---|---|---|---|---|---|---|
| `dashboard.py` | Ensamblar dict de métricas de monitoreo | Unir equity + trades + drift en un reporte | `EquityTelemetry`, `PerformanceTracker?`, `DriftDetector?` | `dict` | drift_detector, equity_telemetry, performance_tracker | `legacy/monitoring/harness_adapter.py` | también `run_backtest` (hoy NO) |
| `config.py` | Config dataclass de monitoreo | Parámetros de drifts/alertas/persistencia | — | `MonitoringConfig` | — | todo `monitoring/` | todo `monitoring/` |
| `equity_telemetry.py` | Serie de equity + métricas de retorno | `record`, `get_series`, `compute_drawdown`, `compute_performance` (Sharpe/Sortino/Calmar/PF/WR) | equity, balance, timestamp (de un feed en vivo) | JSON en `data/monitoring/equity_telemetry.json` + dict de métricas | — | `harness_adapter`, `generate_dashboard` | — |
| `performance_tracker.py` | Acumular trades y curva de equity (en %) | `record_trade`, `get_metrics`, `get_equity_curve`, `_persist` | entry/exit/volume/direction/timestamp | JSON en `data/monitoring/performance.json` + métricas (Sharpe/Sortino/Calmar/PF/WR en %) | `config` | `harness_adapter`, `generate_dashboard` | — |
| `drift_detector.py` | PSI (Population Stability Index) | `check`, `is_drift`, `_psi` | features vs reference (dicts de listas) | dict de PSI por feature | — | `harness_adapter`, `paper_trading/runner.py`, `ml/trainer.py` | `generate_dashboard` (hoy vacío) |

### Adapter (legacy)

`legacy/monitoring/harness_adapter.py` — `MonitoringHarnessAdapter.run(events, parameters)`:
orquesta DriftDetector + EquityTelemetry + PerformanceTracker + `generate_dashboard`
a partir de `parameters` (equity_entries, trades, drift_features, drift_reference).
Es el único consumidor real de `generate_dashboard`. Registrado en
`legacy/harness/__main__.py` como adapter "monitoring".

### Consumidor en vivo

`paper_trading/runner.py` importa `DriftDetector` DIRECTO (l.90-92, 685-688) —
NO usa `generate_dashboard` ni `PerformanceTracker`. O sea el runner en vivo
usa solo drift, no el dashboard.

---

## PARTE 3 — Flujo de datos

### Flujo REAL hoy (en vivo, desacoplado del backtest)

```
feed en vivo (paper/live)
  → equity_entries / trades / drift_features  (parameters)
    → MonitoringHarnessAdapter.run
      → DriftDetector.check      → psi_values
      → EquityTelemetry.record   → data/monitoring/equity_telemetry.json
      → PerformanceTracker.record_trade → data/monitoring/performance.json
      → generate_dashboard(equity, tracker, drift)
        → dict {timestamp, alerts:[], drawdown, performance, trades?, drift:{"features":{}}}
```

### Flujo del BACKTEST (paralelo, que el dashboard IGNORA)

```
run_backtest.run(...)  (ict_backtest/run_backtest.py)
  → sequence → engine.simulate_trade → lista de ICTTrade (pnl_r en R)
  → _metrics(pnls)  → {trades, winrate, pf, expectancy, max_dd_r, total_r}  (en unidades R)
  → (diagnostics/statistics_engine.py: WR/PF/avg_r/expectancy_r por cohortes)
  → plot_equity_curve.py  → PNG de curva de equidad acumulada (R)
```

Cómo llegan los datos al dashboard: **NO llegan**. El backtest devuelve un dict
de métricas en R y un PNG; el dashboard de monitoreo vive en otro ecosistema
(equity/trades en % de un feed en vivo, persistidos en JSON separados).

Métricas calculadas (backtest): WR, PF, expectancy, max_dd_r, total_r en R;
curva de equidad en R. Métricas calculadas (dashboard): WR, PF, Sharpe, Sortino,
Calmar, total_return_pct, avg_win/avg_loss en %; drawdown en %; PSI por feature.

Métricas mostradas: el dashboard las EMITE en el dict (performance/drawdown/
trades/drift) pero NADIE las renderiza (no hay UI, no hay writer de reporte que
consuma `generate_dashboard` salvo el adapter legacy que las devuelve como dict
en memoria). `config.dashboard_report_dir` ("data/monitoring/reports") está
declarado pero **nunca se usa** para escribir nada.

Métricas que existen pero NUNCA se visualizan:
- `result["alerts"]` — siempre `[]` (no hay alerter).
- `result["drift"]` — cuando `drift is not None`, `generate_dashboard` crea
  `psi_summary = {"features": {}}` VACÍO. El PSI calculado por el adapter NUNCA
  se inyecta al dashboard (el adapter pasa el detector, no los `psi_values`).
  → el PSI existe en el adapter pero el dashboard lo descarta.
- `drawdown_duration` (equity_telemetry) — se calcula, se emite, no se usa.
- `get_equity_curve()` de PerformanceTracker — se persiste en JSON pero el
  dashboard no lo grafica.

Información que se pierde durante el flujo:
- El backtest pierde la conexión con el monitoreo: sus métricas en R no llegan
  al dashboard.
- En el adapter, `psi_values` (PSI real) se calcula y se devuelve en el dict de
  retorno del adapter, pero `generate_dashboard` lo ignora y pone `{"features":{}}`.
- `config.performance_metrics_file` / `equity_telemetry_file` se escriben en
  JSON pero el dashboard no los relee para armar reporte.

Lógica duplicada:
- Cálculo de Sharpe/Sortino/Calmar/PF/WR aparece en 3 lugares con fórmulas
  SIMILARES pero distintas unidades:
  1. `monitoring/equity_telemetry.py:compute_performance` (sobre retornos de equity, %).
  2. `monitoring/performance_tracker.py:get_metrics` (sobre retornos de trade, %).
  3. `ict_backtest/run_backtest.py:_metrics` + `diagnostics/statistics_engine.py`
     (sobre pnl_r, unidades R).
  → 3 implementaciones de las mismas métricas, sin shared util.

Componentes desacoplados:
- `generate_dashboard` ↔ backtest: 100% desacoplados.
- `paper_trading/runner.py` ↔ dashboard: usa solo DriftDetector, ignorando
  PerformanceTracker/EquityTelemetry/dashboard.
- `config.dashboard_report_dir` ↔ cualquier writer: desacoplado (nadie escribe ahí).
- `MonitoringConfig.alert_*` ↔ alerter: desacoplado (alerter inexistente).

Partes del dashboard que ya no se usan:
- `result["alerts"]` (siempre vacío).
- `MonitoringConfig` campos `alert_cooldown_sec`, `alert_persistence_file`,
  `alert_escalation_critical_count`, `alert_escalation_window_min`, `max_alert_history`
  (5 de 7 campos `alert_*`) — sin consumidor.
- `config.dashboard_report_dir` — sin escritor.
- `DriftDetector` dentro de `generate_dashboard` vía `drift` param — el PSI no
  se puebla (ver arriba).
- `legacy/harness/__main__.py` — adapter legacy (el harness viejo).

---

## PARTE 4 — Componentes sin utilizar

1. **`alerter` (referenciado en AUDIT_REPORT F15)** — NO EXISTE en el árbol.
   `monitoring/` solo tiene 5 archivos. Deuda documental: AUDIT_REPORT describe
   un alerter que fue removido o nunca se creó.
2. **`MonitoringConfig.alert_*` (5-7 campos)** — config muerta.
3. **`result["alerts"]` en `generate_dashboard`** — inicializado `[]`, nunca poblado.
4. **`config.dashboard_report_dir`** — directorio de reportes nunca usado.
5. **`generate_dashboard(drift=...)` → `result["drift"]["features"]`** — siempre `{}`.
6. **`get_equity_curve()` de PerformanceTracker** — se persiste, no se consume.
7. **`legacy/harness/`** — harness legacy que aún registra el adapter monitoring.

---

## PARTE 5 — Cambios mínimos recomendados (NO ejecutados en esta auditoría)

Prioridad: reutilizar código existente, NO reescribir.

1. **Conectar backtest → dashboard (unificar métricas).** En `run_backtest.run()`,
   tras `_metrics(pnls)`, construir un `EquityTelemetry`/`PerformanceTracker` a
   partir de los `ICTTrade` y llamar `generate_dashboard(...)`. Reusar
   `diagnostics/statistics_engine.py` como fuente de WR/PF/avg_r (en R) para no
   duplicar la fórmula de nuevo. Así el dashboard deja de ser ciego al backtest.
2. **Poblar `drift` en `generate_dashboard`.** El adapter ya calcula `psi_values`;
   pasarlos al dashboard en lugar de pasar el detector vacío. Una línea:
   `generate_dashboard(equity=telemetry, tracker=tracker, drift=psi_values)`.
3. **Marcar `alert_*` como deprecado o implementar alerter mínimo.** Si no se
   implementa alerter, borrar los 5 campos `alert_*` de `MonitoringConfig` para
   no dejar config muerta (o documentarlos como "futuro").
4. **Escribir el reporte.** Si se quiere `dashboard_report_dir`, un writer
   mínimo que haga `json.dump(dashboard, ...)` en ese dir (reusa el dict ya
   armado, cero lógica nueva).
5. **Unificar las 3 implementaciones de métricas.** Extraer un
   `monitoring/metrics_util.py` con `sharpe/sortino/calmar/pf` y que
   `equity_telemetry`, `performance_tracker` y `run_backtest._metrics` lo
   importen. (Refactor, no rewrite; respetar unidades R vs %.)

Ninguno de estos cambios se realizó en la auditoría. Solo documentación.

---

## PARTE 6 — Evaluación de calidad

- **Cobertura funcional**: MEDIA. Cubre monitoreo en vivo (equity/trades/drift)
  pero CERO cobertura de backtest. El PSI y las alertas están declarados pero
  no funcionales de punta a punta.
- **Mantenibilidad**: MEDIA-ALTA. Módulos pequeños, responsabilidad única, fáciles
  de leer. Pero la duplicación de métricas (3 lugares) y la config muerta
  (`alert_*`) añaden ruido.
- **Reutilización**: ALTA en diseño (dataclasses limpias, `generate_dashboard`
  es composable) pero BAJA en la práctica: el backtest no lo reusa, el
  `paper_trading/runner.py` solo usa 1 de 5 módulos.
- **Consistencia con la arquitectura**: BAJA. El dashboard vive en un ecosistema
  paralelo al backtest (otro cálculo de métricas, otros archivos de persistencia,
  otra unidad % vs R). Rompe el principio de única fuente de verdad de métricas.
- **Rendimiento**: ALTA. Cálculos O(n) sobre series en memoria, sin I/O pesado
  (los JSON son pequeños). No es un cuello.
- **Facilidad para agregar nuevas métricas**: ALTA. `generate_dashboard` es un
  dict abierto; agregar una clave es trivial. El problema es que las métricas
  base (Sharpe/etc.) están triplicadas, así que "agregar una métrica nueva"
  implica tocar 3 lugares si se quiere coherencia.

Calificación global: **B-** (funcional y limpio, pero desacoplado del backtest
y con deuda de config muerta + duplicación de métricas).

---

## PARTE 7 — Recomendación del siguiente paso

**No reescribir el dashboard.** Recomiendo UN (1) cambio de alto valor /
bajo riesgo: **conectar `run_backtest` → `generate_dashboard` reusando
`diagnostics/statistics_engine.py`** (cambio #1 de PARTE 5). Eso:

- Cierra la brecha de desacoplamiento (el dashboard deja de ser ciego al backtest).
- Reutiliza código existente (no se inventa nada).
- Unifica la fuente de métricas (WR/PF en R ya calculadas por `statistics_engine`).
- Tiene regresión cero si se hace detrás de un knob (p. ej. `--dashboard` en CLI).

Alternativa (solo si priorizás limpieza): cambio #5 (unificar las 3 fórmulas de
métricas en `monitoring/metrics_util.py`) para matar la duplicación. Es refactor
puro, sin nueva funcionalidad.

NO recomiendo tocar `DriftDetector` ni el harness legacy ahora: funcionan en vivo
y no son el cuello.

Próximo paso sugerido tras este cableado: medir si el dashboard de backtest
revela métricas que el PNG de `plot_equity_curve.py` oculta (p. ej. drawdown
duration, Calmar), para justificar el esfuerzo de unificar.

---

_No se modificó código. Solo documentación (CRONOGRAMA_Y_ROADMAP.md fila
"Auditoría Dashboard"; corrección de deuda en AUDIT_REPORT.md F15)._

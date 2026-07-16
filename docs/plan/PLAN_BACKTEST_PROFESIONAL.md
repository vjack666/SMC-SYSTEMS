# Plan — Backtest profesional (protocolo de actualización)

**Fecha:** 2026-07-13  
**Estado:** Docs listos · Código pendiente (R6)  
**Libro:** [`docs/ict/13_BACKTEST_PROFESIONAL/`](../ict/13_BACKTEST_PROFESIONAL/00_INDICE.md)  
**Encaja en:** [ROADMAP_BIBLIOTECA_Y_APLICACION](ROADMAP_BIBLIOTECA_Y_APLICACION.md) como **R6**  
**No sustituye:** `CRONOGRAMA_Y_ROADMAP.md` (A6/A12)

---

## 1. Protocolo de actualización (el del proyecto)

Este plan **no inventa** un proceso nuevo. Sigue lo ya definido:

| Paso | Protocolo | Fuente |
|------|-----------|--------|
| 1 | Investigar en internet **antes** de codear | `docs/prompts/PROMPTS.md` §2.4 |
| 2 | Documentar en biblioteca `docs/ict/` (carpeta = libro) | PROMPTS §2.3 · ADR-021 |
| 3 | Contrato §0 medible | `_PLANTILLA_LIBRO.md` |
| 4 | Plan de aplicación libro → código | este archivo + ROADMAP R6 |
| 5 | Código + tests sintéticos | `tests/test_ict_backtest.py` (extender) |
| 6 | Re-medir corridas; **solo** actualizar números en `METRICS_CANON.md` | METRICS_CANON regla |
| 7 | Avance en `docs/avances/` | PROMPTS §4 |
| 8 | Commit Conventional Commits; push solo con OK de Ruben | PROMPTS §4 / AGENTS |

**Principios del roadmap de biblioteca (inalterables):**

1. Un número, un sitio → METRICS_CANON  
2. Un contrato, un detector/checklist  
3. Vivo = backtest (misma evaluación)  
4. Medir antes de optimizar  
5. Trader manda (no bot hasta A12)

---

## 2. Qué se hizo en esta actualización (docs)

| Entrega | Ruta |
|---------|------|
| Libro 13 (checklist profesional + gaps) | `docs/ict/13_BACKTEST_PROFESIONAL/` |
| Índice biblioteca ICT | `docs/ict/00_INDICE.md` |
| Plan R6 | este archivo + sección en ROADMAP |
| Índice maestro docs | `docs/00_INDICE_DOCS.md` |

**No se tocó código** en esta pasada (protocolo: documentar primero).

---

## 3. R6 — Aplicación a código (orden estricto)

### R6.0 — Congelar contrato (0.25 día) · docs only

- [x] Libro 13 con §0 global y gap G1–G12  
- [ ] Revisión operador (Ruben): ¿aceptamos `fill_mode=next_open` como default de producción?

**Done:** “approved” o feedback escrito en este archivo.

---

### R6.1 — HTF closed-only (G1) · crítico · 0.5–1 día

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R6.1.1 | `row_at_time` → `closed_row_at_time(df, t, duration)` | `ict_backtest/_util.py` |
| R6.1.2 | Mapa duration por TF (M15=15m, H1=1h, H4=4h, D1=1d) | `_util.py` o `data_feed.py` |
| R6.1.3 | Call sites sequence/engine/optimize/run/plot | `ict_backtest/*` |
| R6.1.4 | `merge_asof` D1/H4 con `close_time` o shift de barra | `trend_context.py`, `signals/pipeline.py` si aplica |
| R6.1.5 | Test sintético: LTF mid-H4 **no** ve OHLC futuro de esa H4 | `tests/test_ict_backtest.py` |

**Done:** pytest verde (tests/test_r6_closed_row_at_time.py); test de no look-ahead multi-TF en row_at_time y merge_asof. R6.1.4 (trend_context merge_asof cerrado) tambien cubierto. ✅ R6.1 COMPLETADA (2026-07-16).

---

### R6.2 — Fill next-open (G2) · alto · 0.5 día

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R6.2.1 | `fill_mode: "next_open" \| "signal_close"` en simulate / signal build | `engine.py`, runners |
| R6.2.2 | Default producción = `next_open`; theory_mode = `signal_close` | `run_backtest.py`, `optimize.py` |
| R6.2.3 | Test: entry_price == open[i+1] cuando next_open | tests |

**Done:** pytest verde (tests/test_r6_fill_next_open.py, 4 tests); fill_entry_price(next_open=open[i+1], signal_close=close[i]); default next_open en generate_sequence_signals + optimize. ✅ R6.2 COMPLETADA (2026-07-16).

---

### R6.3 — Costos ON por defecto en runners (G3) · alto · 0.25–0.5 día

| Tarea | Detalle | Archivos |
|-------|---------|----------|
| R6.3.1 | Tabla `COST_BY_SYMBOL` (spread/commission/slippage pips) | `ict_backtest/` o `config` |
| R6.3.2 | Runners pasan cost salvo `--no-cost` (theory) | `run_backtest.py`, `optimize.py` |
| R6.3.3 | Actualizar PROMPTS anti-patrón (ya existe: no PF sin costos) | verificación |

**Done:** COST_BY_SYMBOL (XAUUSD/EURUSD/GBPUSD) en ict_backtest/costs.py; resolve_cost(symbol, override, no_cost); runners pasan cost por defecto salvo --no-cost. FIX G3: commisa en precio (no /risk) + piso risk 1 pip evita R absurdos por SL mal ubicado (ver test_cost_does_not_inflate_pnl_with_small_risk). ✅ R6.3 COMPLETADA (2026-07-16).

---

### R6.4 — Re-medición post G1–G3 · 0.5–1 día

| Experimento | Qué |
|-------------|-----|
| M1 | Capa 2 EURUSD M15 params actuales **sin** cambios de estrategia |
| M2 | Igual con G1 only / G1+G2 / G1+G2+G3 (ablation de reloj) |
| M3 | Capa 3 WF 4 folds con costs (si tiempo) |

**Done:** M2 ablation ejecutada (scripts/r6_ablation.py, motor real recortado 8000 velas). Veredicto EURUSD M15 H4: G1 PF=-2.49 / G1+G2 PF=-2.52 / G1+G2+G3 PF=-4.89 (WR 38.9%, 18 trades). **GATE R6 NO PASA en EURUSD M15** (PF<1.10). M1/M3 pendientes (requieren R5: mas datos para N>=200/fold). Resultado en METRICS_CANON. 🔴 R6.4 M2 COMPLETADA (2026-07-16), M1/M3 BLOQUEADAS por datos.
**Gate:** no Optuna nuevo hasta M2 reportado.

---

### R6.5 — Validación stats en pipeline ICT (G6–G7) · medio · 0.5 día

| Tarea | Detalle |
|-------|---------|
| R6.5.1 | Al final de optimize: imprimir/guardar DSR o PBO si N lo permite |
| R6.5.2 | Veredicto automático: frágil si algún fold PF<1 o N_OOS < umbral |

**Done:** log JSON/CSV en `docs/ict/logs/` o `results/`.

---

### R6.6 — Opcional / después de R5 datos (G4, G9–G11)

- Gaps de sesión en `simulate_trade`  
- Histórico multi-año XAU (R5)  
- Métricas por régimen/sesión  
- Portafolio multi-símbolo + DD diario prop  

No bloquean el sello “reloj profesional” de R6.1–R6.4.

---

## 4. Criterio de “backtest profesional v1” (sello)

Se puede decir **v1 profesional (mínimo)** cuando:

- [x] G1 cerrado + test
- [x] G2 default next_open + test
- [x] G3 costs ON en runners de referencia
- [x] METRICS_CANON actualizado con corrida M2
- [ ] Libro 13 §06 refleja estados ✅

**No requiere** G4–G12 para el sello v1.

---

## 5. Orden de trabajo recomendado (una semana realista)

```text
Día 1  R6.0 review + R6.1 código/tests HTF
Día 2  R6.2 fill + R6.3 costs
Día 3  R6.4 re-medición M1–M2 + METRICS + avance
Día 4  R6.5 stats opcional + limpieza docs gap
```

---

## 6. Anti-patrones (prohibidos en R6)

- ❌ Optimizar params **antes** de G1–G3  
- ❌ Reportar PF nuevo solo en chat sin METRICS_CANON  
- ❌ “Arreglar” PF subiendo look-ahead o quitando costs  
- ❌ Duplicar `row_at_time` otra vez (usar `_util` único)  
- ❌ Commit + push sin revisión de Ruben  

---

## 7. Entregables por fase

| Fase | Docs | Código | Métricas |
|------|------|--------|----------|
| Ahora | Libro 13 + este plan | — | — |
| R6.1–3 | Actualizar §06 gap | fix + tests | — |
| R6.4 | Avances + §06 | — | METRICS_CANON |
| R6.5+ | logs | optimize report | opcional |

---

*Plan alineado a PROMPTS §2.4 (investigar → documentar → implementar) y a la filosofía de roadmap de biblioteca.*

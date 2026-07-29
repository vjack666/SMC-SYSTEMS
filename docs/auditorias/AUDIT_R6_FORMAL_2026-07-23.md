# Auditoría formal R6 — Backtest Profesional (sello v1 + estado completo)

**Fecha:** 2026-07-23  
**Enmienda datos:** 2026-07-24 (Falla 4 / G9 RESUELTAS a nivel de disco)  
**Severidad:** MIXTA (sello v1 COMPLETO; veredicto edge PENDIENTE de **A12 / WF**, no de "falta parquet")  
**Auditor:** Hermes Agent (agregador de evidencia existente)  
**Fuentes:** `METRICS_CANON.md`, `AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md`, código real, tests, `CRONOGRAMA_Y_ROADMAP.md`, `docs/DATA_STATUS.md`

> ### ENMIENDA 2026-07-24 — Falla 4 / G9 (XAUUSD M15)
>
> El texto original de esta auditoría afirmaba que **XAUUSD M15 no existía en disco** y que
> R5 bloqueaba A12. **Eso ya no es cierto.**
>
> - `data/raw/XAUUSD_M15.parquet` existe: ~109 270 filas, **2022-01-02 → 2026-07-17 (~4.54 años)**.
> - EURUSD M15 también ≥4.5 años. Inventario vivo: `docs/DATA_STATUS.md`.
> - **R5 (umbral datos) = CERRADO.** No reabrir por este documento histórico.
> - **A12** queda pendiente de **re-run**, no de descarga.
> - Nota: `scripts/run_bt_v2_mtf.py` puede seguir excluyendo XAUUSD por **hang del motor**, no por data.

---

## 1. Resumen ejecutivo

R6 se divide en dos capas:

| Capa | Alcance | Estado |
|------|---------|--------|
| **Sello v1 profesional** (G1+G2+G3) | HTF closed-only + fill next-open + costos ON | ✅ CERRADO |
| **Veredicto de edge** (G4-G12 + reproducción) | Stats, portfolio, WF A12 | 🔴 ABIERTO (data R5 ya OK 2026-07-24) |

El sello v1 está técnicamente completo: los 3 gates están implementados, testeados y son el default en todos los runners. El veredicto de edge sigue **abierto** (falta A12 WF multi-fold y, en su caso, versionar v2). La Falla 4 "datos XAUUSD M15" quedó **resuelta en disco** (enmienda 2026-07-24).

---

## 2. Sello v1 — Estado por gate

### G1: HTF closed-only ✅

**Implementación:** `ict_backtest/_util.py`
- `closed_row_at_time(df, t, duration)` — mandatory `duration` param (TypeError si se omite). Cutoff = `tt - Timedelta(duration)`, solo velas HTF **cerradas** antes del tiempo de la señal LTF.
- `closed_merge_asof(df_htf, df_ltf, duration)` — merge temporal que resta `duration` del join time antes de `merge_asof(direction='backward')`.
- `tf_duration(tf)` — mapeo TF string → pandas Timedelta.
- `infer_tf_duration(df)` — infiere duración desde los datos.

**Tests:** `tests/test_r6_closed_row_at_time.py` — 6 tests:
1. Mid-bar devuelve la vela HTF anterior (cerrada)
2. Exact-open devuelve la vela HTF anterior
3. `duration` es mandatory (TypeError si se omite)
4. After-close devuelve la vela HTF actual
5. `closed_merge_asof` mid-bar solo ve velas cerradas
6. `closed_merge_asof` after-close ve la vela actual

**Commit:** `9990390` (2026-07-16)

### G2: Fill next-open ✅

**Implementación:** `ict_backtest/engine.py:86`
- `fill_entry_price(frame, entry_at, fill_mode)` — dos modos: `next_open` (producción, `open[i+1]`) y `signal_close` (teoría). Default: `next_open`.
- Propagado a: `run_backtest.py:109`, `canonical.py:154`, `optimize.py:121`, `v2/orchestrator.py:105`.

**Tests:** `tests/test_r6_fill_next_open.py` — 4 tests:
1. `next_open` usa open de la siguiente vela
2. `signal_close` usa close de la vela señal
3. Modo inválido lanza ValueError
4. `simulate_trade` respeta entry pasada para ambos modos

### G3: Costos ON por default ✅

**Implementación:** `ict_backtest/costs.py`
- `COST_BY_SYMBOL` — tabla con XAUUSD/EURUSD/GBPUSD calibrados + DEFAULT.
- `resolve_cost(symbol, override, no_cost)` — resuelve costo; `no_cost=True` → None; `override` parsea "spread,comm,slip".
- `simulate_trade` acepta `cost: dict | None = None`. Costo en precio (spread/slippage) + commission. Risk floor en 0.3 pip (descarta trades dust).

**FIX crítico (G3):** La commission se restaba del R (dividida por risk), lo que inflaba PF falsamente cuando risk~0 (SL <1 pip del entry en hold_limit lejano → PF -70 falso). Fix: commission se resta del precio + risk floor 1 pip.

**Tests:** `tests/test_r6_costs_on.py` — 5 tests:
1. `resolve_cost` devuelve tabla real
2. `no_cost` es None
3. Override parsea correctamente
4. Costo empeora PnL vs no-cost
5. Tiny risk descarta trade (regression test del fix)

**Commit:** `a59c2fb` (2026-07-16)

---

## 3. Resultados del sello v1 (R6.4 ablation)

**Script:** `scripts/r6_ablation.py`
**Datos:** EURUSD M15, HTF H4, 8000 velas (~3 meses). Params por defecto.

### 3.1 EURUSD (símbolo único)

| Modo | Fill | Costos | PF | WR | Trades |
|------|------|--------|---:|---:|-------:|
| G1 (teoría) | signal_close | OFF | **-2.49** | 38.9% | 18 |
| G1+G2 | next_open | OFF | **-2.52** | 38.9% | 18 |
| G1+G2+G3 (prod) | next_open | ON | **-4.89** | 38.9% | 18 |

### 3.2 Multi-símbolo

| Símbolo | G1 teoría | G1+G2 | PROD (G3 ON) | WR prod | N | Gate (PF≥1.10) |
|---------|----------:|------:|-------------:|--------:|--:|:--------------:|
| EURUSD | -2.49 | -2.52 | **-4.89** | 38.9% | 18 | FAIL |
| GBPUSD | -3.21 | -3.20 | **-7.07** | 40.0% | 30 | FAIL |
| USDCHF | +9.95 | +9.99 | **-0.13** | 48.0% | 25 | FAIL |
| USDCAD | +5.11 | +5.09 | **-8.64** | 36.8% | 38 | FAIL |

**Insight clave:** USDCHF y USDCAD dan PF+ en teoría (sin costos) — el motor detecta estructura direccional real, pero el edge es **más fino que el costo de transacción**. No es "sin edge", es "edge < costo".

### 3.3 Re-baseline post-v2.8 (2026-07-23)

EURUSD H4→M15, sequence, counter-trend, fixed2r, costs ON:
- **278 señales / 258 trades / 52.3% WR / PF 1.155** (+20.0 R)
- Salidas: SL:181, hold_limit:44, TP:33
- **PF 1.155 > 1.0** — primera vez que el motor canónico pasa PF>1 con costos ON

---

## 4. Motor v2 mtf (D1→H4→H1→M15)

**Script:** `ict_backtest/v2/run_v2.py --mode mtf`
**Datos:** 7 majors, costos ON, OOS 0.3. Ventana ~6 meses (2026-01→2026-07). XAUUSD excluido (sin M15).

| Símbolo | orders | trades | WR | PF | R | OOS_PF | coverage |
|---------|-------:|-------:|---:|---:|---:|-------:|----------|
| EURUSD | 0 | 0 | 0% | 0.000 | 0.0 | — | 86.1% |
| GBPUSD | 1 | 1 | 0% | 0.000 | -1.0 | 0.000 | 86.1% |
| USDJPY | 1 | 1 | 100% | inf* | +1.0 | inf* | 86.1% |
| AUDUSD | 4 | 4 | 0% | 0.000 | -4.4 | 0.000 | 86.1% |
| NZDUSD | 2 | 2 | 0% | 0.000 | -2.2 | 0.000 | 86.1% |
| USDCAD | 4 | 4 | 25% | 0.510 | -1.5 | 0.000 | 86.1% |
| USDCHF | 3 | 3 | 33% | 0.295 | -1.5 | inf* | 86.1% |

`* inf` = N=1, no es edge real. Coverage `v2_partial` = 86.1% (C06 POI missing).

**Veredicto v2 mtf:** 🔴 GATE NO PASA en ningún símbolo. Sample 0-4 trades insuficiente.

---

## 5. Fallas de auditoría (AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17)

### Falla 1 — `ict_backtest/v2/` no versionado (CRÍTICA)

**Evidencia:**
- `git log --all -- ict_backtest/v2/` → vacío
- `git ls-files ict_backtest/v2/` → vacío
- En disco: 13 archivos (`orchestrator.py`, `run_v2.py`, `context_mtf.py`, `coverage.py`, etc.)
- `scripts/run_bt_v2_mtf.py` (commit eb691c5) importa de un módulo que no existe en el repo

**Consecuencia:** los números del reporte v2 mtf son irreproducibles desde un clon limpio. El launcher está versionado; el motor que importa, NO.

**Estado:** PENDIENTE autorización de Ruben para commitear.

### Falla 2 — `edge_diagnosis` cap invalida ablación en XAUUSD (CRÍTICA)

**Evidencia:**
- `MAX_SIGNALS_PER_VARIANT = 3000` por confianza descendente
- Para XAUUSD, 13/21 variantes devuelven **exactamente** PF 1.379 / WR 60.1% / Sharpe 2.11 / N=900
- Relajar un filtro solo agrega candidatos de menor confianza que quedan fuera del cap

**Consecuencia:** la ablación es un no-op para XAUUSD (el símbolo que sostiene "candidate edge").

**Estado:** PENDIENTE rediseño del cap (cortar por fecha/ventana, no por confianza).

### Falla 3 — Sin corrección por comparaciones múltiples (ALTA)

**Evidencia:**
- 21 variantes × 8 símbolos = 168 celdas; mejor elegida post-hoc
- `ml/stats_validator.py` tiene DSR/PBO pero NO se aplica a la grilla

**Consecuencia:** "candidate edge" = selección óptima post-hoc sin descontar el look.

**Estado:** PENDIENTE aplicación de DSR/PBO a la grilla 168.

### Falla 4 — "Candidate edge" vive solo en XAUUSD (ALTA)

**Evidencia:**
- XAUUSD PF 1.376 (sostiene el promedio)
- AUDUSD 0.849, NZDUSD 0.809 (pierden)
- XAUUSD está EXCLUIDO del backtest MTF (sin M15 local)

**Consecuencia:** un dato faltante invalida la validación del único símbolo ganador.

**Estado:** BLOQUEADO en R5 (MT5 FundedNext logueado para descargar XAUUSD M15 ≥3-4 años).

---

## 6. Bugs encontrados durante R6

| Bug | Severidad | Estado | Fix |
|-----|-----------|--------|-----|
| Look-ahead residual en `row_at_time` (exact boundary) | CRÍTICA | ✅ FIXED | Ambas ramas (exact + asof) usan `cutoff = tt - Timedelta(duration)` |
| Commission inflation en `simulate_trade` (risk~0) | ALTA | ✅ FIXED | Commission en precio + risk floor 0.3 pip |
| `--model po3` es flag muerto (no-op) | MEDIA | ⚠️ CONFIRMADO (sin fix) | `args.model` nunca se pasa al motor; produce output idéntico a `--model intradia --counter-trend` |
| `--counter-trend` posiblemente muerto en semantic motor | MEDIA | ⚠️ CONFIRMADO (sin fix) | `event_engine.py:253` hardcodea behavior |
| `ict_backtest/v2/` no versionado | CRÍTICA | ⚠️ SIN FIX | Pende autorización |
| Edge diagnosis cap invalida ablación | CRÍTICA | ⚠️ SIN FIX | Pende rediseño |
| `costs.py` solo calibra 3 símbolos | MEDIA | ⚠️ SIN FIX | 5/8 usan DEFAULT genérico |

---

## 7. Tests R6 — Inventario completo

| Test file | Gate | Tests | Estado |
|-----------|------|-------|--------|
| `test_r6_closed_row_at_time.py` | G1 | 6 | ✅ ALL PASS |
| `test_r6_fill_next_open.py` | G2 | 4 | ✅ ALL PASS |
| `test_r6_costs_on.py` | G3 (+ fix) | 5 | ✅ ALL PASS |
| **Total R6** | | **15** | **✅ 15/15** |

---

## 8. Veredicto

### Sello v1 profesional (G1+G2+G3): ✅ CERRADO

Los 3 gates están implementados, testeados (15/15), y son default en todos los runners. La comisión-inflation fue encontrada y corregida durante R6. El sello v1 cumple su contrato: el backtest ahora usa reloj correcto, fill real, y costos reales por defecto.

### Veredicto de edge: 🔴 PENDIENTE (no se puede declarar)

**No es posible declarar "edge" ni "sin edge"** por las siguientes razones:

1. **Re-baseline EURUSD post-v2.8** (PF 1.155, 258 trades, costs ON) es la primera señal positiva, pero:
   - Es un solo símbolo, un solo TF (M15), una sola ventana
   - Falta walk-forward OOS multi-fold
   - Falta N≥200/fold para DSR/PBO

2. **v2 mtf es irreproducible** (Falla 1 — motor no versionado)

3. **Edge diagnosis tiene ablación rota** para XAUUSD (Falla 2) y sin corrección múltiple (Falla 3)

4. ~~**XAUUSD M15 no existe en disco**~~ ✅ **RESUELTO 2026-07-24** (Falla 4 / G9 — ver enmienda arriba)

5. **Flags `--model po3` y `--counter-trend`:** estado evoluciona post-auditoría (PO3 wiring 2026-07-23/24); no usar este punto sin re-leer código actual

### Items abiertos (post-enmienda 2026-07-24)

| Item | Blocker | Acción necesaria |
|------|---------|------------------|
| G4 (session/weekend gaps) | Diseño | Decidir si se modelan gaps o se ignoran |
| G6 (DSR/PBO en Optuna ICT) | Wiring | Cablear `ml/stats_validator.py` → `ict_backtest/optimize.py` (parcialmente avanzado vía `grid_stats.py`) |
| G7 (gate auto N OOS) | Depends G6 | Automatizar veredicto |
| ~~G9 (XAUUSD M15 data)~~ | ~~R5~~ | ✅ Cerrado — parquet multi-año en disco |
| A12 walk-forward | Re-run | Ejecutar WF `no_session`×XAUUSD con data actual |
| v2 mtf reproducible | Autorización Ruben | Commitear `ict_backtest/v2/` |
| Edge diagnosis cap | Rediseño | Cortar por fecha, no por confianza (avance 2026-07-24) |
| Calibrar costos 5 símbolos | Datos MT5 | Spread/commission real de los 5 restantes |
| `run_bt_v2_mtf` excluye XAUUSD | Hang motor | Deuda de runner/código, **no** de descarga |

---

## 9. Archivos R6 relevantes

| Archivo | Rol |
|---------|-----|
| `ict_backtest/_util.py` | G1: `closed_row_at_time`, `closed_merge_asof`, `tf_duration` |
| `ict_backtest/engine.py` | G2: `fill_entry_price`; G3: `simulate_trade` con cost param |
| `ict_backtest/costs.py` | G3: tabla de costos + `resolve_cost` |
| `ict_backtest/run_backtest.py` | Defaults de fill_mode y cost propagation |
| `ict_backtest/canonical.py` | Defaults de fill_mode en `evaluate_signals` |
| `ict_backtest/optimize.py` | Hardcoded next_open |
| `ict_backtest/v2/` | Motor mtf (NO versionado) |
| `scripts/r6_ablation.py` | Script de ablación R6.4 |
| `tests/test_r6_*.py` | 15 tests del sello v1 |
| `docs/METRICS_CANON.md` | §0: resultados R6.4 |
| `docs/auditorias/AUDIT_R6_V2_MTF_Y_EDGEDIAG_2026-07-17.md` | 4 fallas originales |

---

*Auditoría generada 2026-07-23. Formato alineado con `AUDIT_R4_FINAL_2026-07-13.md` y `AUDIT_LOOKAHEAD_HTF.md`.*

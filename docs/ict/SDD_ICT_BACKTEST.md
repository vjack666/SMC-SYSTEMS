# SDD — Software Design Document: `ict_backtest/`

**Proyecto:** SMC-SYSTEMS
**Módulo:** `ict_backtest/` (backtest ICT desde cero, sin ML)
**Versión:** 1.0
**Fecha:** 2026-07-11

---

## 1. Propósito del módulo

`ict_backtest/` es un motor de backtest ICT **event-driven, vela a vela**,
desacoplado del filtro ML del resto del repo. Su objetivo es medir la
robustez de un edge SMC puro (sweep → displacement → BOS → retorno) con
validación OUT-OF-SAMPLE rigurosa y SIN look-ahead.

---

## 2. Módulos y responsabilidades

| Archivo | Responsabilidad | Función clave |
|---------|----------------|---------------|
| `_util.py` | Helpers compartidos (único punto de verdad) | `row_at_time(df, t)` (asof, sin futuro) |
| `data_feed.py` | Carga de frames desde Parquet local | `load_frames(symbol, htf, ltf, d1)` |
| `market_structure.py` | Estructura MT: trend, BOS, CHOCH, liquidity | `detect_market_structure(df, config)` |
| `engine.py` | Señales + simulación vela a vela (con costos) | `build_signals_from_frames`, `simulate_trade(signal, cost)` |
| `sequence.py` | Motor event-driven de la secuencia ICT | `run_sequence(ms_htf, ms_ltf, config)` |
| `optimize.py` | Optuna TPE + walk-forward multi-fold | `main()`, `_split_windows()`, `_OptParams` |
| `run_backtest.py` | CLI Capa 2 (params fijos) | entrypoint `--engine sequence` |
| `plot_equity_curve.py` | Curva de equidad + DD en PNG | `main()` |
| `_diag_signals.py` | Diagnóstico de señales por tramo | helper de debug |
| `__init__.py` | API pública del paquete | exports de estructura/rules/engine |

---

## 3. `market_structure.py` — diseño

### 3.1 `_swing_points(frame, lookback)` [SIN look-ahead, ADR-05]
- Ventana NO centrada hacia atrás (`rolling(window, min_periods=window)`).
- El máximo debe ser estricto (no empatado en serie plana): se compara contra
  el `rolling_max` de la ventana anterior para descartar planos.
- El swing se expone recién en `i + lookback` vía `.shift(lookback).ffill()`.
- Esto ELIMINA el look-ahead del diseño previo (ventana centrada + ffill).

### 3.2 `detect_market_structure(df, config)` 
- Calcula `swing_high/low` (sin leak), `trend` (por tramos), `bos_dir`,
  `choch_dir`, niveles de invalidación, BSL/SSL.
- **CHOCH real (ADR implícito, hallazgo #2):** `_track_choch` usa la memoria
  de `_track_bos` (`_last_bos_dir`, `_last_bos_level`). Un CHOCH ocurre cuando
  el precio rompe el swing que produjo el ÚLTIMO BOS, en dirección opuesta.
  Ya NO es copia de `bos_dir`.

### 3.3 `StructureConfig` (dataclass)
Parámetros: `bos_lookback`, `choch_lookback`, `bos_max_age`, `choch_max_age`,
`trend_lookback`, `use_liquidity`, `liquidity_lookback`.

---

## 4. `engine.py` — diseño

### 4.1 `ICTSignal` / `ICTTrade`
Dataclasses. `ICTTrade` tiene 8 campos (symbol, entry_time, exit_time,
direction, entry, exit, pnl_r, meta). El `exit_reason` vive en `meta`, NO en
el trade (lección del bug de la curva de equidad).

### 4.2 `simulate_trade(frame, signal, max_hold_bars, cost=None)` [ADR costos]
- `cost={spread_pips, commission_pips, slippage_pips}` (pips).
- Entry con slippage adverso + spread/2 (peor caso para el trader).
- SL se evalúa ANTES que TP en la misma vela (conservador). Ya existía; se
  conserva y se suma el costo.
- Comisión restada en unidades de riesgo (R).
- `pip` inferido del precio (FX 4 dec → 0.0001; XAU → 0.01).

---

## 5. `sequence.py` — diseño (event-driven)

`run_sequence(ms_htf, ms_ltf, config)` recorre velas LTF y aplica la fase:
`sweep → displacement → BOS → retorno al cuadro`.
- `SequenceConfig` (dataclass): `displace_gap`, `bos_gap`,
  `require_displacement`, `tp_mode` (fixed2r / liquidity), `max_sweep_age`, etc.
- `_row_at_time` importado de `_util` (ADR-04, sin duplicar).
- Devuelve señales que luego pasan a `build_signals_from_frames`.

---

## 6. `optimize.py` — diseño (Capa 3)

### 6.1 `main()`
1. Carga frames (`load_frames`).
2. Aplica `detect_market_structure` a HTF Y LTF (bug crítico resuelto: sin
   esto → 0 señales).
3. `_split_windows(n, n_windows, min_train)` → walk-forward ROLLING.
4. Optuna TPE optimiza sobre el fold 0 (in-sample, pasado).
5. Evalúa los mejores params en TODOS los folds OOS (futuro) → PF/WR/trades
   promedio + desviación.

### 6.2 `_split_windows(n, n_windows, min_train)` [ADR-06]
- Cada fold: `train = [0, te_s)`, `test = [te_s, te_e)`.
- Los folds avanzan en el tiempo (test contiguo). Dirección CORRECTA
  (pasado→futuro), NO invertida.
- Reporte: `PF OOS MEDIO ± std`, veredicto de robustez por folds.

### 6.3 `_OptParams` (dataclass)
`displace_gap`, `bos_gap`, `require_displacement`, `tp_mode`.

---

## 7. Interfaz pública (API SPEC)
Ver `docs/ict/API_SPEC.md` para firmas exactas y ejemplos de uso.

---

## 8. Calidad y tests
- `tests/test_ict_backtest.py` (7 tests, <1s) cubre: look-ahead (R1),
  CHOCH real (R2), costos (R4), walk-forward (R5), SL-before-TP.
- Toda regla rota por auditoría tiene test que la fija.

---

## 9. Deuda técnica conocida
- **DT-01:** Loop vela-a-vela no vectorizado (~8 min / 50k velas). Medio plazo.
- **DT-02:** `ml/walk_forward.py` acoplado a ML; `ict_backtest/optimize.py` es
  la versión SMC-puro reutilizable.
- **DT-03:** `structure.py` (clasificación bull/bear/ranging) es PARTE 1
  separada de `market_structure.py`; mantener ambos sincronizados.

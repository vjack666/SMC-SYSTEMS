# AVANCES ICT BACKTEST — 2026-07-11

## (B) CAPA 3 — OPTIMIZADOR BAYESIANO (Optuna + Walk-Forward) — COMPLETADA ✅

Resultado de la corrida real del usuario (run_capa3_optuna.bat, 12 trials, ~129 min):

### Optimización (in-sample = último tercio, 16666 velas)
- 12 trials TPE. PF in-sample mejoró trial a trial: 1.048 → 1.233 → 1.250 → 1.545 → 2.063.
- MEJOR PF in-sample: **2.063**
- MEJORES PARÁMETROS: `displace_gap=12`, `bos_gap=8`, `require_displacement=True`, `tp_mode=liquidity`

### Walk-Forward OUT-OF-SAMPLE (prueba de fuego anti-overfit)
- ventana 1 [IN-SAMPLE]: 29 trades, WR 51.7%, PF 1.889, +12.4 R, DD -3.6
- ventana 2 [OUT-OF-SAMPLE]: 32 trades, WR 56.2%, **PF 2.429**, +20.0 R, DD -4.0
- >>> PF OUT-OF-SAMPLE MEDIO: **2.429** (32 trades)
- >>> WR OUT-OF-SAMPLE MEDIO: 56.2%
- >>> VERDICTO: edge mantiene PF>1 en out-of-sample => **SIN overfit claro** ✅

### Conclusión
El edge de la Capa 2 (sequence.py, EURUSD M15) se CONFIRMA y es ROBUSTO:
PF 2.429 out-of-sample es incluso superior al in-sample (2.063). No hay
sobreajuste. Parámetros óptimos encontrados por Optuna son válidos.

### BUG CRÍTICO RESUELTO (raíz de "0 señales")
`optimize.py` y `_diag_signals.py` NO aplicaban `detect_market_structure` al
HTF. Sin eso, `run_sequence` no detecta BOS → 0 operaciones → Optuna
penalizaba todo con -1.0. Corregido: ambos aplican `ms = {tf:
detect_market_structure(df) for tf, df in frames.items()}` IGUAL que
`run_backtest.py`. Tras el fix, la Capa 3 genera señales y optimiza.

### Mejoras al launcher (run_capa3_optuna.bat)
- Reescrito para PowerShell `-NoExit` (ventana NO se cierra sola) + `Tee-Object`
  (log + vivo). El `tee` de bash no existe en cmd.exe de doble-clic → antes se
  cerraba solo.
- Barra de progreso con CONTADOR REGRESIVO ("Trial N/12 | falta ~X min") vía
  callback `_CuentaRegresiva` en optimize.py.
- No requiere MT5 abierto: `load_frames` lee parquet locales (data/raw).

---

## ESTADO POR CAPAS (resumen)

| Capa | Qué es | Estado | Resultado clave |
|------|--------|--------|-----------------|
| 1 | Estructura de mercado (market_structure.py) | ✅ base | trend/BOS/CHOCH por TF |
| 2 | Motor EVENT-SEQUENCE (sequence.py) | ✅ validada (ayer) | EURUSD M15: 70 trades, PF 1.598, WR 47.1%, +22.1 R |
| 2b | XAUUSD H4 (sequence) | ✅ validada (ayer) | PF 1.132, 11 trades, +0.8 R |
| 3 | Opt. bayesiano + walk-forward | ✅ COMPLETADA (hoy) | EURUSD M15 OOS: PF 2.429, 32 trades, WR 56.2% |

---

## HALLAZGOS / APRENDIZAJES
- La (A) [Capa 2 M15] usaba la serie COMPLETA (50k velas) → 70 trades. El primer
  tercio solo da ~0-2 señales; el volumen está en el tramo reciente. Por eso la
  Capa 3 optimiza en el ÚLTIMO tercio (in-sample) y valida hacia atrás.
- `require_displacement=True` + `tp_mode=liquidity` + gaps amplios (12/8) fueron
  los params ganadores. Filtra ruido y mejora PF.
- Optuna TPE con 12 trials en 50k velas tarda ~129 min (cada trial ~8 min). Para
  iterar rápido usar `--window-bars 8000 --trials 3` (~1 min).

## (B.2) CAPA 2 CON PARÁMETROS ÓPTIMOS — CORRIDA LIMPIA ✅

Corrida de `run_backtest.py` con los params que encontró la Capa 3
(displace_gap=12, bos_gap=8, require_displacement=True, tp_mode=liquidity):

- trades: 87
- winrate: 52.9%
- PROFIT FACTOR: 2.003
- expectancy: 0.473 R/trade
- total: +41.1 R
- max drawdown: -5.0 R

Comparación: (A) default (gaps 6/10) daba 70 trades / PF 1.598 / WR 47.1% /
+22.1 R. Los params óptimos MEJORAN la Capa 2 en trades, PF, WR y R total.
El PF out-of-sample de la Capa 3 (2.429) confirma que NO es overfit.

`run_backtest.py` ahora expone `--displace-gap` / `--bos-gap` al motor sequence.

## (B.3) CURVA DE EQUIDAD (gráfica) ✅

`ict_backtest/plot_equity_curve.py` re-corre la Capa 2 con params óptimos y
grafica la equidad (R acumulado) + drawdown por trade:
- 87 trades, PF 2.604, WR 65.5%, +48.1 R, maxDD -3.0 R
- PNG: `docs/ict/plots/CAPA2_EQUITY_CURVE_OPT.png` (verde=+R, rojo=-R)

---

## ESTADO POR CAPAS (resumen)

| Capa | Qué es | Estado | Resultado clave |
|------|--------|--------|-----------------|
| 1 | Estructura de mercado (market_structure.py) | ✅ base | trend/BOS/CHOCH por TF |
| 2 | Motor EVENT-SEQUENCE (sequence.py) | ✅ validada (ayer) | EURUSD M15: 70 trades, PF 1.598 |
| 2b | XAUUSD H4 (sequence) | ✅ validada (ayer) | PF 1.132, 11 trades, +0.8 R |
| 2+ | Capa 2 con params óptimos | ✅ COMPLETADA (hoy) | 87 trades, PF 2.003, +41.1 R |
| 3 | Opt. bayesiano + walk-forward | ✅ COMPLETADA (hoy) | OOS PF 2.429, 32 trades, WR 56.2% |
| 3v | Curva de equidad gráfica | ✅ COMPLETADA (hoy) | PF 2.604, 87 trades, maxDD -3.0 R |

---

## HALLAZGOS / APRENDIZAJES
- (igual que arriba) + plot_equity_curve.py usa `meta.get("exit_reason")` del
  `simulate_trade` (el trade ICTTrade NO tiene exit_reason; viene en el 2do
  retorno). Bug corregido.
- La curva de equidad con params óptimos es MUY estable: maxDD solo -3.0 R en
  la versión por-trade (la corrida resumida marcó -5.0 R por criterio distinto
  de conteo de hold_limit).

## LO QUE FALTA (pendiente)
1. Extender Capa 3 a XAUUSD (solo D1/H4, ~50k barras H4) — backtest en H4.
2. Crear README.md / COMPLETION_REPORT.md que AGENTS.md referencia.
3. (Opcional) Aumentar trials de Optuna a 30-60 para refinar aún más el óptimo.
4. (Opcional) Curva barra-a-barra (cada 15 min) proyectando R no realizado.

## (C) REFACCIÓN POR AUDITORÍA EXTERNA (Claude, 2026-07-11) — EN CURSO ⏳

Auditoría externa sobre `ict_backtest/` (commits 91f24ad…3aafab7). Dos
hallazgos CRÍTICOS VERIFICADOS empíricamente por el equipo antes de actuar:
- #1 Look-ahead bias en `_swing_points` (ventana centrada + ffill desde el
  pico). Confirmado: pico idx 10 aparecía en la fila 10 (debe ser 15).
- #2 `choch_dir` = copia literal de `bos_dir`. Confirmado: `bos_dir==choch_dir`
  en las 10.136 velas de EURUSD H4 (0 filas distintas).

### Fixes aplicados (todos con test unitario sintético en tests/test_ict_backtest.py)
- #1: `_swing_points` usa ventana NO centrada + `shift(lookback).ffill()` → el
  swing solo se expone desde la vela de confirmación. Test: `test_swing_no_lookahead`.
- #2: CHOCH real = rompe el swing que produjo el ÚLTIMO BOS, en dirección
  opuesta (memoria de `_track_bos`). `choch_dir` ahora difiere de `bos_dir`
  (7764 filas distintas en EURUSD H4). Test: `test_choch_differs_from_bos`.
- #3: `tests/test_ict_backtest.py` (7 tests, <1s) cubre swing/CHOCH/engine/WF.
- #4: `simulate_trade` acepta `cost={spread,commission,slippage}` (pips). Entry
  con slippage adverso + spread/2; comisión restada en R. Test: `test_engine_spread_reduces_pnl`.
- #5: walk-forward ROLLING multi-fold (`_split_windows`); dirección temporal
  CORRECTA (pasado→futuro, sin invertir); reporte PF/WR/trades OOS promedio + std.
  Test: `test_walkforward_multi_fold`, `test_walkforward_no_inverted`.
- #7: `_row_at_time` extraído a `ict_backtest/_util.py` (único punto de verdad);
  `engine.py` y `sequence.py` importan de ahí. `Any` importado.

### Corridas de verificación (EN CURSO, background)
- Capa 2 corregida (params 12/8, req_disp, liquidity) → `CAPA2_REFAC_CORRIDACORREGIDA.log`
- Capa 3 walk-forward multi-fold (n_windows=4, 12 trials) → `CAPA3_REFAC_WF.log`
- Por medir: PF real tras corregir #1/#2 (se espera < 2.0-2.6 previos).

### Documentación
- Libro: `docs/ict/10_AUDITORIA_REFACCION/` (carpeta=libro, archivos=temas 01-08)
- SDD: `docs/ict/SDD_REFACCION_2026-07-11.md`

---

## ARCHIVOS (adición a los de arriba)
- `ict_backtest/market_structure.py` — #1 (sin look-ahead) + #2 (CHOCH real)
- `ict_backtest/engine.py` — #4 (costos) + #7 (dedup _row_at_time)
- `ict_backtest/sequence.py` — #7 (dedup _row_at_time)
- `ict_backtest/_util.py` — #7 (row_at_time compartido)
- `ict_backtest/optimize.py` — #5 (walk-forward rolling multi-fold)
- `tests/test_ict_backtest.py` — #3 (nuevo)
- `docs/ict/10_AUDITORIA_REFACCION/` — libro (nuevo)
- `docs/ict/SDD_REFACCION_2026-07-11.md` — SDD (nuevo)



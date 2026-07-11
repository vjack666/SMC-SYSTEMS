# SDD — REFACCIÓN ICT_BACKTEST (auditoría 2026-07-11)

**Estado:** aprobado para ejecución autónoma (autorizado por Ruben).
**Alcance:** corregir los 7 hallazgos de la auditoría externa (Claude) sobre
`ict_backtest/`, documentar en la biblioteca (`docs/ict/10_AUDITORIA_REFACCION/`)
y re-correr Capa 2 + Capa 3 para medir el PF real (sin inflar).

---

## 1. Contexto y veredicto de la auditoría

Auditoría externa sobre commits `91f24ad…3aafab7`. Dos hallazgos CRÍTICOS
verificados empíricamente por el equipo antes de actuar:

- **#1 Look-ahead bias** en `_swing_points` (ventana centrada + `ffill` desde
  el pico). Confirmado: pico en idx 10 aparece en la fila 10 (debe ser 15).
- **#2 CHOCH = copia de BOS**. Confirmado: `bos_dir == choch_dir` en las
  10.136 velas de EURUSD H4 (0 filas distintas).

Más: #3 (0 tests), #4 (sin costos), #5 (walk-forward de 1 split + dirección
invertida), #6 (perf), #7 (`Any` sin importar + `_row_at_time` duplicado).

**Veredicto aceptado:** no confiar en los PF 2.0-2.6 reportados hasta corregir
#1/#2 y re-correr. La magnitud de la caída se MIDE, no se asume.

---

## 2. Requisitos

| ID | Requisito | Aceptación |
|----|-----------|------------|
| R1 | `_swing_points` sin look-ahead | pico en idx 10/lookback 5 → `swing_high` no-nulo en idx 15 (test sintético) |
| R2 | CHOCH real distinto de BOS | tras BOS alcista, break bajista del swing opuesto → `choch_dir=-1`, `bos_dir` puede ser 0 (test) |
| R3 | Tests unitarios sintéticos | `tests/test_ict_backtest.py` con ≥5 casos, corren <2s |
| R4 | Costos en `simulate_trade` | `cost={spread,commission,slippage}` reduce pnl; SL antes que TP en empate |
| R5 | Walk-forward multi-fold | `--n-windows>=3` rolling, reporte PF/WR/trades PROMEDIO + dev; dirección temporal correcta (pasado→futuro) |
| R6 | `_row_at_time` único | mover a `_util.py`, importar en engine/sequence; `Any` importado |
| R7 | pytest verde | `pytest tests/test_ict_backtest.py` pasa; suite global sin regresiones nuevas |

---

## 3. Diseño de la solución (por hallazgo)

### R1 — Swing points sin look-ahead (`market_structure.py`)
Ventana NO centrada (`center=False`, `min_periods=window`), luego
`shift(lookback).ffill()`. El pico queda en su fila pero solo se expone
`lookback` velas después (vela de confirmación).

### R2 — CHOCH real (`market_structure.py`)
`_track_choch` usa memoria de estado: guarda `last_bos_dir` / `last_bos_level`.
CHOCH válido = break en dirección OPUESTA al último BOS, rompiendo
`last_bos_level` (la regla de dailypriceaction del docstring). Ya NO es
`up_choch = bear_break`.

### R4 — Costos (`engine.py`)
`simulate_trade(frame, signal, max_hold_bars, cost=None)`. Entry con slippage
adverso + spread/2; SL/TP ajustados por spread; comisión restada en R.
`cost` opcional (default 0) → comportamiento anterior se conserva para
corridas "teóricas".

### R5 — Walk-forward (`optimize.py`)
`_split_windows` genera N folds rolling (train creciente + test contiguo).
Optuna optimiza sobre el PRIMER train; cada fold valida hacia adelante.
Reporte: PF/WR/trades promedio OOS + desviación. Sin invertir tiempo.

### R6 — Util (`_util.py`)
`row_at_time(df, t)` con `from typing import Any`. `engine.py` y `sequence.py`
importan de ahí; se borra la copia duplicada.

---

## 4. Verificación

1. `pytest tests/test_ict_backtest.py -v` → todos verdes (R1,R2,R3,R4,R6,R7).
2. `python ict_backtest/run_backtest.py --symbol EURUSD --htf H4 --ltf M15 \
   --engine sequence --max-hold 96 --require-displacement --tp-mode liquidity \
   --displace-gap 12 --bos-gap 8` → PF corregido (se reporta, no se compara
   ciegamente con 2.003).
3. `python ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 12 \
   --n-windows 4` → walk-forward multi-fold, PF OOS promedio + dev.
4. Re-correr con `cost={"spread_pips":1.0,"commission_pips":0.5}` para ver
   impacto real del spread.

---

## 5. Riesgos

- R1 puede bajar señales (menos look-ahead → menos entradas "perfectas").
- R2 puede cambiar la cuenta de señales contra-tendencia sustancialmente.
- R5 con N=4 y 12 trials ≈ 4x el tiempo de una corrida (documentar ETA).
- La performance (#6) NO se toca en esta refacción (riesgo de romper
  event-driven); queda para fase siguiente.

## 6. Entregables

- `ict_backtest/market_structure.py` (R1,R2)
- `ict_backtest/engine.py` (R4)
- `ict_backtest/optimize.py` (R5)
- `ict_backtest/_util.py` (R6)
- `tests/test_ict_backtest.py` (R3)
- `docs/ict/10_AUDITORIA_REFACCION/` (libro)
- `docs/ict/SDD_REFACCION_2026-07-11.md` (este SDD)
- `docs/AVANCES_ICT_BACKTEST_2026-07-11.md` (actualizado con PF corregido)

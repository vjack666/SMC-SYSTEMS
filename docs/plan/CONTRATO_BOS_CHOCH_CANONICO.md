# CONTRATO CANÓNICO BOS / CHOCH

Documentado por exigencia de auditoría (ETAPA 4 PASO 1→2, 2026-07-17). Fuente única
de verdad tras la unificación: `ict_backtest/market_structure.py`. `detectors/bos.py`
y `detectors/choch.py` DELEGAN aquí (no reimplementan).

## BOS (Break of Structure)

### Entrada
- `pd.DataFrame` con columnas OHLC: `open`, `high`, `low`, `close`.
- `StructureConfig`:
  - `swing_lookback = 5` (ventana no centrada; swing expuesto desde i+lookback).
  - `atr_period = 14` (Wilder, usado en `_atr`).
  - `followthrough_bars = 8`.
  - `confirm_bars = 2` (exigencia de 2 cierres de CUERPO consecutivos rompiendo el
    nivel; filtra fakeouts / Turtle Soups).

### Salida (columnas)
- `swing_high`, `swing_low`, `swing_label` (HH/HL/LH/LL/NONE).
- `bos_dir` ∈ {1, -1, 0} (alcista/bajista/ninguno).
- `bos_level` (nivel roto; swing shift(1)).
- `bos_status` ∈ {active, invalidated, none}.
- `bos_age` (velas desde activación).

### Reglas
- Ruptura solo por CUERPO (close), nunca mecha (wick = liquidity sweep, no estructura).
- Confirmación: `confirm_bars` cierres consecutivos rompiendo el nivel.
- Invalidación por EVENTO: el cierre cruza de nuevo el nivel roto (por cuerpo) →
  `invalidated`. NO hay caducidad por tiempo/volatilidad (vive por evento).
- CHOCH (Change of Character): el BOS que rompe el swing que produjo el ÚLTIMO BOS,
  en dirección OPUESTA a ese BOS. No es copia de BOS. También requiere confirm_bars=2.
  Salida: `choch_dir`, `choch_status` (active/invalidated/none), `choch_age`.

## Consumidores (quién llama)
- `signals/pipeline.py` → vía `detectors.detect_bos`/`detect_choch` (mapean
  `bos_dir`→`bos_direction`, `choch_dir`→`choch_signal` string). Usado en confluencia
  (pipeline.py:170-174, 227-232, 301-302, 360). DISPATCH REAL, no muerto.
- `scripts/edge_diagnosis/run.py` → harness de diagnóstico de edge (vía pipeline).
- `ict_backtest/run_backtest.py` y `ict_backtest/v2/*` → motor canónico de backtest
  (H4→M15), usa `detect_market_structure` directo.
- `detectors/*` → ahora delegan (sin geometría propia).

## Invariantes que la suite protege
- `tests/test_bos_choch_regression.py::test_post_unification_equivalence` exige
  `detector.bos_direction == canonico.bos_dir` y `bos_status` idénticos, y
  `detector.choch_signal == forma string de canonico.choch_dir`.
- Cualquier nueva implementación de BOS/CHOCH que diverja ROMPE CI.

## Por qué importa para lo que viene
Al entrar XAUUSD (PASO 2), más símbolos, ML (PASO 4) y agentes (PASO 3 w0_agents),
este contrato es el punto de acoplamiento único: todos los consumidores ven la
misma estructura, sin importar el símbolo ni el TF.

# API SPEC — `ict_backtest/`

Documentación de la interfaz pública de `ict_backtest/`. Firmas reales
extraídas del código (2026-07-11). No es una API HTTP: es una biblioteca
Python importable.

---

## 1. Paquete (`ict_backtest/__init__.py`)

```python
from ict_backtest.structure import classify_structure, classify_multi_tf, momentum_direction
from ict_backtest.rules import evaluate, checklist_intradia, checklist_scalping, killzone_en
from ict_backtest.engine import ICTSignal, ICTTrade, build_signals_from_frames, simulate_trade
```

---

## 2. `market_structure.py`

### `detect_market_structure(df: pd.DataFrame, config: StructureConfig | None = None) -> dict`
Detecta estructura MT (trend, BOS, CHOCH, liquidity) SIN look-ahead.

**Parámetros:**
- `df`: DataFrame con columnas `high, low, close, open, time` (y opcional
  `atr`, `bsl_price`, `ssl_price`).
- `config`: `StructureConfig` (ver abajo). Si es None, usa defaults.

**Retorna:** dict con claves `trend, bos_dir, choch_dir, bos_status,
choch_status, bos_age, choch_age, invalidation, bsl_price, ssl_price`
(estas últimas por fila del DataFrame).

### `StructureConfig` (dataclass)
```python
@dataclass
class StructureConfig:
    bos_lookback: int = 3
    choch_lookback: int = 3
    bos_max_age: int = 20
    choch_max_age: int = 20
    trend_lookback: int = 20
    use_liquidity: bool = True
    liquidity_lookback: int = 50
```

### `_swing_points(frame, lookback) -> tuple[pd.Series, pd.Series]`
Interno. Devuelve `(swing_high, swing_low)` SIN look-ahead (ventana no
centrada + `shift(lookback).ffill()`).

---

## 3. `engine.py`

### `ICTSignal` (dataclass)
```python
@dataclass
class ICTSignal:
    symbol: str
    time: str            # ISO del timeframe de ejecución
    direction: int       # +1 long, -1 short
    entry: float
    stop_loss: float
    take_profit: float
    model: str           # 'sequence', 'scalping', etc.
```

### `ICTTrade` (dataclass)
```python
@dataclass
class ICTTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    exit: float
    pnl_r: float
    # NOTA: exit_reason NO está aquí; viene en meta (2do retorno de simulate_trade)
```

### `simulate_trade(frame, signal, max_hold_bars, cost: dict | None = None) -> tuple[ICTTrade | None, dict]`
Simula UN trade vela a vela.

**Parámetros:**
- `frame`: DataFrame LTF con `high, low, close, open, time`.
- `signal`: `ICTSignal`.
- `max_hold_bars`: int (límite de velas en la operación).
- `cost`: dict opcional `{"spread_pips": float, "commission_pips": float,
  "slippage_pips": float}`. Si es None, comportamiento teórico (sin costos).

**Retorna:** `(ICTTrade | None, meta)` donde `meta = {"exit_reason": str,
"mfe_r": float, "mae_r": float, "hold_bars": int}`.

**Reglas:** entry con slippage adverso + spread/2; SL antes que TP en empate;
comisión restada en R.

### `build_signals_from_frames(frames: dict, config) -> list[ICTSignal]`
Construye señales desde los frames detectados.

---

## 4. `sequence.py`

### `run_sequence(ms_htf: dict, ms_ltf: dict, config: SequenceConfig) -> list[ICTSignal]`
Motor event-driven ICT: sweep → displacement → BOS → retorno al cuadro.

### `SequenceConfig` (dataclass)
```python
@dataclass
class SequenceConfig:
    displace_gap: int = 6
    bos_gap: int = 10
    require_displacement: bool = False
    tp_mode: str = "fixed2r"     # 'fixed2r' | 'liquidity'
    max_sweep_age: int = 20
    ...
```

---

## 5. `optimize.py`

### `main()` (CLI)
Optuna TPE + walk-forward multi-fold. Args: `--symbol, --ltf, --trials,
--n-windows`. Imprime PF/WR/trades por fold y PF OOS promedio ± std.

### `_split_windows(n, n_windows, min_train) -> list[tuple[int,int,int,int]]`
Walk-forward rolling. Retorna lista de `(train_start, train_end, test_start,
test_end)`. Dirección temporal correcta (pasado→futuro).

---

## 6. `run_backtest.py` (CLI Capa 2)
```
python ict_backtest/run_backtest.py --symbol EURUSD --htf H4 --ltf M15 \
    --engine sequence --max-hold 96 --require-displacement \
    --tp-mode liquidity --displace-gap 12 --bos-gap 8
```
Args: `--symbol, --htf, --ltf, --engine {sequence}, --max-hold,
--require-displacement, --tp-mode {fixed2r,liquidity}, --displace-gap,
--bos-gap`.

---

## 7. `plot_equity_curve.py` (CLI)
```
python ict_backtest/plot_equity_curve.py --symbol EURUSD --htf H4 --ltf M15 \
    --displace-gap 12 --bos-gap 8 --tp-mode liquidity --require-displacement
```
Genera PNG de equidad + drawdown en `docs/ict/plots/`.

---

## 8. Convenciones
- Todos los DataFrames usan `time` como string ISO.
- Módulos sueltos en RAÍZ se importan vía `sys.path` (estilo legacy del repo).
- Sin ML en `ict_backtest/` por diseño (ADR-01).

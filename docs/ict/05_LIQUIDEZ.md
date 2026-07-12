# ICT — Liquidez (Buyside / Sellside) y Liquidity Sweeps

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo.

## 1. Teoría
El mercado se mueve buscando liquidez: las órdenes agrupadas (stops) en niveles
clave. Esos niveles son la "comida" de las instituciones.

- **BSL (Buyside Liquidity):** niveles donde los cortos tienen su stop loss →
  típicamente por encima de máximos (swing highs, prev day high, equal highs).
- **SSL (Sellside Liquidity):** niveles donde los largos tienen su stop → por
  debajo de mínimos (swing lows, prev day low, equal lows).

**Liquidity Sweep (barrido):** el precio rompe el nivel de liquidez y vuelve.
- **Sweep de SSL:** baja, rompe el low SSL, y sube de vuelta (toma stops de
  largos; atrapa cortos débiles).
- **Sweep de BSL:** sube, rompe el high BSL, y baja de vuelta.

El sweep es la fase de **manipulación** (ver PO3, `08_POWER_OF_THREE.md`): crea
la falsa ruptura para entregar el movimiento real en dirección opuesta.

## 2. Práctica del trader (uso real)
Casi todo setup ICT empieza con un sweep:
- **Turtle Soup:** sweep de SSL + MSS alcista (reversión).
- **Silver Bullet:** sweep de SSL + FVG alcista (intradía).
- **PO3:** la manipulación barre el open del día, luego expansión.

Cómo lo opera el trader:
1. Marcar BSL/SSL en TF mayor (H1/H4) como objetivos de TP y zonas de sweep.
2. Tras el sweep, ESPERAR confirmación (MSS/CHoCH + FVG) antes de entrar.
3. **NO entrar contra el sweep** (no "pescar el cuchillo"); esperar el retorno.
4. El sweep es el disparador; la entrada es en el retorno, no en la ruptura.

## 3. Algoritmo (detección automática)
**Zonas de liquidez (BSL/SSL):** agrupar swings (pivots) cuyos precios caen
dentro de un margen `atr/margin` (LuxAlgo: si hay >2 swings en ese rango, es
zona de liquidez). La zona activa más reciente se proyecta hacia adelante.

**Sweep (barrido):** el precio rompe el swing y revierte en la misma vela:
- `bearish_sweep = (high > swing_high) & (close < swing_high)`
- `bullish_sweep = (low < swing_low) & (close > swing_low)`

**Riesgos:**
- **Look-ahead en el cluster:** los pivots deben confirmarse `left` velas
  después (ventana NO centrada). `detectors/liquidity.py` usa `_swing_highs_lows`
  con ventana simétrica `left=right=3` recorriendo solo el pasado → sin fuga.
- **Chart Shift:** el BSL/SSL que ves a la derecha en MT5 es la zona vigente; el
  backtest usa datos crudos.
- **Profundidad de histórico:** los equal highs/lows y los prev day high/low
  solo son detectables con años de datos; en HTF pocos años sesgan las zonas.

## 4. Código SMC-SYSTEMS (implementación real)
Dos lugares distintos, y ahí está el punto clave:

- **`detectors/liquidity.py` → `detect_liquidity()`**
  - Port de LuxAlgo ICT Concepts. Detecta zonas BSL/SSL por clustering de swings
    (`atr/margin`, `min_count`, `visible`).
  - **Solo informativo para pintar en el mapa** (`bsl_price/bsl_top/bsl_bot`,
    `ssl_*`). El docstring lo dice claro: *"no afecta la rutina de trading"*.

- **`detectors/bos.py` → `liquidity_sweep_up/down`**
  - Calcula el sweep real: romper el high/low previo y cerrar del otro lado, con
    `recent_sweep_*` en ventana `followthrough_bars`. Esto SÍ alimenta la rutina.

- **`signals/pipeline.py` (Item D)**
  - `bearish_sweep = (high > swing_high) & (close < swing_high)`; igual para
    bullish. Marca `liquidity_sweep_detected` y `recent_liquidity_sweep`
    (ventana `sweep_lookback=8`).
  - `filter_sweep`: si `enable_sweep_filter=True`, rechaza entradas de reversión
    SIN sweep previo. Peso en el score: 2.0 (rulebook=2).
  - `filter_ote`: requiere zona OTE / discount (long) o premium (short). Peso 1.0.

> **Hallazgo estructural:** el sweep que FILTRA entradas vive en `bos.py` +
> `pipeline.py`, mientras que `detectors/liquidity.py` solo PINTA zonas. O sea los
> sweeps se detectan y se consumen, pero el detector de "liquidez" propiamente
> dicho queda desacoplado de la señal. Es un hueco de arquitectura, no de
> detección: la señal funciona, pero la fuente de verdad de "dónde está la
> liquidez" no es la misma que la del sweep. Ver Sección 5.

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
- **Hueco real (sweeps detectados pero no consumidos por `liquidity.py`):**
  `detectors/liquidity.py` es decorativo respecto a la señal. La lógica de sweep
  que importa está en `bos.py` y `pipeline.py`. Esto es coherente con la auditoría
  2026-07-11: el pipeline ya consume el sweep vía `filter_sweep`, así que la señal
  NO está "desconectada" — pero el libro debe decir la verdad: la liquidez como
  zona la pinta `liquidity.py`; el sweep como filtro lo hace `pipeline.py`.
- **#1 Look-ahead:** los pivots de `liquidity.py` usan ventana simétrica pero solo
  sobre el pasado (`range(left, n-left)`), sin centro → sin fuga. Los sweeps en
  `pipeline.py` se calculan sobre la vela actual (high/low/close ya cerrados) →
  sin fuga.
- **#2 CHOCH real:** el sweep + CHOCH es la base de Turtle Soup / Silver Bullet;
  al corregir CHOCH, los reversales tras sweep pasaron a ser coherentes.

## 6. Resultados medidos
- PF Capa 2: **2.003 → 1.548** tras corregir #1 y #2. El sweep (vía `filter_sweep`)
  es filtro obligado en reversales; su contribución al edge hereda la limpieza de
  los fixes.
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF prom **3.389 ± 2.303**,
  21 trades OOS. El sweep participa de la cadena; falta aislar su peso con costos
  (fix #4 `--cost` en `optimize.py`, no aplicado).

## En resumen
La liquidez es el objetivo del mercado; el sweep es la manipulación que la toma.
En SMC-SYSTEMS las zonas BSL/SSL se pintan en `detectors/liquidity.py` (solo
visual), pero el sweep que filtra entradas se calcula en `bos.py` y
`signals/pipeline.py`. El libro queda honesto: la señal consume el sweep, pero la
"fuente de liquidez" decorativa está separada de la lógica de trading — hueco de
arquitectura documentado, no bug de detección.

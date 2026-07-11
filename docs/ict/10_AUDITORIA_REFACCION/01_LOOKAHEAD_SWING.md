# Tema 01 — LOOK-AHEAD BIAS EN SWING POINTS (#1, Crítico)

## Qué es
Un swing high/low solo se CONFIRMA en trading real `lookback` velas DESPUÉS
de ocurrir (hay que ver que ninguna vela posterior lo superó). Si el detector
usa una ventana CENTRADA y luego propaga el valor con `.ffill()` desde la vela
del pico, el backtest "sabe" del swing con anticipación indebida.

## Evidencia empírica (verificada 2026-07-11)
Serie sintética: pico claro en índice 10, `lookback=5`.
```
Pico real en idx 10 (valor 101.0)
swing_high YA vale 101.0 en la fila 10 MISMA
```
Esperado: `swing_high` disponible recién en la fila 15 (10+5).

## Código original (market_structure.py:_swing_points)
```python
window = lookback * 2 + 1
rolling_high = frame["high"].rolling(window=window, center=True)
swing_high = frame["high"].where(frame["high"] == rolling_high.max())
return swing_high.ffill(), swing_low.ffill()
```
La ventana `center=True` hace que el pico aparezca en su propia fila, y el
`.ffill()` lo propaga hacia adelante desde ahí. Fuga de ~`lookback` velas.

## Mitigación parcial en la práctica
`detect_market_structure` evalúa el break contra `sh.shift(1)`:
```python
bull_break = d["close"] > sh.shift(1)
```
Eso reduce el leak de 5 velas a ~4 (el break usa el swing de la vela anterior,
pero ese swing ya filtrado trae el valor del pico). Sigue siendo look-ahead,
pero NO tan grave como "5 velas de ventaja en todo".

## Fix aplicado
Desplazar `swing_high`/`swing_low` por `lookback` posiciones hacia adelante
ANTES del `.ffill()`, usando ventana NO centrada (solo hacia atrás):
```python
import pandas as pd
def _swing_points(frame, lookback):
    window = lookback + 1  # solo hacia atrás
    roll_h = frame["high"].rolling(window=window, center=False, min_periods=window)
    roll_l = frame["low"].rolling(window=window, center=False, min_periods=window)
    sh = frame["high"].where(frame["high"] == roll_h.max())
    sl = frame["low"].where(frame["low"] == roll_l.min())
    # El pico queda en su fila; desplazar lookback velas para que solo esté
    # disponible desde la vela de CONFIRMACIÓN (no antes).
    sh = sh.shift(lookback).ffill()
    sl = sl.shift(lookback).ffill()
    return sh, sl
```
Ahora el valor aparece recién en `idx + lookback`, igual que en vivo.

## Impacto esperado en los números
En M15 EURUSD: 4-5 velas = 1-1.25 h de "adelanto". Probablemente baja el PF
(porque el motor ya no entra en el momento óptimo de la estructura). MAGNITUD
= se mide al re-correr Capa 2/3, no se asume.

## Fuentes
- Freqtrade — Lookahead analysis: https://www.freqtrade.io/en/stable/lookahead-analysis/
- Mike Harris — Look-Ahead Bias In Backtests: https://mikeharrisny.medium.com/look-ahead-bias-in-backtests-and-how-to-detect-it-ad5e42d97879
- QuantInsti — Look-ahead bias community: http://quantra.quantinsti.com/community/t/short-selling-in-trading-look-ahead-bias/22755

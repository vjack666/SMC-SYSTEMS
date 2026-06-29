# Stochastic Exhaustion Module

Detects trend exhaustion via stochastics (RSI), price divergence, and compression.

## Logic
- **Oversold cycles**: RSI < threshold, counts cycles of entry/exit
- **Divergence**: price fails to make new lows (bullish) / new highs (bearish) while RSI is extreme
- **Compression**: consecutive narrow-range candles relative to ATR
- **Signal**: all three conditions met → exhaustion confirmed

## Config
- `oversold_threshold` (30.0)
- `overbought_threshold` (70.0)
- `min_cycles` (2)
- `epsilon` (0.0001)
- `compression_ratio` (0.6)
- `lookback` (20)
- `rsi_period` (14)

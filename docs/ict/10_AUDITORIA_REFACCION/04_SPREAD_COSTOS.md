# Tema 04 — SPREAD / COMISIÓN / SLIPPAGE (#4, Alto)

## Hallazgo
`engine.simulate_trade` compara `high`/`low` directo contra SL/TP y entra al
`close` exacto de la vela de señal. Cero costo de transacción. Con SL de
`0.5*ATR` (ajustado), el spread típico de EURUSD puede ser una fracción
no despreciable del riesgo por trade. Con 70-87 trades y PF>2, vale la pena
correr con costos realistas antes de creer el número.

## A favor (ya correcto)
El empate SL/TP en la MISMA vela se resuelve revisando SL ANTES que TP
(`engine.py` líneas 163-167). Eso es CONSERVADOR, no optimista — buen sesgo.

## Fix aplicado — costos parametrizables
`simulate_trade` acepta `cost` (dict con `spread_pips`, `commission_pips`,
`slippage_pips`):
- Entrada: `entry_fill = entry + signo(slippage + spread/2)` (en la dirección
  adversa al trade).
- SL/TP se ajustan por el spread: el SL real se toca `spread/2` antes (peor
  para el trader), el TP `spread/2` después.
- Comisión: resta `commission_pips` del pnl en unidades de riesgo.

```python
def simulate_trade(frame, signal, max_hold_bars, cost=None):
    spread = (cost or {}).get("spread_pips", 0.0)
    comm = (cost or {}).get("commission_pips", 0.0)
    slip = (cost or {}).get("slippage_pips", 0.0)
    # entry con slippage adverso
    entry_fill = entry + (slip + spread/2) * pip * (-1 if direction==1 else 1)
    ...
    pnl_r = (exit_fill - entry_fill)/risk - comm/pip_per_r ...
```
Para EURUSD M15: probar frontera de costos `spread ∈ {0, 0.5, 1.0, 2.0}` pips
(sugerencia algotrading: correr un "cost frontier", no un solo número).

## Fuentes
- QuantStart — Successful Backtesting Part II (transaction costs):
  https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/
- Reddit r/algotrading — Model slippage realistically (cost frontier):
  https://www.reddit.com/r/algotrading/comments/1tty2qg/how_do_you_model_slippage_realistically_in_a/
- ForTraders — Backtesting that works (factor all transaction costs):
  https://www.fortraders.com/blog/backtesting-strategies-that-actually-work

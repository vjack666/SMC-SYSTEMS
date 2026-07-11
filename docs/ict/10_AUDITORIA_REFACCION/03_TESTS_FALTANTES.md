# Tema 03 — TESTS FALTANTES (#3, Alto)

## Hallazgo
No existe `tests/test_market_structure.py`, `test_sequence.py` ni equivalente.
`grep -rl "choch" tests/` solo matchea el detector viejo (`detectors/choch.py`),
no el módulo nuevo. Un test unitario trivial con serie sintética habría cazado
el #1 y el #2 el mismo día que se escribió el código.

## Fix aplicado — tests sintéticos
Se crea `tests/test_ict_backtest.py` con casos conocidos:

1. `test_swing_no_lookahead`: serie con pico en idx 10 / lookback 5 →
   `swing_high` primer no-nulo debe estar en idx 15 (no en 10).
2. `test_choch_differs_from_bos`: tras un BOS alcista, un break bajista del
   swing contrario debe poner `choch_dir=-1` mientras `bos_dir` puede ser 0.
3. `test_engine_sl_before_tp`: vela donde SL y TP se cruzan juntos → debe
   salir por SL (conservador), no TP.
4. `test_engine_spread_reduces_pnl`: con spread>0 el pnl_r debe ser menor que
   sin spread.
5. `test_sequence_order`: la secuencia SWEEP→DISPLACE→BOS→ENTRY respeta el
   orden (no genera entrada sin BOS previo).

## Principio
Los tests usan datos SINTÉTICOS (no el parquet de 50k velas) → corren en
milisegundos y son deterministas. Esto evita el "PF bonito pero bugueado".

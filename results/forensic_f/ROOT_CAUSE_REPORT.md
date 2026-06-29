# ROOT CAUSE REPORT

## Summary

- raw BOS+FVG signals: 14804
- unique entry signals: 14804
- valid structural stops: 141
- invalid risk signals: 0
- simulated trades: 141

## Core findings

1. The main bug is that the structural stop price is being assigned to an origin swing price that is often on the wrong side of the entry.
2. This occurs in modules/structural_sl/detector.py:calculate_structural_stop(), where LONG uses the maximum high as origin swing and SHORT uses the minimum low.
3. The result is that LONG stops are placed above entry and SHORT stops are placed below entry, making sl_hit mathematically inconsistent.
4. The dataset is contaminated by invalid stop positions, invalid exit logic, and false positive sl_hit events.
5. stop_distance_atr is NaN because calculate_structural_stop() computes it using atr at the entry candle, but the code path never ensures a valid atr value at the required index in the symbol data. It is likely due to missing/NaN ATR at the exact entry bars in the loaded detect_bos dataset.
6. Metrics derived from this experiment (win_rate, profit_factor, expectancy_r, avg_stop_distance_atr) are therefore unreliable.

## Evidence

- invalid stop positions: 133
- invalid exit logic violations: 133
- holding_bars constant at 1 for all trades: True

## Suggested test coverage (audit-only)

- unit test to assert LONG structural stops are below entry and SHORT structural stops are above entry.
- unit test for calculate_structural_stop() to verify stop_distance_atr is finite when ATR is valid.
- unit test for simulate_trades() to ensure sl_hit with positive pnl_r cannot occur.
- regression test comparing raw entry signal count to final trade count with known filters.
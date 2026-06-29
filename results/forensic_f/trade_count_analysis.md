# Trade Count Analysis

This file compares the raw signal volume and the filters applied in experiment_F_structural_sl.

| stage | trades_remaining |
|---|---|
| raw_bos_fvg_signals | 14804 |
| unique_entry_signals | 14804 |
| signals_without_structural_stop | 14663 |
| signals_with_valid_structural_stop | 141 |
| signals_with_invalid_risk | 0 |

## Symbol counts in unique signals
- GBPUSD: 5431
- EURUSD: 5386
- XAUUSD: 3987

## Trades generated in simulation
- trades after simulation: 141

- invalid stop positions found: 133
- invalid exit logic violations found: 133
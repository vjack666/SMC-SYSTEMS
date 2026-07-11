# Libro 10 — AUDITORÍA Y REFACCIÓN DE ICT_BACKTEST

Índice de temas (cada archivo es un tema del libro):

- 00_INDICE.md ............... este archivo
- 01_LOOKAHEAD_SWING.md ...... Hallazgo #1: look-ahead bias en swing points
- 02_CHOCH_REAL.md ........... Hallazgo #2: CHOCH duplicado de BOS (implementación real)
- 03_TESTS_FALTANTES.md ...... Hallazgo #3: ausencia de tests unitarios
- 04_SPREAD_COSTOS.md ........ Hallazgo #4: sin spread/comisión/slippage
- 05_WALKFORWARD_REAL.md ..... Hallazgo #5: walk-forward de 1 solo split
- 06_PERFORMANCE.md .......... Hallazgo #6: cuello de botella (~8 min/50k velas)
- 07_IMPORTS_DEDUP.md ........ Hallazgo #7: Any sin importar + _row_at_time duplicado
- 08_FUENTES.md .............. Enlaces y referencias verificadas en internet

Contexto: auditoría externa (Claude) del 2026-07-11 sobre `ict_backtest/`
(commits 91f24ad…3aafab7). Los 2 hallazgos críticos (#1, #2) fueron
VERIFICADOS empíricamente por el equipo con el código real antes de actuar.

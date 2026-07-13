# Auditoría: impacto de `confirm_bars` en R4 (diagnóstico, sin cambios de código)

**Fecha:** 2026-07-13
**Contexto:** El informe de auditoría externa (Claude) marcó H1: `test_choch_differs_from_bos`
roto, atribuyéndolo a que `StructureConfig.confirm_bars` subió de 1 a 2. Se investigó
si ese cambio contamina las métricas de R4 (cadena v2 corriendo con `displacement ON`).

## Evidencia

- `ict_backtest/market_structure.py:60` — `StructureConfig.confirm_bars = 2` (default).
- `detect_market_structure` aplica `confirm_bars` a BOS (líns 161-162) y CHOCH (176-178).
- El backtest R4 (`run_backtest.py` / `engine.build_signals_from_frames`) NO sobreescribe
  `confirm_bars`, así que corre con el default = 2.

## Medición empírica (EURUSD M15, 50k velas, 2 años)

| confirm_bars | BOS eventos | CHOCH eventos | BOS activos (en algún momento) |
|---|---|---|---|
| 1 | 18.144 | 18.988 | 24.688 |
| 2 (default backtest) | 13.745 | 14.444 | 21.482 |

`confirm_bars=2` recorta ~24% de los eventos de estructura vs `confirm_bars=1`.

## Veredicto

1. **H1 NO contamina R4.** El backtest usa `confirm_bars=2` a propósito (filtra
   fakeouts/Turtle Soups según LuxAlgo: "two consecutive candle bodies close beyond").
   Es decisión de diseño documentada, no bug. El test está desactualizado, no el motor.
2. **Riesgo de muestra:** `-24%` de señales de estructura + `displacement ON` puede
   dejar modelos ya escasos (PO3 daba 8 trades sin displacement) por debajo de N>=30
   para conclusión estadística. Se evalúa al llegar R4 v2.
3. **H2 (checklist duplicado vivo vs backtest)** es divergencia de trazabilidad real
   (docstring de `ict_backtest/rules.py` miente), pero NO afecta los números de R4:
   el backtest usa `ict_backtest/rules.py` (correcto); el widget usa su copia para el
   dashboard en vivo.

## Acción

- R4 v2 es válido tal como corre. Interpretar sus números "con confirm_bars=2 +
  displacement ON" (modelo más estricto/honesto hasta ahora).
- H1 (fix de 1 test) y H2 (unificar imports del widget) requieren cambio de código:
  fuera de alcance de RFC-001 (solo documentación) y sujetos a visto bueno de Ruben
  antes de commit (regla de hierro). Quedan documentados para un RFC/cambio futuro.

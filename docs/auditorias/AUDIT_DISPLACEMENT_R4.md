# Auditoría: displacement en el backtest ICT (R4)

**Fecha:** 2026-07-13
**Hallazgo:** Las corridas R4 iniciales (E2/E3/E5, commit `de2d4ed`) usaron la
Opción A (`--engine checklist`, default) **SIN `--require-displacement`**, midiendo
PO3/Turtle **sin** el filtro de displacement.

## Evidencia (código vs documentación)

| Fuente | Qué dice | Estado |
|--------|----------|--------|
| `docs/ict/SDD_ICT_BACKTEST.md:14,79` | Edge ICT = `sweep → displacement → BOS → retorno` | displacement es paso OBLIGADO |
| `ict_backtest/sequence.py:39` | Capa 2: `require_displacement=True` (default) | ✅ aplica por diseño |
| `ict_backtest/engine.py:55` | Opción A `build_signals_from_frames`: `require_displacement=False` (default) | ⚠️ OFF por defecto |
| `ict_backtest/run_backtest.py:203` | `--require-displacement` es `store_true` → default False | ⚠️ OFF salvo flag explícito |
| `scripts/r4_chain.py` (v1) | No pasaba `--require-displacement` | ❌ corridas sin displacement |
| `detectors/displacement.py` + `data_feed.build_features` | displacement SE calcula y puebla columnas | ✅ definido y disponible |

## Veredicto

- El **sistema no está roto**: displacement está definido, calculado y aplicado
  donde la documentación lo promete (Capa 2 / sequence).
- La **medición R4 v1 estuvo incompleta**: midió el modelo desnudo, no el modelo
  completo documentado. Los PF de `METRICS_CANON §8.1` (0.286 / 0.689) NO son
  concluyentes sobre el edge real.
- Gravedad: **error de configuración de corrida**, no bug de código.

## Acción correctiva

`scripts/r4_chain.py` reescrito (R4 v2) para pasar `--require-displacement` en
TODOS los experimentos, multi-símbolo (EURUSD + GBPUSD) y con costos. Resultados
en `results/r4/r4v2_chain_*.json`. §8.1 de METRICS_CANON se actualiza con los
números de R4 v2 (modelo completo) y se marca R4 v1 como baseline desnudo.

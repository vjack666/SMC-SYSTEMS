# ETAPA 1 — VALIDACIÓN DE HALLAZGOS (sin modificar código)

Objetivo: demostrar que cada hallazgo realmente existe, con repro paso a paso.
NO se corrige nada en esta etapa.

## Metodología por hallazgo (clasificado A en el informe de convergencia)
Para cada bug: reproducir → medir impacto → demostrar evidencia → indicar archivos afectados.
Formato de entrada en VALIDACION_DE_HALLAZGOS.md:
- ID · Componente · Pasos de repro · Salida medible · Archivo:línea · Conclusión

## Hallazgos a validar (mapeo desde INFORME_DE_CONVERGENCIA)
- H3/H14 v2 no versionado + XAUUSD M15 ausente → Falla 1 / Falla 4 (repro: clon limpio,
  `python scripts/run_bt_v2_mtf.py` → ModuleNotFoundError; ls data/raw/XAUUSD_M15).
- H4 BOS duplicado → market_structure.py:157-163 vs detectors/bos.py (sin confirm_bars).
- H5 CHOCH duplicado → market_structure.py:166-176 vs detectors/choch.py:14-24 (medias 20/50).
- H12 POI no anclado → coverage.py:44-63 C05 missing; v2 legacy_subset partial.
- H13 Silver Bullet no modelado → no hay módulo SB explícito.
- H15 cap por confianza → edge_diagnosis/run.py:64,410,430-432,627-628; síntoma 13/21 XAUUSD
  idénticas (instrumentación n_raw/capped ya aplica en 104964c, útil para medir capped).
- H16 sin DSR/PBO en grilla → ml/stats_validator.py:83,101 existen; no aplicados en run.py.
- H17 train/serve skew → dataset_builder.py:14,234 (legacy) vs run_backtest.py:103 (canonical).
- H18 features "todo numérico" → train.py:311-314 fallback.
- H20 tests no terminan + auto-download → pytest >600s; dataset_builder.py:146-161.
- H21 ciclo import trend_context → trend_context.py ↔ signals/data.
- H22 dead code → engine.py _coerce_ts duplicada; strategy_mtf.py:101-103 no-op.

## Salida
VALIDACION_DE_HALLAZGOS.md con una entrada por ID arriba.

## Gate de salida
Cada hallazgo A tiene un repro paso a paso con archivo:línea y salida medible. Sin repros =
no se pasa a ETAPA 2.

## Nota
Esta etapa NO modifica código. Solo ejecuta y documenta. La instrumentación n_raw/capped de
104964c ya es evidencia utilizable para H15 sin tocar la lógica.

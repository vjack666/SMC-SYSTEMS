> **✅ HISTORICAL** — Validación completada 2026-07-17. 12 hallazgos validados con repro paso a paso.

# VALIDACIÓN DE HALLAZGOS — ETAPA 1

Objetivo: demostrar que cada hallazgo realmente existe, con repro paso a paso y evidencia
archivo:línea. NO se corrige nada en esta etapa (modo piloto automático supervisado:
ETAPA 1 es validación, no implementación).

Estado al validar: tag `baseline-2026-07-17` (commit `c885ac3`), main en `ff95230`.

---

## H3 / H14 — v2 no versionado + XAUUSD M15 ausente (Fallas 1 / 4)

- Tipo: BUG (A) / restricción de datos (D parcial).
- Pasos de repro:
  1. Clon limpio en `baseline-2026-07-17`: `git cat-file -e baseline-2026-07-17:ict_backtest/v2/orchestrator.py`
     → OK (resuelve Falla 1 a nivel repo).
  2. `ls data/raw/XAUUSD_M15.parquet` → EXISTE (3.6 MB, 2026-07-17 10:53, descargado en trabajo
     previo congelado en ETAPA 0).
- Conclusión:
  - H3 (v2 no versionado): CERRADO. El módulo ya está comiteado y es reproducible desde clon.
  - H14 (XAUUSD M15 ausente): CERRADO a nivel de DATOS. El parquet existe. Lo que queda por
    validar en ETAPA 2 es si `run_bt_v2_mtf.py` incluye XAUUSD en su lista de símbolos MTF
    (puede seguir excluido por config, no por falta de datos).
- Archivos: `ict_backtest/v2/orchestrator.py`, `data/raw/XAUUSD_M15.parquet`.

---

## H4 — BOS duplicado (semántica contradictoria)

- Tipo: BUG (A).
- Pasos de repro:
  1. `detectors/bos.py:90-91`: rompe nivel por `close > swing_high.shift(1)` SIN confirm_bars.
  2. `ict_backtest/market_structure.py:157-160` (canónico): exige confirmación por N cierres
     por encima del nivel (BOS válido solo tras confirmación).
- Salida medible: dos definiciones de "BOS" distintas sobre el mismo frame. El motor de
  producción usa el canónico (market_structure); detectors/bos.py es otra implementación que
  además se auto-declara "única fuente de verdad" (comentario línea 76) de forma engañosa.
- Conclusión: CONFIRMADO. Ambas coexisten; la de detectors/ no está cableada a producción pero
  introduce ambigüedad y riesgo de uso erróneo.
- Archivos: `detectors/bos.py:76,90-91`, `ict_backtest/market_structure.py:157-160`.

---

## H5 — CHOCH duplicado (semántica contradictoria)

- Tipo: BUG (A).
- Pasos de repro:
  1. `detectors/choch.py:14-24`: CHOCH = cierre cruza swing(20) en contexto de medias 20/50.
  2. `ict_backtest/market_structure.py:166-176` (canónico): CHOCH = cierre rompe el ÚLTIMO nivel
     BOS en dirección opuesta, tras confirmación.
- Salida medible: dos definiciones de "CHOCH" mutuamente incompatibles (medias móviles vs
  ruptura de estructura previa).
- Conclusión: CONFIRMADO. Misma situación que H4.
- Archivos: `detectors/choch.py:14-24`, `ict_backtest/market_structure.py:166-176`.

---

## H12 — POI no anclado a narrativa HTF

- Tipo: BUG (A) — brecha B de la tesis ICT.
- Pasos de repro:
  1. `ict_backtest/v2/coverage.py:44-47` (legacy_subset): C05 "POI anchored to narrative" =
     `missing`.
  2. `ict_backtest/v2/coverage.py:71` (mtf_intraday): C05 = `partial` ("PD side as soft POI
     proxy; full POI narrative later").
- Salida medible: el filtro más definitorio de ICT (POI anclado al BOS/CHOCH del TF padre) no
  está implementado; usa un proxy P/D.
- Conclusión: CONFIRMADO. El motor evalúa FVG/OB como entrada sin respaldo del TF padre.
- Archivos: `ict_backtest/v2/coverage.py:44-47,71`.

---

## H13 — Silver Bullet no modelado explícitamente

- Tipo: BUG (A) — brecha de la tesis objetivo.
- Pasos de repro:
  1. Búsqueda de módulo SB en `ict_backtest/v2/`: no existe `silver_bullet.py` ni función
     `detect_silver_bullet`. El SB (ventana NY 10:00–11:00 / 14:00–15:00 + retorno a POI en M15)
     no tiene representación dedicada.
  2. Killzone se modela (C08 implemented) pero no la sub-ventana SB ni el retorno a POI.
- Salida medible: cobertura C05 partial, sin módulo SB.
- Conclusión: CONFIRMADO. Sin SB explícito, el motor no representa la estrategia objetivo.
- Archivos: `ict_backtest/v2/` (ausencia), `ict_backtest/v2/coverage.py:71`.

---

## H15 — Cap por confianza invalida la ablación + w0_agents no-op

- Tipo: BUG (A).
- Pasos de repro:
  1. `scripts/edge_diagnosis/run.py:64`: `MAX_SIGNALS_PER_VARIANT = 3000`.
  2. `scripts/edge_diagnosis/run.py:433-435`: corte por confianza descendente
     `order = rows[np.argsort(-conf.to_numpy()[rows])]; rows = order[:MAX_SIGNALS_PER_VARIANT]`.
  3. `scripts/edge_diagnosis/run.py:412`: `"agents": 0.0` hardcodeado → w0_agents es no-op.
  4. Instrumentación (commit 104964c): el reporte ahora expone `n_raw`/`capped` por celda para
     medir cuánto se recorta.
- Salida medible (evidencia operador / forense): 13/21 variantes XAUUSD colapsan al MISMO
  resultado (PF 1.379 / WR 60.1% / N=900) porque el corte por confianza deja el mismo set base.
- Conclusión: CONFIRMADO. Relajar un filtro no cambia el set medido → la ablación es inválida
  para aislar efecto de filtros.
- Archivos: `scripts/edge_diagnosis/run.py:64,412,433-435`.

---

## H16 — Sin DSR/PBO en la grilla 168

- Tipo: BUG (A) — significancia no evaluada.
- Pasos de repro:
  1. `ml/stats_validator.py:83` define `defecttion_proba` (DSR) y `:101` define PBO.
  2. Búsqueda en `scripts/edge_diagnosis/run.py`: NO se importa ni aplica DSR/PBO a las 168 celdas.
- Salida medible: las celdas se reportan sin p-valor de sobreajuste (PBO) ni DSR.
- Conclusión: CONFIRMADO. La significancia estadística de la grilla no está evaluada.
- Archivos: `ml/stats_validator.py:83,101`, `scripts/edge_diagnosis/run.py`.

---

## H17 — Train/serve skew (ML entrena en motor legacy, produce en canónico)

- Tipo: BUG (A).
- Pasos de repro:
  1. `ml/dataset_builder.py:14` importa `from legacy.backtest import engine`.
  2. `ml/dataset_builder.py:234` construye el dataset con `legacy.backtest.engine`.
  3. `ict_backtest/run_backtest.py:103` evalúa señales con `canonical.evaluate_signals`.
- Salida medible: el modelo ve la distribución del motor LEGACY en entrenamiento y la del
  CANÓNICO en producción. Distribuciones distintas → skew de train/serve.
- Conclusión: CONFIRMADO por imports (no requiere correr A/B; la discrepancia es estructural).
- Archivos: `ml/dataset_builder.py:14,234`, `ict_backtest/run_backtest.py:103`.

---

## H18 — Features "todo numérico" como fallback (riesgo de leakage)

- Tipo: BUG (A).
- Pasos de repro:
  1. `ml/train.py:311-314`: tras la allowlist, hace fallback a TODAS las columnas numéricas del
     frame como features (`numeric_cols = frame.select_dtypes(...).columns`; si no hay allowlist
     válida, usa todas).
- Salida medible: columnas de outcome futuro podrían entrar como features → leakage latente.
- Conclusión: CONFIRMADO (riesgo estructural). Requiere allowlist estricta (ETAPA 4/7).
- Archivos: `ml/train.py:311-314`.

---

## H20 — Suite de tests no termina + auto-download MT5

- Tipo: BUG (A) — reproducibilidad/CI.
- Pasos de repro:
  1. `pytest tests/` en baseline: timeout > 600s (medido en auditoría arquitectónica).
  2. `ml/dataset_builder.py:146-161`: `load_frame(..., auto_download=True)` en tests pesados.
- Salida medible: sin CI verde rápido ni reproducible; posible descarga de red en tests.
- Conclusión: CONFIRMADO.
- Archivos: `ml/dataset_builder.py:146-161`, `tests/`.

---

## H21 — Ciclo de import trend_context

- Tipo: BUG (A) — acoplamiento circular.
- Pasos de repro:
  1. Import aislado de `trend_context` falla por ciclo con `signals`/`data` (verificado en
     auditoría: import circular, no roto en runtime porque se resuelve por orden de import, pero
     frágil).
  2. `trend_context.py` ↔ `signals` ↔ `data` forman ciclo.
- Salida medible: import frágil; `build_trend_context_frame` (línea ~75) existe pero el módulo
  no importa limpio en aislamiento.
- Conclusión: CONFIRMADO.
- Archivos: `trend_context.py`, `signals/`, `data/`.

---

## H22 — Dead code / no-ops

- Tipo: BUG (A) — deuda menor.
- Pasos de repro:
  1. `ict_backtest/engine.py:160` y `:229`: `def _coerce_ts` DUPLICADA (dos definiciones).
  2. `ict_backtest/v2/strategy_mtf.py:101-103`: `if not hasattr(s, "meta") or s.meta is None: pass`
     → no-op (no hace nada).
- Salida medible: código muerto y rama inerte.
- Conclusión: CONFIRMADO.
- Archivos: `ict_backtest/engine.py:160,229`, `ict_backtest/v2/strategy_mtf.py:101-103`.

---

## CORRECCIONES A LA AUDITORÍA FORENSE (encontradas al validar)

- H14 (XAUUSD M15 ausente): YA EXISTE el parquet (`data/raw/XAUUSD_M15.parquet`, 3.6 MB, hoy).
  La Falla 4 de datos quedó resuelta por la descarga de hoy. Queda validar si el runner MTF lo
  incluye (ETAPA 2).
- H3 (v2 no versionado): YA RESUELTO por commits de la auditoría forense (Falla 1). El módulo
  está en el tag baseline.

---

## GATE DE SALIDA DE ETAPA 1

Cada hallazgo A tiene repro + archivo:línea + salida medible. Sin repros pendientes.
Validación completa. Listo para ETAPA 2 (árbol de dependencias / causa raíz).

Nota: NO se modificó código. Solo lectura + ejecución de comandos de inspección + este documento.

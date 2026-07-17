# IMPLEMENTATION PLAN — ETAPA 3 (orden por dependencia)

Orden de cambios por DEPENDENCIA (no por importancia). Cada ítem es UN commit = UN bug.
Tras cada commit: ejecutar tests + backtest + comparar contra baseline; si hay regresión o
desvío >5-10% de métricas → REVERTIR y reportar en el punto de control.

Estado: tag `baseline-2026-07-17` (c885ac3), main en 8216e15.

REGLAS DE ORO (vinculantes):
- No tocar Fase 0 (Killzone, Sequence, Entry=next_open, SL estructural, TP RR 1:3, HTF filter,
  Displacement). Son ICT/Silver Bullet correctos.
- No aumentar N (número de trades) como objetivo. Solo representar la estrategia.
- Un cambio estructural a la vez. Backtest tras cada uno. Revertir si empeora.

---

## ORDEN (cadena de dependencia)

```
CR-1  Fuente unica de verdad BOS/CHOCH        (desbloquea H4, H5, y condiciona H17)
  │
  ├─> CR-6  Incluir XAUUSD en MTF             (corolario H14; dato ya existe)
  │
  ├─> CR-3  Cap por ventana/seed + quitar w0_agents   (H15; independiente de geometria)
  │
  ├─> CR-4  ML sobre stack canonico + allowlist       (H17, H18; requiere CR-1 resuelto)
  │
  ├─> CR-2  POI anclado + Silver Bullet              (H12, H13; lo mas profundo)
  │
  └─> H16   Aplicar DSR/PBO a la grilla               (requiere CR-3: grilla ya valida)

CR-5  Tests reproducibles + ciclo import + dead code  (H20, H21, H22; paralelo, sin senal)
```

---

## PASOS DETALLADOS

### PASO 1 — CR-1: Unificar BOS/CHOCH en fuente única de verdad
- Qué: definir que `ict_backtest/market_structure.py` (canónico, confirm_bars) es la única
  fuente de verdad para BOS/CHOCH. `detectors/bos.py` y `detectors/choch.py` deben delegar al
  canónico o quedar marcados explícitamente como "solo para el stack scalping legacy".
- Por qué primero: H4/H5 nacen de la bifurcación de stacks; H17 (train/serve) depende de saber
  cuál es la verdad. Sin esto, los demás pasos corrigen sobre base ambigua.
- Archivos: `detectors/bos.py`, `detectors/choch.py`, `ict_backtest/market_structure.py`,
  `signals/pipeline.py` (consumidor).
- Aceptación: un solo módulo produce BOS/CHOCH para ambos stacks; tests de `test_detectors.py`
  y `test_ict_backtest.py` siguen verdes; coverage C07 sigue implemented.
- Riesgo: cambiar la semántica de `detectors/` puede mover métricas del diagnóstico. Por eso se
  mide contra baseline y se revierte si >5-10%.
- NOTA: esto NO cambia la regla ICT (la semántica canónica YA es ICT); solo elimina la
  duplicación contradictoria. Cumple los 5 puntos de la regla más importante.

### PASO 2 — CR-6: Incluir XAUUSD en el runner MTF
- Qué: `scripts/run_bt_v2_mtf.py:16` quitar XAUUSD de la exclusión (el parquet ya existe,
  validado en ETAPA 1). Actualizar el comentario línea 3/35.
- Por qué: el filtro es obsoleto (ya no falta M15). Incluir XAUUSD hace el MTF representativo.
- Archivos: `scripts/run_bt_v2_mtf.py`.
- Aceptación: el runner incluye XAUUSD; corre sin ModuleNotFoundError; las demás métricas no se
  mueven por efecto propio (solo se agrega un símbolo).
- Riesgo: bajo. No toca lógica ICT.

### PASO 3 — CR-3: Rediseñar el cap por ventana/seed + quitar w0_agents
- Qué: en `scripts/edge_diagnosis/run.py` reemplazar el corte por confianza descendente
  (líneas 433-435) por un cap determinístico por VENTANA temporal (o sub-muestreo por semilla
  fija) que no colapse variantes idénticas. Quitar `"agents": 0.0` hardcoded (línea 412) o
  dejarlo explícito como "no implementado" sin peso muerto.
- Por qué: H15 invalida la ablación (13/21 idénticas). El cap debe permitir aislar el efecto de
  un filtro relajado.
- Archivos: `scripts/edge_diagnosis/run.py`.
- Aceptación: al correr la grilla, las variantes divergentes siguen divergentes (n_raw/capped de
  104964c lo evidencia); ninguna celda colapsa por corte de confianza.
- Riesgo: medio. Cambia el set simulado; se compara contra baseline y se revierte si empeora.

### PASO 4 — CR-4: ML sobre stack canónico + allowlist estricta
- Qué: `ml/dataset_builder.py:14,234` apuntar al motor canónico (no legacy) para entrenar;
  `ml/train.py:311-314` usar allowlist explícita de features (sin fallback "todo numérico").
- Por qué: H17 skew train/serve; H18 riesgo leakage. Requiere CR-1 (saber cuál es la verdad).
- Archivos: `ml/dataset_builder.py`, `ml/train.py`.
- Aceptación: el dataset se construye con el mismo motor que evalúa producción; features son
  solo la allowlist; sin columnas de outcome futuro.
- Riesgo: alto (re-entrenar ML). Se valida con walk-forward (ETAPA 8); si el PF cae por skew
  previo corregido, es esperado y se documenta, no se revierte ciegamente.

### PASO 5 — CR-2: POI anclado + Silver Bullet
- Qué: implementar C05 (POI anclado a narrativa HTF) y el módulo Silver Bullet (ventana NY
  10-11/14-15 + retorno a POI en M15) en `ict_backtest/v2/`.
- Por qué: H12/H13 son la brecha B de la tesis ICT. Sin esto el motor no representa la
  estrategia objetivo. Es el cambio más profundo.
- Archivos: `ict_backtest/v2/coverage.py` (C05/C12/C13), nuevo `ict_backtest/v2/silver_bullet.py`.
- Aceptación: coverage C05 pasa a implemented; hay módulo SB; el runner usa la sub-ventana.
- Riesgo: alto (nueva lógica de estrategia). Se mantiene dentro de ICT/SB; NO aumenta N por
  diseño. Backtest obligatorio; revertir si altera la regla de la estrategia.

### PASO 6 — H16: Aplicar DSR/PBO a la grilla
- Qué: en `scripts/edge_diagnosis/run.py` aplicar `ml/stats_validator.py:83` (DSR) y `:101` (PBO)
  a cada celda de la grilla 168.
- Por qué: requiere CR-3 primero (grilla válida). Da significancia estadística.
- Archivos: `scripts/edge_diagnosis/run.py`, `ml/stats_validator.py`.
- Aceptación: cada celda reporta DSR/PBO; el veredicto de edge es concluyente.
- Riesgo: bajo (solo medición).

### PASO 7 — CR-5: Tests reproducibles + ciclo import + dead code
- Qué: H20 (quitar auto_download de tests pesados / mockear datos), H21 (romper ciclo
  trend_context), H22 (eliminar `_coerce_ts` duplicada y no-op strategy_mtf).
- Por qué: reproducibilidad y mantenibilidad. No afecta señales.
- Archivos: `ml/dataset_builder.py`, `trend_context.py`, `ict_backtest/engine.py`,
  `ict_backtest/v2/strategy_mtf.py`.
- Aceptación: `pytest tests/` termina < umbral (ej. 120s) sin red; import aislado de
  trend_context OK; sin dead code.
- Riesgo: bajo.

---

## NOTAS DE SECUENCIA (no al revés)
- CR-1 ANTES de CR-4 (H17 necesita saber la verdad).
- CR-3 ANTES de H16 (DSR/PBO sobre grilla válida).
- CR-2 AL FINAL de la corrección estructural (lo más profundo; sobre geometría ya fija).
- Calibración (displace_gap, ATR, RR, costos) es ETAPA 7, SOLO por experimento. No aquí.

---

## GATE DE SALIDA ETAPA 3
Orden de implementación definido por dependencia, con aceptación y riesgo por paso.
Listo para ETAPA 4 (corrección de bugs, UN commit = UN bug).

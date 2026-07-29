> **✅ HISTORICAL** — Árbol de dependencias completado 2026-07-17. 6 causas raíz documentadas.

# DEPENDENCY TREE — ETAPA 2 (causa raíz, no prioridades)

Objetivo: encontrar la CAUSA RAÍZ de cada hallazgo y cómo se encadenan. NO es una lista de
prioridades. El orden de implementación (ETAPA 3) se deriva de este árbol, no de la gravedad.

Estado: tag `baseline-2026-07-17` (c885ac3), main en 8216e15. Sin modificar código.

---

## HALLAZGO CENTRAL (raíz de la fragmentación)

El repo tiene DOS STACKS de estructura que conviven:

- STACK A — `signals/` + `detectors/` (bos, choch, fvg, ob, displacement, liquidity_context).
  Usado por `scripts/edge_diagnosis/run.py` (importa `signals` en run.py:53) y por
  `scripts/build_real_dataset.py`, `ablation_study.py`, `gen_synth_ml.py`.
- STACK B — `ict_backtest/` + `ict_backtest/market_structure.py` (canónico, confirm_bars).
  Usado por `ict_backtest/run_backtest.py` (producción) y `ict_backtest/v2/`.

Evidencia: `signals/pipeline.py:12` importa `detectors`; `run_backtest.py:103` usa
`canonical.evaluate_signals` (Stack B). Los dos stacks definen BOS/CHOCH con reglas distintas
(H4/H5). El ML (`dataset_builder.py:14,234`) se entrena con STACK legacy (emparentado a A), y
producción evalúa con STACK B → H17 train/serve skew.

Raíz: no hubo una decisión única de "cuál es la fuente de verdad para geometría de estructura".
Se sumaron módulos sin unificar.

---

## ÁRBOL POR COMPONENTE

### Killzone (C08 implemented)
- Sin hallazgo. Killzone modelada en ambos stacks.
- Causa raíz de "pocas señales": Killzone acota ventanas → menos barras candidatas. Esto es
  CORRECTO (restricción de estrategia, Fase 0). No se toca.
  Killzone → menos barras → menos señales → (no es bug, es ICT).

### Sequence Engine (sweep→displacement→BOS→mitigation)
- Implementado en ambos stacks (C07 implemented).
- Sin hallazgo de bug. Restricción de estrategia.

### BOS / CHOCH (H4, H5)
```
dos stacks sin fuente unica de verdad        (RAIZ)
        ↓
detectors/bos.py (sin confirm_bars)          (Stack A, USADO en diagnostico/ML)
        ↓
market_structure.py (con confirm_bars)       (Stack B, USADO en produccion canonica)
        ↓
semantica contradictoria sobre el mismo dato (H4/H5)
        ↓
el BOS que ve el diagnostico != el de produccion
        ↓
la ablacion mide un motor distinto al que tradea (conexion con H17)
```

### POI anclado (H12) / Silver Bullet (H13)
```
modelo simplificado (solo 2 TF reales H4→M15 en v2)   (RAIZ de la brecha B)
        ↓
no hay narrativa HTF cableada al POI                  (H12: C05 missing/partial)
        ↓
cualquier FVG/OB cuenta como entrada sin respaldo padre
        ↓
Silver Bullet (ventana NY + retorno a POI) no modelado (H13: ausencia modulo SB)
        ↓
el motor NO representa la tesis ICT objetivo (libros 18/21/08)
```
Nota: esto es por DISEÑO simplificado (brecha conocida), no un bug de implementación suelto.
La causa raíz es arquitectónica (faltan capas / ancla), no un typo.

### Cap por confianza (H15) + w0_agents (no-op)
```
variantes permisivas generan decenas de miles de senales   (sintoma)
        ↓
se impone MAX_SIGNALS_PER_VARIANT=3000 por confianza desc. (run.py:433-435)
        ↓
el set recortado es el MISMO para muchas variantes         (corte deterministico por conf)
        ↓
13/21 variantes XAUUSD colapsan a idéntico                 (H15: ablacion invalida)
        ↓
w0_agents=0.0 hardcoded (run.py:412)                       (no-op, peso muerto)
        ↓
no se puede aislar el efecto de un filtro                  (H15 conexion H16)
```

### Significancia (H16)
```
abla de 168 celdas sin DSR/PBO                           (run.py no aplica stats_validator)
        ↓
no se sabe si el PF es edge o ruido                       (H16)
        ↓
los resultados no son concluyentes                        (conexion con H15: ablacion ya invalida)
```

### Train/serve skew (H17) + features (H18)
```
dataset_builder usa legacy engine (Stack A emparentado)   (dataset_builder.py:14,234)
        ↓
ML entrena sobre distribucion A
        ↓
produccion evalua con canonico (Stack B) (run_backtest.py:103)
        ↓
el modelo ve features de una distribucion que no vera     (H17 skew)
        ↓
train.py:311-314 fallback "todo numérico" como features   (H18 riesgo leakage)
        ↓
sobreajuste latente + invalida la significancia (H16)
```

### Tests / reproducibilidad (H20) + import cycle (H21) + dead code (H22)
```
tests pesados con auto_download=True (dataset_builder.py:146-161)   (H20)
        ↓
pytest >600s, posible descarga de red
        ↓
sin CI verde rapido ni reproducible

trend_context <-> signals/data ciclo (H21)                    (acoplamiento circular)
        ↓
import fragil

engine.py:160,229 _coerce_ts duplicada / strategy_mtf.py:101-103 no-op (H22)
        ↓
ruido / mantenimiento
```

### XAUUSD en MTF (corolario de H14) — reconfirmado 2026-07-24
```
run_bt_v2_mtf.py excluye XAUUSD
        ↓
comentario actual del script: hang del motor canónico con oro
(el claim viejo "falta M15" está OBSOLETO)
        ↓
data/raw/XAUUSD_M15.parquet YA EXISTE (~4.5 años)   (R5 cerrado; docs/DATA_STATUS.md)
        ↓
bloqueo real = runner/hang o decisión de exclusión, NO descarga de datos
        ↓
A12 no requiere re-bajar M15; requiere re-run + (si v2 mtf) arreglar hang
```

---

## CAUSAS RAÍZ (consolidado)

1. CR-1: Ausencia de fuente única de verdad para geometría de estructura (BOS/CHOCH).
   → H4, H5, H17 (parcial).
2. CR-2: Motor simplificado (2 TF reales, sin ancla HTF).
   → H12, H13.
3. CR-3: Cap determinístico por confianza en ablación.
   → H15, arrastra H16.
4. CR-4: ML entrenado en stack distinto al de producción + allowlist débil.
   → H17, H18, arrastra H16.
5. CR-5: Tests con auto-download + ciclo de import + dead code.
   → H20, H21, H22.
6. CR-6: Filtro de símbolos MTF obsoleto.
   → corolario H14.

---

## GATE DE SALIDA ETAPA 2
Cada hallazgo tiene causa raíz trazada y encadenamiento. Sin causas sin explicar.
Listo para ETAPA 3 (orden de implementación por dependencia).

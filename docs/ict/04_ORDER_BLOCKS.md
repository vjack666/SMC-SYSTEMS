# ICT — Order Blocks y Breaker Blocks

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo.

## 1. Teoría
Un **Order Block (OB)** es la huella que dejan las instituciones al acumular
posición justo antes de un movimiento fuerte: la "última vela contraria" antes
del impulso. Funciona como zona de oferta/demanda no cubierta.

- **OB alcista:** la ÚLTIMA vela BAJISTA antes de un impulso fuerte al alza.
  Actúa como soporte (zona de compra).
- **OB bajista:** la ÚLTIMA vela ALCISTA antes de un impulso fuerte a la baja.
  Actúa como resistencia (zona de venta).

**OB válido (3 características):**
1. **Liquidity sweep:** la vela barre liquidez (rompe el low previo en OB
   alcista / el high previo en OB bajista).
2. **Imbalance:** tras el OB el precio se aleja rápido, dejando FVG.
3. **Unmitigated:** el precio aún no volvió a la zona → órdenes "activas".

**Breaker Block:** si el precio rompe el OB y este luego actúa como
soporte/resistencia en sentido contrario, el OB se vuelve **breaker**; confirma
el cambio de estructura.

## 2. Práctica del trader (uso real)
- Esperar el retroceso al OB (o al FVG que dejó el desplazamiento). No entrar en
  la ruptura.
- Entrada en la zona; **SL por fuera del OB** (cierre que invalida la huella).
- Confluencia: **OB + FVG + CHoCH** = setup de alta probabilidad.
- **Multi-TF:** OB en HTF (H1/H4) define zona; entrada en LTF (M15/M5) tras
  CHoCH. Un OB en H1 que coincide con FVG en M15 es de alta calidad.
- **Sesiones:** OB formados en London/NY killzone tienen más peso que en Asian
  (rango).

## 3. Algoritmo (detección automática)
Para una app automática (MQL5 EA / detector Python):
1. Identificar la vela con cuerpo grande (`body_ratio > 0.7`) en dirección
   contraria al impulso.
2. Confirmar followthrough: la siguiente vela cierra por encima del `high`
   (OB alcista) o por debajo del `low` (OB bajista).
3. Marcar el rango `high`/`low` de la vela como zona OB.
4. Seguir validez: el OB sigue "active" hasta que el precio lo cierra (invalida)
   o envejece (no fue tocado en N velas).

**Riesgos:**
- **Look-ahead en followthrough:** usar `close[i+1]` para marcar el OB en la
  vela `i` es legítimo SOLO si la entrada ocurre después (la vela `i+1` ya
  cerró). Si el backtest marca y entra en la misma vela `i`, hay fuga. Ver Sección 5.
- **Mechas vs cuerpo:** la huella se define por el rango `high`/`low` de la vela
  OB, no por el cierre.
- **Chart Shift:** el OB "activo" que ves a la derecha del gráfico en MT5 es el
  vigente; el backtest trabaja sobre datos crudos y no se ve afectado por el
  desplazamiento visual.
- **Profundidad de histórico:** un OB solo es medible si hay velas previas para
  detectar el impulso y la liquidez barrida; pocos años de datos sesgan los OB
  en HTF.

## 4. Código SMC-SYSTEMS (implementación real)
- **Detector:** `detectors/ob.py` → `detect_order_blocks(frame)`
  - `ob_bullish = vela_bajista & cuerpo_grande & (close.shift(-1) > high)`.
  - `ob_bearish = vela_alcista & cuerpo_grande & (close.shift(-1) < low)`.
  - Marca `ob_top`/`ob_bottom` (rango de la huella) y `ob_distance` (distancia
    del cierre al OB más cercano).
  - **Item E — invalidación + envejecimiento:** `_track_ob_validity()` recorre
    vela a vela y marca `ob_status` ∈ {active, invalidated, aged, none} y
    `ob_age`. Un OB "invalidated" es el equivalente automático del OB mitigado
    que rompió; "aged" es uno que caducó sin ser tocado.

- **Pipeline de señales:** `signals/pipeline.py`
  - Combina OB + FVG por proximidad ATR (`ob_fvg_proximity_atr`, default 1.5):
    `filter_ob_fvg` = `((macro BULLISH) & bull_near) | ((macro BEARISH) & bear_near)`.
  - Si `enable_detector_invalidation` está activo, solo considera OB con
    `ob_status` en {active, none} → respeta la invalidación automática.
  - Además usa el OB como ancla para el `bullish_anchor`/`bearish_anchor` del
    filtro direccional.

- **Backtest ICT:** `ict_backtest/`
  - `data_feed.py`: aplica `detect_order_blocks`, expone `ob_direction`.
  - `sequence.py`: usa la zona OB del LTF como entrada cuando hay dirección
    objetivo.
  - `rules.py`: un OB en M5/M1 (`ob_dir`) es confirmación de dirección en la
    rutina EURUSD.

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
- **#1 Look-ahead en swing points (crítico):** el bug estaba en
  `_swing_points`, no en `ob.py`. PERO el OB de `ob.py` usa `close.shift(-1)`
  para el followthrough. Eso es look-ahead potencial: marca el OB en la vela `i`
  usando el cierre de `i+1`. Es correcto SIEMPRE QUE la entrada ocurra en una
  vela posterior (la `i+1` ya cerró). En SMC-SYSTEMS la cadena respeta esto: el
  OB se marca, y el pipeline/filtros operan sobre cierres ya cerrados. Lección:
  el `shift(-1)` en detección de OB es aceptable; el `shift(-1)` en el *filtro de
  entrada* no lo sería. Hay que vigilarlo al leer cualquier backtest.
- **#2 CHOCH real:** el breaker block es la manifestación de un CHOCH sobre un
  OB. Al corregir CHOCH (ya no copia de BOS), los breakers detectados pasaron a
  ser coherentes con el cambio de estructura real.
- **#6 Performance (medio):** el tracking de validez del OB es vela-a-vela en
  Python puro; se recalcula por ventana de walk-forward. No vectorizado (riesgo
  de romper lógica event-driven).

## 6. Resultados medidos
- PF Capa 2: **2.003 → 1.548** tras corregir #1 y #2. El OB participa de la
  cadena (swing → BOS/CHoCH → OB/FVG); su señal hereda la limpieza del fix de
  swings.
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF prom **3.389 ± 2.303**,
  21 trades OOS. El filtro OB+FVG es parte de esa cadena; falta aislar su
  contribución con costos (fix #4 en `optimize.py` `--cost`, no aplicado aún).

## En resumen
El Order Block es la huella institucional previa al impulso; el Breaker es ese
mismo OB tras un cambio de estructura. En SMC-SYSTEMS se detecta por cuerpo
grande + followthrough, se mantiene con estado de validez (active/invalidated/
aged), y se empareja con el FVG por proximidad ATR. Su correcta lectura depende
de que el followthrough no se use como entrada en la misma vela (evitar
look-ahead).

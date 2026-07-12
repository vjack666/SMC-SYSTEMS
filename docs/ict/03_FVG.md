# ICT — Fair Value Gaps (FVG)

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo, no fuentes externas.

## 1. Teoría
Un **FVG** (Fair Value Gap) es un desequilibrio de oferta/demanda: el precio se
mueve tan rápido que deja un rango de precios "no negociado" entre 3 velas
consecutivas. El precio tiende a regresar al FVG para reequilibrarlo (fill the
gap).

**Formación (3 velas):**
- **FVG alcista (imbalance comprador):** el `low` de la vela 3 queda POR
  ENCIMA del `high` de la vela 1 → hueco entre ellas.
- **FVG bajista (imbalance vendedor):** el `high` de la vela 3 queda POR
  DEBAJO del `low` de la vela 1.
- Si las mechas de vela 1 y 3 se solapan → NO hay FVG (no hay hueco real).

El FVG casi siempre acompaña al desplazamiento que confirma un MSS/BOS, y suele
convivir con un Order Block. Funciona como "vacío" que atrae el precio en el
retroceso: zona de entrada en pullback.

## 2. Práctica del trader (uso real)
El trader no persigue el FVG; espera a que el precio lo visite.
1. Tras un **sweep** de liquidez, espera el FVG (señal de desplazamiento real).
2. Entra en el retroceso al FVG (no en la ruptura).
3. **SL:** por debajo del FVG alcista / por encima del FVG bajista.
4. **TP:** liquidez opuesta (BSL si long / SSL si short) o 1:2 mínimo.
5. **Multi-TF:** el FVG en HTF (H4/H1) marca zona de interés; el LTF (M15/M5/M1)
   da la entrada. Un FVG en M15 que coincide con OB en H1 es de alta calidad.
6. **Sesiones:** los FVG que se forman en killzone (London 02:00–05:00 / NY
   08:30–11:00 local US) tienen más probabilidad de ser respetados.

**Mitigado vs no mitigado:**
- **No mitigado (unfilled):** el precio aún no volvió → sigue "activo" como zona.
- **Mitigado:** el precio ya lo tocó → pierde fuerza como entrada, pero confirma
  que la zona fue real.

## 3. Algoritmo (detección automática)
Para una app automática (indicador/EA en MQL5 o detector en Python) el FVG se
calcula vela a vela sobre velas **ya cerradas**:
- `fvg_bullish = low[i] > high[i-2]`
- `fvg_bearish = high[i] < low[i-2]`
- `fvg_size = low[i] - high[i-2]` (alcista) o `low[i-2] - high[i]` (bajista).

**Riesgos que todo detector debe evitar:**
- **Look-ahead:** usar `high[i+1]`/`low[i+1]` (vela futura) para marcar el FVG en
  la vela `i`. La detección debe usar solo `i` y `i-2` (cerradas). Ver Sección 5.
- **Mechas vs cuerpo:** al igual que en BOS/CHoCH, la regla debe ser coherente.
  SMC-SYSTEMS usa los extremos `high`/`low` (el hueco real del rango), no el
  cierre.
- **Chart Shift:** si en MT5 activás "Chart Shift" (desplazamiento del gráfico,
  10–50%), el FVG que ves "a la derecha" es el actual; los históricos no cambian,
  pero tu lectura visual del "último FVG activo" sí. El backtest no depende de
  Chart Shift (trabaja sobre datos crudos), lo cual es correcto.
- **Profundidad de histórico:** un FVG sólo es confiable si la vela 1 e i-2 caen
  dentro del rango cargado. Con pocos años de datos, los FVG en HTF quedan
  sesgados al periodo visible.

## 4. Código SMC-SYSTEMS (implementación real)
Rutas de archivo reales del repo:

- **Detector:** `detectors/fvg.py` → `detect_fvg(frame)`
  - Vectorizado con `shift(2)`: `fvg_bullish = low > high.shift(2)`.
  - Calcula `fvg_size`, `fvg_mid` (punto medio del hueco) y `fvg_fill_status`.
  - `_track_fvg_fill()` recorre vela a vela y marca `bullish_unfilled` /
    `bearish_unfilled` / `just_created` / `none` según si el precio ya volvió al
    hueco. O sea implementa la noción de "mitigado vs no mitigado" de la teoría.
  - **No usa velas futuras** → no tiene look-ahead (ver auditoría #1).

- **Pipeline de señales:** `signals/pipeline.py`
  - Combina OB + FVG por proximidad: `ob_fvg_proximity_atr` (default 1.5 ATR).
    Solo deja pasar si el cierre está cerca del último ancla OB/FVG y la
    `macro_direction` coincide (Item D del rulebook).
  - Filtro `filter_ob_fvg` = `((macro BULLISH) & bull_near) | ((macro BEARISH) & bear_near)`.
  - El FVG no es filtro aislado: vive emparentado al OB y a la dirección macro.

- **Backtest ICT:** `ict_backtest/`
  - `data_feed.py`: aplica `detect_fvg` y expone `fvg_state` (bullish/bearish/-).
  - `sequence.py`: `_latest_fvg_zone()` usa el `fvg_state` del LTF (M5/M1) como
    zona de entrada cuando hay dirección objetivo.
  - `rules.py`: un FVG en M5 o M1 (`fvg_state`) es confirmación de dirección en
    la rutina EURUSD (M15>M5>M1).

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
De `docs/ict/10_AUDITORIA_REFACCION/`:
- **#1 Look-ahead en swing points (crítico):** el bug estaba en
  `_swing_points` de `market_structure.py` (ventana centrada + `.ffill()`), NO
  en el FVG. El FVG de `detectors/fvg.py` usa solo `shift(2)` sobre velas
  cerradas, por lo que **no sufre ese bug**. Lección: el FVG es seguro frente a
  look-ahead; los swings no lo eran hasta el fix. Esto es clave al leer un
  backtest: un edge basado en FVG solo es tan limpio como el swing que lo
  confirma.
- **#6 Performance (medio):** `sequence.py` corre vela-a-vela en Python puro
  (~8 min / 50k velas). El FVG se recalcula por ventana de walk-forward; no se
  vectorizó para no romper la lógica event-driven. Documentado para la siguiente
  fase.

## 6. Resultados medidos
- El PF de Capa 2 cayó de **2.003 → 1.548** tras corregir look-ahead (#1) y
  CHOCH real (#2) en la auditoría 2026-07-11. El FVG no fue la causa del descenso
  (su detector ya era limpio), pero el edge global comparte la misma cadena de
  confirmación (swing → BOS → FVG/OB), así que cualquier señal que use FVG se
  beneficia del fix de los swings.
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF promedio **3.389 ±
  2.303**, solo 21 trades OOS totales. El filtro OB+FVG participa de esa cadena;
  falta medir su contribución aislada con costos (fix #4 cableado en
  `optimize.py` vía `--cost` pero no aplicado en la corrida final).

## En resumen
El FVG es el "vacío" que el precio rellena. En SMC-SYSTEMS se detecta por
`shift(2)` sobre velas cerradas (sin look-ahead), se empareja con OB por
proximidad ATR, y se usa como zona LTF en la secuencia de backtest. Su calidad
depende de los swings que lo confirman: por eso el fix de look-ahead (#1) importa
tanto para cualquier señal que pase por FVG.

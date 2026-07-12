# ICT — Power of Three (PO3 / AMD model)

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo.

## 1. Teoría
Modelo que describe el ciclo del precio en 3 fases (también AMD:
Accumulation-Manipulation-Distribution). Explica POR QUÉ el precio barre
liquidez antes del movimiento real.

**Fases:**
1. **Accumulation (acumulación):** rango lateral de baja volatilidad cerca de
   soporte/resistencia. Se construye la liquidez (stops se apilan fuera del rango).
2. **Manipulation (manipulación / liquidity sweep):** el precio rompe el rango
   para cazar stops (stop hunt / false breakout) y cierra de vuelta adentro.
   - Alcista: sumerge bajo el rango (barre SSL).
   - Bajista: dispara sobre el rango (barre BSL).
3. **Distribution (expansión):** el precio rompe la estructura y se extiende en la
   dirección real con velas fuertes. Es el movimiento que paga.

## 2. Práctica del trader (uso real)
1. Definir **sesgo del día** en TF mayor (H4/D1).
2. Marcar el **open del día** como nivel de referencia.
3. Identificar la **manipulación** más allá del open/rango (barrido de liquidez).
4. Confirmar entrada en TF menor (M5/M15) con **CHoCH** o ruptura de estructura.
5. Gestionar con SL por fuera del extremo de manipulación.

**Confirmación de distribución:** velas direccionales de cuerpo grande, ruptura
decisiva del rango, expansión de volumen, alineación con TF mayor.

## 3. Algoritmo (detección automática)
PO3 no es un detector aislado: es el "relato" que une tres detectores ya
existentes:
- **Manipulation** = sweep de liquidez (`detectors/liquidity.py` para zonas;
  `detectors/bos.py` + `pipeline.py` para el sweep filtrado).
- **Confirmación de entrada** = CHoCH/MSS (`detectors/choch.py`, `bos.py`).
- **Zona de retorno** = FVG / Order Block (`detectors/fvg.py`, `ob.py`).
- **Sesgo** = tendencia HTF (EMA / `trend.py`).

Riesgo de look-ahead: la confirmación de distribución (CHoCH) debe usar velas
cerradas (fix #1); no anticipar la ruptura.

## 4. Código SMC-SYSTEMS (implementación real)
- **Detectores:** `choch.py` (CHoCH), `bos.py` (BOS + sweep), `fvg.py`/`ob.py`
  (zonas), `trend.py` (sesgo), `liquidity.py` (BSL/SSL).
- **Regla de backtest:** `ict_backtest/rules.py`
  - `evaluate(model="intradia", counter_trend=...)` agrupa **PO3 / Turtle Soup**
    (H1/H4/M15). El checklist intradia requiere sweep M15 + FVG M1/M5 + dirección
    + SL en FVG/OB + RR 1:2. O sea PO3 se materializa como la misma secuencia que
    Turtle Soup, pero con énfasis en la manipulación previa al open del día.
- **En vivo:** la pestaña Principal narra "sesgo D1 + sweep de SSL + CHoCH M15 =
  PO3 alcista". El motor ya calcula sesgo D1/H4 (`rutina_eurusd.py`) + sweep +
  CHoCH.

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
- **#1 Look-ahead (crítico):** la fase de distribución (CHoCH que confirma PO3)
  sufría el bug de `_swing_points`. Tras el fix (ventana NO centrada + desplazar
  `lookback`), la confirmación de expansión ya no se anticipa. PF 2.003 → 1.548.
- **#2 CHOCH real:** PO3 necesita un CHoCH genuino tras la manipulación. Antes
  `choch_dir = bos_dir` (copia), así que la "expansión" podía ser continuación
  disfrazada. Al corregir, el PO3 alcista tras barrido de SSL es real.
- **#5 Walk-forward real:** la dirección temporal del walk-forward se corrigió
  para ir de pasado→futuro; PO3 se valida en esa ventana, no en datos vistos.

## 6. Resultados medidos
- PF Capa 2: **2.003 → 1.548** (corregir #1 y #2). PO3 es la narrativa de la
  cadena completa; hereda la limpieza.
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF prom **3.389 ± 2.303**,
  21 trades OOS. PO3 participa de la cadena intradia; falta aislar contribución
  con costos (fix #4 `--cost`, no aplicado).

## En resumen
Power of Three explica el ciclo acumulación→manipulación→distribución. En
SMC-SYSTEMS no es un detector aparte: es la unión de sweep (`bos.py`/`pipeline`),
CHoCH (`choch.py`), zonas (`fvg.py`/`ob.py`) y sesgo (`trend.py`), materializada
en `ict_backtest/rules.py` como modelo intradia. Su validez depende del fix de
look-ahead (#1) y del CHOCH real (#2): sin ellos, la "distribución" era
continuación anticipada.

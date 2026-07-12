# ICT — Turtle Soup (Reversión contra tendencia)

> Tesis (RFC-001 / ADR-021): Teoría → Práctica del trader → Algoritmo →
> Código SMC-SYSTEMS → Auditoría → Resultados medidos. Fuente de verdad: el
> código y las auditorías del repo.

## 1. Teoría
Estrategia de **reversión** que aprovecha falsas rupturas en zonas de liquidez de
TF mayor. Es el modelo clásico de **CONTRA TENDENCIA** en ICT. El mercado "hace
sopa" a los que esperaban la continuación: rompe la liquidez y revierte.

## 2. Práctica del trader (uso real)
1. En TF mayor (H1/H4) marca BSL y SSL (máximos/mínimos recientes, prev day/week
   high/low, equal highs/lows).
2. En TF menor (M15/M5) esperar **sweep** de esa liquidez.
3. Tras el sweep, esperar un **MSS/CHoCH** en dirección opuesta.
4. Entrar tras el MSS (o en el retroceso a OB/FVG).

**Setups:**
- **Turtle Soup alcista:** SSL en TF mayor → en menor, sweep de SSL + MSS alcista
  → long. SL bajo el SSL; TP en el BSL más cercano de TF mayor.
- **Turtle Soup bajista:** BSL en TF mayor → en menor, sweep de BSL + MSS bajista
  → short. SL sobre el BSL; TP en el SSL más cercano.

**Tipos:**
- **External Range:** precio sale del rango y revierte (reversión pura).
- **Internal Range:** el mercado ya tiende y hace pullback (continuación, a favor).

**Notas del trader:** no es obligatorio esperar MSS — se puede entrar en el
retroceso a OB/FVG tras el sweep. Si operas ≤ M15 usa H1 para marcar liquidez; si
operas H1 usa H4+.

## 3. Algoritmo (detección automática)
- El sweep se detecta como en `05_LIQUIDEZ` (ruptura + reversión en la vela).
- El MSS/CHoCH opuesto se confirma con `bos.py`/`choch.py`.
- La "contra tendencia" = `bos_dir` del exec TF es opuesto a la tendencia del HTF.
- Riesgo de look-ahead: el MSS debe confirmarse con velas cerradas (ver auditoría
  #1 en `02_MSS_CHOCH`); el sweep usa high/low/close de la vela actual (sin fuga).

## 4. Código SMC-SYSTEMS (implementación real)
- **Detectores:** `detectors/bos.py` + `detectors/choch.py` (MSS/CHoCH),
  `detectors/liquidity.py` (BSL/SSL).
- **Regla de backtest:** `ict_backtest/rules.py`
  - `evaluate(model="intradia", counter_trend=True)` agrupa PO3 / Turtle Soup
    (H1/H4/M15).
  - Checklist INTRADIA (líneas ~180-229): requiere **sweep M15** presente, **FVG
    en M1/M5** tras el sweep, **dirección del setup** (LONG/SHORT), **SL en
    FVG/OB**, y **RR 1:2** saliendo en liquidez opuesta.
  - `ready = True` solo si no hay items bloqueantes (`FALTA:`); los `PENDIENTE`
    son de ejecución (no bloquean la señal).
  - Smoke test (`__main__`) muestra un ejemplo LONG con sweep_up M15 + FVG M5.
- **Señal en vivo:** la pestaña Principal etiqueta "CONTRA TENDENCIA (Turtle
  Soup)" cuando `bos_dir` M15 es opuesto a la tendencia D1 Y hay sweep de la
  liquidez opuesta. TP sugerido = liquidez opuesta (de `liquidity.py`).

## 5. Auditoría (cómo los hallazgos afectaron la implementación)
- **#1 Look-ahead (crítico):** el MSS/CHoCH que confirma el Turtle Soup sufría el
  bug de `_swing_points` (ventana centrada + ffill). Tras el fix (desplazar
  `lookback` velas, ventana NO centrada), el MSS se confirma solo cuando la vela
  de confirmación cerró → la reversión Turtle Soup ya no se "anticipa". Esto bajó
  el PF de 2.003 → 1.548, pero el edge quedó honesto.
- **#2 CHOCH real:** antes `choch_dir` era copia de `bos_dir`, así que un Turtle
  Soup "alcista contra tendencia" podía dispararse con lógica de continuación. Al
  corregir CHOCH (real, opuesto a BOS cuando procede), la reversión es genuina.
- **#6 Performance:** el checklist corre en Python puro; barato frente a
  `sequence.py`.

## 6. Resultados medidos
- PF Capa 2: **2.003 → 1.548** (corregir #1 y #2). Turtle Soup hereda la limpieza.
- Walk-forward OOS (4 folds, EURUSD M15, SIN costos): PF prom **3.389 ± 2.303**,
  21 trades OOS. El modelo intradia (PO3/Turtle Soup) participa de la cadena; falta
  aislar su contribución con costos (fix #4 `--cost`, no aplicado).

## En resumen
Turtle Soup es la reversión ICT tras un sweep de liquidez + MSS opuesto. En
SMC-SYSTEMS se materializa en `ict_backtest/rules.py` como checklist intradia
contra tendencia (sweep M15 + FVG M1/M5 + SL en FVG/OB + RR 1:2). Su correcta
detección depende del fix de look-ahead (#1) y del CHOCH real (#2): sin ellos, la
"reversión" era continuación disfrazada.

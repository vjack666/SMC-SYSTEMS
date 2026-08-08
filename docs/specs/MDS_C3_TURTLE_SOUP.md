# MDS — Turtle Soup (contratendencia / reversión) (SPEC §18, libro 06)

**Clasificación:** OBLIGATORIO (1 de 3 setups del ciclo PO3) · **Fase:** C3 · **Estado:** 🔄 REESCRITO a geometría+volumen cero indicadores y rescate a `engine/`
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §18 · **Roadmap maestro:** §9 (Turtle Soup)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.
**Arquitectura:** módulo PERMANENTE en `engine/turtle_soup.py`; `ict_backtest/` solo lo CONSUME.

---

## 1. Título + Clasificación

Software Design Doc — **Turtle Soup: barrido de PDH/PDL del día previo + reversión (contratendencia)**.
Obligatorio · Fase C3 · Estado: rescate de `ict_backtest/setups/turtle_soup.py` a `engine/turtle_soup.py`.

## 2. Propósito

Turtle Soup es un setup de **reversión**: cuando el precio rompe el máximo/mínimo del día anterior
(PDH/PDL) — el "stop hunt" de otros traders — y luego **revierte** en la dirección del trade, se entra
EN CONTRA de la ruptura fallida. El módulo detecta la rotura del extremo previo y el displacement de
retorno, y anota la señal. No es continuación: es reversión contra la marea (SPEC §18, tesis 20 §4).

## 3. Por qué importa (geometría de mercado, sin indicadores)

Turtle Soup es geometría pura de **liquidez y estructura**: (1) el precio barre el PDH (short) o PDL
(long) del día previo — sweep de stops — y (2) el cuerpo de las velas siguientes se invierte con
displacement fuerte en la dirección del trade. Cero indicadores técnicos (EMA/RSI/ATR/MACD/Bollinger).
La validez nace de la *secuencia geométrica* "ruptura falsa → reversión", falsable en backtest sobre OHLC.

## 4. Entradas (datos geométricos + VOLUMEN como único extra permitido)

- **`sweep_ts`**: timestamp de la vela de sweep (str / pd.Timestamp) — la que rompe PDH/PDL.
- **`direction`**: `+1` LONG (busca barrer **PDL** por debajo) / `-1` SHORT (busca barrer **PDH** por encima).
- **`frames`**: `dict[str, pd.DataFrame]` por TF; debe contener `ltf` (donde se lee el sweep). Columnas OHLC.
- **`ltf`**: timeframe del setup (p.ej. `"M15"`).
- **OHLC por TF**: `high`/`low` de cada vela para medir PDH/PDL del día previo y la ruptura; `open`/`close`
  para medir el cuerpo del displacement de reversión.
- **Solo entra en CONTRA del sesgo HTF** (BOS/CHOCH va contra la marea; SPEC §18 CRIT). Si está alineado al
  HTF → es PO3 (§19), NO Turtle Soup.
- **VOLUMEN (tick volume, único extra permitido):** confirma que la ruptura y la reversión tuvieron
  participación real — ver §10.

## 5. Lógica (geometría pura, cero indicadores)

Patrón ICT sobre geometría (fiel a `ict_backtest/setups/turtle_soup.py`):

1. **`_prev_day_ohlc(frames, ltf, sweep_ts)`**: calcula PDH = `max(high)` y PDL = `min(low)` de TODAS las velas
   cuyo día es **estrictamente anterior** al día del sweep. Sin día previo → no hay Turtle Soup.
2. **`_sweep_broke(sweep_row, meta_pd, direction)`**:
   - LONG (`+1`): barre PDL si `sweep_row.low < pdl`.
   - SHORT (`-1`): barre PDH si `sweep_row.high > pdh`.
   Devuelve `(broke_pdh, broke_pdl)`.
3. **`_has_reversal(df_ltf, sweep_idx, direction)`**: en las ~20 velas posteriores al sweep, busca un **cuerpo**
   (`close - open`) fuerte en la dirección del trade: `body > 0.6 * rango_promedio_local` (rango = `high - low`).
   Reversión alcista ⇒ cuerpo positivo; bajista ⇒ cuerpo negativo. Umbral para no confundir ruido con displacement.
4. **`is_turtle_soup`**: `confirmed = broke and reversal`. Devuelve `(confirmed, meta)`.
5. **Principio Brecha D:** `flag_turtle_soup` solo **anota** `turtle_confirmed` / `turtle_broke` (atributos
   dinámicos) en cada `ICTSignal`; no descarta señales (quien consuma decide).

Firma propuesta (rescatada a `engine/turtle_soup.py`):

```python
def _prev_day_ohlc(frames, ltf, sweep_ts) -> dict | None:
    """PDH/PDL del DIA PREVIO al de sweep_ts en frames[ltf]."""
    ...

def _sweep_broke(sweep_row, meta_pd, direction) -> tuple[bool, bool]:
    pdh, pdl = meta_pd["pdh"], meta_pd["pdl"]
    low, high = float(sweep_row["low"]), float(sweep_row["high"])
    broke_pdl = direction == 1 and low < pdl
    broke_pdh = direction == -1 and high > pdh
    return bool(broke_pdh), bool(broke_pdl)

def _has_reversal(df_ltf, sweep_idx, direction) -> bool:
    """Displacement opuesto AL sweep en ~20 velas (reversion)."""
    end = min(len(df_ltf), sweep_idx + 21)
    window = df_ltf.iloc[sweep_idx:end]
    avg_rng = float((window["high"] - window["low"]).mean(skipna=True)) or 1e-6
    body = (window["close"] - window["open"]).to_numpy(dtype=float)
    if direction == 1:
        return bool(np.any(body > 0.6 * avg_rng))
    return bool(np.any(body < -0.6 * avg_rng))

def is_turtle_soup(sweep_ts, direction, frames, ltf="M15") -> tuple[bool, dict]:
    meta = {"ts_broke_pdh": False, "ts_broke_pdl": False, "ts_reversal": False}
    ...
    prev = _prev_day_ohlc(frames, ltf, ts)
    if prev is None:
        return False, meta
    broke_pdh, broke_pdl = _sweep_broke(df_ltf.iloc[sweep_idx], prev, direction)
    meta["ts_broke_pdh"], meta["ts_broke_pdl"] = broke_pdh, broke_pdl
    if broke_pdh or broke_pdl:
        meta["ts_reversal"] = _has_reversal(df_ltf, sweep_idx, direction)
    return bool((broke_pdh or broke_pdl) and meta["ts_reversal"]), meta

def flag_turtle_soup(signals, frames, ltf="M15") -> list:
    """Anota sig.turtle_confirmed / sig.turtle_broke (dinamico). NO edita ICTSignal."""
    ...
```

## 6. Salidas (bool confirmado + metadata)

`is_turtle_soup(...) -> (bool, dict)` con
`meta = {"ts_broke_pdh": bool, "ts_broke_pdl": bool, "ts_reversal": bool}`.
`flag_turtle_soup` devuelve la lista de `ICTSignal` mutada in-place con `turtle_confirmed: bool` y
`turtle_broke: bool` (= `ts_broke_pdh or ts_broke_pdl`).

## 7. Integración: rescatarse a `engine/` y consumirse desde `ict_backtest` (nunca al revés)

- **Origen hoy:** `ict_backtest/setups/turtle_soup.py` (`is_turtle_soup`, `flag_turtle_soup`, helpers).
- **Destino PERMANENTE:** `engine/turtle_soup.py`. El motor importa de aquí.
- **Consumo:** `ict_backtest/` (backtest desechable) importa `engine.turtle_soup` para anotar señales.
- **Ley Fundamental:** `engine/` **NUNCA** importa `ict_backtest/`. `engine/turtle_soup.py` importa solo
  `pandas` / `numpy` y `engine` local; NO `ict_backtest`.
- El módulo **NO edita** `ICTSignal` (dataclass estable); usa atributos dinámicos.
- Alineación contratendencia: quien consuma debe exigir `direction` opuesta al sesgo HTF (ver SPEC §18 CRIT);
  esto se resuelve en el motor con `top_down_allows_trade(..., counter_trend=True)`, no dentro de este módulo.

## 8. Anti-look-ahead (solo velas con `time <= t`)

- El sweep se resuelve por índice contra `frames[ltf]` usando `time <= ts` (la vela de sweep ya cerró).
- `_prev_day_ohlc` solo usa velas con día **estrictamente anterior** al del sweep (nunca el día actual ni futuro).
- `_has_reversal` mira solo velas **posteriores al sweep_idx** hasta +20 (todas ya cerradas en backtest).
- No se usa el reloj de la PC ni ninguna vela con `time > t`.

## 9. Verificación (pytest con datos sintéticos)

Pruebas con `frames` sintéticos (sin datos reales):

- Día previo con PDH=1.1000 / PDL=1.0900; vela de sweep `high=1.1010` (rompe PDH) + cuerpo bajista fuerte
  en +3 velas → SHORT `is_turtle_soup(...) == (True, {ts_broke_pdh:True, ts_reversal:True})`.
- Igual pero `low=1.0890` (rompe PDL) + cuerpo alcista → LONG `(True, {ts_broke_pdl:True, ts_reversal:True})`.
- Sweep rompe PDH pero NO hay reversión (cuerpos pequeños) → `(False, {ts_broke_pdh:True, ts_reversal:False})`.
- Sin día previo (solo 1 día de velas) → `(False, meta todo False)`.
- `flag_turtle_soup` anota `turtle_confirmed`/`turtle_broke` correctamente por señal.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 10. Notas de volumen (cómo el volumen ayuda sin ser indicador)

El tick volume es el único dato extra permitido y se usa **solo como confirmación de participación**,
no como indicador derivado:

- **Vela de ruptura (sweep):** volumen de la vela que rompe PDH/PDL debe ser **superior al promedio local**
  ⇒ la ruptura fue un stop hunt real con flujo institucional, no una mecha sin interés.
- **Velas de reversión:** el displacement de retorno con volumen presente confirma que la reversión tiene
  seguimiento (no un simple pullback sin convicción).
- **NO** se usa EMA de volumen, OBV, ni osciladores. Solo el conteo crudo de ticks comparado con el promedio
  de la ventana — geometría de actividad, no indicador.

## Trazabilidad

SPEC §4 · §18 (Turtle Soup, CRIT contratendencia) · §19 (PO3, continuación) · libro 06 · ROADMAP §9 ·
`ict_backtest/setups/turtle_soup.py` (fuente real) · MDS_KILLZONES_L_NYPM (killzone, trazabilidad) ·
PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md (counter_trend en top_down).

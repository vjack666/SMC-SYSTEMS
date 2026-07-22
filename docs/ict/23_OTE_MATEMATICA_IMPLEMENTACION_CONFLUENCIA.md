# 23. OTE (Optimal Trade Entry) — Matemática, Implementación y Confluencia

**Fuente de verdad proyecto:**  
- `ict_backtest/setups/ote.py`  
- `ict_backtest/engine.py`  
- `ict_backtest/canonical.py`  
- `ict_backtest/market_structure.py`  
- `docs/ict/04_ORDER_BLOCKS.md`  
- `docs/ict/10_SWEEP_OTE_FILTRO.md`  

**Estado actual:**  
`ote.py` tiene implementación aislada (`ote_zone`, `is_ote_entry`, `flag_ote`).  
Falta wiring a `canonical.evaluate_signals` y mapeo oficial de campos en `ICTSignal`.  
Este capítulo cierra esa brecha con precisión matemática y contrato de integración.

---

## 1) Teoría ICT

### 1.1 Qué es OTE

En la metodología ICT, el **Optimal Trade Entry** no es “cualquier retroceso”. Es la zona con **probabilidad estadísticamente mayor** de que el precio visite la pierna impulsiva previa antes de reanudar la tendencia.

ICT lo ubica típicamente en el **61.8%–78.6%** de Fibonacci de la pierna previa.  
Ese rango no es místico: resume zonas donde institucionales suelen buscar liquidez antes del squeeze final.

### 1.2 Por qué importa en este proyecto

- Ya detectamos BOS/CHOCH, FVG, Order Blocks y Breaker/MMXM.  
- **Falta confirmar que la entrada tenga calidad de precio.**  
- OTE **no reemplaza** setup detection; actúa como **bonus de confluencia** y como **filtro suave de timing**.
- Principio Brecha D: OTE **metadata only**, no gate hard por defecto.

---

## 2) Matemática detallada

### 2.1 Ratios Fibonacci aplicados

```
Fib profundidad = (cap_price - entry_price) / (cap_price - leg_low)   # LONG
```

ICT usa **61.8%** y **78.6%** porque:

- **61.8%** = 1 / φ² ≈ 0.618034, inverso del golden ratio al cuadrado. Es el primer retroceso estructural fuerte.
- **70.5%** ≈ (61.8% + 78.6%) / 2. ICT lo citó como “sweet spot” porque sintetiza el punto medio de agotamiento.
- **78.6%** = raíz cuadrada de 0.618 ≈ 0.786. Retroceso profundo, casi último refugio antes de invalidación estructural.

Fundamento: en impulsos institucionales, el retroceso suele extremarse hasta la zona donde se acumularon loseseos opuestos (swings). El rango 61.8%–78.6% concentra trips de esa liquidez sin caer en retrace completo (>100%).

### 2.2 Fórmulas exactas

**Definiciones:**
- `swing_low` = mínimo local solución de la pierna impulsiva previa
- `swing_high` = máximo local solución de la pierna previa
- `r = swing_high - swing_low` (rango de la pierna)
- `direction = +1` para LONG, `-1` para SHORT

**Zona OTE LONG (retrace desde el high hacia abajo):**

```
OTE low  = swing_high - 0.786 * r
OTE high = swing_high - 0.618 * r
Zona LONG = [OTE low, OTE high]
```

**Zona OTE SHORT (retrace desde el low hacia arriba):**

```
OTE low  = swing_low + 0.618 * r
OTE high = swing_low + 0.786 * r
Zona SHORT = [OTE low, OTE high]
```

### 2.3 Sweet spot 70.5%

```
OTE 70.5% LONG  = swing_high - 0.705 * r
OTE 70.5% SHORT = swing_low + 0.705 * r
```

Justificación matemática:
- Concentra el centro de masa de la distribución.
- Maximiza distancia al SL estructural y minimiza distancia al TP.
- Minimiza probabilidad de “fakeout” por micro-retrace dentro de la pierna.

### 2.4 Ejemplo numérico completo

**Caso EURUSD pierna impulsiva previa:**

```
swing_low  = 1.0920
swing_high = 1.1025
r = 1.1025 - 1.0920 = 0.0105 = 105 pips
```

**Long OTE band:**

```
OTE low  = 1.1025 - 0.786 * 0.0105 = 1.094191
OTE high = 1.1025 - 0.618 * 0.0105 = 1.096011
Zona 61.8-78.6% = [1.094191, 1.096011]
```

**Sweet spot 70.5%:**

```
1.1025 - 0.705 * 0.0105 = 1.095102
```

Suposición: entry llega en `1.09510`. Dado direction=+1, `entry ∈ [1.094191, 1.096011]` → OTE confirmada.

---

## 3) Implementación en código (Python)

### 3.1 Contrato oficial

**Ubicación:** `ict_backtest/setups/ote.py`

Funciones canónicas:
- `ote_zone(swing_high, swing_low) -> (ote_low, ote_high)`
- `is_ote_entry(entry_price, swing_high, swing_low, direction) -> (bool, dict)`
- `flag_ote(signals, frames, ltf) -> list`

Principios:
- **sin ATR**, **sin indicadores**.
- No cambia `entry/SL/TP`.
- No filtra señales sin OK explícito.
- Si `swing_high/low` ausentes → `ote_confirmed=False`, no inventa.

### 3.2 Código base existente (reutilizar, no duplicar)

```python
# ict_backtest/setups/ote.py
OTE_FIB_LOW = 0.618
OTE_FIB_HIGH = 0.786

def ote_zone(swing_high: float, swing_low: float) -> tuple[float, float]:
    r = float(swing_high) - float(swing_low)
    ote_high = float(swing_high) - OTE_FIB_LOW * r
    ote_low = float(swing_high) - OTE_FIB_HIGH * r
    return ote_low, ote_high

def is_ote_entry(entry_price, swing_high, swing_low, direction):
    r = float(swing_high) - float(swing_low)
    if r <= 0:
        return False, {"ote_confirmed": False, "reason": "r<=0"}
    if direction == 1:
        ote_low = float(swing_high) - OTE_FIB_HIGH * r
        ote_high = float(swing_high) - OTE_FIB_LOW * r
    else:
        ote_low = float(swing_low) + OTE_FIB_LOW * r
        ote_high = float(swing_low) + OTE_FIB_HIGH * r
    confirmed = (ote_low <= float(entry_price) <= ote_high)
    meta = {"ote_confirmed": confirmed, "ote_low": ote_low, "ote_high": ote_high, "leg_range": r}
    return confirmed, meta
```

### 3.3 Integración con BOS / OB / FVG / Breaker (sin duplicar)

**Regla fundamental:** OTE **no reemplaza** BOS/OB/FVG/Breaker.

```
entry_at -> detect_market_structure(ltf_df)[entry_at]
           -> _swing_for_signal(sig, ltf_df) -> swing_high/low
           -> is_ote_entry(sig.entry, swing_high, swing_low, sig.direction)
           -> anotar en ICTSignal.ote_confirmed / ote_zone
```

**Nunca uses OTE como único gatillo.**  
Usalo como confirmación de calidad cuando:

- El setup viene desde BOS + CHOCH,
- y además hay un Order Block o FVG en consenso,
- o hay Breaker/MMXM activo.

### 3.4 Wiring canónico recomendado

```python
# ict_backtest/canonical.py, solo lectura sin mutar upstream.
if raw_sigs:
    from ict_backtest.setups.ote import flag_ote
    raw_sigs = flag_ote(raw_sigs, {"M15": ltf_df, **frames}, ltf=ltf)
```

Luego, al armar `ICTSignal` en `canonical.py`, copiar metadatos:

```python
OTE_CONFIRMED = sig.get("ote_confirmed") if isinstance(sig, dict) else getattr(sig, "ote_confirmed", None)
OTE_ZONE      = sig.get("ote_zone")      if isinstance(sig, dict) else getattr(sig, "ote_zone", None)

signals.append(
    ICTSignal(
        ...
        ote_confirmed=OTE_CONFIRMED,
        ote_zone=OTE_ZONE,
    )
)
```

---

## 4) Reglas de confluencia

### 4.1 Cuándo aceptar una señal OTE

| Condición | Rol | Acción |
|---|---|---|
| BOS + CHOCH confirmados | setup primario | Aceptar OTE como bonus positivo |
| FVG o Order Block en misma dirección | confluencia zona | Subir puntuación |
| Breaker activo o MMXM no mitigado | solidez estructural | Bonus |
| OTE confirmada | calidad precio | Metadata / observador |
| Sesión killzone válida | sesión | Requerido |
| RR>=1:3 + SL estructural | riesgo | Requerido |

### 4.2 Stop Loss e invalidación

- OTE **no define SL**.
- SL permanece en **mecánica estructural** (mecha de sweep / OB).
- Si el precio cierra **fuera** de la zona OTE sin activar SL/TP, no invalida entrada; disminuye el bonus.

### 4.3 Cómo evitar entradas falsas

- No entres solo porque `entry ∈ [OTE_low, OTE_high]`.
- Requiere **BOS previo en la dirección del trade**.
- Si no hay CHOCH/MSS reciente, el setup no es OTE: es retrace casual.
- Prioriza OTE cuando la pierna impulsiva tenga:
  - `r >= avg_range * 2` (pierna clara),
  y el retroceso es **primera visita** desde el breakout.

---

## 5) Estado actual en el proyecto

**Archivo:** `ict_backtest/setups/ote.py`  
**Funciones:** `ote_zone()`, `is_ote_entry()`, `flag_ote()`, `_swing_for_signal()`

| Item | Estado | Observación |
|---|---|---|
| Cálculo zona 61.8–78.6% | ✅ | `ote_zone` |
| Detección entry % Fib | ✅ | `is_ote_entry` |
| Flag helper sobre señal | ✅ | `flag_ote` |
| Declaración en `ICTSignal` | ❌ | Usa `setattr`, no tipado oficial |
| `canonical.py` import | ❌ | No llamado en pipeline |
| `pipeline.py` score | ❌ | No exponido como `filter_ote` |

Próximo paso concreto:
1. Agregar `ote_confirmed` y `ote_zone` en `engine.py@ICTSignal`.
2. Llamar a `flag_ote` en `canonical.py` post-run_sequence.
3. Exponer en `signals/pipeline.py` siguiendo patrón `enable_ote_filter=True/False`.

---

## 6) Ejemplo numérico complementario

### 6.1 Short OTE

```
swing_low  = 1.0875
swing_high = 1.1025
r = 0.0150 = 150 pips

OTE low  = 1.0875 + 0.618 * 0.0150 = 1.09677
OTE high = 1.0875 + 0.786 * 0.0150 = 1.09959
Zona SHORT = [1.09677, 1.09959]
Sweet spot = 1.0875 + 0.705 * 0.0150 = 1.098075
```

Si entry=1.09810 y direction=-1, la entrada está en la zona OTE.

### 6.2 Validación código

```python
from ict_backtest.setups.ote import ote_zone, is_ote_entry

# LONG
ote_low, ote_high = ote_zone(1.1025, 1.0920)
assert ote_low == 1.1025 - 0.786*(1.1025-1.0920)
assert ote_high == 1.1025 - 0.618*(1.1025-1.0920)

ok, meta = is_ote_entry(1.09510, 1.1025, 1.0920, direction=1)
ok2, _   = is_ote_entry(1.09370, 1.1025, 1.0920, direction=1) # probable false
```

---

## 7) Checklist R3.5 OTE

- [ ] Declarar `ote_confirmed` y `ote_zone` en `engine.py@ICTSignal`.
- [ ] Mapear metadatos en `canonical.py` cuando construyas `ICTSignal`.
- [ ] Verificar `python -m pytest tests/test_ote_integration.py tests/test_d1_ote.py -q`.
- [ ] Confirmar N unchanged en backtest `no_session` EURUSD M15 12 meses.
- [ ] Publicar prevalence en `docs/METRICS_CANON.md`.

---

## 8) Referencias

- `ict_backtest/setups/ote.py`
- `ict_backtest/engine.py`
- `ict_backtest/canonical.py`
- `ict_backtest/market_structure.py`
- `docs/ict/10_SWEEP_OTE_FILTRO.md`

# 22 — Breaker / MMXM + 23 — OTE: Implementation Guide
## Guía práctica para cerrar Breaker/MMXM y OTE en SMC-SYSTEMS

**Fuente de verdad:**  
`ict_backtest/setups/breaker_block.py`  
`ict_backtest/setups/ote.py`  
`ict_backtest/canonical.py`  
`ict_backtest/engine.py`  
`docs/ict/R3.5_ICT_CANONICAL_GAPS_SDD.md`

**Principios** (obligatorios):
- Brecha D: **no veta entradas por defecto**; anota metadatos.
- Sin ATR / sin indicadores.
- No duplicar lógica existente.
- No tocar `run_sequence` (R7 intacto).

---

## 1) Mapa de código actual

```
ict_backtest/
 └── setups/
      ├── breaker_block.py   # detector standalone + flag helper
      ├── ote.py             # OTE standalone + flag helper
      ├── silver_bullet.py   # referencia de wiring “solo anota”
      └── turtle_soup.py     # referencia de wiring “solo anota”

engine.py
 └── ICTSignal              # flags se setean via setattr o campos declarados

canonical.py
 └── evaluate_signals()     # hook único post-run_sequence -> antes de armar ICTSignal

signals/pipeline.py        # scoring de confluencia (a extender)
```

---

## 2) Breaker/MMXM — wiring paso a paso

### 2.1 Ejemplo mínimo (unitario)

```python
from ict_backtest.setups.breaker_block import (
    is_breaker_block,
    flag_breaker_block,
    _ob_dicts_from_frame,
)

# OHLC + OB columnas
records = [
    {"type": "bearish", "top": 1.1025, "bottom": 1.0990, "start_idx": 4, "end_idx": 4},
]

# close rompe el OB en idx 10: bullish breaker
df.at[10, "close"] = 1.1035
res = is_breaker_block(df, current_idx=10, fvgs=[], obs=records)

print(res)
# {'breaker_active': True, 'breaker_type': 'bullish', 'mitigation_level': 1.1025, 'strength': ...}
```

### 2.2 Call-site esperado en `canonical.py`

```python
from ict_backtest.setups.breaker_block import flag_breaker_block
from ict_backtest.engine import ICTSignal

signals = _build_signals(raw_sigs, ltf_df=ltf_df, ...)
signals = flag_breaker_block(signals, {"M15": ltf_df, **frames}, ltf=ltf)
# Cada signal ahora exponde: breaker_active / breaker_type / mitigation_level / breaker_strength
```

### 2.3 Diagrama flujo

```
run_sequence --> raw_sigs --> _build_signals --> ICTSignal[]
                                                   |
                              flag_breaker_block() |
                              flag_ote()           |
                              flag_smt_*()         V
                                                   ICTSignal[] con metadata
```

### 2.4 Prueba de no regresión (la correcta)

```python
def test_breaker_flag_does_not_change_signal_count_or_sl_tp():
    sigs = evaluate_signals(symbol, htf, ltf, frames=frames)
    before = len(sigs)
    # intentionally do nothing extra; flag already wired inside canonical
    # assert sl/tp unchanged and before==after
```

---

## 3) OTE — wiring paso a paso

### 3.1 Ejemplo mínimo (unitario)

```python
from ict_backtest.setups.ote import ote_zone, is_ote_entry, OTE_FIB_LOW, OTE_FIB_HIGH

swing_high, swing_low = 1.1025, 1.0920
ote_low, ote_high = ote_zone(swing_high, swing_low)
entry = 1.0990
ok, meta = is_ote_entry(entry, swing_high, swing_low, direction=1)

print(ote_high - ote_low)  # rango banda OTE
print(ok, meta["ote_zone"])  # (True/False), (ote_low, ote_high)
```

### 3.2 Regla clave (anti no-op sin evidencia)

```python
# Si OTE no aparece en >= 1% de señales candidatas en EURUSD M15,
# mantener como metadata y publicar prevalence en METRICS_CANON §X.
```

### 3.3 Call-site esperado en `canonical.py`

```python
from ict_backtest.setups.ote import flag_ote

signals = _build_signals(...)
signals = flag_ote(signals, frames, ltf=ltf)

for s in signals:
    assert hasattr(s, "ote_confirmed")
    assert hasattr(s, "ote_zone")
```

---

## 4) SMT Divergence (brecha pendiente) — implementación desde cero

### 4.1 Archivo nuevo

`ict_backtest/setups/smt_divergence.py`

```python
import numpy as np
import pandas as pd

def _normalized(series: pd.Series) -> pd.Series:
    m, s = series.mean(), series.std(ddof=0)
    if s == 0 or not np.isfinite(s):
        return series * 0.0
    return (series - m) / s

def flag_smt_divergence(signals, frames, *, ltf="M15", symbol="", correlator: dict | None=None):
    if not signals or correlator is None:
        return list(signals)
    corr_df = frames.get(correlator.get(ltf, ""))
    if corr_df is None:
        return list(signals)

    base = _normalized(frames[ltf]["close"].reset_index(drop=True))
    corr = _normalized(corr_df["close"].reset_index(drop=True))

    lookback = 40
    res = _smt_diverge(base, corr, lookback)

    for sig in signals:
        sig.smt_divergence_active = bool(res["active"])
        sig.smt_divergence_direction = int(res["direction"])
        sig.smt_divergence_strength = float(res["strength"])
    return signals
```

### 4.2 Prueba mínima

```python
def test_smt_divergence_sync_detects_bullish():
    base = pd.Series([1,2,3,2.9,3.4,3.7,3.6,4.0,3.9,4.2])
    corr = pd.Series([1,1.1,1.2,1.25,1.2,1.15,1.1,1.05,1.0,0.95])
    res = _smt_diverge(base, corr, lookback=8)
    assert res["active"] is True
    assert res["direction"] == 1
```

---

## 5) Modificación mínima en `engine.py` (ICTSignal)

Agregar en la dataclass existente:

```python
breaker_active: bool | None = None
breaker_type: str | None = None
mitigation_level: float | None = None
breaker_strength: float | None = None
ote_confirmed: bool | None = None
ote_zone: tuple[float, float] | None = None
smt_divergence_active: bool | None = None
smt_divergence_direction: int | None = None
smt_divergence_strength: float | None = None
```

---

## 6) Integración final en `canonical.evaluate_signals`

```python
# ...después de run_sequence y antes de filtrar por kz.validate...
# flags como paso POST, resonancia Brecha D:
signals = _build_signals(raw_sigs, ...)
if signals:
    signals = flag_breaker_block(signals, frames, ltf=ltf)
    signals = flag_ote(signals, frames, ltf=ltf)
    if smt_correlator and smt_correlator.get(ltf):
        from ict_backtest.setups.smt_divergence import flag_smt_divergence
        signals = flag_smt_divergence(signals, frames, ltf=ltf, symbol=symbol, correlator=smt_correlator)
return signals
```

`_build_signals` es actor StageBuilder B2 donde armás `ICTSignal` final (o equivalent current canonical internals). La secuencia exacta de líneas la tenés que mapear al helper real en `canonical.py`; lo que define este doc es: **3 helpers, después de sequence, antes de returns`.

---

## 7) Extensiones recomendadas (no bloquean Fase 1)

| Feature | Dónde | Bloquea |
|---|---|---|
| Exposure `breaker_active` en observador | `app_observador/` | No |
| Backtest aislado OTE | `docs/ict/` + script | No |
| SMT correlator configurable | `ict_backtest/config.py` o `ScalpingConfig` | No |
| Agent usage | `agents/ict_agent.py` | No |

---

## 8) Prompts para IA/agente (copy-paste)

1. "Sumar a `ICTSignal` los campos nuevos en `engine.py` sin cambiar comportamiento runtime existente. Tips: mantener defaults `None` y no alterar `simulate_trade`."
2. "Insertar en `canonical.py` las 3 llamadas `flag_*` como paso POST-sequence, con guardas mínimas, sin cambiar `run_sequence` ni requerimientos upstream."
3. "Escribir `ict_backtest/setups/smt_divergence.py` con normalización sigma y divergencia simple de closes por lookback."
4. "Agregar `tests/test_orchestrator_flags.py` con N unchanged y campos presentes en señales resultantes de `evaluate_signals`."

---

## 9) Checklist de tareas (R3.5 accionable)

- [ ] Agregar campos nuevos a `ICTSignal` y verificar py_compile.
- [ ] Crear `smt_divergence.py` + tests unitarios.
- [ ] Modificar `canonical.py` para llamar a `flag_breaker_block`, `flag_ote`, `flag_smt_divergence`.
- [ ] Verificar tests existentes (`test_breaker_block.py`, `test_ote_integration.py`, `test_d1_ote.py`) siguen verdes.
- [ ] Correr `python -m pytest tests/test_breaker_block.py tests/test_ote_integration.py tests/test_d1_ote.py -q`.
- [ ] Correr backtest `no_session` EURUSD M15 12 meses (script nuevo `scripts/r3.5_verify.py`) y registrar flags en METRICS_CANON.md.
- [ ] Actualizar `docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md` (R3.5) y `docs/ict/00_INDICE.md` con libros 21/22/23 si aplica.

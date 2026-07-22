# 22 — Breaker / MMXM + 23 — OTE: Implementation Guide
## Guía accionable para cerrar R3.5 en 2–3 días

**Contexto:** este módulo ya tiene `breaker_block.py` y `ote.py`. Lo que falta es:
1) exponer flags en `ICTSignal`,
2) cablear en `canonical.py` sin tocar `sequence.py`,
3) llevar los mismos metadatos a `signals/pipeline.py`,
4) crear SMT Divergence (nuevo módulo).

**Principios no negociables:**
- **No ATR**, **no indicadores**.
- **No veta entradas por defecto**: solo **metadata/score**.
- **Brecha D/N unchanged**: after wiring, el N de señales debe ser igual al baseline.

---

## 1) Mapa de código (referencia exacta)

| Archivo | Cambio | Línea aproximada |
|---|---|---|
| `ict_backtest/engine.py` | Agregar campos en `ICTSignal` | 21–61 |
| `ict_backtest/canonical.py` | Insertar llamadas flags luego de `run_sequence` | entre 223 y 263 |
| `ict_backtest/engine.py` | Mapear flags en `for s in raw_sigs:` | donde instancia `ICTSignal(...)` |
| `signals/pipeline.py` | Sumar `breaker`/`ote`/`smt` a `confluence_score` | 340–393 |
| `ict_backtest/config.py` | Agregar `enable_breaker_filter`, `enable_smt_filter`, `enable_ote_filter`, `smt_correlator` | todo |
| `ict_backtest/setups/ote.py` | Mantener como está | - |
| `ict_backtest/setups/breaker_block.py` | Mantener como está | - |
| `ict_backtest/setups/smt_divergence.py` | **Nuevo** | - |

---

## 2) WIRING OTE (canonical.py)

`ote.py` ya tiene `flag_ote(signals, frames, ltf)` que anota `ote_confirmed` y `ote_zone`. El doc actual dice que no filtra señales (p. 7–10, 33–38). Esta guía **no cambia esa política**.

Pegá este bloque **después del `run_sequence(...)` y antes del `for s in raw_sigs:`**

```python
# R3.5 OTE + Breaker posterior a run_sequence, conserva secuencia sin cambios.
if raw_sigs:
    from ict_backtest.setups.breaker_block import flag_breaker_block
    from ict_backtest.setups.ote import flag_ote
    _flag_frames = {"M15": ltf_df, **frames}
    raw_sigs = flag_breaker_block(raw_sigs, _flag_frames, ltf=ltf)
    raw_sigs = flag_ote(raw_sigs, _flag_frames, ltf=ltf)

signals: list[ICTSignal] = []
```

Adapter mínimo para instanciar `ICTSignal` con metadata:

```python
for s in raw_sigs:
    ...
    meta_sig = dict(s) if isinstance(s, dict) else asdict(s)
    signals.append(
        ICTSignal(
            symbol=symbol,
            time=str(entry_row["time"]),
            direction=direction,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            model="intradia",
            confidence=_rr_for_raw_signal(s, ltf_df, direction, ltf),
            sweep_at=s["sweep_at"],
            bos_at=s["bos_at"],
            entry_at=entry_at,
            zone_authority=...,
            htf_anchored=...,
            poi_present=...,
            zone_class=...,
            po3_complete=...,
            external_tp=tp_ext,
            # R3.5 flags:
            breaker_active=meta_sig.get("breaker_active"),
            breaker_type=meta_sig.get("breaker_type"),
            mitigation_level=meta_sig.get("mitigation_level"),
            breaker_strength=meta_sig.get("breaker_strength"),
            ote_confirmed=meta_sig.get("ote_confirmed"),
            ote_zone=meta_sig.get("ote_zone"),
        )
    )
```

Ejecutabilidad mínima: corré esto y confirmá que compile y no tires excepción en `build_signals ... --no-cost no_session EURUSD M15 2000` (no hace falta costs ni sesiones para comprobar wiring).

```bash
python -m py_compile ict_backtest/canonical.py ict_backtest/engine.py
python -c "from ict_backtest.canonical import evaluate_signals; print('canonical ok')"
```

---

## 3) WIRING Breaker (canonical.py)

`breaker_block.py` (libro 22) ya define `flag_breaker_block(signals, frames, ltf)` (líneas 241–315) usando `_ob_dicts_from_frame()`.

**No ted:**
- `frames` tiene columnas `ob_bullish`, `ob_bearish`, `ob_top`, `ob_bottom`, `close`, `high`, `low`.
- El campo `breaker_active` se marca solo cuando MMXMitigation no aplica.

Diagrama de flujo:

```
frames[ltf] -> flag_breaker_block -> anota ICTSignal.breaker_active -> signals/pipeline.py scoring -> observador/backtest
```

Validación: checklist:
- [ ] Tests verdes: `python -m pytest tests/test_breaker_block.py -q`.
- [ ] `RAW_SIGS antes de filters == RAW_SIGS después de flags = N unchanged`.
- [ ] `breaker_active` no tiene N distinto.

---

## 4) WIRING `signals/pipeline.py`

En `build_scalping_context()` ya hay `filter_ote`. Sumar `filter_breaker` y `filter_smt_divergence` con el mismo patrón:

```python
if config.enable_ote_filter:
    data["filter_ote"] = ...  # existente
if getattr(config, "enable_breaker_filter", False):
    # Asumimos que llega como columna del contexto o con default True:
    data["filter_breaker"] = data.get("filter_breaker", True)
if getattr(config, "enable_smt_filter", False):
    data["filter_smt_divergence"] = data.get("filter_smt_divergence", True)

# Confluence weights
w = config.confluence_weights
active = {
    ...
    "ote": data["filter_ote"].astype(float) if config.enable_ote_filter else 0.0,
    "breaker": data["filter_breaker"].astype(float) if getattr(config, "enable_breaker_filter", False) else 0.0,
    "smt_divergence": data["filter_smt_divergence"].astype(float) if getattr(config, "enable_smt_filter", False) else 0.0,
}
confluence_score = sum(active[k] * w.get(k, 1.0) for k in active)
```

En `ScalpingConfig`, default conservador: **todos False**, menos `enable_ote_filter=True` si ya estaba acordado.

---

## 5) SMT Divergence (libro 20) — módulo nuevo

`ict_backtest/setups/smt_divergence.py`

```python
import numpy as np
import pandas as pd


def _normalized(s: pd.Series) -> pd.Series:
    m, st = s.mean(), s.std(ddof=0)
    if st == 0 or not np.isfinite(st):
        return pd.Series(np.zeros(len(s), dtype=float), index=s.index)
    return (s - m) / st


def _smt_diverge(base: pd.Series, corr: pd.Series, lookback: int = 40) -> dict:
    b = _normalized(base.iloc[-lookback:].reset_index(drop=True))
    c = _normalized(corr.iloc[-lookback:].reset_index(drop=True))
    b_high_idx = int(b.values.argmax())
    b_low_idx = int(b.values.argmin())
    bullish = bool(b.iloc[-1] > b.iloc[b_high_idx] and c.iloc[-1] < c.iloc[b_high_idx])
    bearish = bool(b.iloc[-1] < b.iloc[b_low_idx] and c.iloc[-1] > c.iloc[b_low_idx])
    return {
        "active": bullish or bearish,
        "direction": 1 if bullish else (-1 if bearish else 0),
        "strength": float(
            abs(b.iloc[-1] - b.iloc[b_high_idx]) if bullish else abs(b.iloc[-1] - b.iloc[b_low_idx])
        ),
    }


def flag_smt_divergence(signals, frames, *, ltf="M15", symbol="", correlator=None):
    if not signals or correlator is None:
        return list(signals)
    if correlator.get(ltf) is None:
        return list(signals)
    base = frames[ltf]["close"].reset_index(drop=True)
    corr_df = frames.get(correlator[ltf])
    if corr_df is None:
        return list(signals)
    corr = corr_df["close"].reset_index(drop=True)
    if len(base) < 2 or len(corr) < 2:
        return list(signals)
    res = _smt_diverge(base, corr, lookback=40)
    for sig in signals:
        sig.smt_divergence_active = bool(res["active"])
        sig.smt_divergence_direction = int(res["direction"])
        sig.smt_divergence_strength = float(res["strength"])
    return signals
```

Call-site en `canonical.py` (cuando `correlator` esté configurado):

```python
        smt_correlator = getattr(config, "smt_correlator", {})
        if smt_correlator and smt_correlator.get(ltf):
            from ict_backtest.setups.smt_divergence import flag_smt_divergence
            raw_sigs = flag_smt_divergence(raw_sigs, {"M15": ltf_df, **frames}, ltf=ltf, symbol=symbol, correlator=smt_correlator)
```

---

## 6) Ejemplo ejecutable de integración completa

Script `scripts/verify_r3.5_flags.py` mínimo:

```python
from ict_backtest.canonical import evaluate_signals
from ict_backtest.engine import ICTSignal

frames = {...}  # loader production o fixture tests
sig = evaluate_signals("EURUSD", "H4", "M15", frames=frames, enable_pd_index=False)
assert sig, "no signals"
s = sig[0]
assert isinstance(s, ICTSignal)
assert hasattr(s, "ote_confirmed")
assert hasattr(s, "breaker_active")
# N unchanged: assert len(sig) == baseline
print({"breaker_rate": sum(1 for s in sig if s.breaker_active), "ote_rate": sum(1 for s in sig if s.ote_confirmed)})
```

Correr:
```bash
python scripts/verify_r3.5_flags.py
python -m pytest tests/test_breaker_block.py tests/test_d1_ote.py tests/test_ote_integration.py tests/test_orchestrator_flags.py -q
```

Resultado esperado: verde, sin cambio en `len(sig)` vs baseline.

---

## 7) Checklist de tareas (prioridad Alta/Media)

1. **Alta** Agregar los 9 campos en `ICTSignal` `engine.py@21-61`.
2. **Alta** Insertar `flag_breaker_block` y `flag_ote` en `canonical.py@` entre `run_sequence` y el for de `ICTSignal`.
3. **Alta** Mapear metadatos en `ICTSignal(...)` en el mismo bucle.
4. **Alta** Sanity N unchanged + py_compile + py -c import.
5. **Alta** Crear `smt_divergence.py` solo cuando Breaker+OTE estén en verde.
6. **Media** Configurar `enable_*_filter` defaults False y `smt_correlator`.
7. **Media** Extender `signals/pipeline.py` con pesos nuevos.
8. **Media** Medir prevalence OTE/MMXM/SMT en `docs/METRICS_CANON.md`.

---

## 8) Prompts listos para IA externa

- **Prompt A (solo wiring OTE+Breaker):**
  "En `canonical.py` agrega, después de `run_sequence` y antes del `for s in raw_sigs`, las llamadas `flag_breaker_block` y `flag_ote` con `ltf_df` y `frames`. Mapea los campos nuevos en `ICTSignal(...)` sin cambiar `entry/SL/TP` ni cantidad de señales."

- **Prompt B (SMT Divergence):**
  "Crea `ict_backtest/setups/smt_divergence.py` que compare series normalizadas del activo target y su correlato por ventana `lookback=40`. No toque engine ni sequence. Solo setea metadatos en señales."

- **Prompt C (pipeline):**
  "Agrega en `signals/pipeline.py` pesos para `breaker`, `ote`, `smt_divergence` usando patrones iguales a `filter_ote`. Respeta defaults False."

---

## 9) Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| tests/m5_verify.py duplicó slot` | Testear primero `tests/test_orchestrator_flags.py`, no modificar tests heredados sin necesidad. |
| `entry_at` ausente | `ote.py` retorna `ote_confirmed=False` sin romper. |
| `smt_correlator` no cargado | `flag_smt_divergence` devuelve `signals` invariante. |
| `was_mitigated` MMXM muy restrictivo | Esperar medida real 12 meses; ajustar sola tolerancia, no lógica. |

---

## 10) Diagrama ASCII

```
 +------------------+     +-----------------------+     +--------------------+
 | frames/ms LTF    | --> | canonical.evaluate()  | --> |  raw_sigs          |
 +------------------+     +-----------------------+     +--------------------+
                                                             |
                  +-----------------+---------------------+------------------+
                  |                 |                     |                  |
           flag_breaker_block   flag_ote         flag_smt_divergence     run_sequence
                  |                 |                     |                  |
                  +-----------------+---------------------+------------------+
                                                             |
                                                    list[ICTSignal] con flags + N unchanged
                                                             |
                                             +---------------+----------------+
                                             | signal_confidence / backtest/observador |
                                             +----------------------------------------+
```

---

## 11) Validación posterior ideal (script)

Agregar en `scripts/r3.5_verify.py` o usar提琴 física rápida:

```bash
python - <<'PY'
from ict_backtest.canonical import evaluate_signals
sig = evaluate_signals("EURUSD", "H4", "M15", frames=...)
print("N:", len(sig))
print("OTE:", sum(1 for s in sig if getattr(s, "ote_confirmed", False)))
print("Breaker:", sum(1 for s in sig if getattr(s, "breaker_active", False)))
PY
```

Si `N` es igual que sin flags, estás listo para gregar SMT Divergence.

---

## 12) Referencias locales

- `ict_backtest/engine.py`
- `ict_backtest/canonical.py`
- `ict_backtest/setups/ote.py`
- `ict_backtest/setups/breaker_block.py`
- `ict_backtest/setups/smart_money.py`
- `signals/pipeline.py`
- `docs/ict/R3.5_ICT_CANONICAL_GAPS_SDD.md`

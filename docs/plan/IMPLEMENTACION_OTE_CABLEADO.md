# IMPLEMENTACION_OTE_CABLEADO.md

**Tarea:** Cierre de trazado de OTE (Optimal Trade Entry) en el motor SMC-SYSTEMS.
**Alcance:** Este documento explica QUÉ hace OTE, CÓMO se conecta al orquestador,
y POR QUÉ no filtra duro (principio Brecha D). También entrega la firma exacta
y los parámetros que un conector humano/usuario debe tocar para completar el
cableado SIN tocar `canonical.py` antes de tiempo.

No se usa ATR ni indicadores en OTE: la zona se calcula exclusivamente con
Fib 0.618–0.786 sobre la pierna (swing high / swing low) del row de entry.

---

## 1. Resumen para humanos (versión "dumi")

### 1.1 ¿Qué es OTE?
- OTE = Optimal Trade Entry. ICT libro 15 / 23.
- Es la **entrada en el retrace profundo** (62%–79% de retroceso de Fibonacci)
  de la **pierna impulsiva previa** (el último swing que llegó al extremo).
- LONG: pierna subió low → high. El retrace baja desde el high hacia abajo:
  `[high - 0.786*r, high - 0.618*r]`.
- SHORT: pierna bajó high → low. El retrace sube desde el low hacia arriba:
  `[low + 0.618*r, low + 0.786*r]`.

### 1.2 ¿Por qué existe OTE aquí?
Los setups actuales (Silver Bullet, Turtle Soup, PO3) usan RR fijo 1:3 o
reglas de killzone. OTE agrega un **criterio adicional de calidad de entrada**
sin tocar entry/SL/TP generados por el motor: solo anota un flag booleano y
una tupla de precios (`ote_zone`).

### 1.3 ¿Cómo se conecta?
Ya existe un módulo aislado: `ict_backtest/setups/ote.py` con funciones puras
`ote_zone()` / `is_ote_entry()` / `flag_ote()`. El call-site real es la lista
de flags post-loop en `canonical.evaluate_signals()`:

```python
from ict_backtest.setups.ote import flag_ote
...
for _fn in (
    lambda s: flag_silver_bullet(s, ltf_df_for_flags),
    lambda s: flag_turtle_soup(s, frames, ltf) if isinstance(frames, dict) else None,
    lambda s: flag_ote(s, frames, ltf) if isinstance(frames, dict) else None,
    lambda s: flag_rr(s),
):
    ...
```

Esa línea **ya está en el código** desde hace commits. Lo que falta (si se
quiere) es exponer `ote_confirmed` / `ote_zone` en UI/scoring/Diagnosis Engine.

### 1.4 ¿Por qué NO filtra duro?
Porque la experiencia medida con POI HTF mostró que un filtro duro **hunde**
el Profit Factor (PF 1.5 → 0.9) descartando justo las señales ganadoras.
El principio Brecha D del proyecto dice: **anota metadato, no veta**.
El consumidor (scoring/E1) decide; el pipeline base produce toda la señal.

---

## 2. Estado actual del trazo

### 2.1 Ya cableado (no tocar)
- `ict_backtest/setups/ote.py` — detector puro, sin ATR, sin indicadores.
- `canonical.evaluate_signals()` — invoca `flag_ote()` en el paso post-loop,
  dentro de un `try/except` silencioso. Si `frames` no es `dict`, se salta.
- `canonical._rr_for_raw_signal()` — Ya consulta `ote_mod.is_ote_entry(...)`
  sobre `ltf_df` y usa el flag para priorizar `rr_for("ote")` = **3.0**.
- `ict_backtest/setups/rr_map.py` — incluye `"ote": 3.0` y la precedencia
  `SB > Turtle > OTE > default`.
- Tests existentes:
  - `tests/test_d1_ote.py` — 8 tests unitarios + 3 call-site reales.
  - `tests/test_orchestrator_setups_wired.py` — acepta que el orquestador
    anota `ote_confirmed` entre los flags.
  - `tests/test_ote_integration.py` — 10 tests nuevos de integración.

### 2.2 Opcional (documentado, no obligatorio para cerrar OTE)
- Exponer OTE en UI del observador / Diagnosis Engine (Fase E).
- Usar `ote_confirmed` / `ote_target_rr` como input de scoring.
- Persistir `ote_zone` en TradeContext para auditoría.

---

## 3. API de `ote.py` (lo que el conector consume)

```python
# ict_backtest/setups/ote.py

OTE_FIB_LOW: float = 0.618
OTE_FIB_HIGH: float = 0.786


def ote_zone(swing_high: float, swing_low: float) -> tuple[float, float]:
    """Zona OTE (ote_low, ote_high) referenciada desde el swing_high.
    Para LONG es la banda directa.
    Para SHORT el caller usa la banda espejo (ver is_ote_entry / flag_ote).
    """


def is_ote_entry(
    entry_price: float,
    swing_high: float,
    swing_low: float,
    direction: int,
) -> tuple[bool, dict]:
    """True si entry_price cae dentro de la banda OTE según direction.
    Devuelve (confirmado, metadata) con ote_low/ote_high/leg_range/...
    Si rango <= 0 devuelve (False, {...}) sin inventar."""


def flag_ote(signals, frames, ltf: str = "M15") -> list:
    """Anota ote_confirmed/ote_zone en cada ICTSignal leyendo swing_high/swing_low
    del row de entry en frames[ltf]. Si no hay swing claro -> False/None.
    Si frames[ltf] no trae swings, aplica detect_market_structure() una vez.
    Devuelve la misma lista anotada (NO reordena, NO filtra).
    """
```

### 3.1 Contrato de `flag_ote`
- **Entrada:** lista de objetos con atributos dinámicos (`entry`, `direction`,
  `entry_at`), y un `dict[str, pd.DataFrame]` `frames` donde `frames[ltf]`
  trae OHLCV + `sweep_high`/`sweep_low`/`bsl_price`/`ssl_price` (columnas
  estándar del detector de estructura).
- **Efecto secundario:** setea atributos en cada objeto de señal:
  - `sig.ote_confirmed` (bool)
  - `sig.ote_zone` (tuple[float, float] | None)
- **Salida:** misma lista recibida, con las anotaciones aplicadas.

---

## 4. Puntos de conexión oficiales (lo que toca el conector)

### 4.1 Paso post-loop en `canonical.evaluate_signals()` (YA ESTÁ)
El conductor debe asegurarse de que la señal tenga:
- `direction`
- `entry`
- `entry_at`
- acceso a `frames[ltf]` con columnas de swing.

`flag_ote` puede fallar por `detect_market_structure` (zig-zag no produce
swing en rampas). El loop actual usa `try/except` por cada flag. Si `ote.py`
lanza excepción inesperada, el pipeline base sigue intacto (knob apagado).

### 4.2 RR por setup: `_rr_for_raw_signal()` (YA ESTÁ)
Ya lee `ote_mod.is_ote_entry(...)` y la precede Silver Bullet / Turtle Soup.
Si OTE se confirma, devuelve `rr_for("ote") = 3.0`.
El llamador es `evaluate_signals` al construir `ICTSignal(take_profit=tp)`.
Esto es BUENA práctica: el motor respeta el RR del setup **sin filtrar** la señal.

### 4.3 UI / Scoring / Diagnosis (OPCIONAL, no bloquea)
Si el producto final necesita mostrar "OTE: sí/no + zona 62-79%", el consumo
es:

```python
# Ejemplo de consumo en UI/scoring (fuera de canonical.py):
sig.rr_target           # 3.0 si OTE confirmado y no hay SB/Turtle
sig.ote_confirmed       # bool
sig.ote_zone            # (low, high) | None
```

No hay que tocar `ICTSignal` (dataclass): Python admite atributos dinámicos.
Los consumidores actuales usan `getattr(sig, "ote_confirmed", False)` para
no romper si el atributo no existe.

---

## 5. Regla de no-filtrado-duro (Principio Brecha D)

### 5.1 Regla
Los flags de setup **SÓLO ANOTAN metadato** en la señal. Nunca descartan
la señal ni modifican `entry`, `stop_loss` ni `take_profit`.

### 5.2 Evidencia empírica
La lección del POI HTF midió A' vs A'':
- A' (sin filtro duro, solo anotación): PF 1.511, WR 51.3%, +8.9R.
- A'' (POI como hard gate): PF 0.900, WR 41.9%, -1.7R.

Filtrar duro descarta las señales ganadoras y deja entrar las perdedoras
porque el edge intradía suele estar EN CONTRA del sesgo HTF declarado.
Esa misma lógica aplica a OTE.

### 5.3 Implementación actual
En `evaluate_signals()`, la lista final de signals se construye con entry/SL/TP
**antes** de llamar a los flags. Si `flag_ote` lanza excepción, el `except`
silencioso la salta. La señal sigue en la lista.

---

## 6. Datos requeridos por OTE (sin ATR ni indicadores)

- `frames[ltf]` trae OHLCV (open/high/low/close), tiempo, y columnas de
  estructura (`swing_high`, `swing_low`, `sweep_high/low`, `bsl/ssl_price`).
- `entry_at` es el índice LTF donde ocurrió el toque de zona.
- `direction` es `+1` (long) o `-1` (short).
- **NO requiere ATR, EMA, RSI, volatilidad, ni configuraciones adicionales.**

---

## 7. Puntos de fallo conocidos y su manejo

| Fallo | Causa | Manejo |
|-------|-------|--------|
| OTE no se calcula | `frames[ltf]` sin `swing_high/low` | `flag_ote` llama `detect_market_structure()` una vez |
| OTE = False sin razón | `entry_at` fuera de rango o swing NaN | `_swing_for_signal` devuelve `(None, None)` |
| RR no sube a 3.0 | Silver Bullet/TurtleSoup confirmados antes | Precedencia SB > Turtle > OTE (por `_setup_of`) |
| Excepción rompiendo pipeline | `flag_ote` no incluida en lista post-loop | Loop usa ciclo `try/except` por flag |

---

## 8. Checklist de verificación para el conector (humano)

- [ ] `frames[ltf]` trae columnas `swing_high` / `swing_low` (o acepta
      `detect_market_structure()` on-demand).
- [ ] `frames[ltf]` está indexado secuencialmente `0..N-1` (sin índices
      custom que rompan `.iloc[int(entry_at)]`).
- [ ] `evaluate_signals()` no filtra por `ote_confirmed` (solo anota).
- [ ] El componente consumidor lee `getattr(sig, "ote_confirmed", False)` y
      `getattr(sig, "ote_zone", None)`.
- [ ] Tests verdes: `pytest tests/test_ote_integration.py tests/test_rr_map.py -q`.

---

## 9. Documentación cruzada
- `ict_backtest/setups/ote.py` — fuente canónica OTE.
- `ict_backtest/setups/rr_map.py` — RR por setup y `_setup_of`.
- `ict_backtest/canonical.py` — `evaluate_signals()` paso post-loop (C2/C3/D1/RR).
- `tests/test_ote_integration.py` — suite de aceptación de integración.
- `tests/test_d1_ote.py` — tests unitarios de `ote.py`.
- `tests/test_orchestrator_setups_wired.py` — call-site real del orquestador.

---

## 10. Glosario rápido (dumi)

- **Pierna / leg:** el swing completo desde un mínimo a un máximo (o viceversa).
- **Fib 62-79%:** retroceso "profundo" ni muy superficial ni muy profundo.
- **Row de entry:** la vela LTF donde ocurrió el toque de zona (`entry_at`).
- **Brecha D:** principio arquitectónico: los flags de setups solo anotan
  metadato; no filtran duro. El consumidor decide.
- **knob apagado:** filtro presente en el código pero desactivado por defecto
  (no veta, solo informa).

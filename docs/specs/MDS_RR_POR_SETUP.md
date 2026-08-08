# MDS — RR mínimo POR SETUP (geometría + volumen, cero indicadores)

**Clasificación:** OBLIGATORIO (por setup) · **Fase:** C2 · **Estado:** ✅ HECHO (rescatado a `engine/rr_by_setup.py`, commit dd8f7ef; backtest consume vía shim)

---

## 1. Título + Clasificación

- **Título:** RR por setup — mapea cada setup ICT a su ratio riesgo:beneficio objetivo (no todos 1:3 fijo).
- **Clasificación:** OBLIGATORIO (por setup).
- **Fase:** C2.
- **Estado:** ✅ especificado. Código real en `ict_backtest/setups/rr_map.py` (`rr_for`, `RR_BY_SETUP`, `flag_rr`). Pendiente de rescate a `engine/rr_by_setup.py` (ver §7).

## 2. Propósito (lenguaje simple)

Cada tipo de setup tiene su propio RR objetivo. Hoy el motor fuerza RR 1:3 global (`* 3.0 * risk` en `canonical.evaluate_signals`). Este módulo es la **fuente de verdad por-setup**: el orquestador consulta `rr_for(setup_type)` y aplica ese RR al cálculo del take-profit. Así Silver Bullet y Turtle Soup usan su RR propio en vez del 1:3 genérico.

## 3. Por qué importa (geometría, no indicadores)

El RR se define por GEOMETRÍA: `risk = |entry - sl|` (sl estructural) y el TP se ancla a un nivel de **liquidez** (`tp = entry ± rr*risk`, o liquidez internal/external cuando la haya). No interviene ningún indicador: el RR es una decisión de diseño del setup (libro 07 #5, tesis 20 §9) que luego se traduce a un nivel de precio real. Distinguir por setup evita forzar 1:3 donde el patrón natural es más corto (SB 1:2) o más ajustado (Turtle 1:1.5), mejorando la fidelidad al modelo ICT.

## 4. Entradas

- `setup_name: str | None` — nombre del setup resuelto. Valores soportados: `"silver_bullet"`, `"turtle_soup"`, `"ote"`, y `None`/desconocido → `"default"`.
- Resolución del setup a partir de flags de señal (`sb_confirmed` > `turtle_confirmed` > `ote_confirmed` > `default`) — ver §5.
- `risk: float` (para la aplicación en el orquestador) — `|entry - sl|`, geometría pura.
- `entry`, `sl`, nivel de **liquidez** objetivo (internal/external) para anclar el TP.

**+ VOLUMEN (única excepción):** el tick volume puede usarse para confirmar que el nivel de liquidez donde se ancla el TP efectivamente fue barrido (vela de barrido con volumen), pero NO altera el RR objetivo del setup.

## 5. Lógica (geometría pura, sin indicadores)

Fuente real: `ict_backtest/setups/rr_map.py`.

- `RR_BY_SETUP: dict[str, float]`:
  - `"silver_bullet": 2.0` → **1:2** (libro 07 #5, SPEC §17).
  - `"turtle_soup": 1.5` → **1:1.5** (tesis 20 §9).
  - `"ote": 3.0` → **1:3** (default de tesis).
  - `"default": 3.0` → **1:3** (PO3 y setups no reconocidos).

- `rr_for(setup_name: str | None) -> float`:
  Devuelve `RR_BY_SETUP[setup_name]` si existe, si no `RR_BY_SETUP["default"]` (3.0). `None` → 3.0.
  ```python
  >>> rr_for("silver_bullet")
  2.0
  >>> rr_for("turtle_soup")
  1.5
  >>> rr_for(None)
  3.0
  ```

- `_setup_of(sig) -> str` (precedencia): `sb_confirmed` → `"silver_bullet"`; `turtle_confirmed` → `"turtle_soup"`; `ote_confirmed` → `"ote"`; sino → `"default"`. Lee flags con `getattr` defensivo porque `ICTSignal` aún no los declara.

- `flag_rr(signals) -> list`:
  Anota `sig.rr_target = rr_for(_setup_of(sig))` en cada señal (mutación in-place vía `setattr`, encadenable). **NO** calcula el TP ni edita `engine`/`ICTSignal`: solo resuelve y anota el RR objetivo.

**Aplicación al TP (en el orquestador `canonical.evaluate_signals`, call-site real `_rr_for_raw_signal`):** el RR resuelto se usa para `tp = entry ± rr*risk` cuando no hay liquidez internal suficiente; si hay liquidez internal, se respeta pero con guarda mínima de 2R del `risk`. Sin indicadores: todo es `entry`/`sl`/niveles de liquidez.

## 6. Salidas

- `rr_for(...)` → `float` (ratio R, p.ej. 2.0, 1.5, 3.0).
- `flag_rr(...)` → misma lista de señales con atributo `rr_target: float` asignado a cada una.
- En el orquestador: el `tp` resultante es un **nivel de precio geométrico** (`entry ± rr*risk` o liquidez), no un indicador.

## 7. Integración (Arquitectura — Ley Fundamental)

- **Rescatado a `engine/`:** el módulo vive en **`engine/rr_by_setup.py`** (permanente, commit dd8f7ef), exponiendo `rr_for` / `RR_BY_SETUP` / `flag_rr`. `ict_backtest/setups/rr_map.py` quedó como SHIM que re-exporta. El backtest (`ict_backtest/`) es DESECHABLE y consume `engine.rr_by_setup`.
- `engine/` **NUNCA** importa `ict_backtest/`. El backtest (`ict_backtest/`) es DESECHABLE y consume `engine.rr_by_setup`.
- Call-site real: `canonical.evaluate_signals` → `_rr_for_raw_signal` ya llama `rr_for("silver_bullet"|"turtle_soup"|"ote")` y aplica el RR al TP. `flag_rr` anota `rr_target` en el `ICTSignal` para el consumidor (scoring / E1 / UI).
- Responsabilidad limitada (por diseño): este módulo SOLO resuelve/anota el RR; la aplicación al TP queda en el orquestador que consume `engine`.

## 8. Anti-look-ahead

- `rr_for` es una consulta de tabla pura: no mira el futuro, no depende de precios posteriores a la señal.
- La resolución del setup (`_setup_of` / `_rr_for_raw_signal`) usa índices `sweep_at`/`entry_at` ya cerrados de la señal; el orquestador recorta el exec TF a `time <= entry_at` (vela ya cerrada) antes de reanclar. No se consulta información posterior a la entrada para decidir el RR.

## 9. Verificación (pytest)

Tests existentes: `tests/test_rr_map.py`. Casos mínimos obligatorios:

- `rr_for("silver_bullet") == 2.0`, `rr_for("turtle_soup") == 1.5`, `rr_for("ote") == 3.0`, `rr_for(None) == 3.0`, `rr_for("po3") == 3.0` (default).
- `_setup_of` con flags: SB > Turtle > OTE > default.
- `flag_rr` anota `rr_target` correcto en cada señal y es encadenable (retorna la misma lista).
- Integración (orquestador): SB con RR 1:2 pasa el filtro; PO3/Turtle con RR 1:2 cae si el umbral por setup lo exige; todos con RR >= umbral pasan.
- `scripts/diag_etapas.py` con datos chicos. PF bloqueado hasta Fase G (R4); aquí se mide por fidelidad del RR por setup, no por PF.

## 10. Notas de volumen

El **tick volume** es la ÚNICA excepción a cero indicadores y se trata como dato de mercado:

- Confirma que el nivel de **liquidez** donde se anclaría el TP (internal/external) fue realmente barrido (vela de barrido con volumen), dando soporte geométrico a que el RR objetivo es alcanzable.
- El volumen **no** cambia el `rr_for` de un setup: el RR es decisión de diseño del patrón (libro 07 #5 / tesis 20 §9), no una función del volumen.
- En `canonical._rr_for_raw_setup`, el volumen nunca participa en la selección del umbral; solo los detectores de setup (sweep/entry geométrico) lo hacen.

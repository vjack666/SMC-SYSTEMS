# MDS — Trade Management E1: Break-Even / parcial / trailing (geometría pura)

**Clasificación:** OBLIGATORIO · **Fase:** E1 · **Estado:** ✅ especificado (impl. real en `ict_backtest/trade_mgmt.py`, commit 565b501; pendiente rescate a `engine/`)

---

## 1. Título + Clasificación

- **Título:** E1 — Trade Management (gestión post-entry): Break-Even (BE), cierre parcial en liquidez internal, trailing stop por pasos de riesgo.
- **Clasificación:** OBLIGATORIO.
- **Fase:** E1.
- **Estado:** ✅ especificado. Código real ya cableado al backtest (`ict_backtest/trade_mgmt.py`, `apply_trade_management`). Pendiente de rescate a `engine/trade_mgmt.py` (ver §7).

## 2. Propósito (lenguaje simple)

Decir QUÉ hacer con un trade YA abierto: cuándo mover el stop a break-even, cuándo cerrar una parte del lote en la liquidez internal, y cómo arrastrar el stop a favor (trailing) para proteger ganancia. Todo se decide mirando solo el PRECIO (OHLC) y la ESTRUCTURA del mercado — sin ningún indicador.

## 3. Por qué importa (geometría, no indicadores)

Proteger el capital usando niveles de mercado reales: el BE se ancla al propio `entry` (nivel neutro de referencia), el parcial se dispara al tocar la **liquidez internal** (tp1, el primer pool de stops opuestos), y el trailing solo avanza cuando el precio rompe estructura a favor por bloques de riesgo (`risk`). Nada de EMA/RSI/ATR/MACD: el riesgo se mide como `risk = |entry - sl|` puro, y los gatillos son touches de `high`/`low` sobre niveles geométricos. Así la gestión es reproducible y coherente con la detección de setup (POI/estructura), no con una media móvil.

## 4. Entradas

Primitivos (sin objetos de motor; máxima pureza y testeo):

- `entry: float` — precio de entrada.
- `sl: float` — stop loss inicial (estructural, calculado por `engine`).
- `tp: float` — take profit objetivo.
- `direction: int` — `+1` long, `-1` short (igual convención que `ICTSignal.direction`).
- `df: pd.DataFrame` — **serie OHLC POST-entry** (orden cronológico, solo velas posteriores a la entrada). Debe tener columnas `open/high/low/close`.
- `partial_pct: float = 0.5` — fracción del lote a cerrar en tp1 (`(0,1]`).
- `tp1_r: float = 1.0` — distancia de tp1 medida en múltiplos de `risk` (`tp1 = entry ± tp1_r*risk`).
- `trail_step_r: float = 1.0` — paso del trailing en múltiplos de `risk`.
- `be_buf: float = 0.0` — amortiguación opcional para no tocar exacto el entry en BE.

**Entradas de geometría (no indicadores):**
- **Swings / entry** → nivel BE (el `entry` mismo es el ancla de break-even).
- **Liquidez internal** → nivel `tp1` donde se cierra el parcial (primer pool de stops opuestos barrido).
- **Estructura a favor** → cada `trail_step_r * risk` de avance arrastra el SL.

**+ VOLUMEN (única excepción permitida):** el `tick volume` de cada vela se usa SOLO como confirmación de agotamiento del movimiento en tp1/BE (ver §10), no como señal de entrada ni disparador.

## 5. Lógica (geometría pura, sin indicadores)

Funciones PURAS (no mutan estado global, no mutan `df`):

- `to_breakeven(entry, sl, direction, current_price, be_trigger_r=1.0) -> float | None`
  Mueve SL a `entry` si el precio avanzó `>= be_trigger_r * risk`. `risk = |entry - sl|`. Long: avance `= current - entry`; Short: `entry - current`. Sin estructura a favor (`risk <= 0`) → `None` (dejar SL original).

- `partial_exit(entry, tp1, direction, current_price, pct=0.5) -> bool`
  `True` si el precio tocó tp1 (liquidez internal) y corresponde cerrar `pct`. Long: `current >= tp1`; Short: `current <= tp1`. No calcula el cierre, solo señala.

- `trailing_stop(entry, sl, direction, current_price, step_r=1.0) -> float`
  SL deslizante que SOLO MEJORA (sube en long / baja en short), nunca empeora. Cada `step_r` de favor arrastra el SL `step_r*risk` hacia el precio. Devuelve `max(sl, candidato)` en long y `min(sl, candidato)` en short. Sin avance suficiente o `risk<=0` → SL original.

- `apply_trade_management(entry, sl, tp, direction, df, *, partial_pct=0.5, tp1_r=1.0, trail_step_r=1.0, be_buf=0.0) -> dict`
  CALL-SITE REAL. Recorre `df` post-entry y aplica en orden:
  1. **Parcial + BE:** al tocar `tp1` (por `high`/`low`, NO solo `close`) → cierra `partial_pct` del lote y mueve el SL restante a BE (`entry ± be_buf`).
  2. **Trailing:** tras el parcial, aplica `trailing_stop` por pasos de `trail_step_r*risk` (solo mejora).
  3. **Cierre final:** cuando el precio toca TP, el SL (BE o trailing) o se agota `df` → sale y reporta.
  Devuelve `exit_reason`, `exit_price`, `pnl_r` (parcial + remanente ponderado por `pct`), `partial_done`.

**LECTURA POR HIGH/LOW:** el toque de niveles se evalúa con `high`/`low` de cada vela (no solo `close`), para reproducir ejecución exacta a precio. Tolerancia `_EPS = 1e-10` para deriva de flotantes.

## 6. Salidas

`dict` con:
- `exit_reason: str` — `"tp"` | `"sl"` | `"be"` | `"trailing"` | `"open"` (agotó `df` sin tocar SL/TP).
- `exit_price: float` — precio de salida del REMANENTE.
- `pnl_r: float` — PnL total en R (parcial + remanente, ponderado por `pct`). Si hubo parcial: `pnl_r = partial_pct*(partial_price-entry)/risk + (1-partial_pct)*(exit_price-entry)/risk`; si no: `(exit_price-entry)/risk`.
- `partial_done: bool` — si ocurrió el cierre parcial.
- `risk: float` — riesgo nominal (`|entry - sl|`), para conveniencia del consumidor.

## 7. Integración (Arquitectura — Ley Fundamental)

- **Rescate a `engine/`:** el módulo hoy vive en `ict_backtest/trade_mgmt.py` y DEBE RESCATARSE a **`engine/trade_mgmt.py`** (permanente). Es geometría pura de gestión, no consumidor.
- `engine/` **NUNCA** importa `ict_backtest/`. El backtest (`ict_backtest/`) es DESECHABLE y consume `engine.trade_mgmt`.
- Call-site real: `apply_trade_management` es invocado por el backtest para gestionar cada señal de `evaluate_signals` (no es un backtest de PF completo: simula UN trade dada su gestión). Ya cableado en commit 565b501 leyendo `high`/`low` para toques exactos.

## 8. Anti-look-ahead

- Solo se recorren velas **POSTERIORES a la entrada** (`df` ya está recortado al call-site; el bucle itera `closes`/`high`/`low` en orden cronológico a partir de `entry_at`).
- En ningún momento se lee el futuro de la vela actual: el disparo de parcial/BE/trailing usa el `high`/`low`/`close` de la vela en curso, y el cierre se marca en esa misma vela.
- `apply_trade_management` es función pura: no muta `df` ni estado global; misma entrada → misma salida.

## 9. Verificación (pytest)

Tests existentes: `tests/test_e1_trade_mgmt.py` (funciones puras) y `tests/test_e1_applied_trade_mgmt.py` (`apply_trade_management`). Casos mínimos obligatorios:

- **Parcial + TP:** precio toca tp1 (parcial `partial_done=True`) y luego TP → `exit_reason="tp"`, `pnl_r` ponderado >0.
- **BE:** precio avanza >=1R, toca tp1, retrocede y es detenido en BE → `exit_reason="be"`, `partial_done=True`.
- **SL directo:** precio nunca llega a tp1 y cae al SL original → `exit_reason="sl"`, `partial_done=False`.
- **Trailing:** tras el parcial, el SL se arrastra a favor por pasos y detiene en `trailing`.
- **Toque por high/low:** verificar que un wick a tp1/SL cuenta como toque aunque el `close` no lo cruce.

Todos los tests usan OHLC sintético (sin indicadores). `pnl_r` debe coincidir con el cálculo manual por geometría.

## 10. Notas de volumen

El **tick volume** es la ÚNICA excepción a la regla de cero indicadores y se trata como dato de mercado, no como indicador técnico:

- En `tp1` (liquidez internal): un pico de volumen confirma el barrido del pool de stops opuestos (el parcial se ejecuta sobre un movimiento real de participantes, no un wick hueco).
- En `BE`/trailing: volumen decreciente o ausencia de continuación confirma agotamiento del impulso a favor, respaldando la decisión de proteger con BE/trailing.
- El volumen **nunca** dispara ni anula un nivel geométrico: solo pesa/confirma. Los gatillos siguen siendo `high`/`low` sobre `entry`/`tp1`/`sl`.

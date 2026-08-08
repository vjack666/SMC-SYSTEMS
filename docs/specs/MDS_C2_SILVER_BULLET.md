# MDS — Silver Bullet (SB) (SPEC §17, libro 07)

**Clasificación:** OBLIGATORIO · **Fase:** C2 (post B2) · **Estado:** ✅ HECHO (rescatado a `engine/silver_bullet.py`, commit dd8f7ef)
**SPEC fuente:** `docs/ict/SPEC_TESIS_FORMAL.md` §17 · **Roadmap maestro:** §9 (SB)
**R1:** requiere SPEC firmada ✅ + este MDS antes de código.
**Arquitectura:** módulo PERMANENTE en `engine/silver_bullet.py`; `ict_backtest/` solo lo CONSUME.

---

## 1. Título + Clasificación

Software Design Doc — **Silver Bullet (SB): barrido de liquidez + retorno a POI en killzone limpia**.
Obligatorio · Fase C2 · Estado: rescate de `ict_backtest/setups/silver_bullet.py` a `engine/silver_bullet.py`.

## 2. Propósito

Silver Bullet es un setup de "hora limpia": tras un **barrido (sweep) de liquidez reciente** en una
killzone acotada (London Open o New York AM), el precio **retorna a una zona** (FVG / Order Block = POI)
y entra a favor del sesgo. El módulo decide si un par `(sweep_ts, return_ts, direction)` constituye un
SB válido y anota la señal. No toma la decisión final de trade por sí solo: es un detector geométrico
que el motor consume. RR objetivo 1:2 (libro 07 #5), distinto del 1:3 global.

## 3. Por qué importa (geometría de mercado, sin indicadores)

SB es pura **geometría de liquidez y estructura**: un barrido de stops (BSL/SSL) seguido de un retorno
a un PD array (FVG/OB) dentro de una ventana temporal específica. No interviene ningún indicador técnico
(EMA/RSI/ATR/MACD/Bollinger). La validez nace de la *secuencia geométrica* sweep → (estructura) → retorno
a POI, todo dentro de la killzone. Esto lo hace falsable y reproducible en backtest sobre OHLC + swings.

## 4. Entradas (datos geométricos + VOLUMEN como único extra permitido)

- **`sweep_ts`**: timestamp del barrido de liquidez (datetime / str). Vela que toma el extremo previo.
- **`return_ts`**: timestamp del retorno a la zona / entry (datetime / str). Debe ser **posterior** al sweep.
- **`direction`**: `+1` long / `-1` short (se propaga; no se usa para vetar).
- **`killzone_fn`**: `killzone_en(ts) -> str` (reusado de `engine/killzone.py`).
- **OHLC por TF**: se asume que `sweep_ts` / `return_ts` fueron derivados de velas reales (high/low del
  sweep para medir el take de liquidez; estructura BOS/CHOCH y POI FVG/OB en M15/M5/M1).
- **Solo se anota si sweep y retorno caen en la MISMA killzone SB**: `London Open` o `New York AM`
  (`NY PM` NO es killzone SB).
- **VOLUMEN (tick volume, único extra permitido):** confirma que la vela de sweep y la de retorno tuvieron
  participación real (volumen > promedio local) — ver §10. No es indicador derivado.

## 5. Lógica (geometría pura, cero indicadores)

Patrón ICT sobre geometría (fiel a `ict_backtest/setups/silver_bullet.py`):

1. Normalizar `sweep_ts` y `return_ts` a UTC (`_to_ts`). Si alguno es inválido → `(False, meta)`.
2. **Orden temporal:** `return_ts >= sweep_ts` (el retorno es posterior al barrido). Si `ret < sweep` → no SB.
3. **Killzone SB:** ambos deben caer en la **misma** ventana SB: `London Open` → `'L'`, `New York AM` → `'NY_AM'`.
   Mapeo `_SB_KILLZONES = {"London Open": "L", "New York AM": "NY_AM"}`.
4. Si `sb_sweep == sb_return` → SB confirmado.
5. El filtro duro queda como *knob apagado* (`hard_filter=False`): por defecto solo **anota** metadato
   (`sb_confirmed` / `sb_killzone`) en el `ICTSignal`, no descarta señales (Principio Brecha D).

Firma propuesta (rescatada a `engine/silver_bullet.py`):

```python
_SB_KILLZONES = {"London Open": "L", "New York AM": "NY_AM"}

def is_silver_bullet(sweep_ts, return_ts, direction: int, killzone_fn) -> tuple[bool, dict]:
    sweep = _to_ts(sweep_ts); ret = _to_ts(return_ts)
    if sweep is None or ret is None:
        return False, {"sb_killzone": None, "direction": direction,
                       "sweep_kz": None, "return_kz": None}
    if ret < sweep:  # retorno posterior al sweep
        return False, {"sb_killzone": None, "direction": direction,
                       "sweep_kz": killzone_fn(sweep), "return_kz": killzone_fn(ret)}
    sweep_kz = killzone_fn(sweep); return_kz = killzone_fn(ret)
    sb_sweep = _SB_KILLZONES.get(sweep_kz); sb_return = _SB_KILLZONES.get(return_kz)
    if sb_sweep is not None and sb_sweep == sb_return:
        return True, {"sb_killzone": sb_sweep, "direction": direction,
                      "sweep_kz": sweep_kz, "return_kz": return_kz}
    return False, {"sb_killzone": None, "direction": direction,
                   "sweep_kz": sweep_kz, "return_kz": return_kz}

def flag_silver_bullet(signals, frames=None, killzone_fn=None, *, hard_filter=False) -> list:
    """Anota sig.sb_confirmed / sig.sb_killzone (atributos dinamicos) por senal.
    NO edita engine (dataclass ICTSignal no cambia)."""
    ...
```

`flag_silver_bullet` resuelve `sweep_at` / `entry_at` (índices LTF) contra `frames` para obtener los
timestamps, llama `is_silver_bullet`, y setea `sig.sb_confirmed` / `sig.sb_killzone`. Con `hard_filter=True`
devuelve solo las confirmadas.

## 6. Salidas (bool confirmado + metadata)

`is_silver_bullet(...) -> (bool, dict)` con
`meta = {"sb_killzone": "L"|"NY_AM"|None, "direction": int, "sweep_kz": str, "return_kz": str}`.
`flag_silver_bullet` devuelve la lista de `ICTSignal` anotados (con `sb_confirmed: bool`, `sb_killzone: str|None`).

## 7. Integración: rescatarse a `engine/` y consumirse desde `ict_backtest` (nunca al revés)

- **Origen hoy:** `ict_backtest/setups/silver_bullet.py` (`is_silver_bullet`, `flag_silver_bullet`, `_SB_KILLZONES`).
- **Destino PERMANENTE:** `engine/silver_bullet.py`. El motor importa de aquí.
- **Consumo:** `ict_backtest/` (backtest desechable) importa `engine.silver_bullet` para anotar señales.
- **Ley Fundamental:** `engine/` **NUNCA** importa `ict_backtest/`. `engine/silver_bullet.py` importa
  `engine.killzone.killzone_en` (no `ict_backtest.rules`).
- El módulo **NO edita** `engine/.../ICTSignal` (dataclass estable); usa atributos dinámicos para anotar.

## 8. Anti-look-ahead (solo velas con `time <= t`)

- `sweep_ts` y `return_ts` provienen de velas **ya cerradas** (índices `sweep_at` / `entry_at` resueltos
  contra `frames` con `time <= t`). No se usa el reloj de la PC ni velas futuras.
- La comparación `ret >= sweep` garantiza orden causal: el retorno no puede preceder al barrido.
- `killzone_fn` opera sobre timestamps de vela (ver MDS_KILLZONES §8).

## 9. Verificación (pytest con datos sintéticos)

Pruebas con frames/timestamps sintéticos (sin datos reales):

- `sweep_ts` y `return_ts` en NY AM (UTC ~13:00) → `is_silver_bullet(...) == (True, {"sb_killzone":"NY_AM"})`.
- Ambos en London Open (UTC ~08:00) → `(True, {"sb_killzone":"L"})`.
- `sweep` en NY AM y `return` en NY PM → `(False, ...)` (killzones distintas).
- `return_ts < sweep_ts` → `(False, ...)` (orden temporal roto).
- `sweep_ts` en Asia → `(False, ...)` (no es killzone SB).
- `flag_silver_bullet` con `hard_filter=True` devuelve solo señales confirmadas; con `False` anota todas.
- `diag_etapas.py` datos chicos. PF bloqueado hasta Fase G (R4).

## 10. Notas de volumen (cómo el volumen ayuda sin ser indicador)

El tick volume es el único dato "extra" permitido y se usa **solo como confirmación de participación**,
no como indicador derivado:

- **Vela de sweep:** volumen de la vela que toma el extremo debe ser **superior al promedio local**
  (media de `volume` de la ventana) ⇒ el barrido de liquidez fue real (stop hunt institucional), no ruido.
- **Vela de retorno a POI:** volumen presente en la vuelta a la zona confirma interés en el nivel (FVG/OB).
- **NO** se usa EMA de volumen, OBV, ni ningún oscilador. Solo el conteo crudo de ticks por vela comparado
  con el promedio de la ventana — geometría de actividad, no indicador.

## Trazabilidad

SPEC §4 (3 setups PO3) · §17 (SB) · §20 (RR por setup, 1:2) · libro 07 · ROADMAP §9 (SB) ·
`ict_backtest/setups/silver_bullet.py` (fuente real) · MDS_KILLZONES_L_NYPM (killzone consumida) ·
PROPUESTA_BRECHA_A1_CABLEADO_TOPDOWN.md (top_down como filtro de sesgo).

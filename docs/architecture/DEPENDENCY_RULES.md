# DEPENDENCY_RULES.md — Reglas de dependencias

> **Constitución arquitectónica PROPUESTA — Revisión 2.1 (2026-08-09).** Direcciones
> permitidas/prohibidas del grafo. Incorpora: `RESULTS → ENGINE` automático prohibido;
> utilidades neutras no pueden depender de backtest. Incluye el diagnóstico de
> `detectors ↔ ict_backtest` y la distinción de legacy. NO se corrige hoy; se documenta
> para FASE 3.

## 1. Flecha sagrada (nunca se invierte)

```
DATA → ENGINE → BACKTEST → RESULTS
```

- `engine/` NO importa `ict_backtest/` (Ley Fundamental, confirmada: 0 hits).
- `engine/` NO importa `research/`, `results/`, `backtest/`.
- `backtest/` importa `engine/` y `detectors/` (consumidor).
- `results/` es hoja: no importa nada de arriba.
- `data/` es hoja: no importa nada de arriba.

## 2. Permitido

- `backtest/ → engine/` ✅
- `backtest/ → detectors/` ✅ (el backtest usa detectores)
- `engine/ → detectors/` ✅ (detectors es geometría reutilizable del motor)
- `agents/analysis/ → engine/`, `detectors/` ✅
- `research/experiments/ → engine/`, `backtest/`, `data/` ✅
- `app_observador/` (runtime) → `engine/` ✅

## 3. Prohibido (arquitectónicamente incorrecto)

- `engine/ → ict_backtest/` / `backtest/` ❌
- `detectors/ → ict_backtest/` / `backtest/` ❌ (geometría pura no depende del consumidor)
- **`results/ → engine/` (feedback automático) ❌❌** — MODIFICACIÓN 2.1. El resultado
  puede alimentar `research/` (nueva hipótesis), pero la vuelta a `engine/` SOLO ocurre
  mediante decisión explícita y pre-registrada, nunca silenciosamente.
- `research/ → backtest/` en sentido de "backtest decide" ❌ (investigación propone, no manda)
- `results/ → cualquiera` ❌
- `data/ → cualquiera` ❌
- **utilidad neutra → `backtest/` ❌** — MODIFICACIÓN 2.1 (ver §4.5).

> **LEY CENTRAL:** El resultado de un experimento puede generar una nueva hipótesis, pero
> nunca modificar silenciosamente el sistema que produjo ese resultado.

## 4. DIAGNÓSTICO: dependencia `detectors ↔ ict_backtest`

### 4.1 Qué archivos la generan (evidencia real)

**`ict_backtest → detectors` (CORRECTO, es consumo):**
- `ict_backtest/data_feed.py:22` → `from detectors import detect_displacement, detect_fvg, detect_liquidity, detect_order_blocks`
- `ict_backtest/data_feed.py:135` → `from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK`
- `ict_backtest/_cmp_bos.py:3` → `from detectors import detect_bos as old_bos, detect_choch as old_choch`

**`detectors → ict_backtest` (VIOLACIÓN, 1 archivo real):**
- `detectors/killzones.py:25` → `from ict_backtest.rules import server_to_utc, _et_band_to_utc`
- `detectors/displacement.py:23` → SOLO un COMENTARIO (no importa; no cuenta).

### 4.2 Por qué existe

`killzones.py` necesita convertir bandas de sesión (NY/Londres) de hora de servidor a UTC.
Esay lógica vive en `ict_backtest.rules` (módulo del backtest). El autor reusó código del
CONSUMIDOR en lugar de poner la utilidad en sitio neutro.

### 4.3 ¿Producción o test/tool?

De **PRODUCCIÓN** (killzones es filtro del motor usado en backtest y runtime). No es test.

### 4.4 Dirección correcta (Revisión 2.2 — ya resuelta en el código)

La conversión servidor→UTC es una **utilidad de tiempo neutra**. La auditoría 2.2 encontró
que **YA vive en `engine/killzone.py`** (`server_to_utc` l.50, `_et_band_to_utc` l.63) y que
**`ict_backtest/rules.py:6` YA importa de `engine.killzone`**. O sea el backtest ya migró a
la fuente neutra; solo `detectors/killzones.py` quedó atrasado importando de
`ict_backtest.rules`.

`engine/killzone.py` es el **subdominio temporal neutral** (bandas de sesión, servidor↔UTC,
DST vía ZoneInfo). Docstring explícito: "Unica fuente de verdad del motor. El backtest LO
CONSUME; nunca al revés."

### 4.5 Fix de FASE 3 (corrección mínima, no movimiento de archivos)

`detectors/killzones.py:25` debe importar `server_to_utc, _et_band_to_utc` desde
`engine.killzone` (igual que ya hace `ict_backtest/rules.py`), NO desde `ict_backtest.rules`.
Esto elimina la violación sin crear `_time_util.py` ni mover killzones.py a engine. La
utilidad temporal ya está aislada en `engine/killzone.py`; si crece (session_to_utc, DST,
market_session...) puede promoverse a `engine/time/`, pero hoy no hace falta.

## 5. Otras señales del mapa (para FASE 3, no hoy)

- `ml/trainer.py:26` → `from governance.model_registry import ModelRegistry` (graceful
  fallback). Ruido MLOps, no flujo causal. Revisar si `governance/` debe ser importable por
  `ml/` o si el registry vive en `models/`.
- **Legacy — dos cosas distintas (aclaración del Director):**
  - `C:\Users\v_jac\Desktop\legacy_smc_backup` (DISCO) = backup reversible de esta sesión
    (10 ítems). Fuera del repo, SEGURO, se mantiene.
  - `legacy/` (EN EL REPO, 29 .py) = código muerto, NO importado por nada vivo. Investigar
    en FASE 3 (¿referencia? ¿recuperable?) antes de `archive/` o salida. No confundir con el
    backup de disco.

## 6. Estado

Propuesto — Revisión 2.1. La violación `detectors/killzones.py → ict_backtest.rules` queda
documentada para FASE 3. El guardrail se construye en FASE 4 tras aprobación del Director.

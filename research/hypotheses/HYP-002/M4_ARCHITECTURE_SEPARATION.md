# HYP-002 M4b — Separación definitiva MOTOR ↔ BACKTEST (arquitectura)

**Fecha:** 2026-08-12 · **Ejecutor:** Hermes (autónomo, directiva Ruben)
**Estado:** CERRADA (separación verificada por prueba arquitectónica + 21 tests)
**Alcance:** reubicación de la capa de features y de las auditorías de replay FUERA de `ict_backtest/`, de modo que el motor sea autónomo y el backtest quede como hoja consumidora reemplazable.
**Fuera de alcance (por directiva):** estadística / WR / PF / edge, Macro/News.

---

## 1. Veredicto

**M4b — APROBADA.** El motor permanente (`engine/`) es ahora autónomo respecto de
`ict_backtest/`:

- `engine/` y `detectors/` **no importan** `ict_backtest/` (ni directa ni indirectamente).
  Verificado por `tests/test_architecture_motor_autonomy.py` (AST sobre todos los `.py`).
- El cálculo de features (`build_features`) vive en **`engine/market_features.py`** (capa permanente).
- El helper compartido de volatilidad/HTF (`avg_candle_range`, `row_at_time`,
  `closed_row_at_time`, `closed_merge_asof`) vive en **`engine/_util.py`** (capa permanente).
- El backtest (`ict_backtest/data_feed.build_features`) **reenvía** a `engine.market_features.build_features`
  → no duplica lógica; si se borra `ict_backtest/`, el motor y sus auditorías siguen funcionando.
- Las auditorías de replay (M1-M3 + M4) viven en
  `research/hypotheses/HYP-002/functional_replay/` y **consumen únicamente `engine.*`**.

---

## 2. Mapa de dependencias resultante (objetivo alcanzado)

```
                 RAW MARKET DATA (OHLC)
                        │
                        ▼
                 ┌──────────────┐
                 │    ENGINE    │  permanente · autónomo
                 │  (engine/)   │  build_features, _util, detectors, bos,
                 │              │  sequence, market_object, expediente ...
                 └──────┬───────┘
                        │  (interfaz pública: run_sequence_traced, build_features)
          ┌─────────────┼─────────────────────┐
          ▼             ▼                       ▼
      LIVE FEED    FUNCTIONAL REPLAY      ICT_BACKTEST (backtest)
   (adaptador        (research/.../         consume engine,
    real, futuro)    functional_replay/)    reenvía build_features
                        │
                        ▼
                  AUDITORÍAS (causalidad, look-ahead, determinismo,
                  restart, hostile, shadow, cross-val, continuidad)
```

El backtest es una **hoja**: solo consume al motor, nunca le provee lógica.

---

## 3. Qué se movió (y qué NO)

| Antes (erróneo) | Después (correcto) | Naturaleza |
|---|---|---|
| `ict_backtest/data_feed.py::build_features` (orquesta detectores + estructura) | `engine/market_features.py::build_features` | Lógica de features → capa permanente |
| `ict_backtest/_util.py` (helpers puros de volatilidad/HTF) | `engine/_util.py` | Helper compartido → capa permanente |
| `ict_backtest/functional_lab.py` | `research/hypotheses/HYP-002/functional_replay/functional_replay_battery.py` | Auditoría replay → fuera de backtest |
| `ict_backtest/operational_continuity_lab.py` | `research/hypotheses/HYP-002/functional_replay/operational_continuity_battery.py` | Auditoría replay → fuera de backtest |
| (nuevo) `functional_replay/replay_core.py` | núcleo compartido (make_signal_objs, run_session, audit_restart_parity) | Evita duplicar helpers entre baterías |

**NO se tocó `engine/` lógica de decisión** — solo se AÑADIÓ la capa `market_features`/`_util`
que antes residía (mal) bajo `ict_backtest/`. El backtest mantiene `build_features` como
reexport, así que `canonical.py`, `run_backtest.py`, `v2/orchestrator.py` y cualquier consumidor
existente siguen funcionando sin cambios.

---

## 4. Prueba arquitectónica (guarda de regresión)

`tests/test_architecture_motor_autonomy.py`:

- `test_engine_does_not_import_ict_backtest`: parsea con `ast` TODOS los `.py` de
  `engine/` y `detectors/`; falla si alguno contiene `import ict_backtest` / `from ict_backtest`.
- `test_ict_backtest_build_features_is_pure_consumer`: borra `ict_backtest.data_feed` de
  `sys.modules`, lo reimporta y afirma `idf.build_features is emf.build_features`
  (el backtest reenvía, no duplica).

Esta prueba bloquea cualquier futura deriva `engine → ict_backtest`.

---

## 5. Evidencia reproducible

```
python -m pytest tests/test_architecture_motor_autonomy.py \
                   tests/test_functional_lab.py \
                   tests/test_operational_continuity.py \
                   tests/test_sequence_persistence.py -q
→ 21 passed
```

- `test_architecture_motor_autonomy.py`: 2 passed (autonomía motor + consumidor puro).
- `test_functional_lab.py`: 5 passed (M1-M3 batch/stream/determinismo/hostile/OB causal).
- `test_operational_continuity.py`: 10 passed (M4 reinicios/gaps/dup/ooo/sesión/lifecycle).
- `test_sequence_persistence.py`: 4 passed (M3 round-trip + restart parity).

Reporte M4 regenerado desde el módulo reubicado: `run_all()` → `overall_pass = True`.

---

## 6. Conclusión

La contradicción arquitectónica que se detectó (la auditoría funcional montada sobre
`ict_backtest.data_feed`) está resuelta. El motor puede ahora ejecutarse, auditarse y
someterse a replay de mercado **sin importar ningún módulo de `ict_backtest/`**. Cuando
termine la investigación y se elimine `ict_backtest/`, el motor, sus auditorías y la
lectura de mercado sobreviven intactos.

**Deuda fuera de alcance (sin cambios respecto a M4):** el adaptador de feed real debe
normalizar fuera-de-orden/duplicados antes de entregar al motor (el motor asume feed ya
ordenado). Documentada, no es bug del motor.

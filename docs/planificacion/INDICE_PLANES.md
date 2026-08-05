# Planes de Trabajo — SMC-SYSTEMS (VIGENTES)

Índice de los planes de trabajo activos. Fuente de verdad: AGENTS.md + tesis
(docs/tesis/) + engine/. El backtest es desechable y solo demuestra la tesis.

## Plan rector (más acorde a la metodología del trader humano)

**`PLAN_BACKTEST_SESGO_VELA_A_VELA.md`** + **`TODOS_BACKTEST_SESGO.md`** (2026-08-03)

Por qué es el plan correcto:
- Refleja la LEY FUNDAMENTAL: el motor (engine/bias/) es el reflejo de la tesis;
  el backtest existe SOLO para demostrarlo vela a vela. No invierte la relación.
- Demuestra que el sesgo del humano (D1/H4/H1) es legible y coherente desde el
  motor, no desde indicadores.
- Es medible y honesto: vela a vela sobre parquet M15 real, sin look-ahead.
- Apunta a cerrar la deuda de integración (brecha B/A1 ya cerradas en el motor
  en esta sesión: engine/poi_anchor + engine/plan top-down).

## Otros planes / trabajo en curso

- Cerrar deuda de integración en el MOTOR (no backtest): ver bitácora
  `docs/bitacora/bitacora_trabajo.md` — pendiente exec fino M5/M1 y fix sesgo
  NEUTRAL perpetuo (`engine/bias/narrative.py` `_bias_from_swings`).

## Roadmap (recuperado, histórico)
El repo no tenía roadmap vivo (docs/plan/ purgado 2026-08-03). Se recuperaron
21 roadmaps históricos a `docs/planificacion/_roadmap_historico/` marcados como
HISTÓRICOS (no fuente de verdad). El mapa vivo del punto actual está en
`docs/planificacion/_roadmap_historico/PUNTO_DEL_ROADMAP_2026-08-05.md`.

## Documentación de apoyo vigente
- `docs/rutinas/RUTINA_EURUSD.md` — rutina top-down diaria para el humano.
- `docs/auditorias/AUDITORIA_FIDELIDAD_TESIS_ICT_2026-07-17.md` — fidelidad tesis.
- `docs/ict/10_AUDITORIA_REFACCION/` — lecciones de refacción del backtest.
- `README.md` — estado observador FundedNext.
- `docs/bitacora/bitacora_trabajo.md` — estado real verificado (vive).

## Descartados
- Ver `docs/_descartado/INDICE_DESCARTE.md` (roadmaps purgados, SMC_SUCCESSOR,
  ForexClub, deployment F8). Reversibles con git mv.

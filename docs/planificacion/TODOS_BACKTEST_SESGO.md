# TODOs — Backtest del sesgo: demostrar que el motor bias es el reflejo de la tesis

| Campo | Valor |
|-------|-------|
| **Estado** | Lista de TODOs para el implementer (sin código todavía) |
| **Fecha** | 2026-08-03 |
| **Plan madre** | `docs/planificacion/PLAN_BACKTEST_SESGO_VELA_A_VELA.md` |
| **Ley que rige** | `AGENTS.md` § LEY FUNDAMENTAL — MOTOR vs BACKTEST (leer primero) |
| **Motor que se demuestra** | `engine/bias/` (capa 1: `narrative.py`, `compute_htf_bias`, 12/12 tests) |
| **Tesis que se refleja** | `docs/ict/SPEC_TESIS_FORMAL.md` §1 Narrativa HTF · `docs/ict/20_TESIS_ICT.md` |

---

## 0. Contexto y reglas de esta tanda (leer antes de tocar código)

**Qué se construye:** la parte del **backtest** que demuestra que el motor bias produce el
sesgo D1/H4/H1 como lo dicta la tesis — vela a vela sobre el parquet M15, como lo haría un humano.

**Lo que NO se toca en esta tanda:**
- Las capas del motor que faltan (estructura H4, POI, ejecución) — tanda futura.
- La ejecución de trades (sweep→BOS→retorno, SL/TP, costos) — requiere capas del motor que aún no existen.
- `ict_backtest/` existente — no se modifica (el runner nuevo vive aparte).

**Reglas de la ley (obligatorias):**
1. El backtest NO contiene lógica de decisión: **jamás** un "detector de bias" en el backtest.
   Todo lo que sea bias/estructura/POI/ejecución vive en `engine/`. El backtest solo:
   reloj vela a vela + **llamar al motor** + medir.
2. `engine/` nunca importa `ict_backtest/`. El backtest importa `engine/`, nunca al revés.
3. Sin look-ahead: HTF closed-only (la vela HTF en formación NO existe), fill next-open.
4. Un cambio estructural a la vez; tests tras cada TODO; sin commit sin OK de Ruben.
5. Cualquier indicador (EMA/RSI/ATR) en el backtest es sospechoso → justificar contra la tesis o eliminarlo.

---

## 1. Lista de TODOs (esta tanda)

**Orden de ejecución estricto (dependencias):** T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8

| ID | TODO | Criterio de done (evidencia) | Archivos esperados |
|----|------|------------------------------|--------------------|
| **T1** | Crear el paquete del backtest del sesgo en su carpeta: `ict_backtest/sesgo/` (nuevo, separado del backtest existente) con `__init__.py`, estructura para `reloj`, `motor_cable`, `medicion`, y runner CLI de demo. **Sin lógica todavía.** | `python -c "import ict_backtest.sesgo"` sin error; estructura visible en disco | `ict_backtest/sesgo/__init__.py`, `ict_backtest/sesgo/reloj/`, `ict_backtest/sesgo/motor_cable/`, `ict_backtest/sesgo/medicion/`, `ict_backtest/sesgo/run_sesgo.py` (stub) |
| **T2** | F0 — Cargador y validador del parquet M15: carga `data/raw/<SIMBOLO>_M15.parquet`, verifica orden cronológico estricto, sin timestamps duplicados, sin huecos raros; documenta la zona horaria del timestamp. | Test sintético: carga un parquet chico ordenado; detecta duplicados y desorden (error claro); TZ documentada en el código | `ict_backtest/sesgo/reloj/datos.py`, `tests/test_sesgo_datos.py` |
| **T3** | F0 — Configuración única con la **tabla de agregación** (H1=4, H4=16, D1=96 velas M15) y los **warm-ups** (D1=20, H4=60, H1=100 velas propias). Valores en UN solo lugar, importados por todo el paquete. | Test: la tabla de agregación coincide con el plan §3.1; warm-ups accesibles como constantes | `ict_backtest/sesgo/config.py`, `tests/test_sesgo_config.py` |
| **T4** | F1 — **El reloj vela a vela (corazón)**: iterador que recorre el parquet M15 de i=0 a N-1 en orden cronológico; en cada vela calcula el bucket de cada TF (H1 = floor(t/1h), H4 = floor(t/4h), D1 = floor(t/1d)); detecta qué TF "cerró ahora" cuando su bucket cambia respecto a la vela anterior; materializa la vela superior agregando las M15 cerradas de ese bucket. **SIN lógica de trading ni de sesgo.** | Tests sintéticos: (a) un H1 = 4 velas M15, un H4 = 16, un D1 = 96 (conteo exacto de buckets); (b) la vela HTF en formación NO existe para el reloj (test de límite exacto); (c) determinista: misma entrada → misma salida | `ict_backtest/sesgo/reloj/reloj.py`, `tests/test_sesgo_reloj.py` |
| **T5** | F1 — Test anti-look-ahead de regresión en el **límite exacto** del reloj: una H4 que se forma (p. ej. las 4 velas M15 de 08:00) no debe estar disponible hasta que la última M15 del bucket haya cerrado; idem D1 y H1. | Test de límite exacto verde (mismo espíritu que `test_row_at_time_exact_boundary_closed`); 0 lecturas futuras | `tests/test_sesgo_reloj_no_lookahead.py` |
| **T6** | F2 — **Cablear el motor bias al reloj** (el backtest llama al motor, NO reimplementa): en cada cierre de D1, construir las vistas D1/H4/H1 agregadas y llamar a `engine/bias/narrative.compute_htf_bias(d1, h4, h1, swing_lookback=5)`; guardar el sesgo vigente (`HtfBias`); el sesgo vigente rige hasta el próximo cierre de D1. El reloj expone "sesgo vigente" y "¿se actualizó ahora?" a la medición. | Test sintético: transición de sesgo en el límite del día (el sesgo cambia solo en cierre de D1); entre cierres de D1 el sesgo vigente no cambia; `aligned` correcto cuando los 3 TF votan | `ict_backtest/sesgo/motor_cable/cable_bias.py`, `tests/test_sesgo_cable_bias.py` |
| **T7** | F2 — Registro del **warm-up y disponibilidad**: el sesgo reporta "no disponible" hasta que D1≥20, H4≥60, H1≥100 velas cerradas; el runner registra la fecha/hora en que el sesgo queda disponible (para auditar cuánta muestra se pierde). | Test: antes del warm-up el sesgo es "no disponible"; al superar el mínimo, se activa y queda registrado el instante | `ict_backtest/sesgo/motor_cable/warmup.py`, `tests/test_sesgo_warmup.py` |
| **T8** | F5 (parcial) — **Medición de demostración (sin decisión)**: runner que recorre las M15, toma el sesgo vigente del motor en cada vela y compara dirección del sesgo vs movimiento del precio en las próximas K velas M15 (K configurable, p. ej. 48). Sale un reporte: % velas donde el precio siguió la dirección del sesgo, por TF alineado (aligned vs parcial vs no disponible). **Esto mide al motor, no decide nada.** | Corrida sobre EURUSD M15 (2.02 años) genera reporte en `results/sesgo/`; el reporte marca sesgo disponible + % alineación + N de velas evaluadas | `ict_backtest/sesgo/medicion/demostracion.py`, `ict_backtest/sesgo/run_sesgo.py` (runner real), `results/sesgo/reporte_sesgo_<fecha>.json` |

---

## 2. Qué NO debe pasar (anti-patterns de esta tanda)

- ❌ Crear un "detector de bias" o cualquier módulo de decisión dentro de `ict_backtest/sesgo/`.
  El sesgo SIEMPRE sale de `engine/bias/`. (Ley punto 1.)
- ❌ Importar `ict_backtest/` desde `engine/`. (Ley punto 2.)
- ❌ Usar la vela HTF en formación, `shift` hacia adelante, o ventanas centradas de swings. (Ley punto 3.)
- ❌ Añadir EMA/RSI/ATR u otro indicador para "mejorar" la demostración. Matemática pura y geometría. (Ley punto 5.)
- ❌ Tocar `ict_backtest/` existente, `engine/bias/` (ya está 12/12 verde), ni `data/raw/`.
- ❌ Commit/push sin OK expreso de Ruben (y con roadmaps al día en el mismo commit).

---

## 3. Tandas futuras (referencia, NO hacer ahora)

| Tanda | Qué incluye | Depende de |
|-------|-------------|------------|
| Motor capas 2-3 | Estructura H4 (BOS/CHOCH), zona premium/discount, POI anclado HTF, contexto H1 | Motor (engine/) — se escribe en `engine/`, nunca en el backtest |
| Backtest ejecución | F3 (sweep→BOS→retorno + killzone) + F4 (costos) + F5 completo (walk-forward OOS) | Capas del motor de la tanda anterior |
| Cierre | Veredicto → `docs/METRICS_CANON.md`; cuando el motor tenga todos los módulos, **borrar el backtest** | Todo lo anterior |

---

## 4. Resumen de verificación final de la tanda

1. `pytest tests/test_sesgo_*.py` → todos verdes.
2. `python -m ict_backtest.sesgo.run_sesgo --simbolo EURUSD` → reporte en `results/sesgo/`.
3. Revisar que el paquete NO contiene decisión propia (solo importa `engine/bias/` y mide).
4. Informe al cierre: qué se construyó · evidencia · impacto · recomendación (punto de control del modo piloto supervisado).

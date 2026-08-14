# MISIÓN: Validación Causal del Market Replay (BATCH vs INCREMENTAL)

**Fecha:** 2026-08-14 (noche) · **Estado:** FASE 1+2 CERRADAS, FASE 3 EN CURSO (bloqueada por rendimiento, no por semántica)
**Autor:** Hermes (orquestador, Consejo activo) · **Principio rector:** REPLAY ≈ LIVE; batch NO es evidencia de comportamiento online.

## Contexto del Director
> El motor debe producir la MISMA secuencia causal cuando recibe información
> progresivamente (replay/vela-a-vela) que cuando recibe toda la serie (batch).
> Si no puede en incremental, no puede en vivo. MarketReplay NO debe ser un
> reproductor de backtest. La Solución A (batch) queda DESCARTADA.

## FASE 1 — Antecedente histórico (CERRADA)
Se recuperó evidencia previa EN ESTE REPO (no solo en vjack666/quotex):

- `research/hypotheses/HYP-002/FUNCTIONAL_REPLAY_CONTRACT.md` (Hermes, 2026-08-11)
  ya exige en §8: **"Batch vs Stream | eventos k-k idénticos"**. O sea el repo
  YA estableció que batch debe ser idéntico a stream (incremental).
- `research/hypotheses/HYP-002/functional_replay/replay_core.py` ya implementa
  `run_session` que dirige el motor **barra-a-barra** con `initial_state`+`start_i`.
- `git log`: `d76783f HYP-002: auditoria funcional motor (replay vela-a-vela)`,
  `424b060 M2: eliminar O(n^2) de infra temporal en replay (copy_objs=False)`.
- `results/real_replay_smoke_1600.txt` y `real_replay_smoke_8000.txt`: ya hubo
  corridas de replay de 1600 y 8000 velas.
- Antecedente externo (quotex): commits `2f7b0e9` (MarketReplay Engine, "Regla
  Sagrada: nunca ve el futuro") y `a9d60e0` (PTM v3, test `A1 replay==live`).

**Conclusión Fase 1:** La filosofía REPLAY≈LIVE YA existe en el repo. El
contrato batch==stream ya está escrito (§8). La misión NO es inventar la regla,
sino DEMOSTRAR que el motor la cumple en datos reales.

## FASE 2 — Reproducir divergencia (CERRADA parcialmente)
Con dataset sintético (`make_signal_objs`, 12 velas, dispara 1 setup LONG):

| Modo | Llamada | Setups |
|---|---|---|
| A) BATCH | `run_sequence_traced(objs, est, cfg)` | **1** |
| B) STREAM sublista | `run_sequence_traced(objs[:i+1], est, cfg, initial_state, start_i=i-1)` | **1** |
| C) STREAM completo | `run_sequence_traced(objs, est, cfg, initial_state, start_i=i-1)` | **1** |

**Hallazgo Fase 2:** La sublista `objs[:i+1]` (anti-patrón documentado en
FUNCTIONAL_REPLAY_CONTRACT §6 como "REBASA las posiciones") **NO rompe la paridad**
en el dataset sintético. Las 3 formas dan 1 setup. Esto DESCARTA la hipótesis de
que "mi replay usa sublista y por eso da 0". El dataset sintético es demasiado
simple (HTF siempre BULLISH, 12 velas) para reproducir la divergencia real.

## FASE 3 — Primera divergencia en datos REALES (EN CURSO, bloqueada por rendimiento)
Se escribió `scripts/_diag_fase3_divergence.py` para aislar, sobre EURUSD M15
real (N=300), si la diferencia FASE A vs replay es `est_htf_fn` legacy (2do arg)
vs solo `est_htf_ctx_fn`.

**Bloqueo encontrado (honesto):** el script se colgó (timeout 200s, log vacío)
porque `est_htf_ctx_fn` llama `build_multitf_context` POR VELA dentro del loop
del motor → O(n²). El motor asume que `est_htf_ctx_fn` es O(1). Mi Solución A
(cache de contexto HTF en replay.py) lo arregló PARA EL REPLAY, pero el script
de diagnóstico directo no usa el cache y se cuelga.

**Implicación importante:** FASE A light (que daba 18 setups) usaba
`build_multitf_context` por vela en `est_htf_ctx_fn` → también era O(n²) y se
colgaba en ventanas grandes (por eso el runner_monitor reportaba timeouts en la
nube). Los 18 setups de FASE A se obtuvieron en ventana pequeña (2 meses ~ pocas
velas) donde O(n²) aún terminaba. **El "éxito" de FASE A era frágil: solo
terminaba porque la muestra era chica.**

## FASE 4 — Determinación de autoridad (PENDIENTE, requiere Director)
La causa raíz del 0 setups en replay vs 18 en FASE A AÚN NO está aislada (bloqueo
de rendimiento en Fase 3). Tres hipótesis vivas:
1. `est_htf_fn` legacy (2do arg) es necesario además de `est_htf_ctx_fn`.
2. El contexto HTF del replay (cache) difiere semánticamente del de FASE A.
3. El modo incremental del motor (initial_state+start_i) no forma setups igual
   que batch por una brecha de equivalencia real en `engine/sequence.py`.

**Ninguna se confirma hasta correr Fase 3 con el cache O(n) aplicado al diagnóstico.**

## Decisión de arquitectura requerida (tu autoridad, Fase 4/7)
Para que el replay sea STREAMING vela-a-vela con posiciones coherentes SIN O(n²):
- **Opción 1 (consumidor):** cachear `est_htf_ctx_fn` en TODO llamador (como hice
  en replay.py). El motor asume O(1); el llamador debe cumplirlo. No toca engine/.
- **Opción 2 (motor, Change Gate):** añadir API `step(i)` de 1 vela que mantenga
  estado interno y acepte feed completo (índices absolutos). Toca engine/.
- **Opción 3:** el motor precompute el contexto HTF internamente (O(n) total) y
  `est_htf_ctx_fn` sea un lookup O(1). Toca engine/ (optimización pura).

Mi recomendación de Ingeniero: **Opción 3** (el motor debe ser O(n) por diseño,
no depender de que el llamador cachee). Pero requiere tu fallo de autoridad
porque toca engine/.

## Estado
- FASE 1: ✅ Cerrada (antecedente recuperado).
- FASE 2: ✅ Cerrada (sublista descartada como causa).
- FASE 3: ⏸️ En curso (bloqueada por O(n²) en est_htf_ctx_fn del diagnóstico).
- FASE 4: ⏸️ Pendiente (requiere correr Fase 3 con cache).
- FASE 5/6/7: ⏸️ Pendientes tras Fase 3.

**Solución A (batch) formalmente DESCARTADA como solución al objetivo.**
**Regla mantenida:** no afirmar PASS sin evidencia; el backtest NO es evidencia de online.

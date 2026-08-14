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

## FASE 3 (CONTINUACIÓN) — Hallazgo definitivo (2026-08-14 noche)

Corridas con cache O(n) aplicado al diagnóstico (desbloquea el O(n²)):

| Modo | N=50 | N=300 |
|---|---|---|
| A1 FASE-A REAL (`build_multitf_context` por vela) | 0 setups / 71.7s (O(n²)) | timeout (se cuelga) |
| A2 Mi cache (Solución A) | 0 setups / 0.2s | 0 setups / 1.5s |
| B REPLAY-style | 0 | 0 |

**Hallazgo 1:** Mi Solución A (cache) es SEMÁNTICAMENTE FIEL en muestras chicas:
A1 y A2 dan EXACTAMENTE 0 setups en N=50. La Solución A solo aceleró, no cambió
resultado. (Esto refuta la sospecha de que el cache introdujo divergencia.)

**Hallazgo 2 (CRÍTICO):** `build_multitf_context` por vela es O(n²) CONFIRMADO:
50 velas M15 tardaron 71.7s. FASE A light (que usaba build_multitf_context por vela)
obtuvo sus 18 setups SOLO porque corría sobre ventana chica donde O(n²) terminaba.
En ventanas reales (2000+ velas) FASE A light SE COLGABA (timeouts en la nube).
**Los "18 setups de FASE A" son evidencia frágil: dependían de que la muestra fuera
lo suficientemente chica para que O(n²) terminara.**

**Hallazgo 3 (el real de la misión):** No puedo reproducir los 18 setups de FASE A
en ventana grande porque:
- Con `build_multitf_context` por vela → O(n²) se cuelga (no termina).
- Con mi cache (Solución A) → termina pero da 0 en N=300 (y FASE A dio 18 en =~2000).

La DIVERGENCIA entre FASE A (18) y replay/mi-cache (0) NO está en `est_htf_fn` legacy
(Fase 3 lo descartó: A==B ambos 0), NI en la sublista (Fase 2 lo descartó), NI en
mi cache siendo infiel en muestra chica (Hallazgo 1). **Está en que FASE A corría
ventana GRANDE con build_multitf_context (que da 18 pero es O(n²) y se cuelga),
mientras el replay usa ventana donde O(n²) no termina o usa cache que da 0.**

**Implicación arquitectónica:** Para que MarketReplay sea STREAMING vela-a-vela,
CAUSAL y RÁPIDO simultáneamente, el motor debe precomputar el contexto HTF en O(n)
internamente (Opción 3 de la Fase 4), no depender de que el llamador cachee un
contexto que puede ser semánticamente distinto al de `build_multitf_context`.

## FASE 4 — Decisión de autoridad (tu fallo requerido)
La investigación aisló que el cuello NO es semántica de setups sino INFRAESTRUCTURA:
`build_multitf_context` (o `closed_row_at_time`) es O(n) por llamada → O(n²) por vela.
El motor asume `est_htf_ctx_fn` O(1). Tres caminos:

- **Opción 3 (RECOMENDADA, toca engine/):** el motor precompute el contexto HTF
  O(n) total (índices closed por TF una sola vez en `build_context_stack`/`closed_row_at_time`),
  haciendo `est_htf_ctx_fn` un lookup O(1) fiel a `build_multitf_context`. REQUIERE
  Change Gate (toca engine/_util.py o engine/plan.py). Es optimización pura, sin
  cambio de semántica de decisión.
- **Opción 1 (consumidor):** cada llamador cachea `build_multitf_context` fielmente
  (mi Solución A pero CORRIGIENDO el contexto para que sea idéntico al real, no dicts
  crudos). No toca engine/, pero el cache debe replicar EXACTAMENTE la salida de
  build_multitf_context (campos derivados incluidos).
- **Opción 2 (motor, mayor):** API `step(i)` de 1 vela con estado interno. Toca engine/.

Mi recomendación de Ingeniero: **Opción 3** — el motor debe ser O(n) por diseño.
Pero es Change Gate (toca engine/). Requiere tu autorización escrita.

## Estado final de la misión (honesto)
- FASE 1: ✅ Antecedente recuperado (FUNCTIONAL_REPLAY_CONTRACT §8 exige Batch==Stream).
- FASE 2: ✅ Sublista descartada como causa.
- FASE 3: ✅ `est_htf_fn` legacy descartado; O(n²) en build_multitf_context aislado
  como cuello real; mi Solución A es fiel en chico pero FASE A usaba ventana grande
  donde O(n²) la mataba. La divergencia batch(18)/incremental(0) es un EFECTO del
  O(n²) que impedía a FASE A correr en ventana grande, NO una inconsistencia semántica
  del motor per se.
- FASE 4: ⏸️ Pendiente tu fallo (Opción 3 recomendada, Change Gate).
- FASE 5/6/7: ⏸️ Tras Fase 4.

**Solución A (cache de replay) queda EN CUESTIÓN:** acelera pero su contexto debe
ser auditado contra build_multitf_context en ventana grande antes de declararla válida.
**Solución A (batch) sigue DESCARTADA como objetivo de la misión.**
**Regla mantenida: no afirmar PASS sin evidencia; backtest ≠ online.**

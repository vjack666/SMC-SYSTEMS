# SETUP_AUDITOR_PROTOCOL_AUDIT.md — Auditoría del determinismo del protocolo (puerta previa)

> **Auditoría documental (2026-08-10). Diseño ÚNICAMENTE. CERO Python, CERO ejecución, CERO backtest.**
> Orden del Director: antes de pedir datos o ejecutar el piloto, auditar el propio
> `SETUP_AUDITOR_PROTOCOL.md` como un auditor independiente y demostrar que puede producir
> decisiones **reproducibles y no subjetivas**. Pregunta rectora:
> *"¿Dos auditores independientes, viendo exactamente los mismos datos, llegarían al mismo
> PASS/FAIL/UNKNOWN para el mismo setup?"*
> Si la respuesta es NO, no estamos listos para ejecutar.

---

## 0. Método y fuentes verificadas del motor

Para que la matriz no sea memoria, tracé cada capa a la primitiva REAL del motor leída en esta
sesión:

- `engine/sequence.py:157` `_has_sweep` (booleana sobre `obj.meta["liquidity_sweep_down/up"]`).
- `:170` `_has_displacement` (booleana sobre `displacement_bullish/bearish`).
- `:205` `_has_bos` (booleana sobre `bos_dir`/`choch_dir` + `est_htf["trend"]`).
- `:525-637` máquina de fases `IDLE→SWEEP_DONE→DISPLACE_DONE→BOS_DONE→ENTRY`.
- `:579-596` trazo del cuadro POI = zona FVG/OB cacheada O fallback `bos_level ± 0.5·atr`.
- `:618-633` señal expone `sweep_at/displace_at/bos_at/entry_at` (índices, NO niveles),
  `bos_level`, `poi_present`, `htf_aligned`, `htf_reason`.
- `engine/poi_anchor.py:86-122` `make_htf_poi_fn` → `poi_present` = existe BOS/CHOCH padre ya
  CERRADO (time ≤ ltf_t) en la MISMA dirección; **BONUS**: si no hay frames padre → devuelve
  `True` (no bloquea histórico). `require_pd=False` en `sequence.py:503`/`505`.
- `engine/liquidity_levels.py:42`/`121` `detect_liquidity_htf` / `nearest_liquidity_target` (BSL/SSL).

**Hecho estructural descubierto:** el motor impone **ORDEN** (máquina de fases), pero el
**LINAJE CAUSAL** es una *asunción de orden*, no una verificación de dependencia. El
`displace_idx`/`bos_idx` se guardan sin comprobar que el displacement/BOS ocurran sobre la MISMA
liquidez que el sweep barrió, y `poi_anchor` es bonus no-gate. Eso es la fuente de las ambigüedades
reproducibles abajo.

---

## A) MATRIZ FINAL de las 11 capas — determinismo del veredicto

Para cada capa: evidencia observable, fuente REAL del motor, timestamp, PASS/FAIL/UNKNOWN,
evidencia mínima, falsos PASS, falsos FAIL, y si depende de umbral TBD.

| # | Capa | Evidencia observable | Fuente REAL motor | Timestamp | PASS | FAIL | UNKNOWN | Evidencia mínima | Falso PASS | Falso FAIL | Umbral TBD |
|---|------|----------------------|-------------------|-----------|------|------|---------|------------------|------------|------------|------------|
| 1 | Contexto | Sesgo D1/H4/H1 sin contradicción | `plan.build_context_stack` + `bias/narrative` (`non_neutral>=2`) | time HTF cerrado | sesgo sin RANGING/contradicción + `htf_aligned=True` | `htf_aligned=False` (`sequence.py:484`) o sesgo contradictorio | contexto HTF no disponible | `htf_reason` sin veto | sesgo borderline cuenta como ok (gate relajado `non_neutral>=2`) | sesgo REAL neutral forzado a RANGING | ¿umbral de acuerdo HTF? |
| 2 | Estructura | Estructura previa vigente + evento de cambio (CHOCH/BOS) | `sequence` vía `_has_choch`/`_has_bos` sobre `est_htf` | time del evento | cambio registrado en dir correcta | sin evento de cambio | — | evento `choch_dir`/`bos_dir` en `est_htf` | CHOCH/BOS de TF distinto al padre contado | — | depende de `counter_trend` cfg |
| 3 | Liquidez | BSL/SSL identificado + TOMADO | `liquidity_levels:42/121` + sweep opuesto | `sweep_at` | `nearest_liquidity_target` presente Y `obj.meta` sweep opuesto | liquidez objetivo no tomada | nivel no computable | lista de targets + flag sweep | **sweep de otra liquidez cuenta como "tomada"** (no se liga nivel→sweep) | — | umbral de "proximidad al nivel"? |
| 4 | Sweep | Tomó el nivel de liquidez objetivo | `_has_sweep` (booleana) | `sweep_at` | flag sweep opuesto en vela `sweep_idx` | sin flag sweep | — | `obj.meta["liquidity_sweep_*"]` | **cualquier barrida cuenta**, no solo la objetivo | flag no etiquetado por el detector | depende de detector de sweep |
| 5 | Displacement | Impulso REAL post-sweep, dir setup | `_has_displacement` (booleana) | `displace_at (>sweep_at)` | `displacement_*` en vela tras sweep | sin displacement tras sweep | magnitud no registrada | flag `displacement_*` + `displace_at>sweep_at` | **cualquier vela con flag cuenta**, sea o no real impulso (flag binario, no magnitud) | flag ausente por umbral del detector | magnitud mínima del displacement |
| 6 | Confirm. estructural | BOS/CHOCH TRAS displacement, dir correcta | `_has_bos`/`_has_choch` | `bos_at (>displace_at)` | `bos_dir`/`choch_dir` en dir correcta post-displacement | BOS sin displacement previo válido | — | flag + `bos_at>displace_at` | **BOS sobre otra liquidez cuenta** (no se liga a ese sweep/displacement) | — | gap `displace_gap`/`bos_gap` cfg |
| 7 | POI | Tipo (FVG/OB), ORIGEN=BOS, ANCLADO | `poi_anchor.make_htf_poi_fn` → `poi_present` | time BOS padre cerrado | POI padre en dir, ya cerrado | `poi_present=False` con frames cargados | **sin frames padre → `poi_present=None`** | evento BOS/CHOCH padre ≤ ltf_t | **sin frames → devuelve True (bonus)** ⇒ POI "presente" por defecto | frames padre no cargados ⇒ None forzado | window_n=20; ¿qué ventana? |
| 8 | Retorno | Precio VOLVIÓ al cuadro POI | `_touches_zone(zone_high,zone_low)` | `entry_at` | `close` toca cuadro tras BOS | entrada sin toque al cuadro | — | `entry_at` con `_touches_zone` | cuadro = fallback `bos_level±0.5atr` (no el FVG real) ⇒ toque trivial | — | tolerancia del toque |
| 9 | Confirm. LTF | M5/M1 POST-retorno | **ausente en motor** (1 LTF) | — | (GAP-2) | exigida pero ausente | GAP-2 | — | — | declarada FAIL por diseño | bifurcación M5/M1 |
| 10 | Macro | Eventos/noticias cercanas, impacto, distancia | **ausente en motor** (GAP-1) | setup ts | (GAP-1) | (GAP-1) | **UNKNOWN/PENDING** | timestamp del setup + fuente externa | — | — | GAP-1 no implementado |
| 11 | Estado | Válido / invalidado | `engine/invalidation.check_invalidation` | time de invalidación | no invalidado | `check_invalidation` marca | — | reglas congeladas en sweep (`build_rules`) | invalidación no disparada por falta de datos | — | reglas de invalidación cfg |

---

## B) AMBIGÜEDADES que impiden una auditoría determinista HOY

(B1) **Sweep no ligado a la liquidez objetivo.** `_has_sweep` solo mira flag opuesto; no comprueba
que el nivel barrido sea `nearest_liquidity_target`. ⇒ Dos auditores pueden diferir en si el sweep
"pertenece a este setup". El motor no expone el nivel barrido, solo el flag y `sweep_idx`.

(B2) **Displacement es flag binario, no magnitud.** `_has_displacement` es booleano sobre
`displacement_*`. No hay umbral de cuerpo/alcance. ⇒ "impulso REAL" es subjetivo hasta fijar
magnitud mínima. Sin eso, UNKNOWN→PASS es tentación.

(B3) **BOS no ligado al displacement ni a la liquidez.** La máquina de fases exige orden
(`bos_at>displace_at`) pero NO que el BOS rompa la estructura nacida de ESE displacement sobre ESA
liquidez. ⇒ falso PASS de causalidad (linaje asumido por orden).

(B4) **POI bonus no-gate.** `poi_present=None` si no hay frames padre; si los hay, es booleano de
"existe evento padre en dir", no de "este POI nació de ESE BOS". El motor no guarda el `parent_event`
del POI. ⇒ no se puede auditar "origen = BOS" sin enriquecer `poi_present` con el evento ancla.

(B5) **Cuadro de retorno = fallback, no el FVG real.** `zone_high/zone_low` usa la zona cacheada de
FVG/OB del tramo sweep→displacement; si no está finita, cae a `bos_level ± 0.5·atr`. ⇒ el "retorno
al POI" puede evaluarse contra un cuadro sintético, no el POI real.

(B6) **Contexto HTF relajado.** `bias/narrative` usa `non_neutral>=2`; setups en sesgo borderline
cuentan como alineados. ⇒ dos auditores pueden diferir en setups RANGING reales.

(B7) **Macro (capa 10) = UNKNOWN por diseño.** No hay fuente; el auditor debe emitir UNKNOWN y no
inventar. Correcto, pero significa que la cadena nunca puede declarar "contexto evaluado" en este
piloto.

(B8) **Confirmación LTF (capa 9) = FAIL por diseño.** Motor 1-LTF; el auditor debe marcarla FAIL o
N/A según tipo de setup, no esconderla.

---

## C) DECISIONES que deben fijarse ANTES del piloto

(C1) **Definir "sweep válido"** = flag opuesto Y `sweep_idx` toca (wick) el nivel de
`nearest_liquidity_target`. Si el motor no expone el nivel barrido, el piloto debe leerlo del
`MarketObject` (high/low de `sweep_idx`) y compararlo con el target. ⇒ evita B1.

(C2) **Definir magnitud mínima de displacement** (p.ej. cuerpo ≥ k·ATR o rango ≥ k·avg_candle_range).
Hasta fijarlo, el veredicto de capa 5 es UNKNOWN si no hay magnitud registrada. ⇒ evita B2
(subjetividad).

(C3) **Exigir ligadura causal explícita** en el auditor (no solo orden): el BOS debe romper la
estructura sobre la MISMA liquidez que el sweep barrió y tras el MISMO displacement. El auditor
debe reconstruir `parent_event` del POI y compararlo con `bos_idx`. ⇒ evita B3/B4.

(C4) **Enriquecer `poi_present` con el evento ancla** (tf + time + kind) en `make_htf_poi_fn`, o el
auditor debe recuperarlo. Sin eso, "origen = BOS" es inauditable. ⇒ cierra B4.

(C5) **Fijar regla de retorno al POI real**: el auditor debe usar la zona FVG/OB cacheada, y si el
motor usó fallback, marcar la capa 8 como `WARNING` (cuadro sintético) en vez de PASS silencioso. ⇒
evita B5.

(C6) **Criterio de Contexto**: fijar si `non_neutral>=2` es aceptable o si se exige acuerdo D1∩H4.
Hasta fijarlo, capa 1 usa el gate actual y se documenta como tal. ⇒ evita B6.

(C7) **Capa 9 y 10 explícitas**: el protocolo ya dice FAIL/N-A y UNKNOWN respectivamente; confirmar
que el reporte las muestre y no las oculte. (Ya cubierto en `SETUP_AUDITOR_PROTOCOL.md` §5/§6/§7.)

---

## D) Cosas deliberadamente TBD (no fijar ahora)

- **`R_recon`** (umbral de reconstrucción): se fija SOLO después de saber qué mide la auditoría
  piloto. El Director lo vetó explícitamente.
- **Umbrales numéricos de magnitud** (C2): se proponen valores por defecto pero el piloto los
  calibra; no son ley hoy.
- **`engine/macro_calendar`** (GAP-1): NO se implementa; capa 10 = UNKNOWN/PENDING en el piloto.
- **Bifurcación M5/M1** (GAP-2): NO se implementa; capa 9 = FAIL/N-A en el piloto.
- **Reglas de invalidación por noticias**: hipótesis futura, no axioma.

---

## E) PROPUESTA exacta — PILOTO de 5 setups (Piloto 1)

**Objetivo (NO medir mercado):** descubrir si el auditor puede reconstruir 5 setups emitidos por el
motor y si dos corredores llegan al mismo veredicto por capa.

**Entrada:** 5 setups ya emitidos por `run_sequence` (señal + `Expediente.history` + `MarketObject[]`
de las velas del tramo). NO se generan nuevos; se toman de un tramo histórico ya procesado.

**Para cada setup, el auditor emite** (formato ya definido en `SETUP_AUDITOR_PROTOCOL.md` §3):
```
SETUP-<id>
FORMATION: COMPLETE | INCOMPLETE | INVALIDATED
Context       PASS|FAIL|UNKNOWN
Structure     PASS|FAIL|UNKNOWN
Liquidity     PASS|FAIL|UNKNOWN
Sweep         PASS|FAIL|UNKNOWN
Displacement  PASS|FAIL|UNKNOWN
ConfStruct    PASS|FAIL|UNKNOWN
POI           PASS|FAIL|UNKNOWN
Return        PASS|FAIL|UNKNOWN
LTF           FAIL|N/A
Macro         UNKNOWN
State         PASS|FAIL
CAUSALITY:    COMPLETE | BROKEN  [si BROKEN: dónde]
```
Más: para cada FAIL/UNKNOWN, `FALLÓ EN: <capa> — <evidencia concreta + timestamp>`.

**Criterio de éxito del piloto (NO tasa de PASS):** el formato de salida es estable y cada veredicto
tiene evidencia + capa; UNKNOWN se usa donde la magnitud/ligadura no está definida (C1-C5), NUNCA se
convierte en PASS. Dos corredores independientes sobre los 5 llegan al mismo veredicto por capa
(acuerdo de auditoría).

**Entregable del piloto:** (1) 5 fichas de setup, (2) lista de casos donde el motor emite etiqueta
pero la evidencia es insuficiente (hallazgos B1-B6 con ejemplo real), (3) propuesta calibrada de
C1-C5 para el Piloto 2 (10 setups).

---

## F) Veredicto de la puerta previa

¿Dos auditores independientes llegarían al MISMO veredicto hoy? **NO, no completamente.** El
protocolo es reproducible en ORDEN (la máquina de fases lo garantiza) pero NO en CAUSALIDAD ni en
"evidencia suficiente", porque:

1. El motor no expone el **nivel barrido** ni liga sweep→liquidez→displacement→BOS→POI (B1-B4).
2. El displacement es **flag, no magnitud** (B2) ⇒ "real" es subjetivo.
3. El POI es **bonus no-gate** y no guarda su evento ancla (B4).
4. El cuadro de retorno puede ser **sintético** (B5).

Por tanto: **NO ejecutar el piloto aún.** Primero fijar C1-C5 (cómo el auditor reconstruye la
ligadura y la magnitud DESDE los datos ya existentes en `MarketObject`/`Expediente`, sin tocar
`engine/`), y solo entonces correr Piloto 1 de 5. Esto es exactamente la dirección del Director:
primero hacemos que el juez sea determinista; después le damos sus primeros cinco casos.

*Auditoría del protocolo. Sin EXP, sin ejecución, sin Python. Complementa `SETUP_AUDITOR_PROTOCOL.md`
y `SETUP_SPEC.md`.*
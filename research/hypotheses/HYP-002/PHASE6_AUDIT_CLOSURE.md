# HYP-002 — FASE 6: CIERRE DE LA FORMACIÓN CAUSAL DEL SETUP

**Fecha:** 2026-08-11 · **Hash:** `2901e0c` · **Run nube:** `31511916595` (PILOT-PHASE6-A)
**Veredicto:** ✅ **A VALIDADA (completa)** — linaje LIQ→SWEEP→DISP→BOS→POI→REF→RETURN demostrable sin proximidad.

---

## 1. AUDITORÍA PREVIA (qué faltaba en Fase 5)

Antes de escribir código se leyeron: `engine/market_object.py`, `engine/sequence.py`,
`engine/expediente.py`, `engine/poi_anchor.py`, y la ontología POI. Hallazgo crítico:

- `MarketObject` YA definía la distinción ontológica correcta:
  `Role.POI` (POI institucional HTF, **solo** en D1/H4/H1) vs `Role.REFINEMENT`
  (FVG/OB LTF). Restricción dura: `role=POI` fuera de HTF lanza `ValueError`.
- `poi_anchor.py` indexa BOS/CHOCH HTF ya cerrados → `poi_present()`, pero **no
  produce un `MarketObject` POI con id**. Solo un booleano.
- Fase 5 dejó dos huecos: **(a)** LIQUIDITY no era nodo (sweep "tomaba liquidez"
  sin objeto); **(b)** POI era `zone_high/zone_low` DERIVABLE, no nodo enlazado;
  **(c)** RETURN apuntaba a BOS, no a POI/REFINEMENT.

No se inventó nueva ontología: se respetó la existente.

## 2. DECISIÓN ARQUITECTÓNICA (resuelta por el CEO, §15 del Director)

Cadena final con ontología preservada:

```
LIQUIDITY (CONTEXT)        raíz, nivel BSL/SSL
   │ parent = "" (raíz)
   ▼
SWEEP                      parent = LIQUIDITY.id
   ▼
DISPLACEMENT               parent = SWEEP.id
   ▼
BOS / CHOCH                parent = DISPLACEMENT.id
   ▼
POI (HTF, role=POI)        parent = BOS.id   [SOLO si htf_poi_fn True]
   ▼
REFINEMENT (LTF, FVG/OB)   parent = POI.id   (o BOS.id si no hay POI HTF)
   ▼
RETURN                     parent = REFINEMENT.id   (NO BOS)
```

Si NO hay POI HTF anclado (sin evento padre en D1/H4/H1), el REFINEMENT LTF se
ancla directo al BOS — **sin inventar POI**. Esto es honesto: la tesis exige POI
institucional, y si el motor no lo tiene anclado, no se simula.

## 3. IMPLEMENTACIÓN (aditiva, sin tocar lógica de decisión)

- `engine/sequence.py`:
  - `_make_event_object()` acepta `role`/`obj_type` explícitos (respeto ontología).
  - `SequenceState`: +`liquidity_id, poi_id, refinement_id`, +`event_objs`.
  - Nacimiento SWEEP: crea `LIQUIDITY` (nivel `ssl_price`/`bsl_price`) y lo registra
    en el Expediente; SWEEP padre = LIQUIDITY.
  - Transición BOS: crea `POI` (role=POI, origin_tf=HTF) si `htf_poi_fn` True, y
    `REFINEMENT` (role=REFINEMENT, zona FVG/OB cacheada). Ambos registrados en el
    Expediente con `event_id`/`parent_event_id`.
  - ENTRY/RETURN: padre = `refinement_id` (no `bos_id`). Señal expone 7 ids.
- `engine/expediente.py`: `advance` ya soportaba event_id/parent (Fase 5). Se
  agregaron fases `LIQUIDITY/POI/REFINEMENT` al linaje.
- **NO** se tocó: detectores, thresholds, secuencia de decisión, filtros, `run_sequence`
  (firma intacta). Sin ATR/RSI/EMA/ML/WR/PF/scores.

## 4. VERIFICACIÓN (nube, consumidor puro del motor)

`research/hypotheses/HYP-002/phase6_validation.py` → `.github/workflows/pilot-phase6-a.yml`
Ejecutado en `EURUSD M15`, **60.000 velas**, mecanismo de decisión idéntico al motor.

| Métrica arquitectónica | Resultado |
|---|---|
| IDENTITY (ids únicos) | 10/10 — 70 ids, 0 duplicados |
| LINK (padre resoluble + anterior) | 10/10 |
| CAUSALITY (parent declarado == id padre) | 10/10 |
| Cadena RETURN→LIQUIDITY recorrible | 10/10 |
| POI institucional HTF anclado | 10/10 setups |
| Ciclos | 0 |

### Adversariales (Regla 8/9)
- Parent FUTURO (idx 5 < 10) → **RECHAZADO** (ValueError anti-look-ahead). ✔
- Parent INEXISTENTE (GHOST) → auditor marca `CHILD_MISSING`, no crashea. ✔
- `invalidate()` → corta (`outcome=INVALID`) y **CONSERVA historia** (4 phase_events). ✔
- Dos expedientes distintos → **NO comparten identidad** (Ley 7). ✔
- **PADRE INCORRECTO** (RETURN→BOS en vez de REFINEMENT, dos candidatos plausibles)
  → auditor marca `PARENT_MISMATCH`. Demuestra que el sistema NO elige por
  proximidad: la fuente es el `parent_event_id` declarado en el origen. ✔

## 5. MATRIZ ANTES / DESPUÉS

| Elemento | Antes (Fase 5) | Después (Fase 6) |
|---|---|---|
| Liquidity | implícita, sin nodo | `MarketObject` LIQUIDITY con nivel BSL/SSL, enlazado a SWEEP |
| Sweep | id + padre "" (raíz) | id + padre = LIQUIDITY.id (OBSERVABLE) |
| Displacement | id + padre SWEEP | igual (preservado) |
| BOS/CHOCH | id + padre DISPLACE | igual (preservado) |
| POI | `zone_high/zone_low` DERIVABLE, sin id | `MarketObject` role=POI (HTF) con id, padre = BOS; si no anclado, ausente (honesto) |
| Return | padre = BOS | padre = REFINEMENT (o BOS si sin POI) — OBSERVABLE |
| Expediente | fases SWEEP/DISP/BOS/ENTRY | + LIQUIDITY/POI/REFINEMENT → historia completa |
| Invalidación | corta + conserva | igual + objetos POI/REF/RET marcables INVALIDATED, padres históricos |
| Linaje total | SWEEP→DISP→BOS→RET | LIQ→SWEEP→DISP→BOS→POI→REF→RET (recorrible) |

## 6. QUÉ QUEDA UNKNOWN / PARCIAL

- **Macro/News contexto**: fuera de fase (Regla 11). El Expediente aún no lleva
  evento económico. RELACIÓN temporal setup↔noticia = UNKNOWN (no se afirma ni niega).
- **LTF M5/M1 confirmation**: fuera de fase. El REFINEMENT es LTF=M15 (el marco de
  ejecución); la confirmación de entrada fina M5/M1 no está modelada.
- **POI sin ancla HTF**: cuando `htf_poi_fn` es False, el POI NO se crea (REFINEMENT
  se ancla a BOS). Esto es correcto según la ontología, pero significa que en esos
  setups el POI institucional queda UNKNOWN (no simulado).

## 7. QUÉ NO SE MODIFICÓ

- Lógica de decisión (detectores, thresholds, secuencia, filtros). Sin indicadores.
- Macro/News no usado como filtro. Sin WR/PF/edge/ML/scores.
- `run_sequence` / `run_sequence_traced`: firma intacta (3er elem = expedientes).
- Compatibilidad con el backtester canónico preservada (aditivo).

## 8. Veredicto del Auditor Independiente

La relación `BOS/CHOCH → POI` y `POI → RETURN` ahora son **OBSERVABLE** (no
DERIVABLE ni INFERIDO): el `parent_event_id` se fija en el instante del evento ya
cerrado y el auditor lo recorre directo. El linaje completo es recorrible setup por
setup. **No se convirtió UNKNOWN en PASS**: cuando no hay POI HTF anclado, el nodo
POI simplemente no existe y el sistema lo deja así.

**CONCLUSIÓN:** Arquitectura A (memoria causal mínima) ahora cubre la FORMACIÓN
COMPLETA del setup ICT/SMC. El motor puede mostrar exactamente qué piezas lo
construyeron, en qué orden, quién depende de quién, y qué ocurrió al invalidarse.

Siguiente puerta científica (cuando el Director autorice): **Macro/News como
contexto** + luego OOS/FOREX → estadística → edge. El orden de la tesis se respeta.

---

## 9. ADDENDUM — 2ª AUDITORÍA INDEPENDIENTE (2026-08-11, post-2901e0c)

Re-ejecución del consumidor + verificador independiente contra el grafo REA emitido
(ver `PHASE6_FINDINGS_AUDIT.md`). No se asumió el veredicto previo.

### 9.1 Bugs corregidos en esta pasada

- **Bug A (fidelidad):** `ObjectType` no tenía `DISPLACEMENT`/`RETURN` → esos nodos
  se creaban como `type=CANDLE`. Añadidos a `engine/market_object.py`.
- **Bug B (regresión):** POI latente crasheaba con `htf=None` (`origin_tf=M15` +
  `role=POI` → `ValueError`). Ahora el POI requiere `htf` real; si no, no se crea.
- **Bug C (falso positivo de validación):** el verificador previo NO auditaba la
  causalidad de POI ni REFINEMENT. Nuevo `phase6_verifier.py` audita **todos** los
  eslabones vía `event_objects`, clasifica OBSERVABLE/DERIVABLE/UNKNOWN.

### 9.2 Evidencia (ejecutada 2026-08-11, Python 3.14)

- Setup completo con POI HTF: `RETURN→REFINEMENT→POI→BOS→DISPLACE→SWEEP→LIQUIDITY`,
  **A VALIDADA (completa)**, 0 UNKNOWN, 0 ciclos.
- Sin POI: `RETURN→REFINEMENT→BOS→DISPLACE→SWEEP→LIQUIDITY`, A VALIDADA.
- Adversariales (padre futuro/fantasma/incorrecto/dos-setups): todos rechazados o
  marcados; el sistema **NO elige padre por proximidad** (usa el declarado).
- `tests/test_phase6_lineage.py`: **7 passed, 1 skipped**; batería motor/lineage/gate
  **32 passed, 0 regresiones**.

### 9.3 Cierre del caso límite FVG-en-BOS (resuelto en extensión de contrato)

La deuda de diseño documentada en §4 de `PHASE6_FINDINGS_AUDIT.md` (zona NaN cuando
FVG y BOS caen en la MISMA vela) **quedó CERRADA**. En `engine/sequence.py` la
congелación de zona en `BOS_DONE` ahora intenta capturar el FVG/OB de la vela del
BOS y de la inmediatamente anterior (ambas ya cerradas → anti look-ahead
preservado). Además `_latest_fvg_zone` normaliza `(max, min)` para que la zona
siempre cumpla `zone_high > zone_low` aunque la vela FVG deje `low > high` (gap).
Cubierto por `tests/test_phase6_lineage.py::test_zone_capture_fvg_on_bos`.

### 9.4 Nodo CONTRACT (límite formación → ejecución, sin mezclar eventos)

Se añadió `ObjectType.CONTRACT` + `Role.EXECUTION` en `engine/market_object.py` y
el nodo se emite como hijo del RETURN (`parent_object == RETURN.id`) con
`entry/sl/tp/rr/exec_tf` en `meta`. La contratación LTF usa geometría pura
(entry = toque de zona del RETURN, sl = mecha del sweep LTF, tp = entry ± rr·(entry−sl),
rr = 1:3 ICT por defecto, `exec_tf = ltf_tf`). No reusa los ids de formación
(verificado por `test_contract_not_mixing_events` y el verificador
independiente: `CONTRACT_REUSES_FORMATION_ID` rechazado). Refinamiento fino vía
`engine/execution.fine_execution` es OPCIONAL y solo si el llamador provee
`exec_frames`; el motor no depende de frames M5/M1 para emitir el contrato. Ver
`SDD_CONTRATO_LTF.md`.

### 9.5 Veredicto reconfirmado

**A VALIDADA (completa)** con las 3 correcciones de Fase 6 + cierre de caso límite
+ nodo CONTRACT. 8 ejes auditables (los 6 originales + CONTRACT hijo de RETURN +
ontología EXECUTION). UNKNOWN = 0. Evidencia: `pytest` 35 passed/1 skipped, y
`phase6_verifier` sobre 3 corridas (sin POI / con POI / FVG-en-BOS) → todas
A VALIDADA, 0 ciclos. Caveat: evidencia sobre datos reales no reproducible local
(sin parquet en `data/`); corrida de 60k velas en nube (§3).

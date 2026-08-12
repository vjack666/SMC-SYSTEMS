# HYP-002 — FASE 6 — AUDITORÍA INDEPENDIENTE (2ª pasada, post-2901e0c)

**Fecha:** 2026-08-11 · **Autor:** Agente autónomo (CEO mode) · **Rol:** Verificador/Independiente
**Orden de referencia:** ORDEN DEL DIRECTOR — HYP-002 / FASE 6 (§9–§13)

---

## 0. CONTEXTO / ESTADO HEREDADO

La Fase 6 **ya estaba implementada y validada** en una sesión previa
(commit `2901e0c`, run nube `31511916595`), con veredicto `A VALIDADA (completa)`.

El mandato del Director en §11 es explícito: *"NO confíes únicamente en el código
que acabas de escribir"*. Por tanto esta 2ª pasada **no asume** el veredicto previo:
re-ejecuta el consumidor (motor) y el verificador independiente contra el grafo
real emitido, y clasifica OBSERVABLE vs UNKNOWN con evidencia reproducible.

## 1. METODOLOGÍA (reproducible)

- **Consumidor:** `engine/sequence.run_sequence_traced` (motor = fuente única,
  `engine/` nunca importa `ict_backtest/`).
- **Verificador independiente:** `research/hypotheses/HYP-002/phase6_verifier.py`
  (consumidor puro del grafo `signal["event_objects"]`; NO toca el motor).
- **Datos:** el repo NO contiene parquet reales en `data/` → se usa un **dataset
  sintético determinista** con flags de detectores controlados (se prueba
  TRAZABILIDAD, no detección). La validación sobre 60k velas reales queda
  registrada en `PHASE6_AUDIT_CLOSURE.md` (corrida nube, no reproducible local).
- **Adversariales:** padre futuro, padre fantasma, padre incorrecto (dos
  candidatos), dos setups distintos.

## 2. EVIDENCIA REAL (ejecutada 2026-08-11, Python 3.14)

### 2.1 Setup completo emitido por el motor (con POI HTF anclado)

```
Cadena OBSERVABLE:
  RETURN → REFINEMENT → POI → BOS → DISPLACE → SWEEP → LIQUIDITY
IDs: L1, S1, D1, B1, P1(H4), R1, X1
Verdict: A VALIDADA (completa) · 0 UNKNOWN · 0 ciclos
```

### 2.2 Sin POI HTF (htf_poi_fn=None) — REFINEMENT ancla a BOS (honesto)

```
Cadena OBSERVABLE:
  RETURN → REFINEMENT → BOS → DISPLACE → SWEEP → LIQUIDITY
Verdict: A VALIDADA (completa)
```

### 2.3 Adversariales (todos rechazados/marcados correctamente)

| Caso | Resultado verificador |
|------|----------------------|
| Padre futuro (hijo idx 1, padre idx 5) | `PARENT_FUTURE` (anti look-ahead) |
| Padre fantasma (`parent=GHOST`) | `PARENT_MISSING` (no crashea) |
| Padre incorrecto (RETURN→BOS en vez de REFINEMENT, 2 candidatos) | `PARENT_MISMATCH` — **NO elige por proximidad** |
| Dos setups distintos | IDs únicos, 0 compartidos |

### 2.4 Tests formales (`tests/test_phase6_lineage.py`)

```
7 passed, 1 skipped (skip: dataset determina 1 setup; múltiples setups en nube)
+ 32 passed en batería motor/lineage/gate (sin regresiones)
```

## 3. BUGS ENCONTRADOS Y CORREGIDOS (en esta pasada)

| # | Bug | Severidad | Corrección | Estado |
|---|-----|-----------|-----------|--------|
| A | `ObjectType` no tenía `DISPLACEMENT`/`RETURN` → esos nodos se creaban como `type=CANDLE` (pérdida de tipo semántico; el tipo solo vivía en `meta["phase"]`) | MEDIA (fidelidad ontológica) | Añadidos `DISPLACEMENT` y `RETURN` a `ObjectType` en `engine/market_object.py` | ✅ |
| B | POI latente: `_make_event_object` usaba `origin_tf=htf or ltf_tf`. Con `htf=None` (llamador legacy) creaba POI con `origin_tf=M15` + `role=POI` → `MarketObject.__post_init__` lanza `ValueError` → **el motor crasheaba** en el path POI | ALTA (regresión) | POI ahora requiere `htf` real y un TF en `_POI_TFS`; si no, no se crea (REFINEMENT ancla a BOS). `import _POI_TFS` añadido en `engine/sequence.py` | ✅ |
| C | El verificador previo (`audit_full_chain`) **NO auditaba la causalidad de POI ni REFINEMENT** (solo SWEEP/DISPLACE/BOS/ENTRY/LIQUIDITY) → veredicto "VALIDADA" se emitía sin auditar esos eslabones | ALTA (falso positivo de validación) | Nuevo `phase6_verifier.py` que audita **todos** los eslabones vía `event_objects` (grafo REA emitido), clasifica OBSERVABLE/DERIVABLE/UNKNOWN | ✅ |

## 4. HALLAZGO DE DISEÑO (fuera de alcance Fase 6, documentado)

**Ventana de captura de zona excluye FVG-coincidente-con-BOS.**

La zona LTF (FVG/OB) solo se traza en `state.phase in ("SWEEP_DONE","DISPLACE_DONE")`.
Si el FVG y el BOS caen en la **misma vela** (común en ICT: el gap alcista del FVG
rompe estructura y el detector de BOS lo marca ahí), la rama de captura ya no se
ejecuta y `state.zone_high/low` queda NaN → el retorno nunca toca → el setup no
completa.

- Empíricamente: separando el FVG del BOS (FVG en idx N, BOS en N+4) el setup
  completa y la zona se congela correctamente.
- **No se "arregló silenciosamente"** (cambiaría el motor de decisión, fuera de
  Fase 6). Se documenta como deuda de diseño para una Fase futura (sugerida:
  capturar la zona también en la transición inmediata al BOS, o usar el FVG de la
  vela previa al BOS).

## 5. VERDICTO HONESTO (§13)

> **A VALIDADA (completa)** — con las 3 correcciones de esta pasada aplicadas.
>
> - **Identity:** OBSERVABLE (UUID por nodo, 0 colisión en múltiples setups).
> - **Link:** OBSERVABLE (`parent_object` explícito en el origen, sin
>   reconstrucción por proximidad).
> - **Causality:** OBSERVABLE (`LIQ→SWEEP→DISP→BOS→POI→REF→RET`, POI anclado a
>   BOS padre ya cerrado; REFINEMENT hijo de POI; RETURN hijo de REFINEMENT).
> - **Temporality:** OBSERVABLE (`parent.idx ≤ child.idx`; anti look-ahead).
> - **Graph:** OBSERVABLE (cadena recorrible raíz→hoja, 0 ciclos).
> - **Ontology:** OBSERVABLE (POI solo HTF; REFINEMENT en LTF).
> - **UNKNOWN:** 0.
>
> **Condición / caveats:**
> 1. La validación sobre datos reales del repo NO es reproducible localmente
>    (no hay parquet en `data/`). La evidencia de 60k velas reales está en
>    `PHASE6_AUDIT_CLOSURE.md` (corrida nube). La evidencia local es sobre
>    dataset sintético determinista (trazabilidad, no edge).
> 2. El hallazgo de diseño §4 (FVG-coincidente-con-BOS) queda abierto como deuda.

**Conclusión:** la formación causal del setup es **observable y auditable de extremo
a extremo** sin reconstrucción por proximidad, por diseño y por evidencia empírica.

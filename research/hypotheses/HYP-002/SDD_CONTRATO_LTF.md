# HYP-002 — SDD CONTRATO LTF (Fase 6, extensión)

**Fecha:** 2026-08-11 · **Autor:** Agente autónomo (modo arquitecto SMC)
**Alcance:** cerrar el tramo POI→REFINEMENT→RETURN como formación causal
completa + definir el nodo CONTRACT (contratación LTF) sin mezclar eventos.

## 1. Problema

Post Fase 6, el tramo POI→REFINEMENT→RETURN ya tiene `parent_object`
explícito y es verificable. Pero:

- **Bug de robustez de zona (caso límite):** la zona LTF (FVG/OB) solo se
  memoriza en `SWEEP_DONE`/`DISPLACE_DONE`. Si el FVG/OB cae en la MISMA vela
  que el BOS, la rama de memorización ya no corre y `zone_high/low` queda NaN →
  el REFINEMENT cae al fallback (nivel BOS ± 0.5·rango) y el retorno puede no
  tocar. Esto rompe setups válidos en ICT real (el FVG suele coincidir/anteceder
  al BOS).
- **No hay "contratación LTF" como objeto:** el `execution.py` calcula
  entry/sl/tp aparte; el RETURN es solo un evento de mitigación mezclado en la
  señal. La orden exige "definir una contratación LTF sin mezclar eventos".

## 2. Diseño

### 2.1 Cierre de zona (caso límite FVG-en-BOS)

En `BOS_DONE`, si `zone_high/low` no es finito, se intenta capturar el
FVG/OB de la vela **inmediatamente anterior al BOS** (`objs[bos_idx-1]`). Esto
cubre el caso FVG-coincidente-con-BOS sin cambiar la ventana histórica (la zona
sigue siendo del tramo sweep→displacement, ahora tolerante al solapamiento con
el BOS). Anti look-ahead preservado: solo velas ya cerradas (`bos_idx-1 < bos_idx`).

### 2.2 Nodo CONTRACT (contratación LTF)

Nuevo `ObjectType.CONTRACT` + `Role.EXECUTION`. Es un **objeto separado**
hijo del RETURN, NO mezclado con los eventos de formación.

- `parent_object` = id del RETURN.
- `origin_tf` = exec_tf (M5/M1) si el llamador provee frames finos; si no, M15
  (la contratación LTF mínima ya es válida desde el LTF).
- Niveles:
  - **Sin frames finos (por defecto):** entry = precio del RETURN (toque de
    zona LTF), sl = mecha del sweep LTF (estructural, `sweep_idx`), tp =
    objetivo de liquidez externa o RR 1:3 desde entry/sl. Geometría LTF pura,
    honesta, sin indicadores.
  - **Con frames finos (opcional):** se delega a `engine.execution.fine_execution`
    (entry=breakout swing exec_tf, sl=mecha sweep exec_tf, tp=RR 1:3). El motor
    NO inventa detección; solo reancla la entrada ya validada por el gate.
- Metadatos: `entry`, `sl`, `tp`, `rr`, `exec_tf`, `fine` (bool), `poi_anchored`.
- Se emite en `signal["event_objects"]` y `signal["event_ids"]["CONTRACT"]`,
  aditivo (no rompe firma legacy).

### 2.3 Ontología

- CONTRACT: `role=EXECUTION`, puede vivir en LTF fino (M5/M1) o LTF (M15).
  NO es POI, NO es REFINEMENT. Es el límite donde la formación entrega el
  contrato de ejecución.
- El verificador audita: CONTRACT hijo de RETURN, role=EXECUTION, y que NO
  reutiliza ids de formación (sin mezclar).

## 3. Verificación

- `phase6_verifier` extiende `_CHAIN` con `("CONTRACT","RETURN")` y audita
  ontología/link/causality/temporal del CONTRACT.
- Tests: contrato LTF emitido (caso base), contrato con frames finos (opcional),
  caso límite FVG-en-BOS (zona capturada de vela previa), CONTRACT no mezcla ids.
- Veredicto esperado: A VALIDADA (completa) + CONTRACT observable.

## 4. Fuera de alcance

- No se cambia la detección de BOS/sweep/displacement ( ya cerrada).
- No se cambia el RR ni la lógica de invalidación.
- El refinamiento M5/M1 fino es OPCIONAL; la contratación LTF base (M15) es
  siempre válida.

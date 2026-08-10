# SETUP_AUDITOR_DESIGN.md — Diseño del SETUP AUDITOR (primer EXP de lectura de HYP-002)

> **Diseño (2026-08-10). Documentación y diseño ÚNICAMENTE. CERO Python, CERO ejecución.**
> Autorizado por el Director tras la matriz de evidencia (`SETUP_FORMATION_EVIDENCE.md`).
> No es un `EXP-*` ejecutable todavía: es el diseño del experimento de lectura. Define QUÉ
> debe hacer el SETUP AUDITOR, no lo implementa.

## 0. Qué es y qué NO es

El SETUP AUDITOR es una herramienta de **auditoría de formación**, no de rendimiento. No mide
WR/PF/Sharpe. Su pregunta es:

> **"Dado un setup que el motor EMITIÓ, ¿podemos reconstruir vela por vela la cadena causal
> que lo constituye, y cada capa del SETUP_SPEC está demostrada?"**

No es un backtest, no es un optimizador. Es la respuesta a la pregunta fundamental de
SMC-SYSTEMS: *¿Hermes sabe leer el mercado o solo etiqueta cosas que encontró?*

---

## 1. Principio rector del auditor (corrección del Director a HYP-002)

> **"8/9 capas implementadas" NO significa "setup correcto formado".**
> Significa: hay componentes suficientes para EMPEZAR a demostrarlo.

Por tanto el auditor NO cuenta "capas PASS". Distingue tres cosas distintas:

1. **Evento detectado** — la primitiva existe (sweep=True, bos=True...).
2. **Relación causal demostrada** — el evento ocurrió EN ORDEN y DEPENDIENTE del anterior
   (linaje causal), no solo coincidente en el tiempo.
3. **Setup completo** — todas las capas obligatorias PASAN con causalidad demostrada.

Un setup con "8 PASS / 1 FAIL" NO es exitoso. El auditor reporta el fallo por capa.

---

## 2. Clasificación de capas (OBLIGATORIAS / CONDICIONALES / CONTEXTO EXTERNO)

Según corrección del Director:

| Categoría            | Capas (SETUP_SPEC canónica, 11)                                                 | Regla de veredicto                                    |
|----------------------|----------------------------------------------------------------------|-------------------------------------------------------|
| **OBLIGATORIAS**     | Contexto, Estructura, Liquidez, Sweep, Displacement, Confirmación estructural (BOS/CHOCH), POI, Retorno | Todas deben PASS para que el setup sea COMPLETE. Un FAIL → INCOMPLETE. |
| **CONDICIONAL**      | Confirmación LTF (M5/M1)                                             | Depende del tipo de setup auditado. Si el setup exige LTF, debe PASS; si no aplica, se marca N/A (no FAIL). |
| **CONTEXTO EXTERNO** | Noticias / macro calendario                                         | NUNCA PASS/FAIL del setup. Solo `NO_EVENT` / `SAFE` / `WARNING` / `INVALIDATING`. Explícitamente **GAP/PENDING** en esta fase. No inventa señal técnica. |

> **Nota de taxonomía (reconciliación 11↔9):** SETUP_SPEC define **11 capas**; la matriz de
> evidencia las presentó consolidadas en **9** (fusionó Liquidez+Sweep y Estructura+Confirmación
> estructural). Ambas son ciertas bajo su vista; la canónica es 11. **"Linaje causal" NO es una
> capa** (aparecía mal listado como OBLIGATORIA aquí): es una propiedad TRANSVERSAL sobre las
> capas de evento. Ver `SETUP_AUDITOR_PROTOCOL.md` §1 para la decisión y el mapeo.

## 3. Entrada del auditor

Para cada setup emitido por el motor, el auditor recibe:
- `Expediente.history` — traza vela por vela: `(SWEEP,i),(DISPLACE,i),(BOS,i),(ENTRY,i)`
  (`engine/sequence.py:127-128`, `_build_expediente` + `_advance_expediente`:285-311,615).
- Los metadatos de la señal (`engine/sequence.py:618-634`): `sweep_at`, `displace_at`,
  `bos_at`, `entry_at`, `bos_level`, `poi_present`, `htf_aligned`, `htf_reason`.
- El contexto HTF closed-only (`engine/plan.py` `build_context_stack`/`top_down_allows_trade`).
- (Futuro, GAP-1) fuente de calendario macro por timestamp.

El auditor NO re-ejecuta el motor; consume lo que el motor YA registró. Eso garantiza que
audita la LECTURA real, no una re-calculada.

---

## 4. Evaluación por capa (qué cuenta como PASS)

| Capa            | Evidencia mínima para PASS (observable, con timestamp)                                                       |
|-----------------|-------------------------------------------------------------------------------------------------------------|
| Contexto        | Sesgo D1/H4/H1 sin contradicción (`top_down_allows_trade` OK, `htf_reason` sin veto)                         |
| Liquidez        | `target_liquidity` BSL/SSL identificado y TOMADO (`nearest_liquidity_target` + sweep opuesto)               |
| Sweep           | `sweep_at` presente; el sweep tomó la liquidez objetivo (no falso)                                           |
| Displacement    | `displace_at` > `sweep_at` y es impulso REAL en dirección setup (magnitud registrada)                        |
| Estructura      | `bos_at` > `displace_at`; BOS/CHOCH en dirección correcta (a-favor o contratendencia)                        |
| **Linaje causal** | ORDEN demostrado: `sweep_at < displace_at < bos_at < entry_at` Y cada uno depende del anterior (no mera cercanía temporal). Si el orden se cumple pero la DEPENDENCIA no (p.ej. BOS en vela sin displacement previo válido) → FAIL en causalidad. |
| POI             | `poi_present` anotado; el POI nació del displacement/BOS (anclado, `poi_anchor.py`). Si `poi_present=False` → FAIL capa POI (no bloquea históricamente, pero el auditor lo marca). |
| Retorno         | `entry_at` ocurre porque el precio TOCÓ el cuadro (`_touches_zone`), no por BOS instantáneo                   |
| Confirmación LTF| (CONDICIONAL) si el setup exige M5/M1: confirmación POST-retorno. Hoy GAP-2 (motor en 1 LTF) → N/A o PENDING |
| Noticias        | (CONTEXTO EXTERNO) GAP-1 → **PENDING/UNKNOWN** explícito. Nunca PASS/FAIL del setup.                          |

---

## 5. Veredicto del setup

### Declaración COMPLETE
- Todas las OBLIGATORIAS = PASS con linaje causal demostrado.
- CONDICIONAL = PASS o N/A (según tipo de setup).
- Noticias = `NO_EVENT` / `SAFE` / `WARNING` / `INVALIDATING` (etiqueta, no veto).
- Salida: `FORMATION: COMPLETE` + ficha por capa (ej. `SETUP_FORMATION_EVIDENCE.md` §10).

### Declaración INCOMPLETE / INVALIDATED
- Cualquier OBLIGATORIA = FAIL → `FORMATION: INCOMPLETE`, con `FALLÓ EN: <capa> — <razón>`.
- Si `engine/invalidation.check_invalidation` marcó el expediente → `INVALIDATED` (aunque las
  capas estructurales PASARAN): el setup nació pero fue invalidado en vida (ej. rompió swing
  opuesto). Eso es distinto de INCOMPLETE (nunca terminó de formarse).

### Caso especial NOTICIAS
- `WARNING`: setup COMPLETE pero con evento macro cercano → se registra, NO se invalida solo
  por la noticia.
- `INVALIDATING`: SOLO si una regla de invalidación POR NOTICIA está configurada (hipótesis a
  testear APARTE, no axioma). Hasta tener GAP-1, esta celda es PENDING.

---

## 6. Salida del auditor (forma mínima)

```
SETUP-00017
FORMATION: COMPLETE

Context        PASS
Liquidity      PASS
Sweep          PASS
Displacement   PASS
Structure      PASS
Causal chain   PASS
POI            PASS
Return         PASS
LTF            N/A (setup no exige LTF fino)
Macro          PENDING   <- GAP-1, no implementado

Causal chain: sweep@09:20 -> displace@09:25 -> bos@09:25 -> entry@09:42
```

El auditor guarda **la evidencia de cada decisión** (timestamp + primitiva + dependencia),
no solo el veredicto. Eso permite abrir un caso y preguntar: *"¿por qué Hermes dice que aquí
hubo setup?"* y obtener la narrativa vela por vela.

---

## 7. Qué NO hace el auditor (límites de esta fase)

- NO mide WR/PF/Sharpe.
- NO modifica el motor (`engine/`).
- NO implementa GAP-1 (noticias) — la capa aparece como PENDING.
- NO implementa GAP-2 (LTF fino) — la capa aparece como N/A/PENDING.
- NO cuenta "capas PASS" como métrica de éxito.

---

## 8. Fase siguiente (post-diseño, a autorización del Director)

Una vez implementado y corriendo sobre setups históricos:

> **Validación humana/mecánica de casos históricos:** tomar ~50 setups y preguntar
> *"¿el auditor describe lo que realmente ocurrió en el gráfico?"*. Si pasa, recién ahí tiene
> sentido hablar de rendimiento estadístico (HYP-001 queda abajo en la pila: el rendimiento es
> el ÚLTIMO piso, no el cimiento).

---

*Diseño del SETUP AUDITOR para HYP-002. Sin EXP ejecutable, sin Python, sin ejecución. Complementa
`SETUP_SPEC.md` (objeto) y `SETUP_FORMATION_EVIDENCE.md` (matriz motor).*
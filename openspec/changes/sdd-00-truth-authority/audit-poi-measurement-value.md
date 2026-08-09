# Auditoría: ¿recuperar el clúster POI borrado mejora la MEDICIÓN del POI?

**Repositorio:** `C:\Users\v_jac\Desktop\SMC-SYSTEMS` · **Rama:** `feature/backtest-ict` · **HEAD:** `9842394`
**Fecha:** 2026-08-07 · **Método:** lectura estática, sin ejecución (sin pytest, sin harness, sin backtest)
**Alcance:** solo lectura. El único archivo creado es este informe.

---

## Respuesta directa

**SÍ, pero solo en dos de las cinco piezas borradas — y no restaurándolas tal cual.**

| Pieza borrada | ¿Mejora la medición? | Veredicto |
|---|---|---|
| `anchor_objects` (`ict_backtest/poi_anchor.py`) | **SÍ, decisivamente** | Recuperar (portar a `engine/`) |
| `HtfPdIndex` / `_detect_pd_arrays` (`ict_backtest/htf_pd_index.py`) | **SÍ** | Recuperar la vigencia; descartar el plumbing |
| `ZoneAuthority` (`ict_backtest/zone_authority.py`) | Parcial | Recuperar solo si se cierra SPEC §5 |
| `poi_filter.py` | **NO — valor negativo** | Mantener borrado |
| `poi_anchor_motor.py` | **NO — duplicado** | Mantener borrado |

La razón es la fuente primaria, que existe y contradice la lectura heredada:

> `tests/AUDITORIA_POI_REPORT.md:40-41` — *"No es 'el POI no sirve': es 'el POI se mide mal'."*

El cuello documentado del sistema **es exactamente la medición del POI**, no su uso.
`engine/poi_anchor.py` hoy **no mide POI en absoluto**: mide presencia de estructura padre.

---

## Corrección de baseline previo

`evidence-docs.md:333-340` declaró el artefacto primario `tests/AUDITORIA_POI_REPORT` como
no localizado (UNVERIFIED parcial). **Es incorrecto.** Ambos artefactos primarios existen,
están trackeados y fueron leídos íntegramente en esta auditoría:

| Artefacto | Estado real |
|---|---|
| `tests/AUDITORIA_POI_REPORT.md` (53 líneas) | EXISTE, trackeado (`git ls-files`), añadido en `4bd69d5` |
| `tests/FASE_F_REPORT.md` | EXISTE, trackeado — contiene la corrida A / A' / A'' cruda |
| `tests/auditoria_poi.json` | EXISTE, trackeado — 10.669 zonas medidas |
| `scripts/auditoria_poi.py` | EXISTE |

Esto cambia el peso de la evidencia: `PF 0.900 vs 1.511` **sí** tiene reporte crudo, y ese
reporte dice algo distinto de lo que los documentos derivados repiten (ver §Tarea 2).

---

## Tarea 1 — Qué exige la tesis del POI

### 1.1 Definición citable

> `docs/ict/21_POI.md:16` — *"Un **POI** (Point of Interest) es un **PD Array** (Order Block, FVG,
> Breaker, Mitigation, Rejection, Liquidity Void, BPR) que cumple TRES condiciones a la vez:
> (1) está en la **zona correcta del dealing range** (discount para long, premium para short),
> (2) se **alinea con el sesgo HTF confirmado**, y (3) fue creado por **flujo institucional real**
> (desplazamiento con cuerpo >70%). El POI NO es un tipo de estructura: es un **ROL** que adquiere
> un PD Array cuando está en el contexto correcto. Fuera de ese contexto, el mismo FVG/OB no es POI."*

Contrato formal equivalente:

> `docs/ict/SPEC_TESIS_FORMAL.md:277-278` — *"SAL: POI = PD Array que cumple (1) zona correcta P-D,
> (2) alineado a sesgo HTF, (3) creado por displacement real; quality_score += 20 por ancla + stacking."*

### 1.2 Qué hace válido/anclado a un POI

> `docs/ict/21_POI.md:84` — *"Un POI suelto (cualquier FVG/OB en ventana) NO es un POI ICT real.
> El POI real está **anclado a una narrativa**: el desplazamiento estructural que lo creó."*

> `docs/ict/21_POI.md:91` — *"Un POI solo cuenta si está anclado a un desplazamiento estructural
> en su dirección en el TF padre (BOS/CHOCH de HTF en las últimas N velas)."*

> `docs/ict/20_TESIS_ICT.md:88` — *"**POI como nodo de NARRATIVA:** un POI suelto no es POI ICT.
> Debe estar anclado a un desplazamiento estructural HTF (BOS/CHOCH en su dirección).
> Sin ancla = geometría suelta."*

### 1.3 Qué TF padre debe anclar, y ¿BOS o CHOCH?

| Pregunta | Respuesta de la tesis | Cita |
|---|---|---|
| ¿Qué TF marca el POI? | El **ITF**, no el HTF ni el exec TF | `docs/ict/21_POI.md:18`, `:78` |
| ¿Qué TF ancla? | El **TF padre** del TF donde vive el POI (relativo, no una lista fija) | `docs/ict/21_POI.md:91` |
| ¿BOS, CHOCH, o ambos? | **Ambos, indistintamente** | `docs/ict/21_POI.md:91` (`BOS/CHOCH`), `20_TESIS_ICT.md:88` |
| ¿Un solo nivel basta? | Sí; el apilamiento **eleva el tier**, no es requisito | `docs/ict/21_POI.md:93`, `SPEC:112-113` |

**Hallazgo crítico de capa.** La tesis corrigió explícitamente la idea de "POI solo en HTF":

> `docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md:100` — *"**Corrección a nuestra
> interpretación previa:** el POI NO es exclusivo de HTF. Vive en la ZONA del ITF (M15 intradía);
> el stacking multi-TF lo eleva. Eso explica por qué forzar 'POI HTF como filtro duro' daba PF 0.900."*

Pero el código del motor **todavía codifica la interpretación derogada**:

```
engine/market_object.py:45-46
# Capas permitidas para POI (ONTologia: POI solo en HTF).
_POI_TFS = {"D1", "H4", "H1"}
```

```
engine/market_object.py:72-75
        if self.role == Role.POI and self.origin_tf not in _POI_TFS:
            raise ValueError(
                f"POI solo en HTF ({sorted(_POI_TFS)}); recibido {self.origin_tf}"
            )
```

Un `MarketObject` con `role=POI` y `origin_tf="M15"` **lanza `ValueError`**. Es decir: la ontología
del motor **prohíbe por construcción** el POI que la tesis declara canónico (ITF = M15 intradía).
Estado: **CONTRADICTED** (código vs. tesis vigente).

### 1.4 Invalidación del POI

`docs/ict/21_POI.md:97-104` — cuatro reglas, todas ausentes del motor:

| # | Regla de la tesis | Cita | ¿En `engine/`? |
|---|---|---|---|
| 1 | Cierre de cuerpo por el límite lejano del POI → borrar | `21_POI.md:101` | Parcial: `engine/order_block.py:68-93` (`_track_ob_validity`), `engine/fvg_poi.py:68-107` (`_track_fvg_fill`) |
| 2 | Cambio de sesgo contra la dirección del POI → reevaluar | `21_POI.md:102` | **MISSING** para el POI (existe `DIRECTION_FLIP` para el expediente, `engine/invalidation.py:14`) |
| 3 | Edad > 3–5 sesiones sin test → decae | `21_POI.md:103` | **MISSING** (y en tensión con la migración "borrar aged", `CRONOGRAMA:89`) |
| 4 | Consumo por noticia de alto impacto | `21_POI.md:104` | **MISSING** |

Nota importante: los detectores del motor (`_track_ob_validity`, `_track_fvg_fill`) **sí** calculan
vigencia por barra, pero **`engine/poi_anchor.py` no las consulta en ninguna línea**. La capacidad
existe y está desconectada del cómputo de "anclado".

---

## Tarea 2 — VETO vs BONUS (prioridad máxima)

### 2.1 Libro 18 §4 NO habla de POI

La premisa del conflicto es falsa en su primera mitad. `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`
§4 se titula **"Código SMC-SYSTEMS (dónde vive y qué falta)"** (`:101`) y su contenido íntegro
(`:103-111`) es una tabla de brechas de ingeniería sobre `exec_tf`, `calc_structural_sl`, `TF_FREQ`,
`checklist_scalping` y killzones:

```
docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md:105
| Motor de señales | `ict_backtest/engine.py` `build_signals_from_frames` | Itera `ltf` y saca SL
de ese row. Hoy `exec_tf == ltf` (no hay exec_tf separado). | 🔴 falta parámetro `exec_tf` explícito |
```

**El libro 18 §4 no contiene la palabra "POI" ni "ancla" ni "anclado".** La única mención de POI en
todo el libro 18 es `:44` (tabla de capas: *"ITF (Zona) | Dónde reacciona el precio: POIs, BOS, FVG,
OB, Breaker"*) y `:121` (hueco abierto #4). Ninguna es una exigencia de anclaje.

**Origen del error de cita.** No proviene de `AGENTS.md` sino del docstring del propio módulo:

```
engine/poi_anchor.py:1
"""engine/poi_anchor.py — Ancla narrativa de POI al TF padre (Brecha B, tesis 18).
```

`AGENTS.md:106` solo afirma *"`engine/poi_anchor.py` ancla POI a BOS/CHOCH del TF padre ya cerrado"*
— describe el código, no invoca al libro 18. La atribución "tesis 18" es del docstring y es **STALE**:
la fuente normativa correcta es **libro 21 §4** y **`SPEC_TESIS_FORMAL.md` §16**. El docstring de
`ict_backtest/poi_anchor.py` (borrado) citaba correctamente `libro 21 §4`.

### 2.2 Libro 21 §4 dice AMBAS cosas, en el mismo párrafo

```
docs/ict/21_POI.md:90-93
**Contrato de código (cierra ontología → biblioteca → código):**
- Un POI solo cuenta si está anclado a un desplazamiento estructural en su dirección en el TF
  padre (BOS/CHOCH de HTF en las últimas N velas).
- El POI es un **BONUS de calidad** (`quality_score += 20` según `MARKET_OBJECT_MODEL.md`), NO un
  filtro duro que anule la señal. La auditoría demostró que usar POI HTF como filtro duro destruye
  el edge (A'' PF 0.900 vs A' PF 1.511).
- Stacking multi-TF eleva el tier: un OB de M15 dentro de un FVG de H1 es POI T1 apilado, no dos
  POIs distintos.
```

### 2.3 ¿Contradicción real? NO. Son dos planos distintos

**No hay contradicción.** Los dos enunciados operan sobre objetos distintos:

| Plano | Enunciado | Objeto sobre el que actúa | Cita |
|---|---|---|---|
| **Definicional** (ontología) | Sin ancla, el PD Array **no es un POI** | El PD Array / la zona | `21_POI.md:91`, `:84` |
| **Operativo** (ejecución) | El POI **no anula la señal**; suma calidad | La señal / el trade | `21_POI.md:92`, `SPEC:280` |

El contrato formal firmado resuelve la aparente tensión de forma **explícita y literal**:

```
docs/ict/SPEC_TESIS_FORMAL.md:282-283
CRIT: POI = rol adquirido por PD Array bajo las 3 condiciones; SIN ancla = geometría
     suelta (descartar como POI ICT, pero la zona aún puede ser entry por estructura).
```

Esa frase es el nudo. Traducida a código:

- **`anchored == False` → la zona NO se etiqueta como POI** (veto de *clasificación*).
- **`anchored == False` → la zona SIGUE siendo candidata a entry por estructura** (no veto de *trade*).

`ict_backtest/poi_anchor.py` (borrado) implementaba exactamente esto y lo decía en su docstring:
*"NO borra nada: es BONUS (libro 21 §4: POI como bonus, filtro duro destruye edge)"*. **No contradice
a AGENTS.md**: contradice a una lectura de AGENTS.md que confunde "ancla obligatoria para ser POI"
con "ancla obligatoria para operar".

### 2.4 Verificación de los números PF 0.900 / 1.511

**VERIFICADO.** Existen en tres capas y el reporte crudo fue localizado.

| Nivel | Fuente | Cita |
|---|---|---|
| Contrato firmado | `docs/ict/SPEC_TESIS_FORMAL.md:285-287` | `AMBIG: CRÍTICA empírica (tests/AUDITORIA_POI_REPORT): POI como filtro DURO destruye / edge (A'' PF 0.900 vs A' PF 1.511). Por eso es BONUS, no gate. Esto es regla de / tesis validada por evidencia, no ambigüedad.` |
| Libros | `docs/ict/20_TESIS_ICT.md:91`, `docs/ict/21_POI.md:92` | mismo par de cifras |
| Roadmap (histórico) | `docs/planificacion/_roadmap_historico/CRONOGRAMA_Y_ROADMAP.md:91-95` | Fase F, corrida original |
| **Reporte crudo** | **`tests/FASE_F_REPORT.md`** | **localizado en esta auditoría** |

**Qué fue el experimento (de `tests/FASE_F_REPORT.md`, verbatim):**

- Símbolo/config: `EURUSD H4->M15 max_hold=16 counter_trend=True require_displacement=True tp_mode=fixed2r`
- **A** (con `aged`, baseline): `trades=28 PF=1.424 WR=50.0% totalR=5.7R` — diag simple, **sin** killzone / SL estructural / RR 1:3
- **A'** (sin `aged`, pipeline completo): `trades=37 PF=1.511 WR=51.35% totalR=8.9R` — `scripts/fase0_one.py`, **con** killzone + SL estructural + RR 1:3
- **A''** (`htf_poi_fn` como VETO duro, ventana 20 velas H4): `31 trades | PF=0.900 | WR=41.94% | exp=-0.056R | DD=-9.12R | total=-1.7R`

**Qué medía exactamente el "POI" de A''**: `_htf_has_poi` = *"cualquier FVG/OB en una ventana de 20
velas H4"*. Es la definición que la auditoría clasificó como ruido puro.

### 2.5 Cuatro defectos del experimento A'' (el dato NO prueba lo que se le atribuye)

Todos salen de las fuentes primarias, no de interpretación:

1. **La medición del POI era ruido al 100%.**
   `tests/AUDITORIA_POI_REPORT.md:12-13` — de 10.669 zonas, *"CON narrativa HTF (BOS en dirección en
   40 velas H4): 0 → 0.0%"*. El propio reporte concluye (`:36-41`):
   *"El filtro duro exigía 'hay POI en ventana'. Como el 100% de los POI del sistema son ruido, el
   filtro dejaba pasar las señales cuyo 'POI' era más ruido y descartaba las pocas que no tenían ni
   eso. Un filtro que premia el ruido destruye el edge. No es 'el POI no sirve': es 'el POI se mide mal'."*

2. **N = 6.** `tests/AUDITORIA_POI_REPORT.md:24` — *"A'' apenas descartó 6 señales de 37"*.
   `FASE_F_REPORT.md` confirma 37 → 31. Todo el delta `PF 1.511 → 0.900` descansa sobre **6 trades**.

3. **Configuración confundida (`counter_trend=True`).** `tests/FASE_F_REPORT.md` es explícito:
   *"con counter_trend=True las entradas operan a menudo EN CONTRA de la tendencia HTF; exigir POI
   HTF alineado con el trade filtra un edge que vive precisamente cuando el HTF NO tiene POI."*
   Se exigió ancla **en la dirección del trade** a un motor diseñado para operar **contra** el HTF.

4. **A vs A' no es comparable.** `FASE_F_REPORT.md`: *"El delta NO es atribuible de forma aislada a
   la eliminación del aged ni al POI HTF, porque A' [...] sumó el filtro killzone + SL estructural +
   RR 1:3 que A no tenía"*. La línea base del "edge de 1.511" ya está contaminada.

**Y la decisión original NO fue "bonus para siempre".** Fue condicional:

```
tests/AUDITORIA_POI_REPORT.md:48-53
## Decisión (NO apresurada, sale de la auditoría)
  El POI HTF debe implementarse COMO NODO DE NARRATIVA: solo cuenta si
  está anclado a un desplazamiento estructural HTF (BOS/CHOCH previo en
  esa dirección), no por existir como FVG/OB aislado. Recién entonces se
  decide su rol (filtro duro / bonus / peso / quality_score) con un nuevo
  backtest A'''. Hasta ahí: POI HTF DESACTIVADO por defecto.
```

**El experimento A''' nunca se corrió.** No existe en `docs/METRICS_CANON.md` ni en `results/`.
`SPEC_TESIS_FORMAL.md:286-287` promovió el resultado provisional a *"regla de tesis validada por
evidencia, no ambigüedad"* — una **sobre-generalización** respecto de su propio artefacto primario.

### 2.6 Veredicto definitivo

**El POI anclado NO debe ser VETO de entrada. Debe ser (a) gate de CLASIFICACIÓN de zona y
(b) peso de calidad. Nunca gate de trade.**

| Rol | Veredicto | Fundamento |
|---|---|---|
| **VETO de trade** (descartar la señal) | ❌ **INCORRECTO** | Contractualmente prohibido: `SPEC:274` clasifica §16 como `OBLIGATORIO (BONUS, no gate duro)`; `SPEC:280` `POST: POI actúa como BONUS de calidad, NO anula la señal` |
| **Gate de CLASIFICACIÓN de zona** (sin ancla ⇒ no es POI, pero sigue siendo zona) | ✅ **CORRECTO y exigido** | `SPEC:282-283` literal; `21_POI.md:84,91` |
| **Peso / `quality_score`** | ✅ **CORRECTO y exigido** | `SPEC:278` `quality_score += 20`; `21_POI.md:92` |
| **SKIP por wrong-side / EQ** | ✅ **CORRECTO** (gate sobre el *bonus*, no sobre el trade) | `SPEC:284` `CASOS LÍMITE: POI en wrong-side o EQ → SKIP (no bonus)` |

**Matiz obligatorio de honestidad.** El "BONUS, no gate" es correcto **por contrato y por definición
ontológica**, no porque el experimento A'' lo haya demostrado. A'' demostró otra cosa: *un veto sobre
una medición ruidosa, con n=6, en configuración contratendencia, destruye el edge*. Es una
proposición mucho más débil. La conclusión práctica coincide; el razonamiento subyacente no debe
citarse como prueba robusta. **Prohibido usar A'' para argumentar que "el anclaje no aporta"**: el
artefacto primario dice literalmente lo contrario (`AUDITORIA_POI_REPORT.md:30-34`).

---

## Tarea 3 — Matriz de capacidades (delta real de la recuperación)

Leyenda: **PRESENTE** = existe hoy en `engine/` · **PERDIDA** = existía en el clúster borrado y hoy
no existe · **NUNCA EXISTIÓ** = no está en ninguna de las dos capas.

| # | Capacidad | Clúster borrado | `engine/` hoy | Estado | Valor |
|---|---|---|---|---|---|
| 1 | **Anclaje por POI individual** (cada FVG/OB marcado) | `anchor_objects` → `obj.meta["anchored"]` por objeto | Un **único booleano global** por vela: `poi_present` (`engine/poi_anchor.py:111-122`) | **PERDIDA** | **ALTO** |
| 2 | **Identidad del ancla** (trazabilidad) | `obj.parent_object = anchor.id` + `obj.related_objects.append(anchor.id)` | Nada. `_ParentEvent` no se devuelve al llamador | **PERDIDA** | **ALTO** |
| 3 | **Restricción a tipos FVG / OB** | `ObjectType.FVG` / `ObjectType.ORDER_BLOCK` como candidatos | **No hay candidatos**: no se inspecciona ninguna zona | **PERDIDA** | **ALTO** |
| 4 | **Ventana de lookback `window_n=20`** | `prior[-window_n:]` sobre objetos HTF padre | `window_n: int = 20` (`engine/poi_anchor.py:90,121`) — sobre **eventos**, no objetos | PRESENTE (degradada) | Bajo |
| 5 | **Fail-open vs fail-closed sin datos padre** | **fail-closed**: `obj.meta["anchored"] = False` por defecto (línea 1 del bucle) | **fail-open**: `return True` (`engine/poi_anchor.py:116`) | **PERDIDA** (regresión) | **ALTO** |
| 6 | **Anti look-ahead cross-TF** | `bar_time` con fallback a `bar_index` (`_closed_before`) | `time <= ltf_t` (`:120`); sin fallback | PRESENTE | — |
| 7 | **Discriminación BOS vs CHOCH** | No (ambos vía `_is_structural`) | No (`kind` se guarda en `:39,77,80`, nunca se filtra) | **NUNCA EXISTIÓ** | Medio |
| 8 | **Detección de PD Arrays HTF reales (FVG/OB)** | `HtfPdIndex._detect_pd_arrays` | `engine/fvg_poi.py`, `engine/order_block.py` existen, pero **`poi_anchor.py` no los llama** | PRESENTE, DESCONECTADA | **ALTO** |
| 9 | **Vigencia de la zona HTF** (relleno / invalidación) | `fvg_fill_status`, `ob_status == "invalidated"`, forward-fill de la zona ACTIVA | `_track_fvg_fill` (`engine/fvg_poi.py:68-107`), `_track_ob_validity` (`engine/order_block.py:68-93`) — **no consultadas por el ancla** | PRESENTE, DESCONECTADA | **ALTO** |
| 10 | **Mapa LTF→HTF O(n)** (`merge_asof` cerrado) | `HtfPdIndex.build_ltf_map` | Ninguno. `poi_present` reconstruye el índice **por señal** (`ict_backtest/canonical.py:375`) | **PERDIDA** | Medio (rendimiento) |
| 11 | **Tier T1/T2/T3 (BPR > OB/FVG > bloques)** | `ZoneAuthority.tier` + `TIER_RANK` | Constante: `obj.meta.get("pd_tier", "T2")` (`engine/sequence.py:516,520`); **nada en `engine/` escribe `pd_tier`** | **PERDIDA** | Medio |
| 12 | **Stacking multi-TF** | `ZoneAuthority.stacking_level = len({z.tf for z in anchors})` | **Cero** (grep `stacking` en `engine/`: sin resultados) | **PERDIDA** | Medio-Alto |
| 13 | **Peso de confianza `[0,1]`** | `ZoneAuthority.confidence_weight` con invariante en `__post_init__` | `state.zone_authority = None` **incondicional** (`engine/sequence.py:521-523`) | **PERDIDA** | Medio |
| 14 | **Premium/discount + OTE** | No (`htf_pd_index` no lo hace) | `engine/dealing_range.py` completo (`:41-138`) | PRESENTE | — |
| 15 | **Reevaluación por invalidación del padre** | No (índice inmutable también allí) | No (`build_htf_structure_index` corre una vez, `:49-83`) | **NUNCA EXISTIÓ** | **ALTO** |
| 16 | **Reglas de invalidación del POI** (§5 libro 21) | No | Parcial (`engine/invalidation.py` es del *expediente*, no del POI) | **NUNCA EXISTIÓ** | Alto |

### 3.1 ¿`engine/dealing_range.py` supersede a `htf_pd_index.py`? — **NO**

**Respuesta directa: no, y la confusión es puramente nominal.** "PD" significa cosas distintas en
cada módulo.

| | `ict_backtest/htf_pd_index.py` | `engine/dealing_range.py` |
|---|---|---|
| "PD" significa | **PD Array** (Premium/Discount **Array** = FVG, OB, BPR, Breaker…) | **P**remium / **D**iscount (mitad del rango) |
| Qué computa | Inventario temporal de **zonas** HTF vigentes | **Ubicación** del precio dentro del rango |
| Entrada | Detectores FVG + OB sobre frames HTF (`_detect_pd_arrays`) | `high`/`low` rolling (`:57-58`) |
| Salida | `list[HtfPdZone]` con `pd_type`, `pd_tier`, `direction`, `zone_high`, `zone_low` | Columnas escalares: `premium_discount_zone`, `premium_distance`, `ote_*` |
| Rastrea vigencia | **Sí** (relleno de FVG, invalidación de OB, forward-fill) | No aplica |
| Sección de la tesis | **§3 / §4** (`SPEC:66-98`) | **§2** (`SPEC:51-64`) |

El propio contrato los lista como **dependencias separadas** del POI:

```
docs/ict/SPEC_TESIS_FORMAL.md:276
ENT: PD Array (§3/§4) + sesgo HTF (§1) + dealing range (§2).
```

Conclusión: `engine/dealing_range.py` cubre §2 y **no toca §3/§4**. No hay supersesión ni solape.
Sin embargo, **recuperar `htf_pd_index.py` sigue siendo valor NEGATIVO**, por otra razón: sus
detectores (`from detectors.fvg import detect_fvg`, `from detectors.ob import detect_order_blocks`)
apuntan a `detectors/`, mientras el motor ya tiene equivalentes propios y limpios
(`engine/fvg_poi.py:29`, `engine/order_block.py:35`) que **ya calculan la misma vigencia**.
Lo que falta no es el módulo: es **el cable** entre esos detectores y `engine/poi_anchor.py`.

### 3.2 Lo que ya está en `engine/` y facilita la migración

`engine/market_object.py` **ya contiene todos los campos que `anchor_objects` necesita**:
`parent_object` (`:62`), `related_objects` (`:63`), `meta` (`:61`), `quality_score` (`:64`),
`bar_index` (`:66`), `bar_time` (`:67`), `ObjectType.FVG` (`:24`), `ObjectType.ORDER_BLOCK` (`:25`),
`ObjectState.INVALIDATED` (`:41`). El port de `anchor_objects` es un cambio de import
(`ict_backtest.market_object` → `engine.market_object`), **salvo** por la trampa de `_POI_TFS`
descrita en §1.3, que debe resolverse antes.

---

## Tarea 4 — ¿Mejora la MEDICIÓN?

### 4.1 Respuesta: SÍ, y es la mejora más relevante disponible

**SÍ**, con independencia de si el POI termina siendo veto o bonus. Razón única y suficiente:

> Hoy el sistema **no mide el POI**. Mide otra cosa y la llama POI.

Prueba directa, `engine/poi_anchor.py:111-122`: la función no lee `fvg_bullish`, `ob_bullish`,
`zone_high`, `zone_low`, ni ningún objeto de zona. Solo consulta `bos_dir` / `choch_dir`
(`:71-72`). El valor `poi_present == True` significa literalmente *"hubo un BOS o CHOCH en D1, H4
o H1 en mi dirección antes de esta vela"*. Eso es **sesgo estructural**, y ya está medido por
`engine/plan.py::top_down_allows_trade`. Es una métrica **duplicada y mal nombrada**.

Consecuencia medible: `poi_present` **no puede distinguir** entre estos dos casos, que la tesis
considera opuestos (`21_POI.md:84`):

| Caso | Realidad ICT | `poi_present` hoy |
|---|---|---|
| FVG M15 dentro de un OB H4 vigente, creado por el BOS H4 que lo originó | POI T1 apilado, máxima autoridad | `True` |
| FVG M15 aleatorio, sin ninguna zona HTF cerca, con un BOS D1 de hace 8 meses | Geometría suelta (no es POI) | `True` |

Con `anchor_objects` recuperado, el segundo caso da `anchored=False` y el primero da `anchored=True`
**con `parent_object` identificando el BOS concreto**. Eso es una medición, no un indicador binario
de contexto. Es precisamente lo que `AUDITORIA_POI_REPORT.md:44-46` señala como la brecha:
*"Falta la regla: 'Este POI pertenece a ESTA narrativa'."*

### 4.2 El fail-open de `engine/poi_anchor.py:116` — consecuencia práctica

```
engine/poi_anchor.py:115-116
        if not by_dir[tnum]:
            return True  # sin eventos padre -> no bloquea (comportamiento historico)
```

**Sí, produce resultados silenciosamente optimistas en la medición.** Detalle:

**Cuándo se dispara** (todos verificados en código):
1. Un TF padre tiene `< 3` velas o falta → `continue` silencioso (`:60-61`).
2. `detect_market_structure(frame)` lanza → `except Exception: continue` (`:69-70`), sin log.
3. No hay ningún BOS/CHOCH en esa dirección en **ninguno** de D1/H4/H1.

**Asimetría interna.** Dos líneas más abajo el mismo callable es fail-**closed**:

```
engine/poi_anchor.py:117-118
        if i < 0 or i >= len(ltf_times):
            return False
```

Sin datos de estructura → `True`. Con índice fuera de rango → `False`. No hay contrato declarado
que justifique la asimetría.

**Consecuencia sobre las métricas del backtest, con precisión:**

| Vector | ¿Afecta hoy? | Explicación |
|---|---|---|
| **PnL / PF / WR** | **NO, hoy** | `poi_present` es metadata (`engine/sequence.py:503,628`). Además, si `by_dir[tnum]` está vacío, `poi_ok` también da `True` (`:508`), es decir el camino "sin datos" coincide bit a bit con el camino histórico `htf_poi_fn=None`. Regresión cero: correcta por diseño. |
| **Tasa de anclaje reportada** | **SÍ, gravemente** | En un símbolo con HTF fino, el sistema reporta `poi_present=True` en el **100%** de las señales. Indistinguible de "todo perfectamente anclado". |
| **`poi["anchored"]` de la narrativa** | **SÍ** | `engine/htf_narrative.py:152` hereda el mismo `True`, y `_build_summary` (`:86`) imprime *"anclado HTF"* al operador. **Afirmación falsa presentada al humano.** |
| **`htf_anchored` del `ICTSignal`** | **SÍ** | `ict_backtest/canonical.py:375` recalcula el mismo valor; misma inflación. |
| **Comparabilidad entre símbolos** | **SÍ** | La cobertura de datos varía por par (`docs/METRICS_CANON.md` §R6 v2 mtf: XAUUSD sin M15). Un par con HTF corto puntúa "más anclado" que uno con HTF largo — **artefacto de datos leído como calidad de setup**. |

**El riesgo diferido es el que importa.** Si mañana `poi_present` se convierte en peso o en gate de
clasificación **sin corregir el fail-open**, "ausencia de datos" pasa a significar "permiso
concedido / máxima calidad". Es exactamente el modo de falla que produjo A'': un filtro que
**premia el ruido** (`AUDITORIA_POI_REPORT.md:39-40`).

Recomendación: **fail-closed con razón explícita**, distinguiendo tres estados en lugar de un
booleano — `ANCHORED` / `NOT_ANCHORED` / `UNKNOWN_NO_PARENT_DATA`. El tercero nunca debe contarse
como anclado en ninguna métrica agregada.

### 4.3 Ranking por mejora de medición / esfuerzo

| # | Capacidad | Esfuerzo | Ganancia de medición | Ratio |
|---|---|---|---|---|
| **1** | **Fail-closed + tri-estado con razón** (`engine/poi_anchor.py:116`) | Muy bajo (≈10 líneas + tests) | Elimina el sesgo optimista sistemático en TODAS las métricas de ancla | **Máximo** |
| **2** | **Anclaje por objeto + `parent_object`** (portar `anchor_objects` a `engine/`) | Bajo (`engine/market_object.py` ya tiene los campos; el módulo eran 88 líneas) | Convierte un booleano global en una medición por zona, auditable y depurable | **Muy alto** |
| **3** | **Conectar los detectores de zona ya existentes** (`engine/fvg_poi.py`, `engine/order_block.py`) a `poi_anchor` | Bajo-medio (cableado, no código nuevo) | Hace que el "POI" **sea un POI**: hoy no se inspecciona ninguna zona | **Muy alto** |
| **4** | **Vigencia de la zona padre** (`fvg_fill_status` / `ob_status`) en el ancla | Medio | Ancla a zonas **vivas**, no a fantasmas; cierra `21_POI.md:101` | Alto |
| **5** | **Discriminar BOS vs CHOCH** (`kind` ya se guarda, `:39`) | Muy bajo | Permite medir si BOS y CHOCH anclan con distinta calidad. Nunca se pudo medir | Alto |
| **6** | **Tier + stacking** (`ZoneAuthority`) | Medio | Cierra SPEC §5 (`OBLIGATORIO`, hoy 0% implementado) | Medio-alto |
| **7** | **Reevaluación por invalidación del padre** | Alto (requiere ancla event-driven) | Correcto, pero sin (2) y (3) no hay nada que reevaluar | Medio |
| **8** | Mapa `merge_asof` O(n) | Medio | Solo rendimiento. Corrige el O(señales × velas HTF) de `canonical.py:375` | Bajo |

**Orden recomendado: 1 → 2 → 3 → 5 → 4 → 6.** Los ítems 1, 2, 3 y 5 juntos son ≈150 líneas y
convierten `poi_present` de "indicador de contexto mal nombrado" en "medición de POI auditable".

### 4.4 Qué NO mejora nada y debe seguir borrado

| Módulo / pieza | Por qué debe seguir borrado |
|---|---|
| **`ict_backtest/poi_filter.py`** (74 líneas) | Su `make_htf_poi_fn` con el default de producción (`as_gate=False`) es **`return True` constante**. Recuperarlo reintroduce un no-op que *aparenta* ser un gate. Valor **negativo**: es la fuente documental del claim STALE `as_gate=False` que `ict_backtest/canonical.py:233` todavía cita y que **no existe** en la firma actual (`engine/poi_anchor.py:86-91`). |
| **`ict_backtest/poi_anchor_motor.py`** (45 líneas) | `compute_htf_anchored` es un duplicado literal de `poi_filter.poi_present` con otra firma. Tercer cómputo del mismo valor. El repo ya tiene **tres** (`engine/sequence.py:503`, `engine/htf_narrative.py:152`, `ict_backtest/canonical.py:375`); añadir un cuarto empeora la ambigüedad de fuente. |
| **`ict_backtest/htf_pd_index.py`** como **módulo** | La *capacidad* (vigencia de PD arrays) vale; el *módulo* no: importa de `detectors/`, duplica `engine/fvg_poi.py` y `engine/order_block.py`, y su clase `HtfPdIndex` acopla detección + alineación + lookup. Extraer la idea, no el archivo. |
| **`ZoneAuthority` con sus pesos actuales** (`+0.5 / +0.3 / +0.2`) | Los coeficientes son arbitrarios y sin respaldo en la tesis. Viola el Principio R10 (*"decisión SIEMPRE del estado del mercado, NUNCA constante arbitraria"*, `CRONOGRAMA:167`). Recuperar el **contrato** (`tier`, `stacking_level`, peso en `[0,1]`); **no** la tabla de constantes. |
| **`_htf_has_poi`** (`engine/sequence.py:223-238`) | Código muerto: nadie lo llama. Es **la misma función que produjo A'' PF 0.900**. Debe borrarse, no revivirse. |
| **`_POI_TFS = {"D1","H4","H1"}`** (`engine/market_object.py:46`) | No es "recuperación", pero es la trampa que hace fallar cualquier port: prohíbe el POI en el ITF que la tesis declara canónico (`CRONOGRAMA:100`). |

---

## Tarea 5 — Riesgo de la recuperación

### 5.1 ¿Cambiaría el PnL del backtest canónico?

**Depende de la capacidad. Hay un camino que mueve números y casi nadie lo llama "gate".**

| Capacidad recuperada | ¿Mueve PnL? | Mecanismo exacto |
|---|---|---|
| `parent_object` / `related_objects` | **NO — inerte** | Anotación en el objeto; ningún consumidor la lee para decidir |
| `meta["anchored"]` por objeto | **NO — inerte** *si y solo si* no alimenta `htf_poi_fn` | Ver la trampa de abajo |
| `tier` / `stacking_level` / `confidence_weight` | **NO — inerte hoy** | `ict_backtest/canonical.py:372` lee `s.get("zone_authority")`, que `engine/sequence.py:523` fija en `None` incondicionalmente |
| **Cambiar la semántica de `htf_poi_fn`** | **SÍ — MUEVE PnL** | Ver §5.2 |
| **Fail-open → fail-closed** | **SÍ — MUEVE PnL** | Ver §5.2 |
| Vigencia de la zona padre dentro del ancla | **SÍ, si alimenta `htf_poi_fn`** | Mismo camino |
| Mapa `merge_asof` O(n) | **NO** (solo tiempo de ejecución) | Debe dar resultado idéntico; es el criterio de aceptación |

### 5.2 La trampa: `poi_ok` YA mueve el PnL aunque nadie lo llame gate

Es el hallazgo de riesgo más importante de esta auditoría. El motor tiene **dos** consumidores de
`htf_poi_fn`, no uno:

```
engine/sequence.py:502-508
            if htf_poi_fn is not None:
                state.poi_present = bool(htf_poi_fn(i, target))   # (1) metadata — inerte
            else:
                state.poi_present = None
            # Hook historico: poi_ok decide si se memoriza la zona LTF. Con
            # htf_poi_fn=None es no-op (comportamiento historico intacto).
            poi_ok = (htf_poi_fn is None) or bool(htf_poi_fn(i, target))   # (2) NO es inerte
```

Cuando `poi_ok == False`, la zona LTF **no se memoriza** (`:509-520`). Luego, en `BOS_DONE`, el motor
**sintetiza** una banda de reemplazo:

```
engine/sequence.py:588-596
                if not (np.isfinite(state.zone_high) and np.isfinite(state.zone_low)):
                    _atr = obj.meta.get("atr", np.nan)
                    ...
                    if np.isfinite(atr) and np.isfinite(state.bos_level):
                        state.zone_high = state.bos_level + 0.5 * atr
                        state.zone_low = state.bos_level - 0.5 * atr
```

Cadena causal completa: `poi_ok=False` → zona pasa de FVG/OB real a banda sintética
`bos_level ± 0.5·rango` → cambia `_touches_zone` → **cambia la vela de entrada** → cambia `entry`,
`sl` (vía `fine_execution`), `tp` y el resultado. **Es una ruta que mueve PnL.**

Hoy no se manifiesta porque `poi_ok` es efectivamente siempre `True`: en el caso "hay eventos" casi
siempre hay uno (`:120-122`), y en el caso "no hay eventos" el fail-open devuelve `True` (`:116`).
**Cualquier medición más estricta del anclaje —incluida la correcta— hará que `poi_ok` empiece a
dar `False` y el PnL se moverá.** No por un veto: por degradación silenciosa de la zona.

**Mitigación obligatoria:** separar los dos consumidores. `htf_poi_fn` (medición del ancla) NO debe
seguir alimentando `poi_ok` (selección de zona). Se necesitan dos callables o un flag explícito.
Sin esa separación, cualquier mejora de la medición se contamina con un cambio de decisión.

### 5.3 Riesgo de resucitar el filtro duro

| Riesgo | Severidad | Mitigación |
|---|---|---|
| **Reintroducir el veto de trade** (A'' PF 0.900) | **Alta** | Prohibido por contrato: `SPEC:274,280`. No debe existir ningún parámetro `require_poi=True` alcanzable desde `run_sequence`. Si se implementa para experimentar, debe ser inaccesible desde el flujo de producción y estar cubierto por un test de regresión. |
| **Revert accidental de `require_pd=False`** (DP-1) | **Alta** | Vector distinto pero misma familia. `engine/plan.py:371` tiene default `True`; `engine/sequence.py:479` lo pasa `False` explícito. **No hay test que lo proteja.** Añadirlo antes de tocar nada del clúster POI. |
| **Veto encubierto vía `poi_ok`** (§5.2) | **Alta** | Es el riesgo real y menos visible: no se llama veto, no aparece en el embudo `phase_seen` (`engine/sequence.py:435`), y sin embargo cambia el PnL. |
| **Fail-closed sin separar los consumidores** | **Alta** | Corregir `:116` mejora la medición pero, por §5.2, **también cambia el PnL** si no se separa antes `poi_ok`. Orden obligatorio: separar primero, corregir después. |
| **Heredar `_POI_TFS` derogado** | Media | El port de `anchor_objects` puede lanzar `ValueError` en objetos M15 con `role=POI` (`engine/market_object.py:72-75`). Decidir la capa del POI **antes** de portar. |
| **Cuarto cómputo del mismo valor** | Media | Ya hay tres (`sequence.py:503`, `htf_narrative.py:152`, `canonical.py:375`). Declarar una fuente única antes de añadir código. |
| **Tests rotos ya presentes** | Media | `tests/test_poi_anchor.py:40,50,60,70`, `tests/test_plan_cableado_real.py:58`, `tests/test_fase_d_paso2_trade_context.py:94`, `tests/test_r10c_adapter.py:219` importan módulos borrados. `ict_backtest/plan_attach.py:100` es **código de producción** con import roto. Cualquier recuperación debe resolverlos, no dejarlos a medias. |

### 5.4 Protocolo de paridad de DECISIÓN (antes / después)

El operador exige paridad de **decisión**, no igualdad línea a línea. Instrumentación mínima
propuesta (**UNVERIFIED** — nada de esto se ejecutó en esta auditoría):

**Fase 0 — congelar el baseline.** Requiere OK expreso (`AGENTS.md:120`). `engine/poi_anchor.py` es
`??` untracked; un `git clean -fd` lo destruye. Sin baseline reproducible no hay paridad posible.

**Métricas a capturar ANTES y DESPUÉS, con el backtest canónico** (`ict_backtest/run_backtest.run_sequence_backtest`),
mismo símbolo, misma ventana, mismos parámetros, costos ON:

| Nivel | Métrica | Criterio de paridad |
|---|---|---|
| **Decisión** | Conjunto de `(time, direction, entry_at)` de las señales emitidas | **Idéntico** — es el criterio duro |
| **Decisión** | `len(signals)` | Idéntico |
| **Decisión** | Embudo `phase_seen` `{SWEEP, DISPLACE, BOS, ENTRY}` (`engine/sequence.py:435`) | Idéntico + monotónico (`tests/test_b2_funnel.py:89-107`) |
| **Ejecución** | `entry`, `sl`, `tp` por señal | Idéntico (detecta la degradación de zona de §5.2) |
| **Zona** | Distribución `zone_pd_type` FVG / OB / **sintética** | **Clave**: un aumento de zonas sintéticas prueba que `poi_ok` empezó a vetar |
| **Resultado** | PF, WR, N, total R, maxDD | Idéntico si lo anterior es idéntico |
| **Medición (nuevo)** | Tasa de `anchored=True` por símbolo | **Debe cambiar** — es el objetivo. Un delta ≈0 significa que no se midió nada nuevo |
| **Medición (nuevo)** | Recuento de `UNKNOWN_NO_PARENT_DATA` | **Debe ser > 0** en símbolos con HTF fino, o el fail-closed no se aplicó |

**Regla de lectura:** la migración es decisión-neutral **si y solo si** las filas *Decisión*,
*Ejecución* y *Zona* son idénticas **y** las filas *Medición* cambian. Si las de Decisión cambian,
se coló un gate. Si las de Medición no cambian, se añadió código sin ganancia — exactamente lo que
la pregunta del operador busca evitar.

**Experimento pendiente que la tesis exige y nunca se corrió:** **A'''** (`tests/AUDITORIA_POI_REPORT.md:52`).
Es el único que puede decidir el rol final del POI con evidencia. Precondiciones: medición corregida
(ítems 1-3 y 5 de §4.3), `counter_trend=False` para eliminar el confundido de A'', N ≥ 200 por celda,
y más de un símbolo. **UNVERIFIED / no ejecutado.**

---

## Resumen de estados

| Claim | Estado |
|---|---|
| Libro 18 §4 exige POI anclado al BOS padre | **CONTRADICTED** — §4 es una tabla de brechas sobre `exec_tf`/SL; no menciona POI |
| Libro 21 §4 y el docstring borrado se contradicen | **CONTRADICTED** — dicen lo mismo en planos distintos (`SPEC:282-283`) |
| `PF 0.900 vs 1.511` (A'' vs A') | **SUPPORTED** con reporte crudo — pero **n=6**, medición ruidosa y `counter_trend=True` |
| `tests/AUDITORIA_POI_REPORT` no localizable | **CONTRADICTED** — existe y está trackeado (corrige `evidence-docs.md:333-340`) |
| Experimento A''' corrido | **MISSING** — nunca se ejecutó |
| `engine/dealing_range.py` supersede a `htf_pd_index.py` | **CONTRADICTED** — §2 vs §3/§4 del contrato (`SPEC:276`) |
| `engine/poi_anchor.py` mide POI | **CONTRADICTED** — mide estructura padre; no inspecciona ninguna zona |
| `poi_present` es inerte para el PnL | **SUPPORTED hoy**, **frágil**: `poi_ok` (`engine/sequence.py:508`) sí mueve PnL |
| SPEC §5 (stacking, `OBLIGATORIO`) implementado en el motor | **MISSING** — `pd_tier` es constante `"T2"`; grep `stacking` en `engine/` sin resultados |
| Reevaluación por invalidación del padre | **MISSING** en ambas capas |
| `_POI_TFS` coherente con la tesis | **CONTRADICTED** — `engine/market_object.py:46` vs `CRONOGRAMA:100` |

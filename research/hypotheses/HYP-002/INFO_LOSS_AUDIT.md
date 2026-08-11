# AUDITORÍA DE PÉRDIDA DE INFORMACIÓN — HYP-002 (Fase 2)

**Fecha:** 2026-08-11
**Autor:** CEO Hermes (lectura forense del código real; SIN modificar engine/)
**Objetivo:** determinar exactamente dónde se pierde la información necesaria para
demostrar el linaje causal 1:1 LIQUIDEZ → SWEEP → DISPLACEMENT → BOS/CHOCH → POI → RETORNO,
y si el auditor puede reconstruirlo offline (Arquitectura B) o si hay que enriquecer el motor (A).

Regla: AUDITAR → DIAGNOSTICAR → DECIDIR → MODIFICAR. No se modifica el motor en esta fase.

---

## 0. Corrección de wording (orden del Director)

El veredicto de Piloto 1 NO es "SETUP FORMADO / CAUSALITY BROKEN". Es:

> **SETUP CANDIDATO — formación parcial demostrada; linaje causal 1:1 incompleto.**

Tener los eventos ≠ demostrar que forman UN setup causal. Componentes demostrables;
unidad causal NO demostrada. (Se actualizó `SETUP_FORMATION_MAP.md` y `RESEARCH_CONTRACT.md`.)

---

## 1. Estado actual de la trazabilidad en el código real

### 1.1 Identidad de objetos
- `MarketObject` (`engine/market_object.py`) SÍ tiene `id` (uuid), `parent_object`,
  `related_objects`, `bar_index`, `bar_time`, `direction`, `zone_high/low`.
- PERO: en `engine/sequence.py` solo se crean `MarketObject(type=CANDLE)` (una por vela,
  `_candle_objects` línea 133). **Nunca se crea un `MarketObject` para sweep/displacement/BOS/POI**
  con su `id` y `parent_object`. La trazabilidad de objetos no se usa en la secuencia.
- Los detectores (`detectors/displacement.py`, `fvg.py`, `ob.py`, `liquidity.py`) devuelven
  **DataFrames de flags booleanos por vela** — **SIN IDs de objeto**. La identidad única de
  "este displacement" no existe en ningún lado.

### 1.2 Memoria de fase — `SequenceState` (`engine/sequence.py:89`)
Conserva internamente: `sweep_idx, displace_idx, bos_idx, bos_level, zone_high, zone_low,
zone_authority, poi_present, htf_aligned`. Solo ÍNDICES + algunos niveles. Sin IDs, sin parent.

### 1.3 Emisión de señal (`engine/sequence.py:618-634`)
La señal final incluye: `time, direction, entry, bos_level, sweep_at, displace_at, bos_at,
entry_at, zone_authority, poi_present, htf_aligned, htf_reason, expediente`.
**NO incluye:** nivel de sweep, nivel de displacement, `zone_high/zone_low` (SÍ existen en
`state` pero no se copian a la señal), IDs de objeto, `parent_event`.

### 1.4 Expediente (`engine/expediente.py`)
`PhaseEvent(phase, idx, time, condition)` — fases SWEEP/DISPLACE/BOS/ENTRY/INVALID.
Conserva ÍNDICE + TIMESTAMP + TEXTO. **NO nivel de precio, NO id de objeto, NO parent_event.**

### 1.5 Precedente de reconstrucción offline (Arquitectura B ya existe en germen)
`engine/fvg_poi.py:fvg_for_bos` reconstruye el POI de un BOS buscando "el FVG más cercano
ANTERIOR en la dirección del BOS" por `idx` + dirección. Es matching temporal/direccional,
NO identidad. Esto es exactamente la transición BOS→POI bajo la arquitectura B.

### 1.6 GAP-1 Macro/News
`app_observador/ui/noticias_widget.py` tiene noticias **FIJAS hardcoded** (fuente forex.com,
semana 27 jul-2 ago 2026). No es un feed por timestamp. → Macro hoy = CONTEXTO OBSERVABLE
ausente/dummy. No se puede aún relacionar temporalmente con el setup.

---

## 2. MATRIZ DE PÉRDIDA DE INFORMACIÓN (por transición)

Leyenda: ✓ existe | ✗ no existe | DERIV. reconstructible desde OHLC+detectores | PERD. se pierde

| Transición | Evento | Timestamp | Nivel/Preço | ID única | parent_event | Relación causal | Reconstr. OHLC? | Dónde se pierde |
|---|---|---|---|---|---|---|---|---|
| LIQUIDEZ | ✓ (pool bsl/ssl) | ✓ (idx) | ✓ (bsl/ssl_price) | ✗ | ✗ | ✗ | DERIV. | pool escaso (H2) |
| LIQ→SWEEP | ✓ sweep flag | ✓ | ✓ mecha (DERIV) | ✗ | ✗ | ✗ | DERIV. | no se enlaza al pool |
| SWEEP | ✓ | ✓ | ✓ mecha (DERIV) | ✗ | ✗ | ✗ | DERIV. | id no existe |
| SWEEP→DISP | ✓ disp flag | ✓ | ✓ body (DERIV) | ✗ | ✗ | ✗ | DERIV. | solo gap temporal |
| DISPLACEMENT | ✓ | ✓ | ✓ body (DERIV) | ✗ | ✗ | ✗ | DERIV. | id no existe |
| DISP→BOS | ✓ bos_dir | ✓ | ⚠ bos_level NaN a menudo | ✗ | ✗ | ✗ | ⚠ parcial | bos_level no se emite bien (H1) |
| BOS/CHOCH | ✓ | ✓ | ⚠ nivel inestable | ✗ | ✗ | ✗ | ⚠ parcial | id no existe |
| BOS→POI | ✓ zona (state) | ✓ | ✓ zone (state) | ✗ | ✗ (usaría fvg_for_bos) | ✗ | DERIV. (fvg_for_bos) | zona no se emite en señal |
| POI | ✓ (state.zone_*) | ✓ | ✓ | ✗ | ✗ | ✗ | DERIV. | zone_high/low no emitidos |
| POI→RETORNO | ✓ toque zona | ✓ | ✓ close | ✗ | ✗ | ✗ | DERIV. | ok observable |

**Conclusión de la matriz:** la información de NIVEL/PRECIO casi toda es DERIVABLE desde OHLC
por índice. Lo que **NO existe en ningún lado** es la IDENTIDAD ÚNICA y el PARENT_EVENT.
Eso no es "pérdida" en el sentido de que se creó y se borró: **nunca se creó**. El motor
opera por índices + dirección, no por objetos enlazados.

---

## 3. ¿PROBLEMA DE DETECCIÓN, REPRESENTACIÓN O TRAZABILIDAD?

- **Detección:** NO es el problema. Los eventos se detectan (Piloto 1 lo confirmó).
- **Representación:** PARCIAL. El motor representa la secuencia como índices en `SequenceState`,
  no como grafo de objetos. Es una representación válida pero insuficiente para linaje 1:1.
- **Trazabilidad:** ESTE es el verdadero problema. No hay `id`/`parent` que permita decir
  "este BOS #31 fue roto por el displacement #23 que siguió al sweep #17". Solo hay
  "BOS ocurrió después de displacement que ocurrió después de sweep".

Veredicto: **el problema es de TRAZABILIDAD (y en menor medida de representación), NO de detección.**

---

## 4. ARQUITECTURA A vs B — comparación por evidencia

### A — El motor produce y conserva el linaje causal
Requiere: crear `MarketObject` para sweep/disp/bos/poi con `id` + `parent_object` en
`engine/sequence.py`, y emitirlos en la señal + `Expediente`.
- Ventaja: linaje 1:1 garantizado, consultable en vivo.
- Costo: tocar `engine/` (la ÚNICA fuente de decisión). Riesgo de regresión. Contamina el
  motor con preocupaciones de auditoría.
- Estado hoy: NO existe; `MarketObject` tiene los campos pero nadie los popula para la secuencia.

### B — El motor intacto; el SETUP AUDITOR reconstruye offline
El motor ya emite índices + dirección + (parcialmente) niveles + `Expediente` con fases.
El auditor (consumidor puro, ya escrito en Piloto 1) reconstruye el linaje usando:
- `detectors.*` (flags por vela) → re-deriva cada evento por índice.
- `engine/fvg_poi.fvg_for_bos` → ya hace BOS→POI por proximidad+dirección.
- Proximidad temporal + dirección para SWEEP→DISP y DISP→BOS (mismo patrón).
- Niveles: DERIVABLE desde OHLC por índice (mecha de sweep, body de displacement, etc.).
- Deterministicidad: SÍ, porque los detectores son puros sobre OHLC (sin random, sin estado
  oculto). Misma entrada → misma reconstrucción. El piloto ya lo hizo para la zona POI.

- Ventaja: NO toca engine/. El motor "detecta", el auditor "reconstruye y juzga". Cumple la
  Ley Fundamental (motor = única fuente de decisión; backtester/auditor = consumidor puro).
- Costo: el linaje queda como INFERENCIA POR PROXIMIDAD, no identidad real. Es "lo más
  probable dado el orden", no "este objeto causó este". Para ICT/SMC eso suele ser aceptable
  (la tesis misma define el setup por la secuencia en ventana), PERO no es identidad 1:1 estricta.
- Límite duro de B: si dos eventos del mismo tipo colapsan en la misma ventana (ej. dos
  displacements cerca), la proximidad puede emparejar mal. Reconstruible pero ambiguo.

### Determinación por evidencia (no por preferencia)
- Para **DEMOSTRAR FORMACIÓN** (objetivo de esta fase): **B es suficiente y respeta la arquitectura.**
  El piloto ya reconstruyó la zona POI offline; extender a las 3 uniones es el mismo patrón.
- **A solo se justifica** si se quiere linaje 1:1 estricto consultable EN VIVO (no solo auditoría).
  Eso es fase posterior (decisión de producto, no de ciencia de lectura).

**Conclusión:** la evidencia respalda B para esta fase. A queda postergado hasta que se demuestre
que B es ambiguo en la práctica (no solo en teoría).

---

## 5. GAP-1 MACRO/NEWS — contexto observable (no filtro)

Hoy: noticias FIJAS hardcoded en `noticias_widget.py`. No hay feed por timestamp.
Acción de esta fase: registrar SOLO qué evento macro existía, cuándo, importancia, y relación
temporal con el setup. NO convertir en filtro de aprobación/rechazo.
Para cerrar GAP-1 se requiere una FUENTE de eventos macro con timestamp (CSV/API de
calendario económico). Fuera de alcance del piloto; se documenta como pendiente.

---

## 6. QUÉ CAUSALIDAD SE PUEDE DEMOSTRAR / RECONSTRUIR / ES IMPOSIBLE

- **Demostrable HOY (observable en señal):** orden sweep→disp→bos→retorno; dirección coherente;
  contexto HTF; presencia de POI; retorno a zona.
- **Reconstructible OFFLINE (Arquitectura B, determinista):** niveles de cada fase desde OHLC;
  zona POI (ya hecho); emparejamiento BOS→POI por `fvg_for_bos`; SWEEP→DISP y DISP→BOS por
  proximidad+dirección. Linaje "por inferencia de proximidad".
- **IMOSIBLE con datos actuales (sin tocar motor):** identidad 1:1 estricta
  (sweep #17 → disp #23 → bos #31 → poi #44) porque los IDs de objeto no se crean.
  Esto requiere Arquitectura A (o un esquema de IDs derivados deterministas en el auditor,
  ej. `hash(symbol+tf+tipo+idx)` — que sería un híbrido A-lite en B).

---

## 7. CONCLUSIÓN DEL CEO

1. El problema es de **trazabilidad**, no de detección. Los eventos SMC existen y se leen.
2. El motor forma la secuencia; el **linaje causal 1:1 no está demostrado** porque nadie crea
   identidades de objeto enlazadas (ni motor ni detectores).
3. **Arquitectura B (auditor reconstruye offline) está respaldada por la evidencia** y es
   suficiente para DEMOSTRAR LA FORMACIÓN en esta fase, sin tocar engine/.
4. GAP-1 macro: solo contexto observable; requiere fuente externa para relación temporal real.
5. **No se modifica engine/.** La reparación (si se decide A) es fase posterior separada.

## 8. RECOMENDACIÓN DE LA SIGUIENTE FASE

- Extender el auditor (Piloto 1 ya existente) para reconstruir las 3 uniones por proximidad+
  dirección usando `detectors.*` + `fvg_for_bos`, marcándolas como "RECONSTRUCTED (inferencia
  de proximidad)", no "OBSERVABLE causal". Esto cierra la demostración de FORMACIÓN bajo B.
- Mantener UNKNOWN explícito para identidad 1:1 estricta hasta decidir A.
- Cerrar GAP-1 solo con registro de contexto (sin filtro).
- Orden respetado: FORMACIÓN → MACRO/NEWS → OOS/FOREX → ESTADÍSTICA → EDGE.

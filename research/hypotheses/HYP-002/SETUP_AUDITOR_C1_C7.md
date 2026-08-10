# SETUP_AUDITOR_C1_C7.md — Cierre documental de C1-C7 (evidencia mínima por capa)

> **Diseño (2026-08-10). Documentación ÚNICAMENTE. CERO Python, CERO ejecución, CERO backtest.**
> Cierra las decisiones C1-C7 de `SETUP_AUDITOR_PROTOCOL_AUDIT.md` antes del piloto, y aplica el
> esquema de 4 preguntas por capa exigido por el Director:
> 1. ¿Qué **evento** afirmamos que ocurrió? 2. ¿Qué **dato observable** lo demuestra? 3. ¿Qué
> **relación causal** demuestra con el evento anterior? 4. ¿Qué tendría que faltar para declararlo
> **UNKNOWN**?
> Regla de oro (Director): C1-C7 existen para responder *"¿qué evidencia mínima necesito para
> afirmar que este evento causó al siguiente?"*, NO para hacer que el setup pase.

---

## 0. Principio rector de C1-C7 (anti-SESGO de aprobación)

Cada regla se define por la **ausencia de evidencia**, no por la conveniencia del veredicto:
- Si el dato observable no existe en `MarketObject`/`Expediente` → **UNKNOWN**, nunca PASS.
- El auditor **no infiere causalidad por orden temporal** (`sweep_idx < displace_idx < bos_idx`
  solo prueba secuencia, no linaje). La ligadura se reconstruye desde los precios/niveles.
- C1-C7 se aplican LEYENDO los datos ya producidos por el motor; **no se toca `engine/`**.

Fuentes ya verificadas (del auditoría previa):
- `engine/sequence.py:157` `_has_sweep`, `:170` `_has_displacement`, `:205` `_has_bos` (booleanos
  sobre `obj.meta`).
- `:525-637` máquina de fases (`sweep_idx`, `displace_idx`, `bos_idx`, `entry_at`).
- `:579-596` cuadro = zona FVG/OB cacheada o fallback `bos_level ± 0.5·atr`.
- `:618-633` señal expone índices + `bos_level`, `poi_present`, `htf_aligned`, `htf_reason`.
- `engine/poi_anchor.py:86-122` `make_htf_poi_fn` → `poi_present` (bonus; sin frames → True).
- `engine/liquidity_levels.py:42/121` `detect_liquidity_htf` / `nearest_liquidity_target`.

---

## 1. C1 — Sweep válido = flag opuesto Y nivel barrido = liquidez objetivo

**Evento afirmado:** el precio tomó (wick a través de) el nivel de liquidez objetivo.
**Dato observable:** `obj.meta["liquidity_sweep_down/up"]` en vela `i=sweep_idx` Y
`low[i] ≤ target_level ≤ high[i]` (o cruce de wick) donde `target_level` =
`nearest_liquidity_target(...)` evaluado en el contexto previo al sweep.
**Relación causal:** el nivel barrido ES la liquidez que la capa 3 identificó como objetivo; si
no coincide, el sweep "pertenece a otro setup" → no se liga.
**Qué faltaría para UNKNOWN:** el motor no expone `target_level` ni el nivel del wick en la señal;
el auditor DEBE leerlos del `MarketObject` de `sweep_idx` (`low/high/time`) y comparar con el
target. Si el `MarketObject` no está disponible → UNKNOWN.
**PASS/FAIL:** PASS = flag opuesto presente Y wick toca el target. FAIL = flag presente pero wick
no toca el target (sweep de otra cosa) O flag ausente. UNKNOWN = sin `MarketObject` de `sweep_idx`.

---

## 2. C2 — Magnitud mínima de displacement (evitar flag subjetivo)

**Evento afirmado:** impulso direccional REAL posterior al sweep, en dirección del setup.
**Dato observable:** cuerpo de la vela `displace_idx` en dirección `target`, medido en unidades de
volatilidad. Propuesta por defecto (CALIBRABLE en piloto, NO ley):
`|close - open| ≥ k · avg_candle_range` con `k = 1.0` (el motor ya usa `atr = avg_candle_range`,
`sequence.py:586`). O alternativamente `range ≥ k2 · atr`.
**Relación causal:** `displace_at > sweep_at` Y el impulso ocurre SOBRE la misma liquidez barrida
(C1 liga nivel→sweep); el displacement debe abrir por encima/debajo del nivel barrido, no en otro
lado.
**Qué faltaría para UNKNOWN:** si el `MarketObject` de `displace_idx` no tiene `open/close/atr`
(para computar magnitud) → UNKNOWN. El flag `displacement_*` solo cuenta como evidencia de
DIRECCIÓN, no de magnitud.
**PASS/FAIL:** PASS = flag en dir correcta Y magnitud ≥ k·atr. FAIL = flag en dir correcta pero
magnitud < k·atr (no es "real"). UNKNOWN = sin datos de magnitud. **Nunca** PASS por solo flag.

---

## 3. C3 — Ligadura causal explícita (BOS→esa liquidez→ese displacement)

**Evento afirmado:** el BOS rompe la estructura nacida del displacement que siguió al sweep que
tomó ESA liquidez.
**Dato observable:** `bos_idx` con `bos_dir == target` Y `bos_at > displace_at` Y el nivel roto
(`bos_level`, `sequence.py:579`) es una estructura que existía antes del sweep (no una creación
posterior). Además: el BOS debe ser CONSECUTIVO al displacement de C2 (no un BOS de 50 velas
después sobre otra narrativa).
**Relación causal:** NO basta `bos_at > displace_at`. El auditor reconstruye: el swing roto por el
BOS es el mismo swing que el displacement empujó. Si el BOS rompe una estructura distinta a la
empujada por el displacement → linaje roto → `CAUSALITY: BROKEN` (no FAIL de capa aislada, sino
fallo transversal).
**Qué faltaría para UNKNOWN:** si no hay `bos_level` finito ni swing previo identificable → UNKNOWN
en la capa 6.
**PASS/FAIL:** PASS = BOS en dir correcta, post-displacement, sobre la estructura empujada. FAIL =
BOS en dir correcta pero sobre estructura no ligada al displacement. UNKNOWN = sin `bos_level`.

---

## 4. C4 — POI anclado con evento ancla recuperable (no solo booleano)

**Evento afirmado:** el POI (FVG/OB) del LTF nació del BOS/CHOCH del TF padre ya cerrado.
**Dato observable:** `poi_present` (de `poi_anchor`) DEBE poder acompañarse del evento ancla:
`(tf, time, kind)` del BOS/CHOCH padre. Hoy `poi_present` es booleano y `make_htf_poi_fn` no lo
expone. El auditor, SIN tocar `engine/`, DEBE recuperar ese evento re-leyendo `build_htf_structure_index`
sobre los frames HTF ya cargados (la función existe en `poi_anchor.py:49`), y comparar
`parent_event.time ≤ ltf_time[bos_idx]`.
**Relación causal:** el POI del LTF debe anclarse al MISMO `bos_idx`/dirección del setup, no a
cualquier evento padre en dir. Si el evento ancla es de otra dirección o posterior → no anclado.
**Qué faltaría para UNKNOWN:** si no hay frames HTF cargados → `poi_present=None` → UNKNOWN (no
PASS por el comportamiento bonus "sin frames → True"; el auditor lo trata como dato faltante).
**PASS/FAIL:** PASS = evento ancla en dir, ya cerrado, ≤ ltf_t del BOS. FAIL = `poi_present=False`
con frames cargados, o ancla en otra dir. UNKNOWN = sin frames HTF.

---

## 5. C5 — Retorno al POI REAL (marcar cuadro sintético)

**Evento afirmado:** el precio volvió al cuadro del POI (mitigation).
**Dato observable:** `_touches_zone(zone_high, zone_low)` en `entry_at`. El auditor debe registrar
CUÁL cuadro se usó: si `zone_high/zone_low` venían de la zona FVG/OB cacheada → cuadro REAL; si
cayeron al fallback `bos_level ± 0.5·atr` (`sequence.py:594-596`) → cuadro SINTÉTICO.
**Relación causal:** el retorno debe ser al cuadro nacido del POI de C4, no a un nivel arbitrario.
**Qué faltaría para UNKNOWN:** si no hay `zone_high/zone_low` finitos ni `close[entry_at]` → UNKNOWN.
**PASS/WARNING/FAIL:** PASS = toque del cuadro REAL del POI. **WARNING** = toque del cuadro
SINTÉTICO (el motor no trazó el FVG real; el veredicto de capa 8 no es silencioso). FAIL = sin
toque del cuadro. UNKNOWN = sin datos de zona/close.

---

## 6. C6 — Criterio de Contexto HTF (evitar gate relajado subjetivo)

**Evento afirmado:** sesgo D1/H4/H1 sin contradicción, permite la dirección del setup.
**Dato observable:** `htf_aligned` (`sequence.py:484`) Y `htf_reason`. Hoy el gate usa
`non_neutral>=2` en `bias/narrative`.
**Relación causal:** el contexto es el piso 1; si contradice la dirección del setup, el setup no
tiene piso (pero el linaje ICT es válido en contratendencia, por eso `counter_trend` existe).
**Qué faltaría para UNKNOWN:** si `est_htf` no trae tendencias D1/H4/H1 → UNKNOWN.
**PASS/FAIL:** PASS = `htf_aligned=True` con `htf_reason` coherente. FAIL = `htf_aligned=False`.
UNKNOWN = contexto HTF no disponible. **Nota:** el valor por defecto `non_neutral>=2` se documenta
como el gate actual; si el piloto encuentra setups RANGING contados como alineados, C6 se ajusta
(documentado, no silenciado).

---

## 7. C7 — Capas 9 y 10 explícitas (no ocultar lo no implementado)

**Capa 9 (Confirmación LTF):** el motor corre 1 LTF (`sequence.py:641` default M15). El auditor
debe emitir **FAIL o N/A** (según si el tipo de setup exige LTF fino), NUNCA ocultarlo ni dar PASS.
Esto es GAP-2, no un fallo del auditor.
**Capa 10 (Macro/News):** el motor no tiene calendario (`GAP-1`). El auditor emite **UNKNOWN** y,
si se le provee externamente un evento con `time/impact/distance`, lo registra como
`INFO/WARNING/UNKNOWN` (relación = UNKNOWN hasta tener especificación observable). NUNCA BUY/SELL.
**Qué faltaría para UNKNOWN:** ambas por diseño (ausentes en motor). Se declaran explícitamente.

---

## 8. Jerarquía de decisión del veredicto (anti-subjetividad)

El auditor aplica este árbol, no "parece un setup → PASS":

```
¿La evidencia observable existe?  ──NO──► UNKNOWN
        │ SÍ
        ▼
¿La relación causal está demostrada (C1-C4 ligadura)? ──NO──► UNKNOWN (o CAUSALITY: BROKEN)
        │ SÍ
        ▼
   PASS  /  FAIL   (según cumpla la definición operacional de la capa)
```

UNKNOWN es la respuesta por defecto ante dato faltante. El auditor NUNCA convierte UNKNOWN en PASS.

---

## 9. Revisión de consistencia de los 4 docs (C9)

Se cruzaron `SETUP_SPEC` (11 capas canónicas), `SETUP_AUDITOR_DESIGN` (juez forense),
`SETUP_AUDITOR_PROTOCOL` (protocolo + taxonomía 11 resuelta) y `SETUP_AUDITOR_PROTOCOL_AUDIT`
(ambi güedades B1-B8 + C1-C7). Resultado:
- Taxonomía: 11 capas canónicas, linaje causal = transversal (consistente en los 4).
- Noticias: contexto externo, UNKNOWN/PENDING, no filtro (consistente).
- Macro/LTF: GAP-1/GAP-2 declarados UNKNOWN/FAIL explícitos (consistente con C7).
- C1-C7 cierran B1-B6 (sweep→liquidez, magnitud displacement, ligadura BOS, POI ancla, cuadro real,
  contexto). B7/B8 son por diseño (macro/LTF ausentes). B5 mitigado por C5 (WARNING si sintético).
- Sin contradicciones de número ni de filosofía. Los 4 docs hablan el mismo idioma.

---

## 10. Qué queda definido / qué sigue UNKNOWN / qué falta en el motor / condiciones del piloto

**Definido por C1-C7:** reglas de evidencia mínima para capas 1-8 + tratamiento explícito 9-10.
Todas leíbles desde `MarketObject`/`Expediente`/`poi_anchor.build_htf_structure_index` SIN tocar
`engine/`.

**Sigue UNKNOWN (por diseño, no por falta de auditoría):** capa 9 (LTF fino) y capa 10 (macro)
hasta que existan módulos/especificaciones observables.

**Información que FALTA en el motor (para una auditoría plena, futura, NO ahora):**
- `target_level` de liquidez expuesto en la señal (hoy solo `nearest_liquidity_target` interno).
- nivel del wick de sweep expuesto (hoy solo flag).
- `poi_present` acompañado de `parent_event (tf,time,kind)` (hoy solo booleano).
- magnitud de displacement expuesta (hoy solo flag binario).
Estas son observaciones para una futura fase de enriquecimiento del motor, NO para modificar ahora.

**Condiciones antes del piloto (Piloto 1 = 5 setups):**
1. C1-C7 cerrados (este doc). ✓
2. Dos corredores independientes sobre los 5 llegan al mismo PASS/FAIL/UNKNOWN por capa (acuerdo de
   auditoría), usando la jerarquía §8.
3. UNKNOWN se usa donde falte dato; ningún setup se declara COMPLETE con capa 9=FAIL y 10=UNKNOWN
   sin que el reporte lo muestre.
4. Datos: 5 setups ya emitidos por `run_sequence` con su `Expediente.history` y `MarketObject[]`
   disponibles (bloqueo DATA R5/A6 de AGENTS.md debe resolverse antes de correr).

**No ejecutar el piloto hasta cumplir 1-4. No crear EXP-READ-001 hasta entonces.**

*Cierre documental de C1-C7. Sin EXP, sin ejecución, sin Python. Complementa
`SETUP_AUDITOR_PROTOCOL_AUDIT.md` y `SETUP_AUDITOR_PROTOCOL.md`.*
# RESEARCH_CONTRACT.md — Contrato arquitectónico del Mundo CIENCIA (`research/`)

> **Diseño (2026-08-10).** NO es ejecución: no se crea `research/`, no se mueve nada, no se
> repara `geometry_lab/`, no se toca Python. Es el estándar del laboratorio antes de
> construirlo físicamente. Pendiente de autorización del Director.
>
> Alineado con: `ARCHITECTURE.md` §4 (Mundo CIENCIA), `DEPENDENCY_RULES.md` §2/§3
> (`research/experiments/ → engine/backtest/data/` ✅; `research/ → backtest` "backtest
> decide" ❌).

## 0. Regla fundamental (del Director)

> **Un experimento no debe depender de recordar qué hizo Hermes en una conversación. Todo lo
> necesario para reproducirlo debe existir en el repositorio.**

Corolario: `research/` es una **unidad física de investigación reproducible**, no una carpeta
de documentos interesantes. Si no se puede reconstruir desde el repo, no es un experimento:
es una anécdota.

---

## 1. HYP-NNN vs EXP-NNN (pregunta 1)

| | `HYP-NNN` (Hipótesis) | `EXP-NNN` (Experimento) |
|---|---|---|
| Naturaleza | **Pregunta + predicción falsable** | **Ejecución que pone a prueba la hipótesis** |
| Contenido | pregunta, tesis, predicción, criterios de falsación | protocolo + código + datos + resultados + veredicto |
| Estado | boceto / formulada / lista-para-probar | diseñado / en-ejecución / completado / archivado |
| Depende de | nada (puede surgir de `results/`) | de UNA `HYP-NNN` (padre) |
| Reproducible por sí sola | NO (es una afirmación) | SÍ (tiene todo lo necesario) |

**Una hipótesis NO es reproducible; un experimento SÍ.** Por eso la hipótesis es texto, el
experimento es una unidad de carpeta con código y datos.

### 2. ¿Cuándo una hipótesis se convierte en experimento? (pregunta 2)

Una `HYP-NNN` puede convertirse en `EXP-NNN` **solo si** cumple las 3 condiciones de
falsación:

1. Tiene **predicción medible** (qué número/patrón espera).
2. Tiene **criterio de refutación explícito** (si X, la hipótesis cae).
3. Tiene un **protocolo de ejecución determinista** (mismos inputs → mismos outputs).

Si falta alguna, sigue siendo `HYP-NNN` (no promovida). Esto evita "experimentos" que son
opiniones disfrazadas.

### 3. Contrato mínimo obligatorio de un `EXP-NNN` reproducible (pregunta 3)

Un `EXP-NNN` NO es válido si falta alguno de estos archivos:

```
research/experiments/EXP-NNN/
├── experiment.md     ← por qué existe, qué HYP proba, predicción
├── protocol.yaml     ← pasos deterministas de ejecución (versionado)
├── config.yaml       ← parámetros exactos de la corrida
├── code/             ← código fuente del experimento (self-contained o imports de engine/backtest/data)
├── data_manifest.json← QUÉ datos y de DÓNDE (IDs, hashes, rango), NO los datos en sí
├── run/              ← log de ejecución + entorno (python -m X, seed, commit hash)
├── results/          ← salida cruda de la corrida
├── evidence/         ← análisis/figuras derivadas de results/
└── verdict.yaml      ← REFUTADA | INCONCLUSIVA | PROMOVIDA + justificación + tribunal
```

Cualquier `EXP-NNN` sin `protocol.yaml` + `config.yaml` + `data_manifest.json` + `verdict.yaml`
es **incompleto** y no debe promoverse.

### 4. Datos e identificación (pregunta 4)

- Los **datos NO viven en `research/`** (son grandes, externos). Viven en `data/raw/` o se
  referencian por ID.
- `data_manifest.json` registra: símbolo(s), timeframe(s), rango de fechas, fuente, hash de
  los CSV/parquet.
- Reproducibilidad = `data_manifest` + `config` + `protocol` + commit hash del repo.
- Esto cumple la regla fundamental: abres `EXP-NNN` en 2 años y sabes exactamente qué datos
  usó sin preguntarle a nadie.

### 5. Configuración exacta de ejecución (pregunta 5)

- `config.yaml`: todos los hiperparámetros, seeds, límites (n_perm, FDR_alpha, etc.).
- `run/` guarda: `python -m research.experiments.EXP-NNN.code.main`, commit SHA
  (`git rev-parse HEAD` al ejecutar), hash de `config.yaml`, timestamp.
- Esto bloquea "lo corrí con otros parámetros y no lo anoté".

### 6. `research/` ↔ `results/` (pregunta 6) — FUENTE PRIMARIA vs DERIVADA

> **Ajuste del Director (2026-08-10):** no usar "espejo". El término sugiere dos copias
> igualmente válidas y abre la pregunta peligrosa "¿cuál es la verdad si divergen?".

- **`research/experiments/EXP-NNN/` = FUENTE PRIMARIA E INMUTABLE del experimento.** Contiene
  `results/` (salida de ESA corrida), `evidence/`, `verdict.yaml`. Es la única fuente de
  verdad del experimento.
- **`results/experiments/EXP-NNN/` = PUBLICACIÓN/REGISTRO DERIVADO de una promoción.** Se crea
  ÚNICAMENTE cuando el experimento es PROMOVIDO, y es una *referencia* a la fuente primaria
  (apunta al ID + commit + hash de `research/experiments/EXP-NNN/`), nunca una copia
  independiente que pueda divergir. Si algún día difieren, la fuente primaria (`research/`)
  manda; `results/` es derivado y debe regenerarse desde ella.
- `results/` es hoja (no importa nada). `research/` propone y es la fuente; `results/` es el
  registro publicado de lo promovido.
- `results/ → engine/` está PROHIBIDO (DEPENDENCY_RULES §3): la promoción a `engine/` requiere
  decisión explícita y pre-registrada, nunca silenciosa.

### 7. Experimento ↔ Backtest (pregunta 7)

- `research/experiments/ → ict_backtest/`, `engine/`, `data/` es **PERMITIDO** ✅
  (DEPENDENCY_RULES §2): el experimento CONSUME el motor/backtest para poner a prueba la
  hipótesis.
- `research/ → backtest` en sentido "backtest decide" es **PROHIBIDO** ❌: la investigación
  propone, no manda. El backtest es una herramienta del experimento, no su juez.
- `ict_backtest/diagnostics/` (FDR/Bonferroni/veredictos de backtest) **NO se mueve a
  `research/`**: es diagnóstico del backtest, acoplado a él. La separación epistemológica se
  mantiene.

### 8. Registro de veredicto (pregunta 8)

`verdict.yaml` tiene exactamente uno de tres estados (tribunal):

```yaml
exp: EXP-NNN
hyp: HYP-NNN
verdict: REFUTADA | INCONCLUSIVA | PROMOVIDA
promoted_to: engine/<modulo>   # solo si PROMOVIDA
tribunal:
  method: fdr | bonferroni | both
  alpha: 0.05
  adjusted_p: 0.03
justification: "..."
date: 2026-08-10
commit: <sha>
```

- **REFUTADA**: la hipótesis cae; se archiva con su evidencia (valor científico = aprendizaje).
- **INCONCLUSIVA**: evidencia insuficiente; puede re-ejecutarse con más datos (nuevo `EXP`).
- **PROMOVIDA**: pasa el tribunal; se pre-registra la decisión de llevarla a `engine/`.

### 9. Inmutabilidad del veredicto (pregunta 9)

> Cómo garantizar que un resultado no pueda editarse a posteriori para cambiar el veredicto.

- `results/` y `research/experiments/EXP-NNN/results/` son **inmutables tras el veredicto**:
  sellados por hash. El `verdict.yaml` incluye el hash de `results/`.
- Cambiar el veredicto requiere un **nuevo `EXP-NNN`** (re-ejecución) con nuevo ID, no
  editar el anterior. El historial es aditivo, no mutable.
- Esto impide "ajustar el veredicto a la narrativa": si los datos cambian, es un experimento
  distinto con ID distinto.

### 10. Linaje completo (pregunta 10)

Cadena trazable de extremo a extremo:

```
HYP-NNN (pregunta + predicción + falsación)
   │ padre
   ▼
EXP-NNN (protocol + config + code + data_manifest)
   │ ejecución (run/ con commit + seed)
   ▼
results/ (crudo) ──► evidence/ (análisis)
   │
   ▼
verdict.yaml (tribunal FDR/Bonferroni)
   │
   ├─ REFUTADA ──► archivo (se conserva, valor = aprendizaje)
   ├─ INCONCLUSIVA ──► nuevo EXP-NNN (más datos)
   └─ PROMOVIDA ──► results/experiments/EXP-NNN/ + pre-registro ──► engine/<modulo>
```

Cada eslabón es un archivo en el repo. El linaje se lee abriendo las carpetas, no recordando
conversaciones.

---

## 11. Evidencia válida vs solo documentación

| Es evidencia válida | Es solo documentación |
|---------------------|----------------------|
| `results/` crudos + `evidence/` derivado de ellos | `docs/specs/` (hipótesis en texto) |
| `verdict.yaml` con tribunal + hashes | `docs/ict/*.md` (prosa de estrategia) |
| `data_manifest.json` con hashes | `knowledge/` (aprendizajes) |
| `run/` con commit SHA + seed | `docs/lab/*.md` (notas de laboratorio) |

La documentación (docs/, knowledge/) **alimenta** hipótesis (`HYP-NNN`), pero por sí sola no
constituye un experimento. Esto responde a tu distinción: diferenciar afirmación de evidencia
física.

## 12. Tratamiento de experimentos históricos y `geometry_lab/`

- **`scripts/_legacy/fase*_demo_plan.py`, `fase_e_demo_e1.py`, `audit_experiment_f_structural.py`**:
  experimentos huérfanos en `scripts/_legacy/`. Se registran como **candidatos** a
  `research/experiments/EXP-NNN/` cuando el Director autorice su clasificación. NO se mueven
  hoy.
- **`geometry_lab/` (ROTO, 0 consumidores)**: se deja INTACTO. No se repara para moverlo.
  Cuando se defina "qué es un experimento válido" (este contrato), se evalúa si
  `geometry_lab` puede convertirse en un `EXP-D3` real. Hasta entonces: experimento huérfano
  roto pendiente de clasificación.
- **EXP-069 / EXP-071**: son **convenciones de la constitución**, no experimentos físicos.
  NO se inventan carpetas con esos IDs.

## 13. Estructura propuesta de `research/` (para cuando se autorice crear)

```
research/
├── hypotheses/
│   └── HYP-NNN/
│       ├── hypothesis.md
│       └── status.yaml          ← boceto | formulada | lista-para-probar
├── experiments/
│   └── EXP-NNN/                 ← arranca VACÍO; solo unidades autorizadas
│       ├── experiment.md
│       ├── protocol.yaml
│       ├── config.yaml
│       ├── code/
│       ├── data_manifest.json
│       ├── run/
│       ├── results/
│       ├── evidence/
│       └── verdict.yaml
├── protocols/                   ← protocolos versionados reutilizables
└── validation/                  ← validación independiente (vacío al inicio)
```

## 14. Ejemplo concreto (ilustrativo, NO ejecutado)

**HYP-001 — "La curvatura de Menger del precio es invariante de escala en M1→M15"**
- `hypothesis.md`: pregunta + predicción (coseno de ángulo estable bajo permutación) + criterio
  de falsación (p < 0.05 bajo null model refuta invariancia).
- `status.yaml`: formulada.

**EXP-001 — poner a prueba HYP-001**
- `protocol.yaml`: pasos deterministas (cargar M1/M5/M15, computar signed_turn, permutation
  test n=500).
- `config.yaml`: symbols=[EURUSD,GBPUSD,XAUUSD], n_perm=500, seed=42, fdr_alpha=0.05.
- `code/`: implementación (hoy sería el contenido de `geometry_lab/run_experiment.py` SI se
  reparara).
- `data_manifest.json`: ranges + hashes de `data/raw/`.
- `run/`: `git rev-parse HEAD` + `python -m ...` + seed.
- `results/`: `geometry_lab_d3.json`.
- `evidence/`: reporte de p-values.
- `verdict.yaml`: REFUTADA/INCONCLUSIVA/PROMOVIDA + tribunal FDR + hash de results.

> Nota: `geometry_lab/` hoy está ROTO (falta `core.py`/`null_test.py`), así que EXP-001 no
> puede materializarse hasta repararlo — y repararlo es trabajo de INVESTIGACIÓN, no de
> arquitectura. Por eso NO se toca en 3B.

---

## 15. Matriz de decisiones (para autorización del Director)

| # | Decisión | Estado en este diseño |
|---|----------|----------------------|
| 1 | Crear `research/` ahora | ❌ NO (se diseña primero) |
| 2 | HYP-NNN ≠ EXP-NNN (texto vs unidad reproducible) | ✅ definido |
| 3 | Promoción HYP→EXP requiere 3 condiciones de falsación | ✅ definido |
| 4 | Archivos obligatorios de EXP-NNN | ✅ protocol+config+data_manifest+verdict |
| 5 | Datos fuera de `research/` (manifest con hashes) | ✅ definido |
| 6 | `run/` con commit SHA + seed (regla fundamental) | ✅ definido |
| 7 | `research/experiments/ → engine/backtest/data` permitido | ✅ (DEPENDENCY_RULES §2) |
| 8 | `research/ → backtest` "backtest decide" prohibido | ✅ (DEPENDENCY_RULES §3) |
| 9 | `ict_backtest/diagnostics/` queda en backtest | ✅ NO se mueve |
| 10 | Veredicto: REFUTADA/INCONCLUSIVA/PROMOVIDA + tribunal | ✅ definido |
| 11 | Inmutabilidad: veredicto sellado por hash, aditivo | ✅ definido |
| 12 | Linaje HYP→EXP→results→verdict→promoción | ✅ trazable por archivos |
| 13 | Evidencia física ≠ documentación | ✅ diferenciado |
| 14 | `geometry_lab/` intacto, no reparar para mover | ✅ registrado huérfano roto |
| 15 | EXP-069/071 = convención, no inventar carpetas | ✅ registrado |
| 16 | Experimentos históricos en `scripts/_legacy/` = candidatos | ✅ no mover hoy |

---

## 16. Regla rectora — Lectura del mercado antes que win rate (2026-08-10)

> **Cambio de dirección científica del laboratorio.** Principio rector para TODA investigación
> futura sobre ICT/SMC y SMC-SYSTEMS. Anula el paradigma anterior de "medir primero rendimiento".
> Registrada también en memoria persistente (Engram) como regla rectora permanente.

### 16.1 Principio

Cuando trabajamos con ICT/SMC y con la tesis de SMC-SYSTEMS, el objetivo primario **NO** es
demostrar que existe un edge estadístico mediante win rate. El objetivo primario es:

> **Reconstruir y auditar correctamente la formación de un setup según la tesis del repositorio,
> demostrando primero que el motor realmente lee el mercado antes de evaluar si esa lectura
> produce rendimiento.**

### 16.2 Orden obligatorio de investigación

1. **LECTURA DEL MERCADO** — contexto HTF, liquidez, sweep, displacement, BOS/CHOCH/MSS, POI,
   retorno, confirmación LTF, secuencia temporal y causal.
2. **FORMACIÓN DEL SETUP** — los eventos no deben simplemente coexistir; deben formar la
   secuencia exigida por la tesis; el motor debe poder explicar por qué esos acontecimientos
   constituyen un setup.
3. **AUDITORÍA DEL SETUP** — ¿cada evento ocurrió realmente? ¿en el orden correcto? ¿existe
   relación causal o solo coincidencia? ¿la estructura es coherente? ¿hay contradicciones?
   ¿qué condiciones del edificio superó? ¿en qué piso falló?
4. **CONTEXTO DE NOTICIAS / EVENTOS** — noticias del día, de la semana, eventos macroeconómicos,
   proximidad de noticias de alto impacto, impacto potencial sobre la validez/interpretación del
   setup. Las noticias forman parte del contexto de validación del setup; NO se añaden
   posteriormente como una simple variable para mejorar el win rate.
5. **VALIDACIÓN** — primero validar que el objeto SETUP que produce el motor representa realmente
   la tesis ICT/SMC; después comprobar reproducibilidad y estabilidad.
6. **RENDIMIENTO ESTADÍSTICO** — solo después de demostrar que el setup está correctamente
   formado se estudian: MFE, MAE, RR, expectancy, win rate, profit factor, rendimiento económico.

### 16.3 Regla fundamental

> **No buscamos primero demostrar que el sistema gana. Buscamos demostrar primero que el sistema
> sabe qué está viendo.**

Por tanto: **Lectura → Secuencia → Setup → Auditoría → Noticias/Contexto → Validación → Rendimiento.**

### 16.4 Regla para futuras hipótesis

Cada nueva hipótesis ICT/SMC debe responder primero:

> **¿Qué parte de la lectura/formación del setup estamos intentando demostrar o destruir?**

y no:

> **¿Qué combinación produce mayor win rate?**

El rendimiento es consecuencia posterior de una lectura validada, no la definición de un setup válido.

### 16.5 Consecuencia para HYP-001 (trazabilidad, no destrucción)

HYP-001 ("¿el contexto HTF aporta edge?") fue formulada bajo el paradigma anterior de medir
primero rendimiento. **Se CONSERVA** en `research/hypotheses/HYP-001/` como trazabilidad histórica
de esa decisión; NO se reescribe silenciosamente. Pero bajo esta regla rectora:

- **NO se avanza a EXP-001** (la prueba de rendimiento `WR_aligned`/`PF>1`) hasta demostrar que el
  motor está formando correctamente el setup ICT/SMC.
- Antes de continuar hacia EXP-001, se debe evaluar si HYP-001 sigue siendo la hipótesis rectora
  adecuada. Lo probable es que la hipótesis rectora pase a ser una de **LECTURA**
  (ej. "¿el motor forma correctamente el setup ICT/SMC según la secuencia de la tesis?"), y el
  rendimiento se estudie solo tras validar esa lectura.
- El `status.yaml` de HYP-001 lleva el campo `rector_rule_review` marcando este estado.

### 16.6 Impacto en el flujo de `research/`

- Los auxiliares CAND-03/05 (PROTOCOL_AUX_CAND-03-05.md) y el baseline de HYP-001 quedan
  **en espera de validación de lectura**: no se ejecutan para producir `WR_aligned` hasta que
  exista una HYP/EXP de lectura que demuestre formación correcta del setup.
- Cualquier nuevo `HYP-NNN` de ICT/SMC debe declarar explícitamente qué parte de la
  lectura/formación del setup pone a prueba (§16.4).

### 16.7 Nueva línea científica — HYP-002 (hipótesis de LECTURA, rectora)

Bajo esta regla, la hipótesis rectora del laboratorio YA NO es "¿HTF produce mejor WR?"
(HYP-001, conservada como trazabilidad). Es:

> **HYP-002 — ¿El motor reconstruye de forma determinista la formación completa de un setup
> ICT/SMC?** (`research/hypotheses/HYP-002/`)
>
> Cuando el motor emite un SETUP, ¿puede reconstruir físicamente — vela por vela, con relación
> causal — toda la cadena que llevó hasta ese setup? Variable primaria: `R_recon` (tasa de
> reconstrucción determinista). NO `WR`/`PF` (esas son consecuencia posterior, paso 6).

#### 16.7.1 Cadena de formación del setup (qué significa "completo")

```
CONTEXTO → ESTRUCTURA → LIQUIDEZ → EVENTO → DESPLAZAMIENTO → BOS/CHOCH → POI → RETORNO → CONFIRMACIÓN → SETUP COMPLETO
```

NO `HTF → entrada → ¿ganó?`. Si el setup está mal construido, un WR del 55-70% no dice por qué
funciona ni qué se está leyendo.

#### 16.7.2 Macro/noticias = capa de CONTEXTO EXTERNO (no indicador)

```
        MERCADO
           │
    ┌──────┴──────┐
    │             │
LECTURA SMC   CONTEXTO EXTERNO
    │             │
estructura    noticias
liquidez      eventos
POI           calendario
desplazamiento riesgo macro
    │             │
    └──────┬──────┘
           ↓
    FORMACIÓN SETUP
           ↓
 ¿ES COHERENTE CON EL CONTEXTO DEL DÍA?
           ↓
    SETUP VALIDADO
```

La noticia NO "crea" el setup; puede explicarlo, invalidarlo, contextualizarlo o elevar su
calidad. El sistema registra p.ej.: *"setup estructuralmente formado, pero apareció evento
macro de alta relevancia en su ventana de ejecución"* — lectura más rica que `WIN=1`.

#### 16.7.3 Marco de auditoría del setup (tabla de capas)

| Capa         | Pregunta de auditoría                                   |
| ------------ | ------------------------------------------------------- |
| Contexto     | ¿Qué estaba haciendo el mercado (sesgo HTF D1/H4/H1)?   |
| Estructura   | ¿Cuál era la estructura vigente (BOS/CHOCH/MSS)?         |
| Liquidez     | ¿Qué liquidez (BSL/SSL) estaba disponible?               |
| Evento       | ¿Qué fue tomado/swept?                                   |
| Displacement | ¿Hubo desplazamiento real posterior al evento?          |
| Estructura   | ¿El BOS/CHOCH ocurrió después del evento correcto?      |
| POI          | ¿El POI nació del evento correcto (anclado)?            |
| Retorno      | ¿El precio volvió al POI esperado?                      |
| LTF          | ¿Hubo confirmación en el timeframe de ejecución?         |
| Macro        | ¿Qué noticias/eventos rodeaban el setup?                |
| Estado       | ¿El setup seguía válido o fue invalidado?               |

#### 16.7.4 Orden evolutivo (no al revés)

```
LECTURA DEL MERCADO → FORMACIÓN DEL SETUP → VALIDACIÓN CONTEXTO MACRO → SETUP AUDITADO
   → recién entonces → PERFORMANCE (WR/PF/expectancy)
```

El motor debe ser una **representación computable de cómo un humano lee y construye el setup**,
no una máquina que descubre combinaciones de filtros por su win rate. Primero: Hermes señala un
setup y lo explica causalmente vela por vela; después: se pregunta si ese tipo de setup tiene
rendimiento estadístico.

#### 16.7.5 Primer experimento de lectura — SETUP AUDITOR (diseñado, no ejecutado)

El primer experimento verdaderamente importante del laboratorio NO es un backtest de WR. Es el
**SETUP AUDITOR** (`research/hypotheses/HYP-002/SETUP_AUDITOR_DESIGN.md` visión general;
`SETUP_AUDITOR_PROTOCOL.md` protocolo EXP-READ-001), diseñado bajo HYP-002:

- Es un **juez forense**, no un segundo motor: consume la evidencia ya producida por el motor
  (`Expediente.history`, `SequenceState`, objetos de mercado) y comprueba, contra datos
  observables y timestamps, si la historia que el motor cuenta es VERDAD. No confía ciegamente en
  las etiquetas del motor; cada evento debe tener evidencia y timestamp.
- Reconstruye cada setup vela por vela y distingue **evento detectado** vs **relación causal
  demostrada** vs **setup completo**.
- Reporta **PASS / FAIL / UNKNOWN** por capa.
- **Taxonomía canónica = SETUP_SPEC (11 capas)**. La matriz de evidencia las presentó consolidadas
  en 9; ambas son ciertas bajo su vista. "Linaje causal" NO es una capa: es propiedad transversal
  sobre las capas de evento (resuelto en `SETUP_AUDITOR_PROTOCOL.md` §1).
- Separa **OBLIGATORIAS** (Contexto, Estructura, Liquidez, Sweep, Displacement, Confirmación
  estructural, POI, Retorno), **CONDICIONALES** (Confirmación LTF) y **CONTEXTO EXTERNO**
  (Noticias).
- La capa de noticias aparece **explícitamente como GAP/PENDING** (GAP-1: `macro_direction` es
  tendencia HTF, no calendario macro; `noticias_widget.py` está hardcodeado solo para UI). NO se
  implementa `engine/macro_calendar` todavía para no contaminar la lectura con reglas prematuras.
- Declara **COMPLETE** solo si todas las obligatorias PASAN con causalidad demostrada; **INCOMPLETE**
  si alguna falla (con `FALLÓ EN: <capa>`); **INVALIDATED** si `engine/invalidation` lo marcó (aunque
  las capas PASARAN). Nunca cuenta "N PASS / 1 FAIL" como éxito.
- **Muestra piloto 5–10 setups** (descubrir si el auditor puede reconstruirlos), luego 50, luego
  100. No se fija `R_recon`, 0.90 ni umbral de rendimiento.
- Al encontrar un fallo del motor, **NO se corrige durante el experimento**: se registra como
  hallazgo con evidencia y capa. Observación → evidencia → diagnóstico → hipótesis de defecto →
  experimento → recién entonces modificación. Cero cambios en `engine/`.

---

#### 16.7.6 Auditoría de determinismo del SETUP AUDITOR (puerta previa al piloto)

Antes de ejecutar cualquier piloto, el protocolo pasó una auditoría de determinismo
(`research/hypotheses/HYP-002/SETUP_AUDITOR_PROTOCOL_AUDIT.md`). Veredicto: el protocolo es
reproducible en **ORDEN** (la máquina de fases `IDLE→SWEEP→DISPLACE→BOS→ENTRY` lo garantiza) pero
NO completamente en **CAUSALIDAD** ni en "evidencia suficiente", porque el motor no expone el nivel
barrido ni liga sweep→liquidez→displacement→BOS→POI, el displacement es flag (no magnitud), el POI es
bonus no-gate y el cuadro de retorno puede ser sintético. Ambigüedades documentadas B1-B8;
decisiones pre-piloto C1-C7 (cómo el auditor reconstruye la ligadura y magnitud DESDE
`MarketObject`/`Expediente`, sin tocar `engine/`). Hasta fijar C1-C7 **NO se ejecuta el piloto**.
Esto es la puerta que separa "juez con reglas precisas" de "juez con opinión": dos auditores
independientes deben llegar al mismo PASS/FAIL/UNKNOWN para el mismo setup antes de correr Piloto 1
(5 setups). UNKNOWN nunca se convierte en PASS.

---

#### 16.7.7 Cierre documental C1-C7 (evidencia mínima por capa, anti-sesgo de aprobación)

C1-C7 se cerraron documentalmente (`research/hypotheses/HYP-002/SETUP_AUDITOR_C1_C7.md`) sin tocar
`engine/`. Cada capa responde las 4 preguntas del Director (evento afirmado / dato observable /
relación causal / qué faltaría para UNKNOWN), y se aplican LEYENDO `MarketObject`/`Expediente`/
`poi_anchor.build_htf_structure_index`, no añadiendo lógica al motor. Regla anti-sesgo: C1-C7 existen
para responder *"¿qué evidencia mínima necesito para afirmar que este evento causó al siguiente?"*,
NO para hacer que el setup pase. Jerarquía de veredicto: evidencia existe → causalidad demostrada →
PASS/FAIL; ante dato faltante → UNKNOWN (nunca UNKNOWN→PASS). C1 liga sweep al nivel de liquidez
(real, no inferido por orden); C2 exige magnitud de displacement (flag no basta); C3 liga BOS a ESE
displacement/liquidez; C4 recupera el evento ancla del POI (no solo booleano); C5 marca WARNING si el
cuadro de retorno es sintético; C6 documenta el gate de contexto; C7 declara LTF=FAIL/N-A y
Macro=UNKNOWN explícitos. Revisión de consistencia de los 4 docs: sin contradicciones. **NO ejecutar
el piloto** hasta cumplir las 4 condiciones (C1-C7 cerrados, acuerdo de 2 auditores, UNKNOWN usado
donde falte dato, datos de 5 setups disponibles — bloqueo DATA R5/A6). HYP-001 sigue congelada.

---

#### 16.7.8 Reconciliación final del SETUP AUDITOR (previa al piloto, sin ejecutar)

Revisión del Director leyendo los docs desde GitHub encontró 3 problemas; reconciliados en
`research/hypotheses/HYP-002/SETUP_AUDITOR_RECONCILIATION.md` (sin tocar los docs previos, para
preservar trazabilidad):
1. **C2 no introduce umbral**: se retira `k=1.0·ATR`; displacement = evento observado, propiedades
   registradas como DATOS a observar, no veredicto. Umbral TBD por diseño (primero el objeto, después
   la parametrización).
2. **C3 separa causalidad demostrable de NO demostrable**: el motor conserva orden+dirección (sí
   demostrable) pero NO el linaje de liquidez (nivel barrido, swing roto, `parent_event` del POI no
   expuestos) → eso es UNKNOWN/CAUSALITY BROKEN, no inferencia. Hallazgo científico: "el motor no
   conserva suficiente información para demostrar su propia causalidad".
3. **Contradicción SETUP_SPEC §4 ↔ C7 resuelta**: el piloto audita **EMISIONES DEL MOTOR**, no
   "setups completos"; `FORMATION: VALID` queda en suspenso (es el estándar de destino, no el
   criterio de este piloto). Una emisión INCOMPLETE es hallazgo esperado, no fracaso.
Regla rectora superior: **el auditor NO reconstruye retrospectivamente causalidad no observable →
UNKNOWN/BROKEN**. C4/C5 bajo la misma regla (no asumir POI↔BOS ni retorno↔POI por proximidad).
Objetivo del piloto de 5 emisiones: descubrir qué capas son demostrables, cuáles UNKNOWN, cuáles mal
ligadas, y qué falta en el motor — NO una alta tasa de PASS. Macro=contexto externo. Sin `engine/`,
sin backtest, sin WR/PF/R, sin EXP-READ-001, sin ejecución.

---

#### 16.7.9 Auditoría forense de datos del SETUP AUDITOR (etapa previa al piloto)

`research/hypotheses/HYP-002/SETUP_AUDITOR_DATA_FORENSICS.md`: localiza cómo obtener 5 emisiones de
`run_sequence` conservando `Expediente` + `MarketObject[]` + señal + timestamps + contexto HTF, SIN
modificar `engine/` ni backtest de rendimiento. Hallazgos:
- `run_sequence` (público) descarta el `Expediente`; `run_sequence_traced` (`engine/sequence.py:660`)
  SÍ devuelve `(signals, phase_seen, expedientes)` — esa es la vía correcta. El atributo real es
  `Expediente.phase_events` (los docs HYP-002 lo llaman `history` por error de nombre).
- `data/raw/*.parquet` contiene SOLO `time,O,H,L,C` (verificado EURUSD_M15 = 114,237 filas, OHLC);
  las features ICT (`sweep_low`, `bsl/ssl_price`, `fvg_mid`, `displacement_mag`) NO están persistidas
  — se recalculan on-the-fly en `ict_backtest/data_feed.build_features`. El auditor debe leer el wick
  del sweep de OHLC y compararlo con pools recalculados.
- **No hay 5 emisiones ya persistidas en disco** (el motor descarta el `Expediente` salvo por
  `_traced`); pero SON obtenibles ejecutando `run_sequence_traced` sobre `data/raw` (obtención, no
  rendimiento — permitido).
- Cobertura top-down: EURUSD tiene D1/H1/H4/M15 (cadena completa); AUDUSD/GBPUSD/NZDUSD/USDCAD/USDCHF/
  USDJPY tienen D1/H4/M15 (sin H1); XAUUSD NO en raw (solo zip sin procesar). 6 símbolos forex = 5
  emisiones reproducibles alcanzables.
- Linaje de causalidad (sweep→ESA liquidez→displacement→ESE BOS→POI) sigue sin ser observable: el
  motor no embolsa `swing_id` roto ni `parent_event` del POI → el auditor emitirá UNKNOWN/BROKEN donde
  falte eslabón (coincide con Reconciliation). Macro/Noticias = GAP-1 fuera de alcance.
Sin `engine/`, sin backtest, sin WR/PF/R, sin EXP-READ-001, sin ejecución de rendimiento.

---

#### 16.7.10 Auditoría de la contradicción ATR vs Ley Fundamental (SETUP AUDITOR)

`research/hypotheses/HYP-002/SETUP_AUDITOR_ATR_AUDIT.md`: el Director detectó que C2/C5 mencionaban
"ATR" y la Ley Fundamental prohíbe indicadores en `engine/`. Hallazgo: **contradicción de NOMBRE,
no de sustancia**. `engine/` NO usa ATR/EMA/RSI (cada módulo lo declara en docstring); la columna
`atr` del motor es un ALIAS contractual de `avg_candle_range` = media móvil de `high-low` (geometría
pura, verificado en `ict_backtest/_util.py:128` y `detectors/displacement.py:19`). El motor ya decide
displacement con `body > avg_range*1.5` + mecha pequeña (rango, no ATR). C2 (ya sin umbral por la
Reconciliación) queda blindado: magnitud = DATO DESCRIPTIVO AUXILIAR, NO gate, NO evidencia de
displacement. C5: el fallback `bos_level ± 0.5·rango_promedio` NUNCA se acepta como POI real; si se
usa, capa 8 = WARNING ("retorno a cuadro de respaldo, no POI FVG/OB real"). Declaración explícita:
el rango promedio es descriptivo, no gate de ninguna capa. La Ley Fundamental queda CUMPLIDA en
sustancia; solo se renombra `atr`→`rango_promedio` en la documentación del auditor para no reactivar
la sospecha. Sin `engine/`, sin backtest, sin ejecución, sin EXP.

---

#### 16.7.11 Matriz de preparación del piloto: ¿puede el SETUP AUDITOR demostrar causalidad sin inventarla?

`research/hypotheses/HYP-002/PILOT_PREP_MATRIX.md`: auditoría documental final antes del piloto.
Hallazgo estructural (verificado en `sequence.py`): la máquina de estados guarda en `state` SOLO
ÍNDICES ENTEROS (`sweep_idx`, `displace_idx`, `bos_idx`, `entry_at`), NO referencias a `MarketObject`,
ni `swing_id` roto, ni `parent_event` del POI. El `MarketObject` (`market_object.py:50`) SÍ tiene
`parent_object`/`related_objects`, pero la secuencia NO los usa para ligar. El anclaje de POI
(`poi_anchor.py`) empareja por dirección+timestamp cross-TF, no por identidad de swing roto.
Por tanto el motor demuestra ORDEN TEMPORAL + DIRECCIÓN + ANCLAJE HTF POR TIMESTAMP, pero NO
identidad causal 1:1 (este sweep→este displacement→este BOS→este POI). Las 3 uniones rotas
(LIQUIDEZ→SWEEP nivel de pool; SWEEP→DISPLACEMENT swing ligado; DISPLACEMENT→BOS swing roto;
BOS→POI parent_event) son RE-DERIVABLES del OHLC de `data/raw/*.parquet` por el auditor off-line, sin
tocar `engine/`. MACRO/NEWS = GAP-1, siempre UNKNOWN (sin fuente en motor). Decisión: **PILOTO
LISTO** — condición: el auditor emite UNKNOWN/BROKEN donde la identidad causal no se demuestre, nunca
PASS por orden temporal solo, y MACRO/NEWS = UNKNOWN siempre. Sin `engine/`, sin backtest, sin
ejecución, sin EXP-READ-001.

#### 16.7.12 Piloto 1 de HYP-002 AUTORIZADO y en ejecución (2026-08-10)

El Director autorizó el Piloto 1 bajo regla rectora estricta (14 condiciones, ver
`research/hypotheses/HYP-002/status.yaml#pilot1`). Resumen de la orden:

- **Objetivo NO es medir WR/PF/edge**, ni determinar si el setup "funciona".
- Objetivo EXCLUSIVO: comprobar si podemos **reconstruir y auditar la FORMACIÓN REAL**
  del setup ICT/SMC sin inventar causalidad.
- Consumidor puro del motor: `engine.sequence.run_sequence_traced` (devuelve
  `(signals, phase_seen, expedientes)`), con `est_htf_ctx_fn` cableado igual que
  `ict_backtest/canonical.py` (vía `engine.plan.build_multitf_context` +
  `engine.poi_anchor`). **Sin tocar `engine/`, ni detectores, ni backtester.**
- Condición de datos verificada (prueba de emisión ad-hoc): el motor emite **79 setups
  reales** en 20k velas M15 (EURUSD 29 + AUDUSD 29 + GBPUSD 21) → cumple ≥5.
- Separación estricta OBSERVADO / RECONSTRUIDO / INFERIDO; orden temporal NUNCA → PASS
  causal; ATR/avg_candle_range solo descriptivo; MACRO/NEWS = UNKNOWN (sin fuente).
- El auditor emite UNKNOWN/BROKEN/CAUSALITY_BROKEN donde falte identidad causal; no
  completa la historia por plausibilidad.

**Veredicto agregado adelantado (mapa de formación real, sustentado en código ya
auditado, no en el conteo del piloto):**

| Capa del setup | Estado en el motor hoy |
|---|---|
| OBSERVABLE (emitido en el momento) | orden sweep→disp→BOS→retorno; dir coherente; flags; `bos_level`; `zone_*`; `htf_aligned`/`htf_reason`; `expediente.phase_events` |
| CAUSAL (demostrable con datos actuales) | solo coherencia DIRECCIONAL (disp sigue dir del sweep; BOS sigue dir del disp). Ninguna unión 1:1. |
| RECONSTRUIDA (derivable del OHLC, NO = causalidad) | nivel de liquidez barrido (wick emparejado con `bsl/ssl_price`); swing roto por BOS |
| DESCONOCIDA (sin fuente) | MACRO/NEWS (GAP-1) → UNKNOWN; ejecución fina M5/M1 → UNKNOWN; `parent_event` del POI → UNKNOWN |
| DÓNDE SE ROMPE EL LINAJE | SWEEP→DISPLACEMENT (sin `swing_id`); DISPLACEMENT→BOS (sin swing roto embolsado); BOS→POI (anclaje por dir+timestamp, no identidad) |

Conclusión del piloto (esperada, coherente con la auditoría): el motor **FORMA** la
secuencia (orden+dir observables) pero la **identidad causal 1:1 no está demostrada** en
SWEEP→DISP, DISP→BOS, BOS→POI. Cada setup emitido → veredicto agregado
**SETUP EMITIDO / CAUSALITY BROKEN** en esas uniones. Eso es resultado correcto: revela
dónde el edificio lee realmente vs. donde narra después de los hechos. Reparaciones,
si las hay, serán fase posterior separada (no durante el piloto).

#### 16.7.13 Puerta de reconstrucción offline del SETUP AUDITOR (2026-08-11)

Orden del Director (2026-08-11): **NO ejecutar el piloto hasta cerrar la puerta de
reconstrucción offline** — auditoría de que cada relación causal que el auditor pretende
recuperar desde OHLC usa una regla YA DEFINIDA por la tesis/código del repo, y que el
auditor NO introduce una segunda interpretación ICT/SMC escondida.

Entregable: `research/hypotheses/HYP-002/SETUP_AUDITOR_RECONSTRUCTION_AUDIT.md`
(auditoría forense de lectura, cero ejecución). Hallazgo central confirmado en código
(`engine/sequence.py`, `engine/expediente.py`): el `Expediente` conserva SOLO índices +
timestamps de fases (`sweep_idx < displace_idx < bos_idx < entry_at`) + dirección; NO
conserva `MarketObject[]` ni niveles de liquidez/sweep/POI. El linaje causal no se guarda
como identidad, solo como orden+dirección.

Clasificación por elemento:
- **OBSERVABLE** (dato directo del emitido): htf_aligned, sweep ocurrió+dir+ts, displacement
  ocurrió+dir, BOS ocurrió+dir, POI zona (`zone_*`), retorno al POI, poi_present.
- **DERIVABLE SIN INTERPRETACIÓN** (mismos detectores del motor sobre el OHLC): HTF bias
  (`detect_market_structure`), pools BSL/SSL (`detect_liquidity`), niveles de mecha sweep
  (`sweep_low/high`), BOS rompió "un swing" (`ms["swing_*"]`).
- **INTERPRETACIÓN NUEVA = PROHIBIDA** (se marca **UNKNOWN**, no se infiere): displacement←sweep
  (causal), BOS←swing específico (causal), POI←BOS LTF (causal). El motor solo exige
  proximidad temporal (`displace_gap`/`bos_gap`), no causalidad.
- **GAP-1** (sin fuente): MACRO/NEWS → siempre UNKNOWN.

Veredicto de la puerta: **CERRADA Y CONSISTENTE**. El auditor usa los MISMOS detectores que
el motor; no redefine BOS/swing/POI. No hay segunda tesis escondida. Las 3 uniones marcadas
INTERPRETACIÓN NUEVA ya estaban previstas en el protocolo como UNKNOWN/BROKEN y el auditor las
deja así. Ejecución diferida a Opción B (reescribir `pilot1_run.py` evitando el import de
`ict_backtest` que arrastra `rules.py` bug `datetime`, para no contaminar el objeto auditado).

#### 16.7.14 Resultado real del Piloto 1 — ejecutado (2026-08-11, cliente = CEO)

Ejecutado como CEO del laboratorio (autonomía total, sin micro-dirección). Opción B aplicada:
`pilot1_run.py` reescrito para NO importar `ict_backtest` (evita el bug `datetime` en
`rules.py` y no contamina el objeto auditado). Consumidor puro: usa `detectors.*`,
`engine.bos.structure.detect_market_structure`, `engine.sequence.run_sequence_traced` y
`engine.poi_anchor.make_htf_poi_fn` directamente. Corrido en GitHub Actions (Ubuntu,
`run 31497898201`, 32s) porque el entorno local es lento en la fase de features.

- **Muestra:** EURUSD M15, 3000 velas (2022-01..02). Setups emitidos por el motor: **4**.
- **Fichas forenses:** `research/hypotheses/HYP-002/pilot1_output.md` (formato del cliente:
  CONTEXTO/LIQUIDEZ/FORMACIÓN/CAUSALIDAD/POI/RETORNO/MACRO/LTF/VEREDICTO).
- **Mapa agregado:** `research/hypotheses/HYP-002/SETUP_FORMATION_MAP.md`.

**Resultado confirmado (setup por setup):**
- ✓ demostrado (OBSERVABLE/DERIVABLE): contexto HTF (`htf_aligned=PASS`), liquidez tomada
  (mecha del sweep con nivel real), sweep, displacement, BOS/CHOCH, zona POI (re-derivada
  FVG/OB entre sweep y BOS con niveles reales), retorno, dirección coherente en los 4.
- ✗/UNKNOWN (no demostrado): las **3 uniones causales** (Sweep→Disp, Disp→BOS, BOS→POI) —
  el motor no conserva linaje 1:1 (solo orden+dirección). MACRO/NEWS (GAP-1) → UNKNOWN.
  Ejecución fina M5/M1 → UNKNOWN.

**Hallazgos (registrados, NO reparados en el piloto — regla AUDITAR→DIAGNOSTICAR→DECIDIR→MODIFICAR):**
- H1: `bos_level` no se conserva en la emisión (`state.bos_level` existe pero no se emite;
  columna `bos_level` vacía en velas BOS). Brecha de trazabilidad.
- H2: liquidez estructural no anclada al sweep (pools `bsl/ssl_price` escasos; 3/4 sin match).
- H3: `Expediente.meta` solo `{symbol, ltf_tf}`; no `MarketObject[]` ni niveles.
- H4/H5: GAP-1 macro y LTF fina → UNKNOWN por diseño (fuera de alcance del piloto).

**Veredicto de fase (corrección de wording por el Director 2026-08-11):** **SETUP CANDIDATO —
formación parcial demostrada; linaje causal 1:1 incompleto.** Tener los eventos ≠ demostrar que
forman UN setup causal. Componentes demostrables; unidad causal NO demostrada. El motor lee y
forma correctamente contexto, liquidez tomada, sweep, displacement, BOS, POI y retorno — pero la
**identidad causal del linaje no está demostrada** (3 uniones UNKNOWN). No es "el setup perdió":
es que **el setup no llega a estar completamente formado como cadena causal demostrable** con lo
que el motor emite hoy. Reparaciones (enriquecer `Expediente` con `MarketObject[]` + linaje 1:1)
son fase posterior separada. Auditoría de pérdida de información en §16.7.15. Orden de apertura
de siguientes fases respetado: FORMACIÓN → VALIDACIÓN MACRO/NEWS → OOS/OTC → ESTADÍSTICA → EDGE.

#### 16.7.15 Auditoría de Pérdida de Información — HYP-002 Fase 2 (2026-08-11, cliente = CEO)

Misión del Director: determinar dónde se pierde la información para el linaje causal 1:1, SIN
modificar engine/. Entregable: `research/hypotheses/HYP-002/INFO_LOSS_AUDIT.md`.

Hallazgos de lectura forense (código real):
- `MarketObject` (`engine/market_object.py`) TIENE `id`/`parent_object`/`related_objects`, pero
  `engine/sequence.py` solo crea `MarketObject(type=CANDLE)` por vela. **Nunca se crea objeto
  para sweep/disp/bos/poi con su id+parent.** Los detectores devuelven flags por vela SIN IDs.
- `SequenceState` conserva índices + `bos_level/zone_*` internamente; la señal emitida
  (`sequence.py:618-634`) NO copia `zone_high/zone_low`, y `bos_level` queda NaN a menudo (H1).
- `Expediente` (`expediente.py`) guarda `PhaseEvent(phase,idx,time,condition)` — índice+timestamp,
  SIN nivel, SIN id de objeto, SIN parent_event.
- Precedente de reconstrucción offline (Arquitectura B): `engine/fvg_poi.fvg_for_bos` ya hace
  BOS→POI por proximidad+dirección (idx). Mismo patrón extensible a SWEEP→DISP y DISP→BOS.

Matriz (ver doc): niveles casi todos DERIVABLES desde OHLC por índice; lo que **NO existe en
ningún lado** es IDENTIDAD ÚNICA y PARENT_EVENT (nunca se creó, no se "perdió").

**Diagnóstico:** el problema es de **TRAZABILIDAD** (y parcialmente representación), NO de
detección. Los eventos SMC se detectan; el motor opera por índices+dirección, no por grafo de
objetos enlazados.

**A vs B (por evidencia, no preferencia):**
- **A** (motor conserva linaje): requiere tocar engine/ (crear MarketObject enlazados). Garantiza
  1:1 en vivo; riesgo de regresión; contamina motor con preocupación de auditoría. Hoy NO existe.
- **B** (auditor reconstruye offline): el motor intacto emite índices+dirección+niveles parciales;
  el auditor re-deriva por proximidad+dirección con `detectors.*` + `fvg_for_bos`. **Determinista**
  (detectores puros sobre OHLC, sin estado/random). El piloto ya reconstruyó la zona POI offline.
  Límite: linaje por inferencia de proximidad, no identidad estricta; ambiguo si dos eventos del
  mismo tipo colapsan en la ventana.

**Determinación:** para DEMOSTRAR LA FORMACIÓN (esta fase), **B está respaldada por la evidencia
y respeta la Ley Fundamental** (motor = única fuente de decisión; auditor = consumidor puro). A
queda postergado hasta demostrar que B es ambiguo en la práctica.

**GAP-1 macro:** `noticias_widget.py` tiene noticias FIJAS hardcoded (sin feed por timestamp).
Fase: registrar SOLO contexto observable (qué ocurrió, cuándo, relación temporal) — NO filtro de
aprobación. Requiere fuente de eventos macro con timestamp para relación temporal real.

**Veredicto Fase 2:** problema de trazabilidad, no detección. Arquitectura B suficiente para
demostrar formación sin tocar engine/. Identidad 1:1 estricta imposible sin A (o IDs derivados
deterministas en el auditor = híbrido A-lite en B).

---

*Diseño puro del contrato. Pendiente de autorización del Director para crear/migrar `research/`.*
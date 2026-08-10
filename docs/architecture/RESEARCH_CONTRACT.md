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

*Diseño puro del contrato. Pendiente de autorización del Director para crear/migrar `research/`.*
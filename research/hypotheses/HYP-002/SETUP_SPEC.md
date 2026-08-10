# SETUP_SPEC.md — Especificación formal de "SETUP COMPLETO" (HYP-002)

> **Diseño (2026-08-10). Documentación y diseño ÚNICAMENTE. Cero Python, cero ejecución.**
> Autorizado por el Director tras revisión de `feature/backtest-ict`. Parte de HYP-002
> (hipótesis de LECTURA, rectora). Define el OBJETO de estudio ANTES de fijar umbrales.

## 0. Propósito

HYP-002 pregunta si el motor reconstruye **deterministamente** la formación del setup. Pero
"reconstrucción" y "setup completo" son ambiguos hasta que definimos el objeto. Este documento
fija:

1. La **anatomía observable** del setup por capas (los "pisos del edificio").
2. Qué **evidencia debe existir** en cada piso (observable, con timestamp).
3. Cómo se demuestra **CAUSALIDAD** entre eventos (linaje causal), no solo coincidencia temporal.
4. Cómo entra el **contexto macro** (como contexto, no como indicador).
5. Cómo se determina que un setup está **CORRECTAMENTE FORMADO**.

**Principio rector (§16):** primero definir el objeto y validar la lectura; los umbrales
(numéricos, p.ej. `R_recon`) se fijan DESPUÉS, no antes. Por eso HYP-002 NO fija 0.90 hoy.

---

## 1. Anatomía del SETUP COMPLETO — 11 capas (pisos del edificio)

Cada capa es un piso que debe existir con **evidencia observable y timestamp**. El auditor
emite por capa: `PASS` / `FAIL` / `WARNING` (macro = `INFO`/`WARNING`).

| # | Capa                | Evidencia requerida (observable)                                            | Fuente esperada en el motor (ya presente*)              |
|---|---------------------|-----------------------------------------------------------------------------|---------------------------------------------------------|
| 1 | Contexto            | Sesgo y dirección D1/H4/H1; sin contradicción                               | `engine/plan.build_context_stack` + `engine/bias/narrative` |
| 2 | Estructura          | Estructura previa vigente + evento de cambio (CHOCH/BOS/MSS)                | `engine/sequence` (sweep→displace→BOS)                   |
| 3 | Liquidez            | BSL/SSL disponible y TOMADA, con nivel y timestamp                          | `engine/liquidity_levels`                                |
| 4 | Evento (sweep)      | Sweep REAL (no falso) del nivel de liquidez, con nivel y timestamp          | `engine/sequence` (sweep detection)                      |
| 5 | Displacement        | Impulso direccional REAL posterior al evento (magnitud + timestamp)         | `engine/sequence` (displacement)                         |
| 6 | Confirmación estructural | BOS/CHOCH ocurre TRAS el displacement                                    | `engine/sequence` (BOS)                                  |
| 7 | POI                 | Tipo (FVG/OB), ORIGEN = BOS, ANCLADO al evento                             | `engine/poi_anchor` (POI anclado)                        |
| 8 | Retorno             | Precio VOLVIÓ al POI esperado (timestamp)                                  | retorno en `engine/sequence` + `engine/zone`             |
| 9 | Confirmación LTF    | M5/M1 confirmación POST-retorno al POI                                     | `engine/sequence` (LTF confirm)                          |
| 10| Macro / contexto    | Eventos/noticias cercanas, impacto, distancia a la ventana de ejecución     | **NUEVA capa contexto externo** (no en motor hoy)        |
| 11| Estado              | Válido / invalidado (no contradice capas previas)                          | auditoría global                                          |

\* Según `AGENTS.md` Ley Fundamental y el inventario de módulos del motor. Se listan como
"fuente esperada" para ligar la especificación a la materia prima ya existente; no es una
afirmación de que cada módulo ya emita exactamente estos campos — eso lo verifica el futuro
EXP de lectura.

### 1.1 Ejemplo de registro de un setup (forma mínima del objeto)

```
SETUP-ID: 0001
CONTEXTO    D1:bearish H4:bearish H1:bearish
ESTRUCTURA  previa:bullish  cambio:CHOCH
LIQUIDEZ    objetivo:BSL  tomada:sí  ts:10:15
EVENTO      sweep:sí  nivel:xxxx  ts:10:15
DISPLACEMENT sí  magnitud:xx  ts:10:18
CONFIRMACIÓN BOS:sí  ts:10:20
POI         tipo:FVG  origen:BOS  anclado:sí  ts:10:20
RETORNO     al_POI:sí  ts:10:45
LTF         M5:confirm  M1:confirm
MACRO       CPI:sí  hora:10:49  impacto:alto  distancia:4min
ESTADO      válido
```

---

## 2. Linaje causal — separar EVENTO de CAUSALIDAD

Proximidad temporal **≠** causalidad. El motor debe demostrar la flecha causal, no solo listar
eventos en orden:

```
BOS
  ↑ causado/confirmado por displacement
  ↑ después del sweep
  ↑ que tomó determinada liquidez
  ↑ dentro de determinado contexto
```

Esto es el **linaje causal del setup**: cada piso debe estar causalmente enlazado al siguiente,
no meramente coincidente en el tiempo.

- **INVÁLIDO (coincidencia):** `10:00 sweep · 10:05 FVG · 10:10 BOS · 10:15 OB` listados en
  orden pero SIN demostrar que el BOS nació del displacement que siguió al sweep que tomó la
  liquidez.
- **VÁLIDO (linaje):** sweep tomó BSL → displacement lo confirmó → BOS sobre ese displacement →
  POI nació de ese BOS → retorno a ese POI → confirmación LTF posterior.

El auditor registra el fallo como: `FALLÓ EN: <capa> — <razón>` (p.ej. "POI no causalmente
anclado al BOS"). Eso es lectura de mercado, no conteo de banderas.

---

## 3. Macro como CONTEXTO (no indicador)

La capa macro es **contexto externo**, no regla BUY/SELL. NO "crea" el setup. Puede: explicarlo,
invalidarlo, contextualizarlo o elevar su calidad.

```
              SETUP
                │
       ┌────────┴────────┐
       │                 │
  estructura        contexto macro
       │                 │
       └────────┬────────┘
                ↓
           AUDITORÍA
```

- Salida: `INFO` / `WARNING` (nunca `PASS`/`FAIL` automático del setup).
- Ejemplo: *"setup estructural válido, pero CPI de alto impacto 4 min después"* — eso NO implica
  automáticamente que el setup sea malo; es una **condición contextual a registrar**.
- Solo se OBSERVA primero si ciertas condiciones macro invalidan/retasan/producen false-sweep/
  alteran el POI o simplemente no importan. Cualquier regla macro que invalidE el setup es, a su
  vez, una hipótesis a testear MÁS ADELANTE, no un supuesto metido para "mejorar el WR".

---

## 4. Determinación de "CORRECTAMENTE FORMADO"

Un setup está **CORRECTAMENTE FORMADO** si y solo si:

- Todas las capas estructurales (1–9) = `PASS`.
- **Linaje causal COMPLETO** (cada piso causalmente enlazado, no coincidente).
- Estado (11) = `válido` (no invalidado por contradicción).
- Macro (10) = registrado como contexto (`WARNING`/`INFO` NO invalida por sí solo; solo una
  regla de invalidación configurada puede, y esas reglas son hipótesis, no axiomas).

### 4.1 Salida del SETUP AUDITOR (concepto, no código hoy)

```
SETUP-00017
FORMATION: VALID
Context       PASS
Structure     PASS
Liquidity     PASS
Sweep         PASS
Displacement  PASS
BOS           PASS
POI           PASS
Return        PASS
LTF           PASS
Macro         WARNING
State         PASS
Causal chain: COMPLETE
```

Esa salida enseña a leer el mercado; no es `WIN=1`.

---

## 5. Umbral `R_recon` — TBD (NO fijar aún)

Por decisión del Director: **no fijar `≥ 0.90` ahora**. Primero esta especificación debe ser
operable: ¿puede el motor poblar cada capa desde los módulos reales? El umbral numérico de
`R_recon` se fija SOLO después de que el objeto esté definido y sepamos qué mide "reconstrucción".
Hasta entonces la predicción de HYP-002 es: *"`R_recon` alta y localizable por capa"*, sin número.

---

## 6. Relación con el laboratorio

Esta especificación es el **OBJETO** del futuro EXP de LECTURA (aún no creado). El primer
experimento verdaderamente importante sería:

> **"Dame 100 setups y demuéstrame, vela por vela, cuáles realmente existen y cuáles son
> artefactos del motor."**

Eso requiere: (a) esta especificación, y (b) un **SETUP AUDITOR** que evalúe cada capa y el
linaje causal. Ambos son diseño por ahora; la ejecución viene después de validar la lectura,
nunca antes.

---

*Diseño de HYP-002. Sin EXP, sin ejecución, sin tocar código. Complementa `hypothesis.md` y
`status.yaml` de HYP-002.*
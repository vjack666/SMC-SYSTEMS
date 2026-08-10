# SETUP_AUDITOR_RECONCILIATION.md — Reconciliación final antes del piloto (sin ejecutar)

> **Revisión documental (2026-08-10). CERO Python, CERO ejecución, CERO backtest.**
> El Director leyó `SETUP_SPEC`, `SETUP_AUDITOR_PROTOCOL_AUDIT` y `SETUP_AUDITOR_C1_C7` directamente
> desde GitHub y encontró 3 problemas conceptuales. Este doc los reconcilia y fija el objetivo real
> del piloto. NO modifica los docs anteriores (se preserva la trazabilidad de la evolución). Las
> correcciones se aplican como **enmiendas** a C2/C3/C4/C5 y a la contradicción `SETUP_SPEC §4` ↔ `C7`.

---

## 0. Regla rectora de esta reconciliación (nueva, explícita)

**El auditor NO puede reconstruir retrospectivamente una relación causal que el motor no haya
dejado observable.**

Si una relación causal no se puede demostrar con evidencia observable en los datos que el motor
conservó (`MarketObject`/`Expediente`/`poi_anchor`), el auditor emite **UNKNOWN** o
**CAUSALITY: BROKEN**, NUNCA la infiere por proximidad temporal ni por "orden de la máquina de
fases". Esta regla es superior a C1-C7 cuando entren en conflicto.

---

## 1. Problema 1 — C2 introducía un umbral antes de tiempo

**Lo que dijo C2:** `|close-open| ≥ k·atr` con `k=1.0` (aunque "calibrable").
**Por qué está mal:** viola nuestra propia regla — primero definir el OBJETO (qué es displacement
en la tesis ICT/SMC), después parametrizarlo. Meter ATR/magnitud antes de demostrar que esa es la
definición correcta de displacement para ESTA tesis es prematuro. `SETUP_SPEC §5` dice que los
umbrales numéricos vienen DESPUÉS de definir el objeto.

**Corrección (C2 enmendado):**
- El auditor NO usa `k=1.0·ATR` como regla de PASS. Se **retira** cualquier apariencia de umbral
  aprobado.
- En el piloto, el displacement se trata como **evento observado**, no como magnitud decidida:
  - SI hay flag `displacement_*` en `displace_idx` con dirección correcta → registrar las
    propiedades OBSERVABLES (cuerpo, rango, dirección, tiempo, relación con `sweep_idx`) y emitir
    **PASS** por *detección*, no por *magnitud*.
  - El auditor registra además las propiedades numéricas (cuerpo, rango en unidades de `atr`) como
    **datos a observar**, NO como veredicto.
  - NO decide "1 ATR = displacement". Esa definición matemática se DESCUBRE después de observar qué
    caracteriza a los displacement que el motor ya detecta.
- Si el `MarketObject` de `displace_idx` no existe → **UNKNOWN** (igual que antes), pero por falta
  de dato, no por magnitud.

**Resultado:** C2 ya no promete umbral. El piloto observa; la parametrización queda TBD por diseño.

---

## 2. Problema 2 — C3 prometía demostrar causalidad que el motor no conserva

**Lo que dijo C3:** el auditor "reconstruye" que el BOS rompe la estructura sobre la MISMA liquidez
que el sweep barrió y tras el MISMO displacement, leyendo los datos existentes.

**Por qué está mal:** la propia auditoría (`SETUP_AUDITOR_PROTOCOL_AUDIT.md` B1-B4) reconoce que el
motor NO guarda identificadores de linaje (nivel barrido, evento ancla del POI, swing roto por el
BOS). Por tanto, "reconstruir" esa cadena completa es **imposible retrospectivamente** con los datos
que el motor conserva hoy. Forzarla sería inventar causalidad.

**Corrección (C3 enmendado) — separar dos cosas:**

A) **Causalidad demostrable con datos existentes** (el auditor SÍ puede hacer):
- Orden: `sweep_at < displace_at < bos_at < entry_at` (índices en la señal, `sequence.py:623-626`).
- Dirección coherente: sweep opuesto, displacement y BOS en dirección `target` (`_has_*`).
- Que el BOS esté en la MISMA dirección que el displacement (no contradictorio).
Esto prueba **secuencia + coherencia direccional**, no linaje de liquidez.

B) **Causalidad que la tesis exige pero el motor NO puede demostrar retrospectivamente** (el auditor
   debe declarar UNKNOWN/CAUSALITY BROKEN, NO inferir):
- Que el BOS rompió ESE swing empujado por ESE displacement sobre ESA liquidez barrida por ESE sweep.
- Que el POI nació específicamente de ESE BOS (sin `parent_event` expuesto, no se demuestra).
- Que el retorno fue a ESE cuadro real (no al fallback sintético).

**Veredicto de C3:** el auditor reporta `CAUSALITY: DEMONSTRABLE` (solo orden+dirección) o
`CAUSALITY: BROKEN/UNKNOWN` (si falta algún eslabón observable). NUNCA afirma linaje de liquidez que
no está en los datos. Esto es un **hallazgo científico valioso**: "el motor no conserva suficiente
información para demostrar su propia causalidad" — no un fallo del auditor.

---

## 3. Problema 3 — Contradicción SETUP_SPEC §4 ↔ C7

**La contradicción:** `SETUP_SPEC §4` dice "FORMATION: VALID requiere capas 1–9 = PASS". `C7` declara
capa 9 (LTF) = FAIL/N-A porque el motor corre 1 LTF (`sequence.py:641`). ⇒ con la especificación
actual, **FORMATION: VALID es IMPOSIBLE** ⇒ el piloto no puede llamarse "auditoría de 5 setups
completos".

**Corrección (decisión del Director: auditar EMISIONES, no setups completos):**

- El piloto audita **"EMISIONES DEL MOTOR QUE PRETENDEN SER SETUPS"**, no "setups completos".
- `FORMATION` se redefine para el piloto como: `FORMATION: EMITIDO` + desglose por capa
  (PASS/FAIL/UNKNOWN) + `CAUSALITY: DEMONSTRABLE/BROKEN/UNKNOWN`. NO se usa `FORMATION: VALID`
  (reservado para cuando el motor pueda demostrar capas 1-9+linaje).
- Una emisión que salga `INCOMPLETE` o con capas UNKNOWN **NO es un fracaso del experimento**: es el
  hallazgo esperado — el objeto que el motor llama "setup" no cumple todavía nuestra definición de
  setup completo (tesis SMC ≠ señal del motor).
- `SETUP_SPEC §4` queda en suspenso para el piloto: su "FORMATION: VALID" es el ESTÁNDAR de destino,
  no el criterio de este piloto. Se documenta explícitamente la divergencia.

---

## 4. C4 y C5 bajo la regla de no-invención retrospectiva

- **C4 (POI):** el auditor NO asume que un POI pertenece al BOS solo porque aparece después. Si no
  hay `parent_event` recuperable (frames HTF ausentes o `poi_present=None`) → **UNKNOWN**, no PASS por
  el bonus "sin frames → True". Si hay evento ancla recuperable y coincide en dir/tiempo → PASS; si
  no coincide → FAIL. Nada se infiere por proximidad.
- **C5 (Retorno):** el auditor NO asume que el retorno pertenece al POI si el cuadro usado fue
  sintético (`bos_level ± 0.5·atr`). En ese caso → **WARNING** (no PASS silencioso), y la capa 8
  queda marcada como "retorno a cuadro no verificable como POI real". Si no hay datos de zona/close →
  UNKNOWN.

---

## 5. Qué puede demostrar hoy el motor / qué NO puede (hallazgo central)

**Puede demostrar (observable en datos conservados):**
- Orden de eventos (`sweep_at < displace_at < bos_at < entry_at`).
- Dirección coherente de cada evento vs `target`.
- Contexto HTF (`htf_aligned`/`htf_reason`).
- Presencia de flag de sweep/displacement/BOS y, si hay frames HTF, presencia booleana de POI anclado.
- Nivel `bos_level` y cuadro usado (real o sintético) para el retorno.

**NO puede demostrar retrospectivamente (linaje de liquidez — hallazgo):**
- Que el sweep tomó ESA liquidez concreta (no expone nivel barrido).
- Que el displacement empujó ESE swing y el BOS rompió ESE swing (no expone swing roto).
- Que el POI nació de ESE BOS (no expone `parent_event`).
- Confirmación LTF fina (capa 9, 1 LTF).
- Contexto macro (capa 10, GAP-1).

Esto separa limpiamente: **MOTOR** ("tengo suficientes eventos para emitir una señal") vs **TESIS
SMC** ("tengo suficiente evidencia para afirmar que se formó un setup"). El piloto mide esa brecha.

---

## 6. Objetivo final del piloto de 5 emisiones (reemplaza el criterio anterior)

- **NO es** el éxito = alta cantidad de setups PASS.
- **ES** descubrir, por cada emisión:
  - qué capas son DEMOSTRABLES,
  - cuáles son UNKNOWN,
  - cuáles están mal ligadas (CAUSALITY: BROKEN),
  - y qué información falta en el motor para que pueda demostrar su propia lectura.
- Un resultado donde 5 emisiones salgan `INCOMPLETE` / con capas UNKNOWN / causalidad rota es una
  **victoria científica**: sabríamos exactamente dónde el edificio está construido y dónde solo
  PARECE estarlo. Solo entonces (y no antes) tiene sentido modificar el motor para conservar el
  linaje.
- Macro/News: contexto externo INFO/WARNING/UNKNOWN. NO filtro BUY/SELL. NO `engine/macro_calendar`.
- Cero `engine/`, cero backtest, cero WR/PF/R, cero EXP-READ-001, cero ejecución.

---

## 7. Resumen de enmiendas (trazabilidad)

| Doc origen | Enmienda en este doc |
|------------|----------------------|
| C2 (`SETUP_AUDITOR_C1_C7.md` §2) | Retirar `k=1.0·ATR`; displacement = evento observado, propiedades registradas como datos, no veredicto. Umbral TBD. |
| C3 (`...` §3) | Separar causalidad demostrable (orden+dirección) de linaje de liquidez NO demostrable → UNKNOWN/BROKEN. |
| C4 (`...` §4) | No asumir POI↔BOS por proximidad; sin `parent_event` → UNKNOWN. |
| C5 (`...` §5) | Cuadro sintético → WARNING, no PASS; retorno no verificable como POI real. |
| SETUP_SPEC §4 ↔ C7 | Piloto audita EMISIONES, no setups completos; `FORMATION: VALID` en suspenso; divergencia documentada. |
| Nueva regla | Auditor NO reconstruye causalidad no observable → UNKNOWN/BROKEN. |

*Reconciliación final. Sin EXP, sin ejecución, sin Python. Complementa `SETUP_AUDITOR_C1_C7.md` y
`SETUP_SPEC.md`.*
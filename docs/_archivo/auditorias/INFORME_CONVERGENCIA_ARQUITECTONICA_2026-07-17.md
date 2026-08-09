# INFORME DE CONVERGENCIA ARQUITECTÓNICA

**Fecha:** 2026-07-17
**Auditorías reconciliadas:**
- Auditoría Arquitectónica Comité Técnico (2026-07-17) — 23 hallazgos, 325 archivos, ~41.7K LOC
- Auditoría Forense del Backtest (2026-07-17) — 2 causas raíz de bajo conteo de trades
- Auditoría R4 Final + R4 v2 (2026-07-13) — look-ahead HTF, displacement, PO3/Silver bugs
- Auditoría R6 v2 MTF (2026-07-17) — v2 sin versionar, cap de señales, sin DSR/PBO
- Auditoría de Uso (2026-07-09) — 64% del repo es código no usado

**Regla rectora:** Todo cambio debe respetar simultáneamente: arquitectura, teoría ICT,
metodología Silver Bullet, evidencia forense y datos objetivos. Ningún cambio se aprueba
sólo porque produce más trades.

---

## 1. MATRIZ DE CONVERGENCIA

Cada hallazgo se cruza entre las auditorías. "—" = no cubierto por esa auditoría.

| # | Hallazgo | Arquitectónica | Forense | R4/R4v2 | R6v2 | Uso | Clasif. |
|---|----------|:--------------:|:-------:|:-------:|:----:|:---:|:-------:|
| C1 | Killzone-HTF mismatch (78% kills) | — | **Primario** | — | — | — | **A** |
| C2 | Displacement bottleneck (90% kills) | F4 (sin calibrar) | **Primario** | Incompatible con SB | — | — | **C** |
| C3 | PO3 choch_status mapping bug | — | — | **Primario** | — | — | **A** |
| C4 | 3 implementaciones BOS/CHOCH | F2 | — | — | — | — | **A+B** |
| C5 | ML train/serve mismatch | F5 | — | — | — | — | **A** |
| C6 | D1 cargado, nunca usado (43K LOC) | F1 | — | — | — | — | **B** |
| C7 | v2/ sin versionar | — | — | — | **Primario** | — | **A** |
| C8 | edge_diagnosis cap rompe ablación | — | — | — | **Primario** | — | **A** |
| C9 | Sin corrección múltiple (DSR/PBO) | — | — | — | **Primario** | — | **A** |
| C10 | Edge concentrado en XAUUSD (1 símbolo) | — | — | — | **Primario** | — | **D** |
| C11 | Look-ahead cross-timeframe (97.4%) | — | — | **FIXED** | — | — | ~~A~~ ✓ |
| C12 | Silver sweep M15 hardcoded | — | — | **FIXED** | — | — | ~~A~~ ✓ |
| C13 | costs.py calibra 3/8 símbolos | — | — | — | Menor | — | **C** |
| C14 | signals/ legacy island | — | — | — | — | Clasif. | **B** |
| C15 | 64% código no usado (~10.6K LOC) | — | — | — | — | **Primario** | **B** |

**Clave de clasificación:**
- **A = Bug** — Error que corrompe datos o produce resultados incorrectos. Fix obligatorio.
- **B = Design Decision** — Requiere decisión de arquitectura. No rompe nada, pero complica.
- **C = Calibrable Parameter** — Parámetro que necesita validación empírica dentro de restricciones ICT/SB.
- **D = Strategy Restriction** — Restricción estratégica que requiere decisión del usuario.
- ✓ = Ya corregido en código.

---

## 2. ANÁLISIS DE CONVERGENCIA POR HALLAZGO

### C1 — Killzone-HTF Mismatch [A — Bug]

**¿Qué dice la evidencia forense?**
`canonical.py:122-124` filtra `killzone_en(entry_row["time"])` contra la ventana wall-clock
de la vela de entrada. Para H4, las barras caen en 00/04/08/12/16/20 UTC. Solo 08:00
(London Open, 07-10 UTC) y 16:00 (NY PM, 15-17.5 UTC) pasan el filtro. NY AM inicia
12:30 UTC pero la barra H4 es 12:00 → `killzone_en(12:00)` = "" (fuera de rango 12.5-15.0).
Resultado: 78% de señales raw eliminadas.

**¿Qué dice la auditoría arquitectónica?** No lo detecta directamente. El hallazgo F4
("displacement sin calibrar en H4") está relacionado pero no cubre la causa raíz.

**¿Qué dice R4?** En M5, `killzone_en` funciona correctamente (NY AM recibe ~5200 velas
de 50000). El bug solo se manifiesta en H4.

**Convergencia:** Hallazgo **nuevo de la auditoría forense**. Ninguna auditoría previa lo
detectó porque nunca se instrumentó el funnel completo sobre H4.

**Decisión:** Es un **bug** (clasificación A). La intención del código es filtrar por sesión
de trading, pero la implementación no sabe que opera sobre H4. Hay dos opciones:

| Opción | Descripción | Pro ICT | Pro Arquitectura | Riesgo |
|--------|-------------|:-------:|:-----------------:|--------|
| A1 | `killzone_en` recibe la hora de la sesión subyacente (08:30 ET = 12:30 UTC), no la barra H4 | ✅ Respeta la sesión real | ✅ Generaliza el filtro | Requiere parsear la sesión del trade |
| A2 | Ampliar las ventanas UTC para cubrir barras H4 (NY AM = 12.0-15.0 en vez de 12.5-15.0) | ⚠️ Incluye 30min "fantasma" | ❌ Hack temporal | Señales falsas en ventana fantasma |

**Recomendación:** A1. Es el fix correcto arquitectónicamente y respeta la intención ICT.

---

### C2 — Displacement Bottleneck [C — Calibrable Parameter]

**¿Qué dice la evidencia forense?** `body_atr_multiple=1.5` + `wick_threshold=0.4` en
`detectors/displacement.py:11-12`. Solo ~10% de sweeps tienen displacement dentro de la
ventana de 6 velas post-sweep. El 90% restante se descarta.

**¿Qué dice la auditoría arquitectónica?** F4: "El umbral 0.4 no está validado empíricamente
para H4. Las restricciones en `DisplacementConfig` y `SequenceConfig` son por defecto y
pueden estar causando filtrado excesivo."

**¿Qué dice R4 v2?** "Silver Bullet (M5, NY AM) es incompatible con el filtro displacement.
El displacement casi nunca ocurre justo en la ventana NY AM tras sweep+FVG."

**Convergencia:** Las tres auditorías convergen en que los umbrales son excesivamente
estrictos, pero difieren en la causa:
- Forense:参数值太高 para H4
- Arquitectónica: 参数没有经过empirical validation
- R4 v2: El filtro es **estructuralmente incompatible** con Silver Bullet

**Decisión:** Es **calibrable** (clasificación C), pero con restricción ICT:

El displacement en ICT no es "cualquier vela grande". Es la **impulsión institucional**
post-sweep que crea el FVG. En H4, una vela de 1.5 ATR con wick < 40% es razonable
como definición de displacement institucional. El problema no es el valor per se,
sino que se aplica al **mismo TF** (H4) en vez de al TF de ejecución (M15).

**Recomendación:** Evaluar displacement en el TF de ejecución (M15), no en H4. Esto es
consistente con ICT: la displacement es la vela de entrada, no la vela HTF. Parámetros
`body_atr_multiple=1.5` y `wick_threshold=0.4` son razonables para M15; requieren
validación empírica en M15 antes de fijar.

---

### C3 — PO3 choch_status Mapping Bug [A — Bug]

**¿Qué dice R4 v2?** `build_features` crea `choch_signal`, pero `engine._build_estructura`
pasa `choch_status` (engine.py:251). Como `build_features` NO crea `choch_status`,
ese campo siempre es `""` → la fase D del PO3 solo se activa por `bos_dir`,
ignorando el CHOCH real.

**¿Qué dice la auditoría arquitectónica?** No lo cubre directamente (está en el path
de sequence, no en los 3 BOS/CHOCH de F2).

**Convergencia:** Bug conocido, documentado en R4 v2, parche propuesto pero NO aplicado.

**Decisión:** Bug (A). El fix es de bajo riesgo y alto impacto:

```python
# engine._build_estructura, línea ~251
"choch_status": str(row.get("choch_signal", row.get("choch_status", ""))),
```

**Recomendación:** Aplicar el fix y re-medir PO3. Esto es prerequisite para cualquier
conclusión sobre PO3.

---

### C4 — 3 Implementaciones BOS/CHOCH [A+B — Bug + Design Decision]

**¿Qué dice la auditoría arquitectónica?** F2: `bos.py`, `market_structure.py`, y
`displacement.py` tienen detecciones BOS/CHOCH independientes. `bos.py` y
`market_structure.py` divergen en lógica (threshold 0.0 vs 0.01, detección en
vs después de cierre).

**¿ qué dice R4 v2?** La desincronización `choch_signal` vs `choch_status` es
consecuencia directa de tener múltiples implementaciones.

**Convergencia:** F2 (arquitectónica) y R4 v2 (forense de PO3) convergen en que la
fragmentación causa bugs de mapeo.

**Decisión:** Clasificación dual:
- **A (Bug):** El mapping `choch_signal`→`choch_status` está roto. Fix inmediato.
- **B (Design):** Consolidar las 3 implementaciones en una. Requiere planificación
  pero no es urgente — el fix A resuelve el bug inmediato.

**Recomendación:** Fix A ahora. Consolidación B en Fase 1.

---

### C5 — ML train/serve Mismatch [A — Bug]

**¿Qué dice la auditoría arquitectónica?** F5: `ml/feature_engine.py` crea 30+ features,
`ict_backtest/features.py` crea 26. Solo 16 coinciden. El modelo ML entrena con un
set de features y sirve con otro.

**¿Qué dice la auditoría de uso?** `ml/` no está en la rutina diaria. Es código heredado.

**Convergencia:** F5 es un bug real, pero su impacto es bajo porque `ml/` no se usa
en producción (auditoría de uso). Solo importa si se reactiva el pipeline ML.

**Decisión:** Bug (A), pero **baja prioridad** porque no afecta el path productivo actual.

**Recomendación:** Documentar como Known Issue. No fixear hasta que se decida reactivar `ml/`.

---

### C6 — D1 Cargado, Nunca Usado [B — Design Decision]

**¿Qué dice la auditoría arquitectónica?** F1: `D1` se carga en `run_backtest.py:119`
y `_build_estructura`, pero ningún detector ni checklist lo consume.

**¿Qué dice el caveat de AGENTS.md?** "La tesis 18 exige 3 capas (HTF bias → ITF zona →
exec entry). D1 se carga pero NO se usa."

**Convergencia:** F1 y el caveat convergen. La decisión es estratégica: ¿se implementa
la 3-capas (D1→H4→M15) o se acepta 2-capas (H4→M15)?

**Decisión:** Design Decision (B). No es un bug — D1 está disponible pero no conectado.

**Recomendación:** Dejar para Fase 3 (Decisión Estratégica). La 3-capas es el camino
correcto ICT pero require:
1. Definir qué detector D1 provee (bias direction)
2. Conectar D1 al pipeline de sequence
3. Re-medir con 3 capas activas

---

### C7 — v2/ Sin Versionar [A — Bug de Proceso]

**¿Qué dice R6 v2?** `ict_backtest/v2/` existe en disco pero nunca fue commiteado.
`run_bt_v2_mtf.py` importa de ahí → desde un clon limpio, falla con ModuleNotFoundError.

**Convergencia:** Solo R6 v2 lo cubre. Es un bug de proceso, no de código.

**Decisión:** Bug (A). Fix: commitear `ict_backtest/v2/` completo.

**Recomendación:** Commitear antes de cualquier otra corrida de v2.

---

### C8 — edge_diagnosis Cap Rompe Ablación [A — Bug]

**¿Qué dice R6 v2?** `MAX_SIGNALS_PER_VARIANT=3000` corta por confianza descendente.
Para XAUUSD, 13/21 variantes devuelven exactamente los mismos números → el cap las
hace idénticas. La ablación no prueba nada.

**Convergenia:** Solo R6 v2.

**Decisión:** Bug (A). El cap invalida la ablación.

**Recomendación:** Cambiar el criterio de corte de "top-3000 por confianza" a
"ventana temporal fija" para que relajar un filtro realmente cambie el set de señales.

---

### C9 — Sin Corrección Múltiple [A — Bug]

**¿Qué dice R6 v2?** 21 variantes × 8 símbolos = 168 pruebas. No hay DSR/PBO.
`ml/stats_validator.py` tiene la función pero no se aplica.

**Convergencia:** Solo R6 v2.

**Decisión:** Bug (A). Sin corrección, cualquier "candidate edge" es potencialmente
ruido.

**Recomendación:** Aplicar DSR/PBO de `ml/stats_validator.py:83` a la grilla 168
antes de declarar edge.

---

### C10 — Edge Concentrado en XAUUSD [D — Strategy Restriction]

**¿Qué dice R6 v2?** `no_session` × XAUUSD = PF 1.376. Promedio 8 símbolos = 1.159.
AUDUSD 0.849, NZDUSD 0.809 (pierden).

**Convergencia:** Solo R6 v2.

**Decisión:** Strategy Restriction (D). Requiere decisión del usuario:
1. ¿Operar solo XAUUSD? (concentra riesgo)
2. ¿Excluir símbolos que pierden? (reduce diversificación)
3. ¿Buscar edge en otros símbolos con parameters ajustados?

**Recomendación:** Decidir después de Fase 0 y Fase 1, cuando los datos sean confiables.

---

### C13 — costs.py Calibra 3/8 Símbolos [C — Calibrable]

**¿Qué dice R6 v2?** `costs.py` calibra spread/comisión real para XAUUSD/EURUSD/GBPUSD.
Los otros 5 usan DEFAULT genérico.

**Convergencia:** Solo R6 v2.

**Decisión:** Calibrable (C). Bajo riesgo, media prioridad.

**Recomendación:** Calibrar costos de los 5 símbolos restantes antes de la corrida final.

---

## 3. ROADMAP — FASES DE EJECUCIÓN

Cada fase es **bloqueante** para la siguiente. No se salta una fase.

### Fase 0 — Corrección de Bugs Críticos [A]
**Objetivo:** Eliminar bugs que corrompen datos o producen resultados incorrectos.
**Prerequisito:** Ninguno.
**Criterio de salida:** Todos los bugs A corregidos y verificados con tests.

| # | Hallazgo | Fix | Archivos | Esfuerzo |
|---|----------|-----|----------|----------|
| C1 | Killzone-HTF mismatch | `killzone_en` recibe hora de sesión, no hora de barra | `canonical.py`, `rules.py` | Medio |
| C3 | PO3 choch_status mapping | Mapear `choch_signal` → `choch_status` | `engine.py` | Bajo |
| C7 | v2/ sin versionar | `git add ict_backtest/v2/` | `ict_backtest/v2/*` | Bajo |
| C8 | edge_diagnosis cap | Criterio de corte temporal, no por confianza | `edge_diagnosis/run.py` | Medio |
| C9 | Sin DSR/PBO en grilla | Aplicar `ml/stats_validator.py` a grilla 168 | `edge_diagnosis/run.py` | Bajo |

**NO incluido en Fase 0:** C5 (ML mismatch) — bajo impacto porque `ml/` no está en producción.

### Fase 1 — Consolidación Arquitectónica [B]
**Objetivo:** Reducir fragmentación sin cambiar comportamiento.
**Prerequisito:** Fase 0 completa.
**Criterio de salida:** Una implementación de BOS/CHOCH, D1 decidido (usar o remover).

| # | Hallazgo | Fix | Archivos | Esfuerzo |
|---|----------|-----|----------|----------|
| C4-B | Consolidar 3 BOS/CHOCH | Unificar en `market_structure.py` | `bos.py`, `market_structure.py`, `displacement.py`, `canonical.py` | Alto |
| C6 | D1 sin usar | Decisión: implementar 3-capas o remover D1 | `run_backtest.py`, `canonical.py` | Medio |
| C14 | signals/ legacy | Decisión: integrar o eliminar | `signals/*` | Medio |
| C15 | 64% código no usado | Etiquetar como "no activo" o eliminar | Varios | Medio |

### Fase 2 — Calibración con Restricciones ICT [C]
**Objetivo:** Ajustar parámetros dentro de los bounds que ICT/SB permiten.
**Prerequisito:** Fase 1 completa (para tener una arquitectura limpia que medir).
**Criterio de salida:** Parámetros validados empíricamente, documentados en `METRICS_CANON.md`.

| # | Hallazgo | Fix | Archivos | Esfuerzo |
|---|----------|-----|----------|----------|
| C2 | Displacement bottleneck | Evaluar en TF ejecución (M15), no H4. Validar `body_atr_multiple` y `wick_threshold` en M15 | `displacement.py`, `canonical.py` | Alto |
| C13 | costs.py 3/8 símbolos | Calibrar spread/comisión para AUDUSD, NZDUSD, USDCAD, USDCHF, USDJPY | `costs.py` | Bajo |

**Restricción ICT para C2:** El displacement debe继续保持 en M15 porque:
- ICT define displacement como "impulsión institucional en el TF de ejecución"
- Silver Bullet opera M1/M5 → displacement en M5/M15 es correcto
- En H4, displacement es "structure shift", no "impulsión de entrada"

### Fase 3 — Decisión Estratégica [D]
**Objetivo:** Responder preguntas que solo el usuario puede responder.
**Prerequisito:** Fase 2 completa (datos confiables para decidir).
**Criterio de salida:** Decisión documentada en ADR.

| # | Pregunta | Opciones | Dependencia |
|---|----------|----------|-------------|
| C10 | ¿XAUUSD? | (a) Operar solo XAUUSD, (b) Excluir perdedores, (c) Buscar edge en otros | Fase 0-2 |
| 3-capas | ¿D1→H4→M15? | (a) Implementar 3-capas, (b) Aceptar 2-capas | Fase 1 |
| Silver Bullet | ¿Sin displacement? | (a) SB sin filtro displacement, (b) SB con displacement calibrado en M15 | Fase 2 |

### Fase 4 — Validación Final
**Objetivo:** Confirmar que el stack completo produce resultados válidos.
**Prerequisito:** Fase 3 completa.
**Criterio de salida:** Corrida MTF completa con costos, DSR/PBO, y PF por símbolo.

| Paso | Descripción |
|------|-------------|
| 4.1 | Re-run forense del funnel después de Fase 0 (verificar que el conteo sube naturalmente) |
| 4.2 | Re-run R6 ablation completa después de Fase 1 |
| 4.3 | Walk-forward OOS sobre ≥4 años con datos completos |
| 4.4 | Reporte final con PF por símbolo, N, DSR, PBO |

---

## 4. HALLAZGOS SIN CRUZAR (Nuevos de esta Convergencia)

Estos hallazgos emergen del cruce de auditorías y NO estaban en ninguna individualmente:

### 4.1 — La Forense y la Arquitectónica no se superponen
La auditoría arquitectónica examinó **fragmentación de código** (3 BOS/CHOCH, ML mismatch,
código muerto). La forense examinó **el funnel de señales** (killzone, displacement). Son
dominios complementarios, no superpuestos. Esto significa que **ambas son necesarias y
ninguna es redundante**.

### 4.2 — El bottleneck real es una CASCADEA, no un solo filtro
Forense identificó 2 filtros (killzone + displacement). Pero hay al menos 4 filtros en
serie que reducen señales:

```
Raw signals (sweep detectado)
  → Killzone filter (78% killed)         [C1]
  → Displacement filter (90% killed)     [C2]
  → SL estructural (some killed)
  → Risk/reward filter (some killed)
  = Final signals (3-8 trades en 6 años)
```

**Fixear solo C1 o solo C2 no multiplica linealmente.** Si C1 pasa 22% y C2 pasa 10%,
el combo pasa 2.2%. Fixear C1 (killzone correcto) haría pasar ~100% × 10% = 10%.
Fixear C2 (displacement correcto) haría pasar 22% × ~50% = 11%. Fixear ambos:
100% × 50% = 50%. **Los filtros se multiplican, no se suman.**

### 4.3 — R4 v2 ya encontró las causas de Silver Bullet = 0
AUDIT_BUG_SILVER_TF y AUDIT_R4_V2_SENALES_PO3_SILVER documentaron que:
- Silver Bullet necesitaba M5/M1 data (no solo M15)
- El sweep M15 estaba hardcodeado (ya fixed)
- El displacement es incompatible con Silver Bullet

Esto NO está en la auditoría arquitectónica ni en la forense. Es contexto crítico que
debe informar la Fase 3.

### 4.4 — La auditoría de uso revela que 64% del repo es irrelevante
10,611 LOC de código "bot heredado" no están en la rutina diaria del operador.
Esto no es un bug, pero afecta la mantenibilidad y la capacidad de cualquier agente
de navegar el codebase. La Fase 1 debe decidir qué hacer con esto.

---

## 5. CONCLUSIÓN

**La situación NO es "el stack ICT no tiene edge".** La situación es:

1. **Bugs de mapeo** (C1, C3) están silenciando señales válidas
2. **Parámetros no calibrados** (C2) están filtrando demasiado
3. **Fragmentación** (C4) está causando bugs de mapeo y dificultando diagnóstico
4. **Proceso** (C7, C8, C9) está invalidando las conclusiones de backtest

**Ninguna de estas cosas significa que la estrategia ICT/Silver Bullet no funcione.**
Significa que el código que la representa tiene errores que impiden medirla correctamente.

**El camino correcto es:** Fix bugs → Consolidar → Calibrar → Decidir → Validar.

**El camino incorrecto es:** Cambiar parámetros para producir más trades sin entender
por qué los filtros actuales están mal.

---

*Generado por agente de convergencia — evidencia: 5 auditorías reconciliadas, código real,
funnel instrumentado, datos EURUSD/GBPUSD/XAUUSD.*

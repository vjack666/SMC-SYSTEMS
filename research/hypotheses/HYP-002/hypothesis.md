# HYP-002 — ¿El motor reconstruye de forma determinista la formación completa de un setup ICT/SMC?

> **Hipótesis de LECTURA (regla rectora §16, 2026-08-10).** Nace de la nueva dirección
> científica del laboratorio: el objetivo primario NO es demostrar edge por win rate, sino
> demostrar que el motor realmente LEE el mercado (forma el setup ICT/SMC correctamente)
> antes de medir rendimiento. NO es un experimento; es una AFIRMACIÓN a destruir.

## Pregunta científica

¿Cuando el motor emite un objeto SETUP ICT/SMC, es capaz de reconstruir físicamente — vela por
vela, con relación causal — toda la cadena de acontecimientos que llevó hasta ese setup, usando
solo los módulos del motor (`engine/`) y los datos del mercado?

Es decir: **¿el motor sabe QUÉ está viendo y puede explicarlo causalmente?** (regla fundamental
§16.3), no "¿ganó?".

## Tesis

El motor de SMC-SYSTEMS ya contiene la materia prima para una auditoría de formación de setup:
estructura, liquidez BSL/SSL, dealing range, premium/discount, POI anclado, secuencia
event-driven, sweep→displacement→BOS→retorno, memoria/reset, SL estructural, HTF closed-only,
y la arquitectura D1→H4→H1→M15. Por tanto, un setup emitido por el motor DEBE ser
reconstruible como la secuencia causal exigida por la tesis, no como una coincidencia de
eventos.

## Predicción cuantitativa

Sobre una muestra de setups emitidos por el motor (dominio REAL = datos del motor; FOREX =
backtest canónico como consumidor del motor):

- **Tasa de reconstrucción determinista** `R_recon`: fracción de setups donde CADA capa de la
  cadena (Contexto→Estructura→Liquidez→Evento→Displacement→BOS/CHOCH→POI→Retorno→Confirmación)
  puede reconstruirse con los datos brutos y el timestamp correcto, en el ORDEN causal exigido.
- Predicción (cualitativa por ahora): `R_recon` es ALTA y, cuando un setup NO se reconstruye,
  el fallo se localiza en una capa concreta (no es "ruido").

> **Umbral numérico NO fijado aún (decisión del Director, 2026-08-10).** No se fija `≥ 0.90`
> porque primero debe definirse el objeto "setup completo" (ver `SETUP_SPEC.md`). El número se
> fija SOLO después de que el objeto esté operable. Hasta entonces la predicción es cualitativa.

Si la predicción no se cumple (setups que el motor "ve" pero no puede explicar causalmente), la
tesis de LECTURA cae y se abre un diagnóstico de qué capa del motor falla.

## Variable primaria

- `R_recon` (tasa de reconstrucción determinista del setup completo).
- `capa_fallo` (cuando `R_recon < umbral`, qué capa de la cadena no se reconstruye: contexto /
  estructura / liquidez / evento / displacement / BOS-CHOCH / POI / retorno / confirmación).
- **NO** `WR` ni `PF` (esas son consecuencia posterior, §16.2 paso 6, no el objeto de estudio).

## Baseline

- `R_recon` de un "motor ciego" (emisión aleatoria de setups sin reconstrucción) ≈ 0 por
  construcción → cualquier reconstrucción causal real es superior al ruido.
- El baseline de comparación interna es la **coherencia de la propia cadena del motor**: un
  setup es válido solo si la secuencia causal se sostiene; no se compara contra un WR arbitrario.

## Criterio de falsación

HYP-002 queda REFUTADA si, sobre la muestra:

- `R_recon < umbral` (el motor emite setups que no puede reconstruir causalmente), O
- los fallos de reconstrucción NO se localizan en una capa concreta (son irreducibles → el
  motor no "lee", solo etiqueta).

No hay ajuste de narrativa: el veredicto lo dicta si la cadena causal se sostiene vela por vela.

## Dominio REAL / FOREX

- **REAL (descubrimiento)**: los setups emitidos por `engine/` sobre datos reales del motor
  (documentados en AGENTS.md Ley Fundamental y `docs/lab/LABORATORIO_ICT_SMC.md`).
- **FOREX (validación)**: el backtest canónico (`ict_backtest/run_backtest`) como consumidor
  PURO del motor, auditando setups que el motor marca como válidos.

## Marco de capas (qué significa "setup completo")

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

## Contexto macro como capa externa (no indicador)

Las noticias/eventos macro **NO son un indicador BUY/SELL** que "crea" el setup. Son una
**capa de contexto externo** que puede: explicar, invalidar, contextualizar o elevar la
calidad de la lectura. El sistema registra p.ej.: *"setup estructuralmente formado, pero
apareció evento macro de alta relevancia dentro de su ventana de ejecución"*. Eso es una
lectura más rica que `WIN=1`.

## Relación con HYP-001 (trazabilidad)

HYP-001 ("¿HTF aporta edge vía WR/PF?") se CONSERVA como artefacto histórico del paradigma
anterior, con `exp_001_blocked: true`. HYP-002 es la hipótesis rectora bajo la regla nueva:
primero demostrar que el motor FORMA correctamente el setup; el rendimiento (WR/PF) se estudia
solo tras validar esa lectura (cadena: LECTURA→FORMACIÓN→VALIDACIÓN CONTEXTO MACRO→SETUP
AUDITADO→recién entonces→PERFORMANCE).

## Decisión que permite

- **PROMOVIDA**: el motor reconstruye causalmente el setup → se valida la lectura; solo
  entonces se abre la rama de rendimiento (WR/PF sobre setups ya auditados).
- **REFUTADA**: el motor emite setups que no reconstruye → se diagnostica qué capa falla antes
  de cualquier prueba de rendimiento.
- **INCONCLUSIVA**: muestra insuficiente → nuevo EXP con más datos.

---

*Formulada 2026-08-10 como hipótesis de LECTURA bajo la regla rectora (RESEARCH_CONTRACT.md §16). Sin EXP, sin ejecución, sin tocar código.*
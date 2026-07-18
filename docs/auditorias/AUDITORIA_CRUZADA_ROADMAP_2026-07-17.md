AUDITORÍA CRUZADA DEL ROADMAP
===========================

Cruza tres fuentes vivas:
- Roadmap vigente: CRONOGRAMA_Y_ROADMAP.md (v2.5, "ÚNICA fuente de verdad"),
  IMPLEMENTATION_PLAN.md (ETAPA 3, orden por dependencia), ETAPA_4_BUGS.md,
  DECISION_LOG.md (DEC-001..008).
- Auditoría de validez del backtest: AUDITORIA_FINAL_COBERTURA_BACKTEST_2026-07-17.md
  (veredicto: ~30% del problema original resuelto).
- Auditoría de fidelidad a la tesis: AUDITORIA_FIDELIDAD_TESIS_ICT_2026-07-17.md
  (veredicto: ~65% fidelidad, PARCIAL).

Objetivo: no decir "está/no está", sino si cada deuda QUEDA CERRADA tras el roadmap.
Fecha: 2026-07-17. Modo: SOLO lectura cruzada de documentos + código ya leído.

=====================================================================
PARTE I — COBERTURA DE LA TESIS ICT (por componente)
=====================================================================

| Componente            | Existe deuda | Roadmap lo contempla | Etapa/Paso        | Forma de implementación                      | Resultado esperado        | Estado hoy |
|-----------------------|--------------|----------------------|-------------------|----------------------------------------------|---------------------------|------------|
| Narrativa HTF         | SÍ (htf_poi_fn OFF) | SÍ (PASO 5 CR-2) | ETAPA 4 PASO 5 | cablear htf_poi_fn + filtro zona/sesgo/respaldo | POI anclado activo        | ⚠ parcial (35%) |
| POI narrativo         | SÍ           | SÍ (PASO 5)          | ETAPA 4 PASO 5   | ancla a BOS/CHOCH HTF padre                  | C05 → implemented         | ⚠ parcial (35%) |
| PD Arrays jerárquicos | SÍ (sin tiers) | PARCIAL (no explícito en PASO 5) | ETAPA 4 PASO 5? | tier BPR>OB/FVG + stacking (21_POI §2/§3) | quality_score por tier    | ❌ ausente |
| Dealing Range         | NO           | ya hecho             | previo           | dealing_range_pd (context_mtf)               | EQ 50% operativo          | ✅ completo |
| Liquidity Sweep       | NO           | ya hecho             | previo           | canonical_sweep                              | cierra adentro            | ✅ completo |
| Displacement          | NO (existe, calibra) | ETAPA 7 calibrate | ETAPA 7     | displace_gap por experimento                 | umbral medido             | ✅ existe / ⚠ calibrar |
| Market Structure      | NO           | ya hecho (PASO 1)    | ETAPA 4 PASO 1   | canónico confirm_bars=2                      | fuente única              | ✅ completo |
| MSS / BOS             | NO           | ya hecho             | previo           | _has_bos/_has_choch canónico                 | secuencia OK              | ✅ completo |
| Silver Bullet         | SÍ (ausente) | SÍ (PASO 5)          | ETAPA 4 PASO 5   | módulo SB: NY 10-11/14-15 + retorno POI M15  | hay módulo SB             | ❌ ausente (15%) |
| OTE (62-79% retr.)    | SÍ (ausente) | NO (R3.5 libros 22/23, "opcional") | FUERA ETAPA 4 | no en plan de ejecución | — | ❌ ausente (0%) |
| Entry M5 (exec fino)  | SÍ (solo M15) | NO (3 capas con exec=M15) | FUERA ETAPA 4 | no contemplado | — | ❌ ausente (20%) |
| Confirmación M1        | SÍ           | NO                   | FUERA ETAPA 4   | no contemplado                               | —                         | ❌ ausente |
| Gestión activa        | SÍ           | NO                   | FUERA ETAPA 4   | no contemplado                               | —                         | ❌ ausente |
| Parciales             | SÍ           | NO                   | FUERA ETAPA 4   | no contemplado                               | —                         | ❌ ausente |
| Break Even            | SÍ           | NO                   | FUERA ETAPA 4   | no contemplado                               | —                         | ❌ ausente |
| Re-entry              | SÍ           | NO                   | FUERA ETAPA 4   | no contemplado                               | —                         | ❌ ausente |

Leyenda: ✅ completo · ⚠ parcial · ❌ ausente.

CONCLUSIÓN PARTE I:
El roadmap (ETAPA 4) cierra la MECÁNICA ESTRUCTURAL de la tesis (sweep, displacement,
BOS/CHOCH, structure, SL, TP, bias D1/H4/H1, killzone, dealing range, EQ, RR 1:3) y
ADICIONALMENTE contempla POI anclado + Silver Bullet (PASO 5). Cubre ~10 de 16
componentes de la lista del usuario. PERO omite sistemáticamente las capas FINAS de
CALIDAD/OPERACIÓN: OTE, exec M5/M1, BE, parciales, re-entry, gestión activa. Esas
deudas de fidelidad QUEDAN FUERA del roadmap vigente (OTE va a R3.5 "opcional";
M5/M1/BE/parciales ni siquiera se mencionan).

=====================================================================
PARTE II — ORDEN LÓGICO DEL ROADMAP
=====================================================================

El roadmap NO ordena por la secuencia de la tesis ICT. Ordena por CAUSA RAÍZ de
deuda de software (CR-1..CR-6). Eso es correcto para INGENIERÍA, pero hay que
verificar que no rompa dependencias de la tesis.

Orden de la tesis (modelo conceptual):
  Narrativa HTF → Dealing Range → PD Arrays → POI → Sweep → Displacement →
  MSS → Silver Bullet → OTE → Entry M5 → Confirm M1 → Trade Mgmt

Orden del roadmap (IMPLEMENTATION_PLAN ETAPA 3):
  CR-1 (BOS/CHOCH única verdad) → CR-6 (XAUUSD) → CR-3 (cap) →
  CR-4 (ML canónico) → CR-2 (POI+SB) → H16 (DSR/PBO) || CR-5 (tests)

¿Dependencia rota? Revisión nodo a nodo:
  - CR-1 ANTES de CR-4 (H17 necesita saber la verdad) → CORRECTO, documentado.
  - CR-3 ANTES de H16 (DSR/PBO sobre grilla válida) → CORRECTO, documentado.
  - CR-2 (POI+SB) AL FINAL de la corrección estructural → CORRECTO: POI necesita
    geometría única (CR-1 ya hecho). Coherente con la tesis (POI vive sobre
    estructura confirmada).
  - CR-6 (XAUUSD) como corolario de H14 (dato ya existe) → CORRECTO.

NO hay dependencia rota DENTRO de lo que el roadmap contempla. El "desorden" aparente
vs la tesis es intencional y válido: son dominios distintos (deuda de software vs
modelo conceptual). La única observación: PASO 5 (POI+SB) es "lo más profundo" pero
el roadmap lo trata como un commit más, sin reconocer que OTE/stacking/tiers son
prerequisitos de un POI REAL (21_POI §2/§3). Si PASO 5 se implementa SIN tiers ni
stacking, el POI queda "anclado pero plano" → fidelidad parcial, no completa.

VEREDICTO PARTE II: orden de INGENIERÍA correcto. Riesgo: PASO 5 podría entregar
POI anclado mínimo sin jerarquía (PD Arrays jerárquicos queda en ❌ aunque PASO 5
digas "POI hecho").

=====================================================================
PARTE III — DEPENDENCIAS OCULTAS
=====================================================================

Relaciones no documentadas explícitamente en el roadmap, detectadas por cruce:

  POI depende de Narrativa HTF.
      → CONOCIDA: PASO 5 lo contempla (ancla a BOS/CHOCH HTF). OK.

  Silver Bullet depende de POI.
      → IMPLÍCITA: SB opera "retorno a POI en M15" (tesis 21 §3). Si PASO 5 hace
        POI plano (sin tiers), SB hereda zona plana. Riesgo de fidelidad encadenada.

  OTE depende de Dealing Range.
      → NO CONTEMPLADA: OTE (retrace 62-79%) necesita el rango para medir el
        pullback. Dealing Range YA existe, pero OTE está fuera del roadmap → la
        infraestructura existe, la capa fina no se cablea.

  M1 depende de M5.
      → NO CONTEMPLADA: roadmap fija exec=M15. M5/M1 ni se mencionan en ETAPA 4.
        Sin M5 no hay exec fino ni SB de libro 07 (que es M15→M5/M1).

  ML depende del motor definitivo.
      → CONOCIDA: CR-4 tras CR-1. OK (canónico ya es la verdad tras PASO 1).

  DSR depende de una ablación válida.
      → CONOCIDA: H16 tras CR-3. OK.

  Trade Management (BE/parciales/re-entry) depende del motor de ejecución fina.
      → NO CONTEMPLADA: esas capas ni siquiera tienen hook en el pipeline actual
        (solo hold_limit). Están FUERA del roadmap en su totalidad.

DEPENDENCIAS OCULTAS CRÍTICAS (fuente de problemas futuros):
  1. SB → M5 (sin M5, SB es solo una ventana de killzone, no el setup de libro 07).
  2. POI → tiers/stacking (sin ellos, POI anclado es geometría con ancla pero sin
     jerarquía; la tesis 21 lo exige para "POI de alta probabilidad").
  3. OTE → Dealing Range (infra lista, capa fina ausente).

Estas tres NO están en el roadmap. Son las brechas de fidelidad que sobreviven al
roadmap.

=====================================================================
PARTE IV — ¿QUÉ MOTOR QUEDA AL FINAL?
====================================================================

Opción A: "Después del roadmap el motor sigue siendo una simplificación de ICT."
Opción B: "Después del roadmap el motor representa la tesis ICT con alta fidelidad."

RESPUESTA DEL COMITÉ: NI A NI B PURAS — es un GRADIENTE, y la dicotomía es
reduccionista. Pero si Ruben exige una letra, la más honesta es:

  → B MITIGADA (alta fidelidad estructural, simplificación operativa residual).

Justificación con evidencia:
  - Lo que el roadmap SÍ cierra (PASO 5 incluido): sweep→displace→BOS→retorno→
    SL estructural→TP liquidez→bias 3-capas→killzone→RR 1:3→POI anclado→Silver
    Bullet. Eso es la COLUMNA VERTEBRAL + las dos capas que faltaban para "ICT
    completo" en sentido amplio. Fidelidad pasaría de ~65% a ~85%.
  - Lo que el roadmap NO cierra: OTE, exec M5/M1, BE, parciales, re-entry,
    gestión activa, PD Arrays jerárquicos (tiers/stacking). Sin eso, un operador
    ICT diría "el motor opera el setup, pero no gestiona ni afina como yo".
  - Por tanto NO es A (no es una simplificación que contradiga la tesis: lo que
    implementa es FIEL). Pero TAMPOCO es B COMPLETA (faltan capas operativas que la
    tesis de libro 07/15/21 sí exige).

Conclusión: el roadmap entrega un motor que REPRESENTA ICT con alta fidelidad
estructural pero sigue siendo simplificación OPERATIVA. La deuda residual es de
CALIDAD FINCA, no de LÓGICA.

=====================================================================
PARTE V — COBERTURA FINAL (4 dimensiones)
=====================================================================

| Dimensión                         | Hoy (2026-07-17)        | Después del roadmap (ETAPA 4 + 7) |
| --------------------------------- | ----------------------- | --------------------------------- |
| Validez metodológica backtest     | ~30% (ablación rota, sin DSR/PBO, XAUUSD fuera, funnel mata 78-90%) | ~75% (cap válido + DSR/PBO + XAUUSD adentro + tests CI). NO 100%: sigue sin walk-forward OOS A12 (bloqueado por R4 sin edge). |
| Fidelidad a la tesis ICT          | ~65% (PARCIAL)          | ~85% (POI anclado + SB cableados; falta OTE/M5/M1/BE/parciales). |
| Calidad de ingeniería             | ~55 (motores duplicados, ML skew, tests timeout) | ~80 (fuente única BOS/CHOCH, ML canónico, CI verde, dead code fuera). |
| Preparación para producción       | BAJA (~40): R4 REJECT_NO_EDGE, sin ejecución real, sin live | BAJA-MEDIA (~55): motor honesto y reproducible, PERO R4 ya dijo ICT mecánico no tiene edge para fondeo; falta ejecución real/slippage/spread dinámico. |

Nota clave: "Preparación para producción" NO sube mucho aunque las otras 3 suban,
porque el roadmap NO aborda ejecución real (es explícitamente "observador sin bot",
principio 7 del cronograma: "Trader manda. No bot de órdenes hasta A12 + autorización").
Eso es una DECISIÓN, no un hueco accidental.

=====================================================================
PARTE VI — RIESGOS RESIDUALES (aunque el roadmap se complete 100%)
=====================================================================

Esto seguirá faltando aunque ETAPA 4 + 7 cierren todo lo planeado:

  EJECUCIÓN REAL (dominio no abordado por el roadmap):
    - Slippage real vs fill next_open simulado.
    - Spread dinámico (costos ON pero estáticos por símbolo; solo 3/8 calibrados).
    - Latencia de broker / rechazo de órdenes.
    - Ejecución parcial de la entrada.
    - Múltiples sesiones (London/NY overlap no modelado como tal).
    - Gestión de cartera / tamaño correlacionado entre activos.
    - Correlación entre pares (el runner MTF los trata independientes).

  MODELO CONCEPTUAL (deuda de fidelidad fuera del roadmap):
    - OTE (62-79% retrace) — R3.5 "opcional", no en ETAPA 4.
    - Exec fino M5/M1 y confirmación M1 — fuera del roadmap.
    - Break Even / parciales / re-entry / gestión activa — fuera del roadmap.
    - PD Arrays jerárquicos (tiers/stacking) — no explícito en PASO 5.
    - Silver Bullet real de libro 07 requiere M5 (ver PARTE III): sin M5, SB queda
      como sub-ventana de killzone, no el setup completo.

  PSICOLOGÍA DEL OPERADOR:
    - La tesis ICT (libros) incluye disciplina/timing humano. El motor es puramente
      mecánico; la "decisión ICT" del operador no es modelable por definición. Esto
      es aceptado en R4 (ICT mecánico SIN edge para fondeo).

VEREDICTO PARTE VI: el roadmap cierra la DEUDA DE SOFTWARE y la FIDELIDAD
ESTRUCTURAL, pero deja intacto el salto a PRODUCCIÓN REAL (ejecución/slippage/
spread) y las capas finas de operación ICT. Esos son riesgos residuales por diseño,
no por omisión.

=====================================================================
PARTE VII — EL RIESGO MÁS IMPORTANTE (alineación implementación ↔ tesis)
=====================================================================

La trampa que señalaste:
  "Optimizar la arquitectura del software sin cerrar la brecha con la tesis
   operativa." → código limpio + tests verdes + CI estable + arquitectura modular
   PERO motor tomando decisiones DISTINTAS a las de un operador ICT siguiendo la
   tesis.

¿Cae el roadmap en esa trampa? Análisis del comité:

  1. Señal A FAVOR de que NO cae: el cronograma (R4, línea 7) YA acepta
     explícitamente "ICT puro mecánico SIN edge para live/fondeo — REJECT_NO_EDGE".
     El repo lleva caveat en AGENTS.md. O sea: el roadmap NO confunde "arquitectura
     limpia" con "edge". Separó los conceptos.

  2. Señal DE ALERTA (la trampa al REVÉS): el GATE de éxito del cronograma (§5)
     sigue siendo PF ≥ 1.10 / Win Rate ≥ 52%. Si PASO 5 (POI+SB) se IMPLEMENTA y
     el backtest NO sube PF (porque R4 ya demostró que ICT mecánico no tiene edge
     automatizable), el riesgo es CONCLUIR ERRÓNEAMENTE "la tesis ICT no funciona"
     cuando en realidad el motor simplemente sigue sin ser operativo-ICT COMPLETO
     (falta OTE/M5/BE). Esa es la trampa disfrazada: medir fidelidad por PF.

  3. Deuda de MEDICIÓN: el roadmap tiene harness de tests, pero NO tiene un
     TEST DE FIDELIDAD (¿el motor toma las decisiones que tomaría un operador ICT
     siguiendo la tesis?). La auditoría de hoy (AUDITORIA_FIDELIDAD_...) es
     manual; no está cableada como gate de PASO 5. Sin eso, PASO 5 se acepta por
     "hay módulo SB + C05 implemented" (superficial) en vez de por "el motor ahora
     coincide con la tesis en X% más de casos" (profundo).

CONCLUSIÓN PARTE VII:
  El roadmap NO cae en la trampa clásica (arquitectura bonita ≠ tesis) porque ya la
  documentó y la acepta (R4 NO_EDGE). PERO corre el riesgo INVERSO y sutil: medir
  PASO 5 (el paso de fidelidad) por PF en lugar de por FIDELIDAD, y declarar la
  tesis "sin edge" cuando en realidad falta completar capas operativas.

MITIGACIÓN PROPUESTA (para que el roadmap cierre de verdad la brecha tesis):
  - Añadir al aceptar PASO 5 un GATE DE FIDELIDAD, no solo de PF: comparar el
    set de señales del motor contra las señales que marcaría un operador ICT
    siguiendo 20_TESIS_ICT.md + 21_POI.md en un subconjunto etiquetado a mano.
    Métrica: % de coincidencia de decisión (entry/SL/TP/dirección) por setup.
  - Separar en los reportes "fidelidad a la tesis" de "PF/edge" (ya lo hace la
    auditoría de hoy; el roadmap debe institucionalizarlo en el harness).
  - Explicitar en ETAPA_4_BUGS PASO 5 que OTE / tiers / stacking / M5 son
    prerequisitos de un POI+SB REAL, no adornos opcionales.

=====================================================================
VEREDICTO GLOBAL DE LA AUDITORÍA CRUZADA
=====================================================================

El roadmap vigente es ARQUITECTÓNICAMENTE SANO y ORDENA BIEN por dependencia.
Cierra la deuda de software y la fidelidad ESTRUCTURAL de la tesis (sweep→...→POI→
SB). PERO:

  1. Deja fuera del alcance las capas finas de operación ICT (OTE, M5/M1, BE,
     parciales, re-entry) → la deuda de fidelidad no se cierra 100%.
  2. No tiene un test de fidelidad cableado; mide PASO 5 por existencia de módulo
     y (peligrosamente) por PF → riesgo de trampa inversa.
  3. La "preparación para producción" no sube porque ejecución real está fuera del
     scope por decisión (observador sin bot).

Por tanto: el roadmap SÍ cierra las deudas de INGENIERÍA y las de FIDELIDAD
ESTRUCTURAL, pero NO cierra las deudas de FIDELIDAD OPERATIVA fina ni el salto a
producción real. La brecha tesis↔implementación queda reducida de ~65% a ~85% de
fidelidad, no eliminada.

Recomendación del comité (para decidir Ruben):
  - Agregar OTE + exec M5/M1 + tiers/stacking a PASO 5 (o a una ETAPA 4.5) si se
    quiere "B completa".
  - Cablear un test de fidelidad (no de PF) como gate de PASO 5.
  - No usar PF para aceptar/rechazar PASO 5 (R4 ya dijo que ICT mecánico no tiene
    edge; eso no debe interpretarse como "la tesis falló").

=====================================================================
FIN — Auditoría Cruzada del Roadmap (2026-07-17).
Cruce: CRONOGRAMA_Y_ROADMAP.md + IMPLEMENTATION_PLAN.md + ETAPA_4_BUGS.md +
DECISION_LOG.md + AUDITORIA_FINAL_COBERTURA_BACKTEST + AUDITORIA_FIDELIDAD_TESIS_ICT.

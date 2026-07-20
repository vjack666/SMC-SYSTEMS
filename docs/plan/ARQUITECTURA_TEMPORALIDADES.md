# Arquitectura Funcional de Temporalidades (SMC-SYSTEMS)

Contrato de diseño para la integración de H1 / M5 / M1 en el motor de
production. Describe **decisiones ya tomadas** (2026-07-19, con Ruben), no
puntos abiertos. Fuente de verdad complementaria: `BACKTEST_V2_SPEC.md`
(secciones 1.2, 1.3, 2) y `AGENTS.md` (CAVEAT R6).

## 1. Principio rector (define toda la jerarquía)

> Las temporalidades superiores definen el CONTEXTO del plan (sesgo D1/H4/H1,
> POI anclado, premium/discount); las inferiores validan/descartan la ejecución.
>
> ACLARACIÓN DE ALCANCE (2026-07-20, cierra contradicción con ETAPA_4_FASE_C_PLAN):
> En este doc, "plan" = el ESTADO DE MADUREZ del setup a través de las capas
> (NO_TRADE→CONTEXT_OK→ZONE_ARMED→SETUP_LIVE→STRUCTURE_OK→ENTRY_READY). El PlanFSM
> es la máquina que AVANZA ese estado de madurez y VETA la EJECUCIÓN (Opción B,
> A1 Nivel 2). NO es un segundo cerebro de DIRECCIÓN: la dirección la dicta el HTF
> como filtro top-down (libro 18 §0 #2; SPEC §1/§9) y la DECIDE el motor único
> (R7 = run_sequence). Ver contrato "un solo cerebro" en ETAPA_4_FASE_C_PLAN.md §1/§2.

El plan nace arriba (D1/H4/H1 aportan sesgo/zona). Nunca abajo (M15/M5/M1). Una capa
inferior puede descartar un setup concreto, pero no convierte un BUY en
SELL ni redefine el sesgo. Si M5 rechaza una entrada, el plan sigue
vigente hasta que una capa superior lo invalide. La dirección del setup la
fija el motor único R7 usando el filtro HTF; el PlanFSM solo certifica que
la cascada maduró.

## 2. FSM central basada en eventos

Cada temporalidad es un **emisor independiente** que analiza SOLO su
propio TF, genera `VerdictEvent` y NUNCA consulta directamente a otra
temporalidad. Un bus de eventos alimenta una `PlanFSM` central; la FSM
decide el estado y el backtest consume `ENTRY_READY`.

```
D1  ─┐
H4  ─┤
H1  ─┤
M15 ─┼──► Event Bus ─► PlanFSM ─► Backtest
M5  ─┤
M1  ─┘
```

- **Emisores por TF** (`emit_d1/emit_h4/emit_h1/emit_m15/emit_m5/emit_m1`):
  funciones puras que consumen SOLO los `MarketObject[]` de su TF
  (construidos vía `detect_market_structure` + `df_to_objects`, ya
  existentes) y devuelven un `VerdictEvent`. Cero referencia a frames de
  otros TF.
- **`VerdictEvent`**: `{layer, verdict, payload, bar_index, time}` donde
  `verdict ∈ {CONTEXT_OK, CONTEXT_INVALID, ZONE_ARMED, ZONE_INVALID,
  SETUP_LIVE, STRUCTURE_OK, ENTRY_READY}`.
- **`PlanFSM` central**: reductor puro `(state, event) -> (new_state,
  plan_update)`. Solo avanza cuando el evento del layer coincide con el
  gate esperado en ese estado. Cualquier `*_INVALID` devuelve a
  `NO_TRADE`.
- **Loop driver**: por cada barra del exec TF en `t`, se juntan barras
  cerradas ≤ `t` de cada TF (regla de reloj R4/R6: sin OHLC futuro,
  vía `closed_row_at_time`/`row_at_time`); se llama cada emisor una vez;
  los eventos se alimentan a `PlanFSM` en orden causal; al emitir
  `ENTRY_READY`, el simulador llena la orden.
- El emisor M15 internamente corre la sub-máquina que YA existe
  (`run_sequence`, `IDLE→SWEEP→DISPLACE→BOS→ENTRY`); queda como módulo
  de setup ya desacoplado (trabaja sobre `MarketObject[]`). No se toca.

Ventajas frente a "una FSM por TF que se consultan entre sí":
- Inversión de dependencia: los módulos TF dependen de la abstracción
  `VerdictEvent`; nadie conoce a nadie.
- El reloj causal anti look-ahead se impone UNA vez en la ingesta.
- Emisores y FSM son unit-testeables aislados (TDD).

## 3. Responsabilidad y autoridad por TF (matriz de decisión)

| TF  | Rol mental                     | Aporta contexto/dirección (filtro HTF) | Cancela setup | Ejecuta | Estado hoy        |
|-----|--------------------------------|----------------------------------------|---------------|---------|-------------------|
| D1  | Contexto macro / régimen       | ✅ (sesgo, filtro top-down SPEC §1)     | ✅            | ❌      | Cargado, no usa   |
| H4  | Bias + POI de contexto         | ✅ (sesgo, filtro top-down SPEC §1)     | ✅            | ❌      | Implementado      |
| H1  | Validación POI (ITF intradía)  | ✅ (zona, filtro top-down SPEC §1)      | ✅            | ❌      | Pendiente (v30)   |
| M15 | Setup ICT (sweep→disp→BOS)     | ❌ (el motor único R7 decide la dirección DENTRO del filtro HTF) | ✅ | ❌ | Implementado      |
| M5  | Refinamiento / exec SB          | ❌                                     | ✅            | ✅      | Pendiente (v30)   |
| M1  | Entry ultrafino (opcional)     | ❌                                     | solo trigger  | ✅      | Fuera flujo princ.|

> Nota de coherencia (2026-07-20): la columna "Crea/modifica plan" del diseño
> original se relee como "aporta contexto/dirección como FILTRO top-down" (libro 18
> §0 #2), NO como autoridad de decisión. El PLANFSM no es un 2do cerebro: la
> dirección la decide el motor único R7 usando el filtro HTF. Ver ETAPA_4_FASE_C_PLAN.md
> §1 "un solo cerebro. C es capa de CONTEXTO, no de decisión."

Notas:
- **H1**: emite `ZONE_ARMED` o `ZONE_INVALID`. Si INVALID, `PlanFSM`
  vuelve a `NO_TRADE`. H1 NO "manda" sobre H4: verifica si la hipótesis
  de H4 sigue viva (invalidación temprana).
- **M5**: filtra (micro-confirmación, mitigación) y ejecuta, PERO NO
  modifica el plan estratégico. Su cancelación es LOCAL a ese setup, no
  anula el sesgo H4.
- **M1**: módulo Silver Bullet Ultra especializado, FUERA del flujo
  principal (D1→H4→H1→M15→M5). El sistema principal termina en M5.

## 4. Orden de evaluación (FSM de plan)

```
NO_TRADE → CONTEXT_OK → ZONE_ARMED → SETUP_LIVE → STRUCTURE_OK
         → ENTRY_READY → IN_TRADE → CLOSED
```

| Desde       | Hacia        | Condición                              | Capa      |
|-------------|--------------|----------------------------------------|-----------|
| NO_TRADE    | CONTEXT_OK   | Bias D1/H4 usable; régimen operable    | D1+H4     |
| CONTEXT_OK  | ZONE_ARMED   | POI/zona alineada a bias y P/D         | H4+H1     |
| ZONE_ARMED  | SETUP_LIVE   | Sweep de liquidez opuesta al setup     | M15       |
| SETUP_LIVE  | STRUCTURE_OK | Displace + BOS/CHOCH según modelo      | M15       |
| STRUCTURE_OK| ENTRY_READY  | Mitigación en exec TF + gates sesión   | Exec (M5/M1) |
| ENTRY_READY | IN_TRADE     | Simulador llena Order                  | Sim       |
| *           | NO_TRADE     | Invalidación de plan                   | Multi-TF  |

Sin `CONTEXT_OK` y `ZONE_ARMED`, la sub-máquina M15 NO arma trades
(modo full). `legacy_subset=true` sigue permitiendo H4+M15 para
comparación R6.4.

## 5. Alcance

Este documento es el contrato para R4-tesis / v30 + R3.5 (brecha B POI
anclado + A1 tres capas reales). Queda FUERA del alcance de la
migración R7/R9 (unificación BOS/CHOCH/TREND en
`ict_backtest/market_structure.py`), ya validada funcionalmente por
diagnóstico por etapas (la secuencia H4→M15 vive). El backtest actual
solo evalúa la versión de 2 TF (H4→M15); los números de PF/WR/DD sobre
él NO juzgan la estrategia ICT completa (CAVEAT AGENTS.md).

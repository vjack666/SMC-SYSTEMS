# Roadmap por Capacidades (vista superpuesta)

Vista funcional del roadmap de SMC-SYSTEMS, superpuesta sobre la
numeración cronológica existente (R3.5 / R4 / R4-tesis/v30 / R6 / R7 /
R9). NO reemplaza los hitos R: conserva trazabilidad de commits,
auditorías y referencias cruzadas. Los hitos R siguen siendo la fuente
de verdad cronológica; esta vista los etiqueta por CAPACIDAD.

Decidido con Ruben el 2026-07-19. Complementa
`ARQUITECTURA_TEMPORALIDADES.md` (jerarquía y FSM) y `BACKTEST_V2_SPEC.md`
(secciones 1.2, 2).

## 1. Principio

El progreso se mide por CAPACIDADES FUNCIONALES, no por temporalidades.
Cada capacidad es un nivel de la FSM de plan (`BACKTEST_V2_SPEC.md` §2) y
tiene su propio benchmark y criterios de salida. No se mezcla arquitectura
con rendimiento: primero Plan, luego Setup, luego Ejecución, al final
Optimización.

```
NO_TRADE → CONTEXT_OK → ZONE_ARMED → SETUP_LIVE → STRUCTURE_OK
         → ENTRY_READY → IN_TRADE → CLOSED
```

- CONTEXT_OK + ZONE_ARMED  = Capacidad 1 (Plan)
- SETUP_LIVE + STRUCTURE_OK = Capacidad 2 (Setup)
- ENTRY_READY              = Capacidad 3 (Ejecución)
- Post-entry / M1          = Capacidad 4 (Optimización)

## 2. Las 4 capacidades y sus benchmarks

| # | Capacidad            | Pregunta que responde            | Benchmark de la fase            |
|---|----------------------|----------------------------------|---------------------------------|
| 1 | Arquitectura de Plan | ¿Existe un plan institucional?   | Concordancia con ICT del plan   |
| 2 | Arquitectura de Setup| ¿Apareció un setup válido?       | Conteo y calidad de setups      |
| 3 | Arquitectura de Ejecución | ¿Entrar o no entrar?         | PF / WR / DD / Expectancy       |
| 4 | Arquitectura de Optimización | ¿Mejora M1 vs M5?          | Delta estadístico vs M5         |

El backtest Legacy H4→M15 (Opción A) se conserva como benchmark de
regresión permanente de las Capacidades 2 y 3 (modo `legacy_subset=true`,
`BACKTEST_V2_SPEC.md` §3).

## 3. Matriz de doble entrada (Cronológica × Funcional)

| Tarea                 | R3.5 | R4/v30 | R6  | R7/R9 | Plan | Setup | Ejecución | Optimización | Estado       |
|-----------------------|------|--------|-----|-------|------|-------|-----------|--------------|--------------|
| POI anclado (brecha B)| ✅   |        |     |       | ✅   |       |           |              | Pendiente    |
| 3 capas reales (A1)   | ✅   |        |     |       | ✅   |       |           |              | Pendiente    |
| SMT / OTE / Breaker   | ✅   |        |     |       | ✅   |       |           |              | Pendiente    |
| H1 ITF (itf≠ltf)      |      | ✅      |     |       | ✅   |       |           |              | Pendiente    |
| Datos ≥3-4 años       |      | ✅      |     |       | ✅   |       |           |              | Pendiente    |
| run_sequence (M15)    |      |        | ✅   | ✅     |      | ✅     |           |              | Hecho        |
| Exec TF M5 (exec≠ltf) |      | ✅      |     |       |      |       | ✅         |              | Pendiente    |
| Killzones L/NY PM     |      | ✅      |     |       |      |       | ✅         |              | Pendiente    |
| M1 Silver Bullet fino |      |        |     |       |      |       |           | ✅            | Futuro       |

Estados según evidencia 2026-07-19:
- POI anclado / A1 / SMT-OTE-Breaker: `enable_pd_index=False` hoy
  (AGENTS.md CAVEAT); R3.5 abierto.
- H1 ITF: `exec_tf`/`itf` separados de `ltf` marcado ❌ en R4-tesis/v30
  (ROADMAP_BIBLIOTECA:160).
- run_sequence: migrado al canónico y validado por diagnóstico por etapas
  (la secuencia H4→M15 vive; `scripts/diag_etapas.py`).
- Exec TF M5 / Killzones: ítems ❌ R4-tesis/v30 (ROADMAP_BIBLIOTECA:160-162).
- M1: fuera de alcance R9/R7 y v30 (BACKTEST_V2_SPEC:120).

## 4. Criterios de salida (Exit Criteria) por capacidad

Cada capacidad se da por TERMINADA solo cuando cumple TODOS sus criterios
objetivos. "Compila" o "funciona técnicamente" NO alcanza.

### Capacidad 1 — Plan
- ✅ D1 genera contexto macro (régimen / P/D / liquidez).
- ✅ H4 genera bias y POI de contexto.
- ✅ H1 valida o invalida el POI (emite `ZONE_ARMED` o `ZONE_INVALID`).
- ✅ La FSM alcanza `ZONE_ARMED` de forma reproducible.
- ✅ Benchmark de concordancia con ICT supera el umbral definido
  (revisión manual de un sample de planes contra el libro 20 / 18).
- ✅ Sin look-ahead (regla de reloj R4/R6: solo barras cerradas ≤ t).

### Capacidad 2 — Setup
- ✅ `run_sequence` emite `SETUP_LIVE` y `STRUCTURE_OK` sobre MarketObject[].
- ✅ Los conteos de setups son consistentes (ni explosión ni 0 sistemático).
- ✅ Sin look-ahead en la sub-máquina M15.
- ✅ Pasa tests de regresión (modo Legacy H4→M15 como referencia).

### Capacidad 3 — Ejecución
- ✅ Produce `ENTRY_READY` con exec TF separado de ltf (M5).
- ✅ Calcula SL/TP correctamente en el exec TF (regla dura tesis 18).
- ✅ Ejecuta el backtest completo (Plan+Setup+Entry) con costos ON.
- ✅ Se obtiene un benchmark PF/WR/DD válido (post cierre de brecha B/A1
  y SMT/OTE/Breaker; NO sobre el motor 2TF).

### Capacidad 4 — Optimización (M1)
- ✅ M1 como módulo SB fino separado del flujo principal.
- ✅ Demuestra mejora estadísticamente significativa frente a M5 en al
  menos: Expectancy, PF, DD, R múltiple, coste operativo.
- ✅ Si NO mejora de forma consistente, M1 NO pasa el criterio de salida
  (aunque funcione técnicamente) y el sistema principal queda en M5.

## 5. Dependencias técnicas (no de temporalidad)

La FSM impone el orden de desbloqueo por CAPACIDAD:
- Capacidad 2 requiere Capacidad 1 (`ZONE_ARMED` es gate de SETUP_LIVE;
  BACKTEST_V2_SPEC:157).
- Capacidad 3 requiere Capacidad 2 (ENTRY_READY requiere STRUCTURE_OK).
- Capacidad 4 requiere Capacidad 3 (M1 necesita el pipeline M15→M5 armado).
- D1 se enciende en paralelo con H1 (ambos alimentan CONTEXT_OK/ZONE_ARMED).

Orden táctico de implementación: Plan (D1+H4+H1) → Setup (M15, ya hecho)
→ Ejecución (M5) → Optimización (M1).

## 6. Alcance

Vista de planificación para R3.5 / R4-tesis/v30 / R6. FUERA del alcance de
la migración R7/R9 (unificación BOS/CHOCH/TREND en
`ict_backtest/market_structure.py`), ya validada funcionalmente. El
backtest actual (H4→M15, 2 TF) NO representa la arquitectura completa y
sus números de PF/WR/DD NO juzgan la estrategia ICT final (CAVEAT
AGENTS.md).

Eres un agente autónomo de SMC-SYSTEMS. Tu rol es ejecutar tareas de forma ordenada, documentada y autónoma.

## ⚖️ LEY FUNDAMENTAL — MOTOR vs BACKTEST (leer antes de escribir CUALQUIER código)

> **El MOTOR es el reflejo de la TESIS hecho código.** El backtest existe SOLO para probar el motor.
> Nada del motor se escribe en el backtest. El backtest es la demostración de que el motor
> funciona como lo dicta la tesis — que a su vez es el reflejo del trabajo de un humano.
> Sin indicadores: matemática pura y geometría del mercado.

Obligatorio, en este orden:

1. **El motor (`engine/`) es la ÚNICA fuente de decisión.** Toda la lógica de la estrategia
   (bias, estructura, POI, ejecución) vive en el motor y se ejecuta para responder en vivo
   ("el bias de hoy", "qué opción de trading tengo hoy"). El motor es el reflejo de la tesis
   hecho código.
2. **El backtest NO tiene lógica propia.** Su único rol es el reloj vela a vela + llamar al
   motor y medir resultados. PROHIBIDO crear en el backtest cualquier módulo que sea decisión
   o detección (jamás un "detector de bias" en el backtest: eso va en el motor).
3. **El backtest es desechable.** Cuando el motor tenga todos sus módulos, el backtest se borra
   sin perder nada. Todo lo necesario para operar en vivo vive en el motor.
4. **El backtest demuestra la tesis.** El resultado del backtest debe demostrar que el motor
   funciona como dicta la tesis (el trabajo de un humano): SIN indicadores — matemática pura y
   geometría del mercado (estructura, liquidez, POI, rangos). Cualquier indicador/EMA/RSI/ATR
   en el motor es sospechoso y debe justificarse contra la tesis.
5. **Regla técnica derivada:** `engine/` nunca importa `ict_backtest/`. El backtest puede
   importar `engine/` (es su consumidor), nunca al revés.

Reglas obligatorias:
- Lee siempre README.md y COMPLETION_REPORT.md antes de tomar decisiones técnicas.
- Actualiza este opencode.json si agregas o movés archivos de configuración.
- Nunca modifiques código sin haber leído el contexto completo.
- Mantén todo versionado y sincronizado con Git.

### Procesos largos / Runner Monitor (OBLIGATORIO)

Umbral: **cualquier comando que pueda superar 60 segundos**.

**Cómo lanzar (Windows):**
```bat
python scripts\runner_monitor.py --window --title "NOMBRE" -- <comando>
```
Ejemplo:
```bat
python scripts\runner_monitor.py --window --title "build_bos_table" -- python scripts\build_bos_table.py
```

**Obligatorio:**
- Usar `scripts/runner_monitor.py` con **`--window`** para que el operador vea una **consola nueva** (no background oculto).
- **Una sola espera bloqueante** hasta el exit del proceso (el SO notifica el fin).
- Tras el exit: leer stdout/stderr + `results/runner_monitor_last.json` y analizar **una vez**.

**Prohibido:**
- Background silencioso / detached sin ventana visible.
- Polling en el chat cada N segundos (“sigo esperando…”, “vivo (73s)…”, “aún corre…”).
- Porcentajes de progreso inventados.
- Jobs < 60s: pueden ir en la terminal principal sin monitor.

**Recursos (laptop 16 GB / multi-core):**
- Workers ~70–80% de hilos (`HERMES_WORKERS`); no 100% CPU.
- Prioridad Windows: Above Normal (nunca High/Realtime).
- Si RAM del sistema ≥ 80%: bajar paralelismo.

**Multi-símbolo (backtest / ablation):**
- Se pueden correr **varios pares en paralelo** (ahorra wall-time) con **máx. 2 concurrentes por defecto** (3 solo si RAM estable).
- **Una ventana `--window` por símbolo**; outputs aislados por par.
- Repartir el presupuesto de workers entre jobs; no dar 75% de CPU a cada uno.
- Esperar el exit de **todos** los monitores del batch sin spam en el chat; luego agregar métricas.

Detalle: `docs/plan/RUNNER_MONITOR.md`

### Estado backtest R6 y CAVEAT CRÍTICO (2026-07-16)

**R6 (backtest profesional) está CERRADO en código:** G1 HTF closed-only ✅, G2 fill next-open ✅, G3 costs ON por defecto ✅ (código en `ict_backtest/`, commits 9fc5237/9990390/a59c2fb). Ablation honesta (`scripts/r6_ablation.py`) ya corrió en EURUSD/GBPUSD/USDCHF/USDCAD.

**Resultado R6.4 (modo producción = costos ON), motor sequence H4→M15, 8000 velas:**

| Símbolo | PF prod | WR | N |
|---------|--------:|----:|--:|
| EURUSD  | -4.89   | 38.9% | 18 |
| GBPUSD  | -7.07   | 40.0% | 30 |
| USDCHF  | -0.13   | 48.0% | 25 |
| USDCAD  | -8.64   | 36.8% | 38 |

GATE R6 NO PASA en ningún símbolo en producción. Números en `docs/METRICS_CANON.md` §0.

> ⚠️ **CAVEAT OBLIGATORIO para cualquier agente:** el PF negativo NO es evidencia de
> "la estrategia ICT no tiene edge". Es evidencia de que el motor backtesteado es una
> **VERSIÓN SIMPLIFICADA** de la estrategia objetivo (libros 18/21/08, Principios R10/R11).
> Auditoría 1:1 (2026-07-16) confirmó:
> - El motor usa SOLO 2 TF reales (H4→M15). **D1 se carga pero NO se usa**; H1/M5/M1 ausentes.
>   La tesis 18 exige 3 capas (HTF bias → ITF zona → exec entry). → AUSENTE.
> - **POI anclado a narrativa HTF DESACTIVADO** (`htf_poi_fn=None` en `run_backtest.py:119`).
>   El filtro más definitorio de ICT está muerto: cualquier FVG/OB cuenta como entrada sin
>   respaldo BOS/CHOCH del TF padre (libro 21: 100% sin ancla). → AUSENTE.
> - No hay dealing_range/premium-discount, ni stacking multi-TF, ni `po3_state` cableado al runner,
>   ni filtro de régimen, ni gestión post-entrada (solo hold_limit).
> - COMPLETO en el motor: secuencia event-driven (sweep→displace→BOS→retorno con memoria y reset),
>   SL estructural en mecha de sweep, fill next-open, costs ON, killzone, RR 1:3, HTF closed-only.
>
> Conclusión: antes de declarar "stack ICT intradía sin edge", falta cerrar la brecha B (POI
> anclado) y A1 (3 capas reales) — exactamente lo que el cronograma marca como R3.5 / Fase v30
> pendiente, FUERA del alcance de R6.

**Bloqueo real = DATOS (R5/A6), no motor:** los datos históricos deben descargarse/verificarse con el flujo definido en el repo.

**Regla commit/push (Ruben):** NO hacer commit ni push sin OK expreso. Los roadmaps
(`docs/plan/`) fueron PURGADOS intencionalmente (2026-08-03); la fuente de verdad vigente
es este AGENTS.md + `docs/tesis/` + `engine/`.

**Fuentes de verdad a leer antes de conclusiones de backtest:** `docs/tesis/SPEC_TESIS_FORMAL.md`,
`docs/tesis/TRUTH_SOURCES.md`, `engine/`, `feature/motor-ict`, `feature/backtest-ict`.

Tu prioridad es avanzar el proyecto de forma eficiente mientras mantienes la memoria del proyecto siempre actualizada.

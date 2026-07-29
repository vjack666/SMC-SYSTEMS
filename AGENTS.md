Eres un agente autónomo de SMC-SYSTEMS. Tu rol es ejecutar tareas de forma ordenada, documentada y autónoma.

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

Detalle: `docs/plan/RUNNER_MONITOR.md` · Backtest v2 ops: `docs/plan/BACKTEST_V2_SPEC.md` §15.

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

**R5/A6 DATOS (actualizado 2026-07-24 — NO repetir el mito "falta XAUUSD M15"):**
- `data/raw/XAUUSD_M15.parquet` **EXISTE** (~109k velas, **2022-01 → 2026-07 ≈ 4.5 años**).
- EURUSD M15 también ≥4.5 años. XAUUSD tiene los 6 TF (D1/H4/H1/M15/M5/M1). Fuente viva: `docs/DATA_STATUS.md`.
- **R5 (umbral datos ≥3–4 años M15 XAUUSD/EURUSD) = CERRADO a nivel de disco.**
- **A12 NO está bloqueado por falta de parquet.** Está **pendiente de re-run** walk-forward OOS
  (`no_session`×XAUUSD, celda top histórica PF 1.642) con motor limpio post-R4/R6 (costs ON, no look-ahead).
  El 1er pase A12 falló (PF ~-0.058, N baja) con datos/setup viejos — hay que re-medirlo, no "bajar el archivo".
- Caveats honestos: (1) M1/M5 de majors principales vienen de HistData+resample/merge, no solo MT5 demo;
  (2) scripts viejos tipo `run_bt_v2_mtf.py` aún **excluyen XAUUSD por hang del motor v2**, no por data ausente
  — eso es deuda de código/runner, no de descarga.
- Inventario canónico: `docs/DATA_STATUS.md`. No reabrir R5 por docs históricos de julio-10/17.

**Regla commit/push (Ruben):** NO hacer commit ni push sin OK expreso y con `docs/plan/CRONOGRAMA_Y_ROADMAP.md`
+ `docs/plan/ROADMAP_BIBLIOTECA_Y_APLICACION.md` al día en el mismo commit.

**Fuentes de verdad a leer antes de conclusiones de backtest:** `docs/METRICS_CANON.md` (números),
`docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`, `docs/ict/21_POI.md`, `docs/ict/08_POWER_OF_THREE.md`,
`docs/plan/PRINCIPIOS_ARQUITECTONICOS.md`, `docs/ict/13_BACKTEST_PROFESIONAL/`.

Tu prioridad es avanzar el proyecto de forma eficiente mientras mantienes la memoria del proyecto siempre actualizada.

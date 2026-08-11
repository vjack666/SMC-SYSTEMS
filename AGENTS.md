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

> **Backtest canónico (único):** `ict_backtest/run_backtest.run_sequence_backtest` y
> `ict_backtest/v2/orchestrator.run_sequence_parity`. Es consumidor PURO del motor: corre el
> reloj vela a vela y llama a `engine/sequence.run_sequence`. El motor ejerce la secuencia
> top-down D1→H4→H1→M15→M5→M1 vía `est_htf_ctx_fn` (`engine/plan.build_context_stack` +
> `top_down_allows_trade`). El backtest es adaptativo: crece con `engine/`.
> NO crear módulos de decisión/detección en `ict_backtest/`, ni buscar "backtest v2", ni usar
> `run_mtf_intraday` / `generate_mtf_signals` (fueron eliminados; ver
> `docs/DECISION_BACKTEST_UNICO.md`). Toda nueva lógica de estrategia va al MOTOR (`engine/`).

Reglas obligatorias:
- Lee siempre `README.md` (estado del repo) y `docs/specs/SDD_GOVERNANCE.md` (proceso SDD) antes de
  tomar decisiones técnicas. NO leas `COMPLETION_REPORT.md`: fue borrado de la raíz (ver §16).
- Actualiza `opencode.json` si agregas o movés archivos de configuración.
- Nunca modifiques código sin haber leído el contexto completo.
- Mantén todo versionado y sincronizado con Git.

### Procesos largos / Runner Monitor (OBLIGATORIO)

Umbral: **cualquier comando que pueda superar 60 segundos**.

```bat
python scripts\runner_monitor.py --window --title "NOMBRE" -- <comando>
```

- Usar `scripts/runner_monitor.py` con **`--window`** para que el operador vea una consola nueva.
- **Una sola espera bloqueante** hasta el exit del proceso.
- Tras el exit: leer stdout/stderr + `results/runner_monitor_last.json` y analizar **una vez**.
- Prohibido: background silencioso, polling en el chat, porcentajes inventados.
- Jobs < 60s: pueden ir en la terminal principal sin monitor.
- Recursos: Workers ~70–80% de hilos (`HERMES_WORKERS`); prioridad Above Normal. Si RAM ≥ 80%, bajar.

### Estado backtest R6 y CAVEAT (histórico, solo contexto)

**R6 (backtest profesional) CERRADO en código** (G1 HTF closed-only, G2 fill next-open, G3 costs ON).
Resultado R6.4 (costos ON, motor sequence H4→M15, 8000 velas): EURUSD PF -4.89/WR 38.9%,
GBPUSD -7.07/40.0%, USDCHF -0.13/48.0%, USDCAD -8.64/36.8%. GATE R6 NO PASA en producción
(números en `docs/METRICS_CANON.md` §0, **solo históricos**: previos al motor `engine/` actual).

> ⚠️ **CAVEAT OBLIGATORIO:** el PF negativo NO es evidencia de "la estrategia ICT no tiene edge".
> Es evidencia de que el motor backtesteado era una VERSIÓN SIMPLIFICADA de la estrategia
> objetivo. Las brechas B (POI anclado) y A1 (3 capas reales) YA ESTÁN CERRADAS en el MOTOR:
> - **3 capas reales CERRADAS**: `engine/plan.py` (`build_context_stack` + `top_down_allows_trade`),
>   lectura top-down D1→H4→H1→M15 con premium/discount y anti look-ahead por timestamp.
> - **POI anclado CERRADO**: `engine/poi_anchor.py` ancla POI a BOS/CHOCH del TF padre ya cerrado;
>   `engine/htf_narrative.py` marca `poi["anchored"]`. Consumido por `ict_backtest/canonical.py:42`.
> - `engine/dealing_range.py` (EQ 50% / premium-discount) y `engine/liquidity_levels.py`
>   (BSL/SSL) COMPLETOS.
> - COMPLETO en el motor: secuencia event-driven (sweep→displace→BOS→retorno con memoria y reset),
>   SL estructural en mecha de sweep, fill next-open, costs ON, killzone, RR 1:3, HTF closed-only.

**Bloqueo real = DATOS (R5/A6), no motor:** los datos históricos deben descargarse/verificarse con
el flujo definido en el repo.

**Regla commit/push (Ruben):** NO hacer commit ni push sin OK expreso.

### Fuentes de verdad (cadena de autoridad — ver `docs/specs/SDD_GOVERNANCE.md` §0)

1. **`AGENTS.md`** (este archivo) — Ley Fundamental, regla de commit/push. Constitución.
2. **`docs/ict/SPEC_TESIS_FORMAL.md`** — contrato formal firmado de la estrategia ICT/SMC
   (ruta real; NO está en `docs/tesis/`).
3. **`docs/DECISION_BACKTEST_UNICO.md`** — arquitectura de backtest vigente.
4. **`engine/`** — única fuente de decisión en vivo.
5. **`docs/specs/SDD_GOVERNANCE.md`** — proceso SDD (DoR/DoD/estados/verificación semántica).
6. **`docs/tesis/SDD_*.md`** — specs de diseño de estrategia (rescate POI, capa LTF).
7. **`docs/specs/INDICE_MDS.md`** — índice maestro de componentes del motor.
8. **`research/`** (HYP/EXP) — hipótesis/experimentos fuera del producto.

> NOTA: `docs/tesis/` contiene hallazgos + SDDs de diseño, NO la tesis formal. La tesis formal
> vive en `docs/ict/SPEC_TESIS_FORMAL.md`. No existe `docs/tesis/TRUTH_SOURCES.md` (fue eliminado
> del reset; su rol lo absorbió la cadena de autoridad arriba). Cualquier referencia a
> `docs/tesis/TRUTH_SOURCES.md` o a `docs/tesis/SPEC_TESIS_FORMAL.md` es ROTA.

### Gobernanza institucional (agentes adaptativos)

El organigrama de agentes de gobernanza vive en `agents/governance/`. Catálogo maestro:
`agents/governance/ROLES_GOBERNANZA.md`. Constitución del roster y enrutamiento:
`agents/governance/ORQUESTADOR.md`. Procedimiento obligatorio de todo agente:
`agents/governance/PROTOCOLO_AGENTE.md`. Disciplina de edición:
`agents/governance/CONTRATO_ORDEN.md`.

Roles permanentes: `investigador.md` (explora→hipótesis), `ingeniero.md`
(spec→implementación verificable), `auditor_independiente.md` (veto de PROMOCIÓN, mata hipótesis),
`memoria_institucional.md` (autoridad del registro), `cumplimiento_operativo.md`
(Ley Fundamental + secretos), `alertas_tempranas.md` (severidad INFO/WARNING/CRITICAL/BLOCKING).

> Los agentes de CÓDIGO que consumen el motor (`agents/ict_agent.py`, `wyckoff_agent.py`,
> `structure_agent.py`, `decision_agent.py`, `orchestrator.py`) son infraestructura de
> trading, distintos de los de gobernanza. No se pisan.

### §16 — DOCUMENTACIÓN HISTÓRICA / ELIMINADA (no reusar como fuente)

Para evitar que una sesión futura interprete docs obsoletos como instrucciones vigentes:

- **`COMPLETION_REPORT.md`**: BORRADO de la raíz. Sus copias supervivientes están en
  `docs/_descartado/` (NO fuente de verdad). No leerlo como estado actual.
- **`docs/plan/`**: PURGADO intencionalmente (2026-08-03). Cualquier referencia a
  `docs/plan/PROJECT_PROTOCOL.md`, `VISION.md`, `PRD.md`, `SRS.md`, `SAD.md`, `RUNNER_MONITOR.md`,
  `ROADMAP_*.md` apunta a archivos **eliminados**; los equivalentes históricos viven en
  `docs/planificacion/_roadmap_historico/` marcados como HISTÓRICOS. No resucitar `docs/plan/`.
- **`docs/CRONOGRAMA_Y_ROADMAP.md` / `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md`**: NO EXISTEN. El README
  los citaba erróneamente como "única fuente de verdad"; fueron corregidos en la Misión 1.
- **`harness/`**: contiene SOLO `harness/README.md` (describe un framework inexistente). No ejectar
  `python -m harness`; no aporta tests.
- **`opencode.json`**: sus 14 instrucciones originales apuntaban a `docs/plan/*` (eliminados).
  Fue depurado en la Misión 1 para referenciar solo fuentes vivas.
- **`scripts/r6_ablation.py`**: ruta real `scripts/_legacy/r6_ablation.py`.
- **`README.md`** describe el estado VIGENTE del repo (Forex/ICT-SMC, motor `engine/`); las
  secciones sobre el bot "SMC_SUCCESSOR" heredado (EMA/RSI/ATR, `paper_trading/`, `ml/` quality
  filter) están marcadas como HISTÓRICAS / no cableadas al flujo diario.

**Precedencia:** si dos documentos discrepan, manda la cadena de autoridad arriba (AGENTS.md →
tesis → DECISION_BACKTEST_UNICO → engine → SDD_GOVERNANCE → SDD diseño → INDICE_MDS). Un doc
marcado HISTÓRICO/OBSOLETO/_descartado NUNCA prevalece sobre un CURRENT.

### §17 — VERIFICACIÓN AUTOMÁTICA DE REFERENCIAS

`scripts/check_truth_sources.py` audita las referencias activas de `AGENTS.md`, `README.md`,
`opencode.json` contra el árbol real y falla si hay referencias rotas activas, referencias a
docs históricos como autoridad, o referencias a proyectos ajenos. Correrlo antes de declarar
cualquier misión de documentación CLOSED.

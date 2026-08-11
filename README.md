# SMC-SYSTEMS

> **⚠️ PROYECTO: FOREX / ICT-SMC (Sistema profesional de trading Forex).**
> SMC-SYSTEMS es un sistema de **Smart Money Concepts (ICT/SMC)** para Forex. NO es un bot de
> opciones binarias, NO es Quotex, NO es mercado OTC de binarias. Toda la lógica de decisión
> vive en `engine/` (geometría de mercado pura: OHLC, estructura, liquidez, POI — **CERO
> indicadores técnicos** EMA/RSI/ATR/MACD/Bollinger; única excepción: volumen como confirmación).
> El backtest (`ict_backtest/`) es consumidor puro y desechable del motor.
>
> **Modo actual: OBSERVADOR FUNDEDNEXT (SIN BOT).** El loop `scripts/loop_analisis.py` corre
> 24/7 (lun-vie) y genera ficha técnica + informe + semáforo + alertas. **NUNCA abre órdenes.**
> El `vigilante_riesgo.py` solo CIERRA posiciones (2%/4% flotante) si operás manualmente.

**Smart Money Concepts trading system** — modular, event-driven, motor de decisión ICT/SMC en
`engine/`, backtest adaptativo en `ict_backtest/`, observador de análisis para prop firm
(FundedNext) con app de escritorio PySide6, y biblioteca ICT (`docs/ict/`) como tesis formal.

---

## 📌 Fuente de verdad del proyecto

La autoridad del proyecto se determina por la **cadena de autoridad** (no por un solo archivo):

1. `AGENTS.md` (raíz) — Ley Fundamental motor≠backtest, regla de commit/push. **Constitución.**
2. `docs/ict/SPEC_TESIS_FORMAL.md` — contrato formal firmado de la estrategia ICT/SMC.
3. `docs/DECISION_BACKTEST_UNICO.md` — arquitectura de backtest (canónico único).
4. `engine/` — única fuente de decisión en vivo.
5. `docs/specs/SDD_GOVERNANCE.md` — proceso SDD (DoR/DoD/estados/verificación semántica).
6. `docs/tesis/SDD_*.md` — specs de diseño de estrategia.
7. `docs/specs/INDICE_MDS.md` — índice maestro de componentes del motor.
8. `research/` (HYP/EXP) — hipótesis/experimentos fuera del producto.

> ⚠️ **NO EXISTEN** `docs/CRONOGRAMA_Y_ROADMAP.md` ni `docs/HOJA_DE_RUTA_SMC-SYSTEMS.md`
> (fueron eliminados/purgados). Cualquier documento que los cite como "única fuente de verdad"
> está desactualizado. Los roadmaps históricos viven en `docs/planificacion/_roadmap_historico/`
> marcados como HISTÓRICOS (no fuente de verdad).

---

## Architecture (vigente)

```text
Datos (MT5 / Parquet histórico)
        │
        ▼
engine/  ← ÚNICA fuente de decisión (ICT/SMC, geometría pura, CERO indicadores)
  ├─ bias/        sesgo HTF D1/H4/H1 (premium-discount, anti look-ahead)
  ├─ bos/          estructura BOS/CHOCH real
  ├─ dealing_range.py   EQ 50% / premium-discount
  ├─ liquidity_levels.py  BSL/SSL (sweeps)
  ├─ poi_anchor.py        POI anclado a BOS/CHOCH del TF padre ya cerrado
  ├─ plan.py       build_context_stack + top_down_allows_trade (top-down D1→M1)
  ├─ sequence.py   run_sequence (event-driven: sweep→displace→BOS→retorno)
  ├─ execution.py  fine_execution M5/M1 (SL mecha sweep, RR 1:3)
  └─ trade_mgmt.py BE + parciales
        │  (el motor es la tesis hecha código; responde en vivo)
        ▼
ict_backtest/  ← Consumidor PURO y desechable (NO decide, NO detecta)
  ├─ run_backtest.run_sequence_backtest
  └─ v2/orchestrator.run_sequence_parity
        │
        ▼
app_observador/  ← UI PySide6 del observador FundedNext (semáforo, mapa ICT, black-box)
scripts/         ← loop_analisis.py, rutina_eurusd.py, vigilante_riesgo.py, runner_monitor.py
```

> El backtest NO tiene lógica propia y NO debe crearse en él ningún módulo de decisión/detección.
> `engine/` NUNCA importa `ict_backtest/`.

---

## Quick Start

### Prerequisites
- Python 3.11+ (entorno real usa `C:\Python314\python.exe` con MT5 real; venv `smc_probe` solo stub).
- PySide6 para la app del observador.

### Install
```bash
git clone https://github.com/vjack666/SMC-SYSTEMS.git
cd SMC-SYSTEMS
pip install -e .
```
Dependencias: `pandas`, `numpy`, `PySide6`, `MetaTrader5`, `scikit-learn`, `xgboost`, `pyarrow`,
`scipy`, `optuna`, `langgraph`.

### Rutina EURUSD (observador)
```bat
C:\Python314\python.exe scripts\rutina_eurusd.py          # ver ficha
C:\Python314\python.exe scripts\rutina_eurusd.py --save   # guardar al diario (docs/diario/)
```

### Run Observador UI
```bash
python app_observador/main.py
```
Ventana: semáforo FundedNext, sesgo + alineación D1/H4/M15, mapa ICT embebido, noticias rojas.

### Backtest (consumidor del motor, demostración de tesis)
```bat
python scripts\runner_monitor.py --window --title "bt_eurusd" -- python ict_backtest/run_backtest.py --symbol EURUSD --htf H4 --ltf M15
```

---

## Documentation

| Document | Authoridad | Descripción |
|----------|-----------|-------------|
| `AGENTS.md` | CURRENT | Ley Fundamental, regla commit/push, cadena de autoridad (§16) |
| `docs/ict/SPEC_TESIS_FORMAL.md` | CURRENT | Contrato formal firmado de la estrategia ICT/SMC |
| `docs/DECISION_BACKTEST_UNICO.md` | CURRENT | Arquitectura de backtest (canónico único) |
| `docs/specs/SDD_GOVERNANCE.md` | CURRENT | Proceso SDD (DoR/DoD/estados/verificación semántica) |
| `docs/specs/INDICE_MDS.md` | CURRENT | Índice maestro de componentes del motor |
| `docs/tesis/SDD_*.md` | CURRENT | Specs de diseño (rescate POI HTF, capa LTF) |
| `docs/architecture/RESEARCH_CONTRACT.md` | CURRENT | Contrato de investigación (HYP/EXP) |
| `docs/ict/00_INDICE.md` | CURRENT | Biblioteca ICT (libros 01–21) |
| `docs/specs/app_observador.md` | CURRENT | SDD de la UI del observador |
| `docs/METRICS_CANON.md` | HISTÓRICO | Números de backtest R6 (julio 2026, previos al motor `engine/`) |
| `docs/planificacion/_roadmap_historico/` | HISTÓRICO | Roadmaps y decisiones previas (marcados HISTÓRICO) |
| `docs/_descartado/` | DESCARTADO | Documentación de proyectos/historia no vigente |
| `openspec/` | HISTÓRICO | Línea base forense SDD-00 (2026-08-07, baseline 9842394) — no SDD vivo |
| `harness/` | OBSOLETO | Solo `README.md`; framework inexistente, no aporta tests |

---

## Running Tests

```bash
pytest tests/ -q
```

---

## ⚠️ SECCIONES HISTÓRICAS — BOT "SMC_SUCCESSOR" (NO VIGENTES)

Las secciones siguientes describen el proyecto **"SMC_SUCCESSOR"** original (bot scalping con
EMA/RSI/ATR, `paper_trading/`, `ml/` quality filter, MQL5 bridge). **NO están cableadas al flujo
diario actual** (modo observador) y **contradicen la Ley Fundamental de CERO INDICADORES** del
proyecto Forex/ICT-SMC vigente. Se conservan solo por trazabilidad histórica.

- `ml/` (XGBoost quality filter), `paper_trading/`, `signals/`, `integration/`, `MQL5/`,
  `risk/`, `features/`, `monitoring/`, `governance/` — módulos del bot heredado, no usados en
  modo observador.
- `detectors/` (BOS/CHOCH/FVG/OB) — del bot heredado; el motor vigente usa `engine/`.
- `bin/smc_trading.spec` — packaging del bot heredado.
- Cualquier mención de ATR filter, EMA/RSI, "live trading bot" — obsoleta para el proyecto actual.

> Para reactivar el bot se requiere una decisión explícita del Director y re-evaluación contra la
> Ley Fundamental (el motor `engine/` actual NO usa indicadores; un bot con EMA/RSI/ATR necesitaría
> justificación de tesis).

---

## Current Status (motor Forex/ICT-SMC)

| Componente | Estado |
|-----------|--------|
| Sesgo HTF (D1/H4/H1) | ✅ CERRADO (`engine/bias/`) |
| Estructura BOS/CHOCH real | ✅ CERRADO (`engine/bos/`) |
| Dealing Range / EQ / Prem-Disc | ✅ CERRADO (`engine/dealing_range.py`) |
| Liquidez BSL/SSL | ✅ CERRADO (`engine/liquidity_levels.py`) |
| POI anclado (PD arrays) | ✅ CERRADO (`engine/poi_anchor.py` + `zone_authority.py`) |
| 3 capas HTF/ITF/exec (top-down) | ✅ CERRADO (`engine/plan.py`) |
| Exec fino M5/M1 | ✅ CERRADO (`engine/execution.py`) |
| Trade Management BE/parciales | ✅ CERRADO (`engine/trade_mgmt.py`) |
| Secuencia event-driven + backtest canónico | ✅ CERRADO (`engine/sequence.py` + `ict_backtest/`) |
| Observador FundedNext (loop 24/7) | ✅ Producción |
| SDD governance | ✅ CERRADO (`docs/specs/SDD_GOVERNANCE.md`) |

**Bottom line:** el motor Forex/ICT-SMC es la fuente de decisión vigente (geometría pura, sin
indicadores). El backtest lo consume para demostrar la tesis. Las secciones del bot "SMC_SUCCESSOR"
son históricas y no cableadas al flujo diario.

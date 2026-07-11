# SRS — Software Requirements Specification

**Proyecto:** SMC-SYSTEMS
**Versión:** 1.0
**Fecha:** 2026-07-11
**Alcance:** Requisitos funcionales y no funcionales del sistema.

> Los requisitos funcionales (FR) mapean a las funcionalidades del PRD
> (F-xx). Los no funcionales (NFR) cubren performance, seguridad, calidad y
> operación. Todo requisito aquí listado está IMPLEMENTADO salvo que se marque
> [PENDIENTE].

---

## 1. Requisitos funcionales (FR)

### Observador
- **FR-01** (F-01): El loop debe generar ficha técnica EURUSD D1/H4/M15 cada
  ciclo, con sesgo + alineación Wyckoff, sin intervención manual.
- **FR-02** (F-02): La app PySide6 debe mostrar semáforo FundedNext, mapa ICT,
  noticias rojas y estado de procesos en una ventana refrescable.
- **FR-03** (F-03): El vigilante de riesgo debe CERRAR posiciones manuales al
  alcanzar 2% (o 4%) flotante; nunca debe abrir órdenes.
- **FR-04** (F-04): El arranque automático debe levantar MT5 + datos + loop +
  vigilante + observador en una sola acción desde la Carpeta de Inicio.

### Backtest ICT (`ict_backtest/`)
- **FR-10** (F-10): `detect_market_structure` debe clasificar trend/BOS/CHOCH/
  liquidity por TF SIN look-ahead (ventana no centrada, exposición diferida).
- **FR-11** (F-11): `run_sequence` debe ejecutar la secuencia ICT event-driven
  (sweep → displacement → BOS → retorno) vela a vela.
- **FR-12** (F-12): `simulate_trade` debe aceptar `cost={spread,commission,
  slippage}` (pips) y restarlos del resultado en unidades de riesgo (R).
- **FR-13** (F-13): `optimize.py` debe correr Optuna TPE y validar walk-forward
  ROLLING multi-fold con dirección temporal correcta (pasado→futuro).
- **FR-14** (F-14): `plot_equity_curve.py` debe graficar equidad acumulada + DD
  por trade en PNG.

### Calidad y trazabilidad
- **FR-20** (M-02): Todo PF reportado debe ser reproducible con los mismos
  parámetros y datos; los costos deben estar explícitos en el reporte.
- **FR-21** (M-03): Cada regla ICT en `docs/ict/` debe tener detector
  correspondiente y test que la fije.

---

## 2. Requisitos no funcionales (NFR)

### Performance
- **NFR-P1:** La carga de features para EURUSD H4/M15 (50k velas) debe tomar
  < 90s en la máquina de operación (medido: ~67s).
- **NFR-P2:** Una corrida de backtest Capa 2 completa (50k velas, 96 hold) debe
  completar en < 15 min (medido: ~10 min). [NOTA: el loop es vela-a-vela en
  Python puro, no vectorizado — hallazgo #6 de la auditoría, medio plazo.]
- **NFR-P3:** Los tests unitarios (`tests/test_ict_backtest.py`) deben correr
  en < 2s (datos sintéticos).

### Seguridad y riesgo
- **NFR-S1:** El sistema en modo observador NUNCA debe enviar órdenes a MT5.
  Solo el vigilante puede cerrar (y solo si Ruben opera manualmente).
- **NFR-S2:** Sin credenciales en el repo. `update_mt5_data.py` usa la cuenta
  logueada en el terminal; no hay secretos en código.
- **NFR-S3:** El risk governor debe bloquear entradas en estado LOCKDOWN.

### Calidad y mantenibilidad
- **NFR-Q1:** Sin look-ahead en ninguna variable derivada (principio rector P1).
- **NFR-Q2:** Tests deterministas con datos sintéticos para reglas; datos reales
  solo para corridas pesadas.
- **NFR-Q3:** Todo cambio de arquitectura/regla se documenta en `docs/ict/`.
- **NFR-Q4:** Cobertura de los módulos críticos (`market_structure`,
  `engine`, `optimize`) con al menos un test por regla rota.

### Operación / disponibilidad
- **NFR-O1:** El loop observador debe correr 24/7 lun-vie; finde off.
- **NFR-O2:** El launcher de optimización debe mostrar progreso + ETA y no
  cerrarse solo (PowerShell -NoExit + Tee-Object).
- **NFR-O3:** Ante caída del loop, debe haber reporte de salud al arrancar
  sesión.

### Reproducibilidad / auditoría
- **NFR-A1:** Toda corrida de backtest debe guardar log con params + métricas +
  commit SHA.
- **NFR-A2:** Walk-forward debe usar ≥ 3 folds contiguos (no 1 split) para
  declarar robustez.
- **NFR-A3:** El PF se reporta SIEMPRE con costos de mercado explícitos.

---

## 3. Restricciones
- **C-01:** Python 3.11+; MT5 solo compatible con `C:\Python314\python.exe`.
- **C-02:** Sin pip-install ni venv sin autorización explícita de Ruben.
- **C-03:** El launcher pesado lo corre Ruben con doble-clic; el agente solo
  construye tooling con barra + ETA, no lo ejecuta por él.
- **C-04:** Idioma del proyecto: español (respuestas y documentación).

---

## 4. Trazabilidad

| Requisito | PRD | Implementación | Test |
|-----------|-----|----------------|------|
| FR-10 | F-10 | `market_structure.py:detect_market_structure` | `test_swing_no_lookahead` |
| FR-11 | F-11 | `sequence.py:run_sequence` | (integración) |
| FR-12 | F-12 | `engine.py:simulate_trade` | `test_engine_spread_reduces_pnl`, `test_engine_sl_before_tp_on_tie` |
| FR-13 | F-13 | `optimize.py:_split_windows` | `test_walkforward_multi_fold`, `test_walkforward_no_inverted` |
| FR-20 | M-02 | `run_backtest.py` + logs | manual |
| NFR-Q1 | P1 | `market_structure._swing_points` | `test_swing_no_lookahead` |
| NFR-A2 | P3 | `optimize._split_windows` | `test_walkforward_multi_fold` |

---

## 5. Supuestos
- **A-01:** Los datos en `data/raw/` están actualizados y son correctos.
- **A-02:** Ruben opera manualmente fuera del loop cuando usa el vigilante.
- **A-03:** La arquitectura observador (no bot) se mantiene hasta nueva orden.

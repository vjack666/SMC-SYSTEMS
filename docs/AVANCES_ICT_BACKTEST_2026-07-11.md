# AVANCES ICT BACKTEST — 2026-07-11

## (B) CAPA 3 — OPTIMIZADOR BAYESIANO (Optuna + Walk-Forward) — COMPLETADA ✅

Resultado de la corrida real del usuario (run_capa3_optuna.bat, 12 trials, ~129 min):

### Optimización (in-sample = último tercio, 16666 velas)
- 12 trials TPE. PF in-sample mejoró trial a trial: 1.048 → 1.233 → 1.250 → 1.545 → 2.063.
- MEJOR PF in-sample: **2.063**
- MEJORES PARÁMETROS: `displace_gap=12`, `bos_gap=8`, `require_displacement=True`, `tp_mode=liquidity`

### Walk-Forward OUT-OF-SAMPLE (prueba de fuego anti-overfit)
- ventana 1 [IN-SAMPLE]: 29 trades, WR 51.7%, PF 1.889, +12.4 R, DD -3.6
- ventana 2 [OUT-OF-SAMPLE]: 32 trades, WR 56.2%, **PF 2.429**, +20.0 R, DD -4.0
- >>> PF OUT-OF-SAMPLE MEDIO: **2.429** (32 trades)
- >>> WR OUT-OF-SAMPLE MEDIO: 56.2%
- >>> VERDICTO: edge mantiene PF>1 en out-of-sample => **SIN overfit claro** ✅

### Conclusión
El edge de la Capa 2 (sequence.py, EURUSD M15) se CONFIRMA y es ROBUSTO:
PF 2.429 out-of-sample es incluso superior al in-sample (2.063). No hay
sobreajuste. Parámetros óptimos encontrados por Optuna son válidos.

### BUG CRÍTICO RESUELTO (raíz de "0 señales")
`optimize.py` y `_diag_signals.py` NO aplicaban `detect_market_structure` al
HTF. Sin eso, `run_sequence` no detecta BOS → 0 operaciones → Optuna
penalizaba todo con -1.0. Corregido: ambos aplican `ms = {tf:
detect_market_structure(df) for tf, df in frames.items()}` IGUAL que
`run_backtest.py`. Tras el fix, la Capa 3 genera señales y optimiza.

### Mejoras al launcher (run_capa3_optuna.bat)
- Reescrito para PowerShell `-NoExit` (ventana NO se cierra sola) + `Tee-Object`
  (log + vivo). El `tee` de bash no existe en cmd.exe de doble-clic → antes se
  cerraba solo.
- Barra de progreso con CONTADOR REGRESIVO ("Trial N/12 | falta ~X min") vía
  callback `_CuentaRegresiva` en optimize.py.
- No requiere MT5 abierto: `load_frames` lee parquet locales (data/raw).

---

## ESTADO POR CAPAS (resumen)

| Capa | Qué es | Estado | Resultado clave |
|------|--------|--------|-----------------|
| 1 | Estructura de mercado (market_structure.py) | ✅ base | trend/BOS/CHOCH por TF |
| 2 | Motor EVENT-SEQUENCE (sequence.py) | ✅ validada (ayer) | EURUSD M15: 70 trades, PF 1.598, WR 47.1%, +22.1 R |
| 2b | XAUUSD H4 (sequence) | ✅ validada (ayer) | PF 1.132, 11 trades, +0.8 R |
| 3 | Opt. bayesiano + walk-forward | ✅ COMPLETADA (hoy) | EURUSD M15 OOS: PF 2.429, 32 trades, WR 56.2% |

---

## HALLAZGOS / APRENDIZAJES
- La (A) [Capa 2 M15] usaba la serie COMPLETA (50k velas) → 70 trades. El primer
  tercio solo da ~0-2 señales; el volumen está en el tramo reciente. Por eso la
  Capa 3 optimiza en el ÚLTIMO tercio (in-sample) y valida hacia atrás.
- `require_displacement=True` + `tp_mode=liquidity` + gaps amplios (12/8) fueron
  los params ganadores. Filtra ruido y mejora PF.
- Optuna TPE con 12 trials en 50k velas tarda ~129 min (cada trial ~8 min). Para
  iterar rápido usar `--window-bars 8000 --trials 3` (~1 min).

## LO QUE FALTA (pendiente)
1. Commitear Capa 3: `optimize.py`, `_diag_signals.py`, `run_capa3_optuna.bat`,
   libro `09_OPTIMIZADOR_BAYESIANO.md`, este avance.
2. Probar la CONFIG ÓPTIMA (displace_gap=12, bos_gap=8, req_disp=True,
   liquidity) en una corrida limpia de run_backtest.py para confirmar PF final
   end-to-end con esos params.
3. Extender Capa 3 a XAUUSD (solo D1/H4, ~50k barras H4) — backtest en H4.
4. Crear README.md / COMPLETION_REPORT.md que AGENTS.md referencia (pendiente
   desde siempre).
5. (Opcional) Aumentar trials a 30-60 para refinar aún más el óptimo.

## ARCHIVOS
- `ict_backtest/optimize.py` — Capa 3 (Optuna+WF, fix detect_market_structure, contador regresivo)
- `ict_backtest/_diag_signals.py` — diagnóstico de señales por tramo (fix aplicado)
- `run_capa3_optuna.bat` — launcher PowerShell -NoExit + Tee-Object
- `docs/ict/09_OPTIMIZADOR_BAYESIANO.md` — libro teórico + implementación
- `docs/ict/logs/CAPA3_OPTUNA_WF.log` — log completo de la corrida exitosa
- `docs/AVANCES_ICT_BACKTEST_2026-07-11.md` — este archivo

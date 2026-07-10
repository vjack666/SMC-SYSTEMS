# Estado Actual — Edge Diagnosis SMC-SYSTEMS

**Fecha:** 2026-07-10
**Estado:** PENDIENTE un último paso en Windows (Ruben reinició la PC).

## Qué estamos haciendo
Medir el **edge puro del stack de detectores SMC** (ICT/Wyckoff) sin ML ni agentes,
con el gobernador de riesgo neutralizado. Matriz de **21 variantes × 8 símbolos = 168 celdas**.
El reporte vive en `docs/EDGE_DIAGNOSIS_REPORT.md`.

## Qué logramos hasta ahora
1. Reporte generado con 5 símbolos completos (EURUSD, AUDUSD, NZDUSD, USDCAD, XAUUSD).
2. **Descargada la data multi-año de los 3 símbolos cortos** que faltaban
   (GBPUSD, USDCHF, USDJPY — ~99.400 barras M15 cada uno, 2022→2026).
3. **Arreglado el bloqueo de MT5**: el venv `smc_probe` tenía un `sitecustomize.py`
   que inyectaba un stub de `MetaTrader5` (para pytest offline) y mataba la conexión
   real. Se renombró a `sitecustomize.disabled.py` y MT5 conecta (login 10011586708).
4. Herramientas de diagnóstico y accesos directos (`.bat`) creados.

## Hallazgo clave del edge (del reporte actual)
- Mejor variante: `no_session` (OOS PF 1.126 promedio).
- Mejor símbolo: **XAUUSD OOS PF 1.376**; luego USDCAD 1.264, EURUSD 1.162.
- AUDUSD (0.849) y NZDUSD (0.809) PIERDEN — el stack se invierte ahí.
- Celda TOP: `no_session` × XAUUSD → **OOS PF 1.642, N=900, Sharpe 3.28**.
- Filtro `prox_*` (proximidad OB/FVG) DESTRUYE el edge (peores PF).

## QUÉ FALTA (el paso pendiente)
El `run_edge_diagnosis.bat` hace **resume** y como `full_results.json` ya tenía 168/168
(reporte viejo con los cortos en 0), SKIPeó todo. Los 3 cortos siguen "insufficient".

**Al volver, correr (doble clic):**
```
C:\Users\v_jac\Desktop\SMC-SYSTEMS\reset_and_run_cortos.bat
```
Ese `.bat`:
- Borra `results/edge_diagnosis/_ctx/{GBPUSD,USDCHF,USDJPY}.pkl`
- Quita las celdas de esos 3 del `full_results.json`
- Corre el harness → rebuild del contexto desde los parquets frescos y recalcula las 63 celdas.

Cuando termine, el reporte tendrá los **8 símbolos completos**.

## Próximo objetivo (después de recalcular)
Validar **walk-forward OOS** de `no_session` × XAUUSD (PF 1.642) antes de cualquier
automatización live — PurgedKFold, DSR>0, ≥200 trades, PF>=1.10.

## Notas técnicas (no olvidar)
- El harness lee de `_ctx/*.pkl`, NO de los parquets crudos. Cambiar parquets no basta.
- MT5 real: `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe` (la carpeta
  `C:\Program Files\MetaTrader 5\` es un decoy, no usarla).
- `run_edge_diagnosis.bat` usó `C:\Python314\python.exe` (tiene MT5 real); funciona.
- Regla dura: NO tocar `signals/pipeline.py`.

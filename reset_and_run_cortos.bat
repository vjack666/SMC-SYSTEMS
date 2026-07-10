@echo off
REM Reset de los 3 simbolos cortos y re-corrida del harness.
REM Borra _ctx/*.pkl de los cortos y sus celdas en full_results.json,
REM asi el harness rebuild del contexto desde los parquets frescos y recalcula.
setlocal
cd /d "%~dp0"

set "PY=C:\Python314\python.exe"
if not exist "%PY%" set "PY=C:\Users\v_jac\smc_probe\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "SMC_MT5_TERMINAL=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
echo MT5 path: %SMC_MT5_TERMINAL%
echo.

echo Borrando _ctx de GBPUSD/USDCHF/USDJPY...
if exist "results\edge_diagnosis\_ctx\GBPUSD.pkl" del /q "results\edge_diagnosis\_ctx\GBPUSD.pkl"
if exist "results\edge_diagnosis\_ctx\USDCHF.pkl" del /q "results\edge_diagnosis\_ctx\USDCHF.pkl"
if exist "results\edge_diagnosis\_ctx\USDJPY.pkl" del /q "results\edge_diagnosis\_ctx\USDJPY.pkl"
for %%s in (GBPUSD USDCHF USDJPY) do (
  for %%v in (prox_1 prox_2 prox_3 mc_1 mc_3 mc_4 w0_sweep w0_ote) do (
    if exist "results\edge_diagnosis\_ctx\%%s__%%v.pkl" del /q "results\edge_diagnosis\_ctx\%%s__%%v.pkl"
  )
)
echo Listo.
echo.

echo Quitando celdas de los 3 cortos de full_results.json...
"%PY%" -c "import json,pathlib; p=pathlib.Path('results/edge_diagnosis/full_results.json'); d=json.load(p.open()); antes=len(d); d=[r for r in d if r.get('symbol') not in ('GBPUSD','USDCHF','USDJPY')]; json.dump(d,p.open('w')); print('celdas:',antes,'->',len(d),'(quitadas',antes-len(d),')')"
echo.

echo Corriendo harness (rebuild contexto de los cortos desde parquets frescos)...
"%PY%" -u scripts\edge_diagnosis\run.py --all
set "RC=%ERRORLEVEL%"
echo.
echo RC=%RC%
if %RC%==0 (echo OK: reporte en docs/EDGE_DIAGNOSIS_REPORT.md) else (echo FALLO)
echo.
pause

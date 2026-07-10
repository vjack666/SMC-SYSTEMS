@echo off
REM Precacha el contexto de los 3 simbolos cortos CON los datos ya descargados.
REM (el harness lee de _ctx/*.pkl, no de los parquets crudos; hay que rebuild)
setlocal
cd /d "%~dp0"
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\v_jac\smc_probe\Scripts\python.exe" set "PY=C:\Users\v_jac\smc_probe\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY set "PY=python"

set "SMC_MT5_TERMINAL=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
echo Precachando GBPUSD USDCHF USDJPY (lee parquets frescos)...
echo.
"%PY%" -u scripts\edge_diagnosis\_precache.py --symbol GBPUSD USDCHF USDJPY
echo.
echo Listo. Ahora corre run_edge_diagnosis.bat para el panorama completo.
echo.
pause

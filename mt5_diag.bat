@echo off
REM Diagnostico MT5: dice si el terminal esta conectado y logueado.
REM Doble clic. No descarga nada. Abre el resultado solo al terminar.
setlocal
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\v_jac\smc_probe\Scripts\python.exe" set "PY=C:\Users\v_jac\smc_probe\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY set "PY=python"

set "SMC_MT5_TERMINAL=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
echo MT5 path: %SMC_MT5_TERMINAL%
echo Corriendo diagnostico... (no se cierra, abre el resultado al final)
echo.

"%PY%" -u scripts\mt5_diag.py > mt5_diag_result.txt 2>&1

echo.
echo ===================================================
echo  RESULTADO en: %~dp0mt5_diag_result.txt
echo ===================================================
start "" "mt5_diag_result.txt"
echo (se abrio el archivo; si no, abrilo manualmente)
ping -n 2 127.0.0.1 >nul

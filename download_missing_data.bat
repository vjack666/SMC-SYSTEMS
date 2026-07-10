@echo off
REM ============================================================
REM  DESCARGAR DATA FALTANTE (GBPUSD / USDCHF / USDJPY)
REM  Requiere: MetaTrader 5 ABIERTO y LOGUEADO.
REM  Borra los parquets vacios (500 barras) y baja multi-anio.
REM  Al terminar, correr run_edge_diagnosis.bat para el panorama.
REM ============================================================
setlocal
cd /d "%~dp0"

title SMC-SYSTEMS — Download missing data

echo.
echo  ========================================================
echo   DESCARGAR DATA DE GBPUSD / USDCHF / USDJPY
echo  ========================================================
echo   REQUISITO: MetaTrader 5 abierto y logueado.
echo   (sino, el script falla con "cannot unpack NoneType")
echo.

REM Prefer project venv if present, else python on PATH.
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\v_jac\smc_probe\Scripts\python.exe" set "PY=C:\Users\v_jac\smc_probe\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY set "PY=python"

echo  Using: %PY%
echo.

REM Ruta real de tu MetaTrader 5 (el conector la lee de SMC_MT5_TERMINAL).
REM La ruta hardcodeada en _data_legacy.py apunta a "FundedNext MT5 Terminal" que no existe.
set "SMC_MT5_TERMINAL=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
echo  MT5 path: %SMC_MT5_TERMINAL%
echo.

REM Borrar parquets vacios (500 barras) para que el download no los salte.
echo  Borrando parquets cortos (GBPUSD/USDCHF/USDJPY M15/H4/D1)...
del /q data\raw\GBPUSD_M15.parquet data\raw\GBPUSD_H4.parquet data\raw\GBPUSD_D1.parquet 2>nul
del /q data\raw\USDCHF_M15.parquet data\raw\USDCHF_H4.parquet data\raw\USDCHF_D1.parquet 2>nul
del /q data\raw\USDJPY_M15.parquet data\raw\USDJPY_H4.parquet data\raw\USDJPY_D1.parquet 2>nul
echo  Listo.
echo.

echo  Descargando multi-anio (4 anos, M15/H4/D1)...
"%PY%" -u scripts\download_multiyear.py --symbols GBPUSD USDCHF USDJPY --years 4 --timeframes M15 H4 D1 --output data\raw
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo  DESCARGA OK. Ahora precachea contexto y corre el panorama:
  echo    scripts\edge_diagnosis\status_edge.bat  (medidor)
  echo    run_edge_diagnosis.bat                  (harness completo 21x8)
) else (
  echo  FALLO (RC=%RC%). ¿MetaTrader 5 abierto y logueado?
)
echo.
pause

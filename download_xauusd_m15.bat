@echo off
REM =====================================================================
REM  A6 - Bajar 4 anos de XAUUSD M15 (MT5 de FundedNext)
REM
REM  IMPORTANTE: antes de dar doble-clic, ABRI MetaTrader 5 de FundedNext
REM  y ENTRA a tu cuenta (que diga "Conectado" arriba a la derecha).
REM  Este script usa el terminal de FundedNext por defecto.
REM
REM  El XAUUSD_M15 actual se borra y se reemplaza por 4 anos completos
REM  (el script salta archivos existentes, por eso se borra primero).
REM =====================================================================

SETLOCAL ENABLEDELAYEDEXPANSION
SET ROOT=%~dp0

IF EXIST "C:\Python314\python.exe" (SET PY=C:\Python314\python.exe) ELSE (SET PY=python)

echo.
echo  ============================================================
echo   A6 - Descarga 4 anos XAUUSD M15 (MT5 FundedNext)
echo  ============================================================
echo.
echo   Verificando Python...
"%PY%" --version
IF ERRORLEVEL 1 (
    echo   ERROR: no se encontro Python.
    pause
    EXIT /B 1
)

echo.
echo   ATENCION: necesitas MT5 de FundedNext ABIERTO y LOGUEADO.
echo   (El XAUUSD_M15 actual se borrara y se bajaran 4 anos frescos)
echo.
echo   Presiona una tecla para continuar o CIERRA esta ventana para cancelar.
pause

REM Borrar el M15 actual para forzar re-descarga de 4 anos completos
IF EXIST "%ROOT%data\raw\XAUUSD_M15.parquet" (
    echo   Borrando XAUUSD_M15.parquet actual...
    del "%ROOT%data\raw\XAUUSD_M15.parquet"
)

echo.
echo   Lanzando descarga en ventana propia (no muere al cerrar esta)...
echo.

REM start "" abre en ventana independiente; el script corre hasta terminar.
start "" "%PY%" "%ROOT%scripts\download_multiyear.py" --symbols XAUUSD --timeframes M15 --years 4 --output data/raw

echo   La descarga corre en su propia ventana. Espera a que diga "Done".
echo   Luego podes re-correr run_validation.bat (A12) para la prueba de fuego.
echo   Presiona una tecla para cerrar esta ventana (la descarga sigue sola).
pause
ENDLOCAL

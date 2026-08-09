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
REM
REM  La salida (y cualquier error) se guarda en download_m15.log
REM  y la ventana ESPERA a que apretes ENTER, asi no se cierra sola.
REM =====================================================================

SETLOCAL ENABLEDELAYEDEXPANSION
SET ROOT=%~dp0
SET LOG=%ROOT%download_m15.log

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
echo   Lanzando descarga... (log en %LOG%)
echo   La ventana se queda abierta hasta que apretes ENTER, aunque falle.
echo.

REM Ejecuta el Python y guarda TODO (stdout + stderr) en el log.
"%PY%" "%ROOT%scripts\download_multiyear.py" --symbols XAUUSD --timeframes M15 --years 4 --output data/raw > "%LOG%" 2>&1
SET RC=%ERRORLEVEL%

echo.
IF %RC%==0 (
    echo   DESCARGA OK. Revisa el final de %LOG%
) ELSE (
    echo   FALLO (codigo %RC%). El error completo esta en:
    echo     %LOG%
)
echo.
echo   Presiona ENTER para cerrar.
pause
ENDLOCAL

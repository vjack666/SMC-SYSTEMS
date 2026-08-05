@echo off
REM Launcher Fase 0 — EURUSD A'' (POI HTF ACTIVO). Doble clic.
REM Backtest event-driven + POI HTF activado. Barra de progreso viva.
title SMC-SYSTEMS Fase0 EURUSD A'' (POI HTF)
cd /d "C:\Users\v_jac\Desktop\SMC-SYSTEMS"
"C:\Python314\python.exe" scripts\fase0_one.py EURUSD poi
if errorlevel 1 (
    echo.
    echo [!] El proceso termino con error (posible OOM del host al cargar frames).
    echo     Revisa /tmp/fase0_one_tb.log si existe.
)
echo.
echo [listo] Presiona una tecla para cerrar...
pause >nul

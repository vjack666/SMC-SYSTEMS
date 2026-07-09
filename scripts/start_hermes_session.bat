@echo off
REM Arranque de sesion SMC-SYSTEMS para Hermes.
REM 1) Abre el terminal MT5 de FundedNext (si no esta corriendo).
REM 2) Actualiza data/raw con datos EN VIVO (lo primero que hace Hermes).
REM Reusa scripts/update_mt5_data.py (NO recrea logica de descarga).
REM Usa el Python del sistema (C:\Python314) que tiene MetaTrader5 real.

cd /d "%~dp0.."

echo [Hermes] Abriendo MT5 FundedNext y actualizando datos...
"C:\Python314\python.exe" scripts\update_mt5_data.py --symbols EURUSD --tfs D1,H4,M15
if errorlevel 1 (
    echo [Hermes] ADVERTENCIA: no se pudo actualizar la data. Revisa que el terminal FundedNext este logueado.
)

echo [Hermes] Datos listos. Podes correr la rutina:
echo   C:\Python314\python.exe scripts\rutina_eurusd.py

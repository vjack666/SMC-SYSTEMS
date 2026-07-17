@echo off
REM Hermes Runner Monitor launcher (Windows).
REM Usage:
REM   scripts\run_with_monitor.bat --title "pytest" -- pytest -q
REM   scripts\run_with_monitor.bat --window --title "backtest" -- python ict_backtest\run_backtest.py --symbol XAUUSD

setlocal
cd /d "%~dp0\.."
if exist "C:\Python314\python.exe" (
  "C:\Python314\python.exe" scripts\runner_monitor.py %*
) else (
  python scripts\runner_monitor.py %*
)
exit /b %ERRORLEVEL%

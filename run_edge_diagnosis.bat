@echo off
REM ============================================================
REM  EDGE DIAGNOSIS — double-click to run the full ablation harness
REM  Shows a live progress bar + ETA. Resumes if interrupted.
REM  When finished writes:
REM    results\edge_diagnosis\progress.json
REM    results\edge_diagnosis\EDGE_DIAGNOSIS_REPORT.md
REM ============================================================
setlocal
cd /d "%~dp0"

title SMC-SYSTEMS — Edge Diagnosis

echo.
echo  ========================================================
echo   SMC-SYSTEMS  -  EDGE DIAGNOSIS
echo  ========================================================
echo   Variants x symbols ablation (detectors only, no ML).
echo   Progress file : results\edge_diagnosis\progress.json
echo   Final report  : results\edge_diagnosis\EDGE_DIAGNOSIS_REPORT.md
echo.
echo   To check progress from another window:
echo     check_edge_progress.bat
echo  ========================================================
echo.

REM Prefer project venv if present, else python on PATH, else common installs.
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY set "PY=python"

echo  Using: %PY%
echo  Started at %DATE% %TIME%
echo.

REM Ruta real de tu MetaTrader 5 (el conector la lee de SMC_MT5_TERMINAL).
set "SMC_MT5_TERMINAL=C:\Program Files\FundedNext MT5 Terminal\terminal64.exe"
echo  MT5 path: %SMC_MT5_TERMINAL%
echo.

"%PY%" -u "scripts\edge_diagnosis\run.py" --all
set "RC=%ERRORLEVEL%"

echo.
if exist "results\edge_diagnosis\EDGE_DIAGNOSIS_REPORT.md" (
  echo  Report ready:
  echo    %CD%\results\edge_diagnosis\EDGE_DIAGNOSIS_REPORT.md
  echo.
  echo  Opening report...
  start "" "results\edge_diagnosis\EDGE_DIAGNOSIS_REPORT.md"
) else (
  echo  WARNING: report MD was not created. Check errors above.
)

echo.
if "%RC%"=="0" (
  echo  Finished OK. Press any key to close.
) else (
  echo  Finished with exit code %RC%. Press any key to close.
)
pause >nul
endlocal
exit /b %RC%

@echo off
REM Quick status of a running (or finished) edge diagnosis job.
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY set "PY=python"

echo.
"%PY%" -u "scripts\edge_diagnosis\run.py" --status
echo.
if exist "results\edge_diagnosis\progress.json" (
  echo  Raw file: results\edge_diagnosis\progress.json
)
pause

@echo off
cd /d "%~dp0.."
start "SMC Trading System" pythonw scripts\run_desktop.py
echo Desktop UI launched in separate process.
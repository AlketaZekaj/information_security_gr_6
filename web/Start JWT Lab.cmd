@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" web\server.py --open
) else (
    python web\server.py --open
)
if errorlevel 1 pause

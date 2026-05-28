@echo off
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\python\python.exe"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ROOT%\scripts\win_stop_services.py"
echo BoneMet stopped. You can start again with install-and-run.bat
if /i not "%~1"=="silent" timeout /t 3 >nul

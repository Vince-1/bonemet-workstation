@echo off
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\python\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ROOT%\scripts\win_uninstall.py" %*
set "RC=%ERRORLEVEL%"
if %RC% neq 0 if /i not "%~1"=="/SILENT" pause
exit /b %RC%

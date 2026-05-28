@echo off
cd /d "%~dp0\.."
set "ROOT=%CD%"
if not defined BONEMET_PORT set "BONEMET_PORT=1012"
set "BONEMET_AGGRESSIVE_STOP=0"
set "PY=%ROOT%\python\python.exe"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%ROOT%\data\logs" mkdir "%ROOT%\data\logs"
echo %BONEMET_PORT%>"%ROOT%\data\logs\bonemet.port"
echo [%date% %time%] api start >>"%ROOT%\data\logs\api.log"
if exist "%ROOT%\bin\bonemet-api.exe" (
  "%ROOT%\bin\bonemet-api.exe" >>"%ROOT%\data\logs\api.log" 2>&1
) else (
  "%PY%" "%ROOT%\scripts\win_launch_api.py" >>"%ROOT%\data\logs\api.log" 2>&1
)
set "EC=%ERRORLEVEL%"
echo [%date% %time%] api exit %EC% >>"%ROOT%\data\logs\api.log"
if %EC% neq 0 (
  echo.
  echo API failed. Last lines of api.log:
  powershell -NoProfile -Command "Get-Content -Path '%ROOT%\data\logs\api.log' -Tail 12"
  echo.
  pause
)

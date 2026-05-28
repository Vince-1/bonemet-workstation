@echo off
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\python\python.exe"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%ROOT%\data\logs" mkdir "%ROOT%\data\logs"
echo [%date% %time%] worker start >>"%ROOT%\data\logs\worker.log"
if exist "%ROOT%\bin\bonemet-worker.exe" (
  "%ROOT%\bin\bonemet-worker.exe" >>"%ROOT%\data\logs\worker.log" 2>&1
) else (
  "%PY%" "%ROOT%\scripts\win_launch_worker.py" >>"%ROOT%\data\logs\worker.log" 2>&1
)
echo [%date% %time%] worker exit %ERRORLEVEL% >>"%ROOT%\data\logs\worker.log"

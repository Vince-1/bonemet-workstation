@echo off
setlocal
cd /d "%~dp0.."
set ROOT=%CD%

if exist ".venv\Scripts\python.exe" (
  set PY=%ROOT%\.venv\Scripts\python.exe
) else if defined BONEMET_PYTHON (
  set PY=%BONEMET_PYTHON%
) else (
  set PY=python
)

set PYTHONPATH=%ROOT%\packages;%ROOT%
if not defined BONEMET_DATA_ROOT set BONEMET_DATA_ROOT=%ROOT%\data
set PORT=8080
set URL=http://127.0.0.1:%PORT%/

if not exist "apps\web\dist\index.html" (
  echo 前端未构建，请先运行 scripts\install-desktop.bat
  pause
  exit /b 1
)

if not exist "config\local.yaml" copy config\default.example.yaml config\local.yaml

echo BoneMet Workstation
echo   地址: %URL%
echo   关闭本窗口即停止服务
echo.

start "BoneMet Worker" /MIN cmd /c "set PYTHONPATH=%PYTHONPATH%&& set BONEMET_DATA_ROOT=%BONEMET_DATA_ROOT%&& "%PY%" -m apps.worker.main"
timeout /t 2 /nobreak >nul
start "" "%URL%"
"%PY%" -m uvicorn apps.api.main:app --host 127.0.0.1 --port %PORT%

endlocal

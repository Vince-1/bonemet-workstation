@echo off
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "MARKER=%ROOT%\.bonemet_installed"
set "LOG_DIR=%ROOT%\data\logs"
set "BUNDLED_PY=%ROOT%\python\python.exe"
rem Default 1012: avoid common dev ports (8080/8081).
if not defined BONEMET_PORT set "BONEMET_PORT=1012"
set "PORT=%BONEMET_PORT%"
echo BoneMet will use port %PORT%  (override: set BONEMET_PORT=XXXX)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if exist "%BUNDLED_PY%" (
  set "PY=%BUNDLED_PY%"
) else if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PY=%ROOT%\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

if not exist "%MARKER%" goto do_install

rem --- Already installed: ask whether to reinstall ---
if defined BONEMET_FORCE_INSTALL goto do_install
if defined BONEMET_SKIP_INSTALL goto start_services

echo.
echo ========================================
echo   BoneMet - environment already installed
echo ========================================
echo   Skip reinstall and start directly, or run pip install again.
echo.
choice /C SN /M "Press S to Start only, N to Reinstall"
if errorlevel 2 goto do_install
goto start_services

:do_install
echo.
echo ========================================
echo   BoneMet Workstation - install dependencies
echo ========================================
echo   Internet required, about 10-30 minutes.
echo   Progress: %LOG_DIR%\install.log
echo.

if not exist "%PY%" (
  echo ERROR: Python not found.
  pause
  exit /b 1
)

if not exist "apps\web\dist\index.html" (
  echo ERROR: missing apps\web\dist\index.html
  pause
  exit /b 1
)

echo [%date% %time%] install start >"%LOG_DIR%\install.log"

if exist "%BUNDLED_PY%" (
  if exist "%ROOT%\python\get-pip.py" (
    "%PY%" "%ROOT%\python\get-pip.py" --no-warn-script-location >>"%LOG_DIR%\install.log" 2>&1
    if errorlevel 1 goto install_failed
  )
  "%PY%" -m pip install -U pip >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 goto install_failed
  "%PY%" -m pip install -U "numpy<2.0" >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -m pip uninstall -y onnxruntime onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -m pip install -U "onnxruntime-gpu<1.17" >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 "%PY%" -m pip install -U onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -c "import onnxruntime as ort; print('onnx providers:', ort.get_available_providers()); import sys; sys.exit(0 if 'CUDAExecutionProvider' in ort.get_available_providers() else 1)" >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 (
    echo ONNXRuntime GPU not available, falling back to CPU>>"%LOG_DIR%\install.log"
    "%PY%" -m pip uninstall -y onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
    "%PY%" -m pip install -U onnxruntime >>"%LOG_DIR%\install.log" 2>&1
  )
  "%PY%" -m pip install -r requirements.txt >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 goto install_failed
) else (
  if not exist "%ROOT%\.venv\Scripts\python.exe" (
    py -3 -m venv .venv 2>nul
    if not exist "%ROOT%\.venv\Scripts\python.exe" python -m venv .venv
    set "PY=%ROOT%\.venv\Scripts\python.exe"
  )
  "%PY%" -m pip install -U pip >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 goto install_failed
  "%PY%" -m pip install -U "numpy<2.0" >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -m pip uninstall -y onnxruntime onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -m pip install -U "onnxruntime-gpu<1.17" >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 "%PY%" -m pip install -U onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
  "%PY%" -c "import onnxruntime as ort; print('onnx providers:', ort.get_available_providers()); import sys; sys.exit(0 if 'CUDAExecutionProvider' in ort.get_available_providers() else 1)" >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 (
    echo ONNXRuntime GPU not available, falling back to CPU>>"%LOG_DIR%\install.log"
    "%PY%" -m pip uninstall -y onnxruntime-gpu >>"%LOG_DIR%\install.log" 2>&1
    "%PY%" -m pip install -U onnxruntime >>"%LOG_DIR%\install.log" 2>&1
  )
  "%PY%" -m pip install -r requirements.txt >>"%LOG_DIR%\install.log" 2>&1
  if errorlevel 1 goto install_failed
)

"%PY%" "%ROOT%\scripts\win_post_install.py" >>"%LOG_DIR%\install.log" 2>&1
"%PY%" "%ROOT%\scripts\win_check_env.py" >>"%LOG_DIR%\install.log" 2>&1
if errorlevel 1 goto install_failed

if not exist "config\local.yaml" copy /Y config\default.example.yaml config\local.yaml
echo installed>"%MARKER%"
echo Install OK. See %LOG_DIR%\install.log
echo.
goto start_services

:install_failed
echo.
echo ERROR: install failed. Open %LOG_DIR%\install.log
echo Common causes: no network, blocked pip, missing VC++ runtime.
pause
exit /b 1

:start_services
if not exist "config\local.yaml" copy /Y config\default.example.yaml config\local.yaml

"%PY%" "%ROOT%\scripts\win_health_check.py" >nul 2>&1
if not errorlevel 1 (
  echo BoneMet is already running on port %PORT%.
  goto api_ready
)

echo Stopping any previous BoneMet instance...
call "%ROOT%\scripts\stop-bonemet.bat" silent
ping -n 2 127.0.0.1 >nul

"%PY%" "%ROOT%\scripts\win_health_check.py" >nul 2>&1
if not errorlevel 1 (
  echo BoneMet is already running on port %PORT%.
  goto api_ready
)

set "BONEMET_AGGRESSIVE_STOP=1"
echo %PORT%>"%LOG_DIR%\bonemet.port"
echo Starting BoneMet on port %PORT%...
start "BoneMet Worker" /MIN "%ROOT%\scripts\win-run-worker.bat"
ping -n 3 127.0.0.1 >nul
start "BoneMet API" /MIN "%ROOT%\scripts\win-run-api.bat"

echo Waiting for API (up to 2 minutes)...
set /a _n=0
:wait_api
ping -n 2 127.0.0.1 >nul
if exist "%LOG_DIR%\bonemet.port" set /p PORT=<"%LOG_DIR%\bonemet.port"
"%PY%" "%ROOT%\scripts\win_health_check.py" >nul 2>&1
if not errorlevel 1 goto api_ready
set /a _n+=1
if %_n% lss 60 goto wait_api
echo.
echo WARNING: API not ready. Check %LOG_DIR%\api.log
if exist "%LOG_DIR%\bonemet.port" set /p PORT=<"%LOG_DIR%\bonemet.port"
goto done

:api_ready
if exist "%LOG_DIR%\bonemet.port" set /p PORT=<"%LOG_DIR%\bonemet.port"
if not "%PORT%"=="8080" echo Note: using port %PORT% because 8080 was busy.
start "" "http://127.0.0.1:%PORT%/"

:done
echo.
echo BoneMet: http://127.0.0.1:%PORT%/
echo Logs: %LOG_DIR%
echo.
pause

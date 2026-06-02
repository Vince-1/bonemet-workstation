@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\python\python.exe"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo BoneMet - 检查并修复模型配置
echo 目录: %ROOT%\data\models
echo.

"%PY%" "%ROOT%\scripts\ensure_models.py" --repair-registry
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo 修复完成。请双击「停止BoneMet.bat」后重新「安装并启动」。
) else (
  echo 若仍失败：请把打包目录里的 data\models 整夹复制到:
  echo   %ROOT%\data\models
  echo 需含 registry.yaml、detect\model.onnx、bone_seg\*.onnx
)
pause
exit /b %RC%

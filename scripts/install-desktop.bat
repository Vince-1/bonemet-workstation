@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0.."
set ROOT=%CD%

echo ==^> BoneMet Workstation 安装
echo     目录: %ROOT%

if not exist ".venv\Scripts\python.exe" (
  echo ==^> 创建 Python 虚拟环境
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
set PY=%ROOT%\.venv\Scripts\python.exe
set PYTHONPATH=%ROOT%\packages;%ROOT%

echo ==^> 安装 Python 依赖
"%PY%" -m pip install -U pip
"%PY%" -m pip install -r requirements.txt

where npm >nul 2>&1
if %ERRORLEVEL%==0 (
  echo ==^> 构建前端
  cd apps\web
  call npm install
  call npm run build
  cd ..\..
) else (
  echo WARN: 未找到 npm，请安装 Node.js 后手动构建前端
)

if not exist "config\local.yaml" copy config\default.example.yaml config\local.yaml
if not exist "data" mkdir data\cases data\queue data\models 2>nul

echo.
echo 安装完成。双击或运行: scripts\launch.bat
pause

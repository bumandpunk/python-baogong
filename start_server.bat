@echo off
chcp 65001 >nul
title 报工自动发送服务

echo ======================================
echo   报工自动发送服务 启动中...
echo ======================================
echo.

:: 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"

:: 检查虚拟环境是否存在
if exist "venv\Scripts\activate.bat" (
    echo [INFO] 激活虚拟环境 venv...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] 激活虚拟环境 .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] 未找到虚拟环境，使用系统 Python...
)

:: 检查依赖
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH
    pause
    exit /b 1
)

echo [INFO] 安装/同步依赖...
python -m pip install -r requirements_server.txt
if errorlevel 1 (
    echo [ERROR] 依赖安装失败，请检查 requirements_server.txt 或网络环境
    pause
    exit /b 1
)

echo.
echo [INFO] 启动服务...
echo [INFO] 访问地址: http://localhost:8000
echo [INFO] API文档:  http://localhost:8000/docs
echo [INFO] 按 Ctrl+C 停止服务
echo.

:: 启动 FastAPI 服务
python -m uvicorn baogong_server.main:app --host 0.0.0.0 --port 8000 --log-level info

echo.
echo [INFO] 服务已停止
pause

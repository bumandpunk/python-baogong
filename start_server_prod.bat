@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title 报工自动发送服务（生产版）

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"

set "HOST=%BAOGONG_HOST%"
if not defined HOST set "HOST=0.0.0.0"

set "PORT=%BAOGONG_PORT%"
if not defined PORT set "PORT=8000"

set "LOG_DIR=%PROJECT_DIR%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TIMESTAMP=%%i"
if not defined TIMESTAMP set "TIMESTAMP=%date:/=-%_%time::=-%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "LOG_FILE=%LOG_DIR%\baogong_server_%TIMESTAMP%.log"

set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ======================================
echo   报工自动发送服务（生产版）启动中...
echo ======================================
echo [INFO] 项目目录: %PROJECT_DIR%
echo [INFO] 监听地址: http://%HOST%:%PORT%
echo [INFO] 日志文件: %LOG_FILE%
echo.

echo [%date% %time%] startup begin > "%LOG_FILE%"

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
    echo [INFO] 使用虚拟环境: venv
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
    echo [INFO] 使用虚拟环境: .venv
) else (
    echo [WARN] 未找到虚拟环境，准备创建 venv...
    echo [%date% %time%] creating venv >> "%LOG_FILE%"

    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH
        echo [%date% %time%] python not found >> "%LOG_FILE%"
        pause
        exit /b 1
    )

    python -m venv venv >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败，请查看日志：%LOG_FILE%
        pause
        exit /b 1
    )

    set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
    echo [INFO] 已创建虚拟环境: venv
)

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 不可用，请检查虚拟环境或系统 Python
    echo [%date% %time%] selected python unavailable >> "%LOG_FILE%"
    pause
    exit /b 1
)

netstat -ano | findstr /C:":%PORT%" | findstr /C:"LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] 端口 %PORT% 已被占用，请先停止已有服务
    echo [%date% %time%] port %PORT% already in use >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo [INFO] 安装/同步依赖...
echo [%date% %time%] pip install begin >> "%LOG_FILE%"
"%PYTHON_EXE%" -m pip install -r requirements_server.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] 依赖安装失败，请查看日志：%LOG_FILE%
    pause
    exit /b 1
)

echo.
echo [INFO] 服务启动中...
echo [INFO] 本机访问: http://localhost:%PORT%/docs
echo [INFO] 局域网访问: http://你的服务器IP:%PORT%/docs
echo [INFO] 按 Ctrl+C 可停止服务
echo.

echo [%date% %time%] uvicorn start host=%HOST% port=%PORT% >> "%LOG_FILE%"
"%PYTHON_EXE%" -m uvicorn baogong_server.main:app --host %HOST% --port %PORT% --log-level info >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] uvicorn exit code=!EXIT_CODE! >> "%LOG_FILE%"

echo.
if "!EXIT_CODE!"=="0" (
    echo [INFO] 服务已停止
) else (
    echo [ERROR] 服务异常退出，退出码=!EXIT_CODE!
    echo [ERROR] 请查看日志：%LOG_FILE%
    pause
)

exit /b !EXIT_CODE!

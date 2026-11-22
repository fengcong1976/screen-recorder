@echo off
chcp 65001 >nul
title 影随录屏

echo.
echo ==========================================
echo              影随录屏
echo ==========================================
echo.
echo 正在启动程序...
echo.

cd /d "%~dp0"

:: 优先使用项目虚拟环境
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% main.py

if errorlevel 1 (
    echo.
    echo 程序启动失败，请检查错误信息
    pause
) else (
    echo.
    echo 程序已正常退出
)

echo.
pause
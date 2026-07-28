@echo off
setlocal
set SCRIPT_DIR=%~dp0

if /I "%~1"=="emily" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_emily.ps1"
) else (
    echo Uso: run emily
    exit /b 1
)

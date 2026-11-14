@echo off
setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw launcher\main.py %*
) else (
    python launcher\main.py %*
)

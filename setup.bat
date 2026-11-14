@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Antigravity Launcher & Micro-Proxy - Windows Setup
echo ============================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay Python! Vui long cai dat Python 3.8+ tu https://www.python.org/
    echo        Luu y: Nho tich chon "Add python.exe to PATH" khi cai dat.
    pause
    exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay Node.js! Vui long cai dat Node.js LTS tu https://nodejs.org/
    pause
    exit /b 1
)

echo [1/3] Dang cai dat cac thu vien Python (PyQt6, requests)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Cai dat thu vien Python that bai.
    pause
    exit /b 1
)

echo.
echo [2/3] Dang cai dat thu vien Node.js cho Micro-Proxy...
cd proxy
call npm install
cd ..
if %errorlevel% neq 0 (
    echo [ERROR] Cai dat dependencies npm cho proxy that bai.
    pause
    exit /b 1
)

echo.
echo [3/3] Dang tao Shortcut tren Desktop...
python launcher\main.py --create-shortcut

echo.
echo ============================================================
echo   [OK] Cai dat hoan tat!
echo   De khoi chay, hay nhap dup vao Shortcut Desktop hoac "launch.bat"
echo ============================================================
echo.
pause

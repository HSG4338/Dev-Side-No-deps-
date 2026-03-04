@echo off
title Agentic AI System
color 0A
cls

echo.
echo  ============================================
echo   AGENTIC AI SYSTEM
echo  ============================================
echo.

:: ── Find Python ──────────────────────────────────────────────
set PYTHON=

:: Check venv first (created by install_dependencies.bat)
if exist "%~dp0venv\Scripts\python.exe" (
    set PYTHON=%~dp0venv\Scripts\python.exe
    echo  [OK] Using venv Python: %~dp0venv\Scripts\python.exe
    goto :found_python
)

:: Check system python
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    echo  [OK] Using system Python
    goto :found_python
)

:: Check python3
python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python3
    echo  [OK] Using python3
    goto :found_python
)

:: Check py launcher (Windows Store Python)
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=py
    echo  [OK] Using py launcher
    goto :found_python
)

:: Nothing found
echo.
echo  [ERROR] Python not found on PATH.
echo.
echo  Please install Python 3.10+ from https://python.org
echo  Make sure to check "Add Python to PATH" during install.
echo.
pause
exit /b 1

:found_python
for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^>^&1') do echo  [OK] %PYTHON%: %%v

:: ── Check we are in the right directory ──────────────────────
if not exist "%~dp0main.py" (
    echo.
    echo  [ERROR] main.py not found.
    echo  Please run this from inside the agentic_ai folder.
    echo.
    pause
    exit /b 1
)

:: ── Check configs exist ───────────────────────────────────────
if not exist "%~dp0configs\config.json" (
    echo.
    echo  [ERROR] configs\config.json not found.
    echo  Your download may be incomplete. Re-download the zip.
    echo.
    pause
    exit /b 1
)

:: ── Quick import check ────────────────────────────────────────
echo.
echo  Checking imports...
"%PYTHON%" -c "import sqlite3, json, http.server, threading, subprocess, ast, hashlib, urllib.request; print('  [OK] All stdlib imports OK')" 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Import check failed. Your Python install may be broken.
    pause
    exit /b 1
)

:: ── Init memory DB ────────────────────────────────────────────
echo  Initialising memory database...
cd /d "%~dp0"
"%PYTHON%" -c "import sys; sys.path.insert(0,'.'); from memory.memory_store import init_db; init_db(); print('  [OK] Memory DB ready')" 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to initialise memory database.
    echo  Make sure you are running from inside the agentic_ai folder.
    pause
    exit /b 1
)

:: ── Read port from config ─────────────────────────────────────
for /f "tokens=*" %%p in ('"%PYTHON%" -c "import json; c=json.load(open('configs/config.json')); print(c['ui'].get('port',5000))" 2^>nul') do set PORT=%%p
if "%PORT%"=="" set PORT=5000

:: ── Launch UI ─────────────────────────────────────────────────
echo.
echo  ============================================
echo   Starting web UI on http://127.0.0.1:%PORT%
echo   Press Ctrl+C to stop
echo  ============================================
echo.
echo  Opening browser...
start "" "http://127.0.0.1:%PORT%"

"%PYTHON%" main.py --ui 2>&1
if errorlevel 1 (
    echo.
    echo  ============================================
    echo   SERVER STOPPED WITH AN ERROR
    echo  ============================================
    echo.
    echo  If you see "Address already in use":
    echo    - Change "port" in configs\config.json to 5001
    echo    - Then re-run this file
    echo.
    pause
)

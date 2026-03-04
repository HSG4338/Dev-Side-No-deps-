@echo off
title Agentic AI - Run Goal
color 0A
cls

echo.
echo  ============================================
echo   AGENTIC AI — RUN A GOAL
echo  ============================================
echo.

:: Find Python (same logic as run.bat)
set PYTHON=
if exist "%~dp0venv\Scripts\python.exe" ( set PYTHON=%~dp0venv\Scripts\python.exe & goto :fp )
python --version >nul 2>&1 && set PYTHON=python && goto :fp
python3 --version >nul 2>&1 && set PYTHON=python3 && goto :fp
py --version >nul 2>&1 && set PYTHON=py && goto :fp
echo [ERROR] Python not found. Install from https://python.org & pause & exit /b 1

:fp
cd /d "%~dp0"

echo  Enter your goal below (e.g. Build a CLI calculator)
echo  Then press Enter to run.
echo.
set /p GOAL="  Goal: "

if "%GOAL%"=="" (
    echo  No goal entered. Exiting.
    pause
    exit /b 0
)

echo.
echo  Running goal: %GOAL%
echo  ============================================
echo.

"%PYTHON%" main.py --goal "%GOAL%" 2>&1

echo.
echo  ============================================
echo   Done. Press any key to close.
echo  ============================================
pause

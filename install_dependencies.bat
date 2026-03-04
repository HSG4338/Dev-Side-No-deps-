@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AGENTIC AI SYSTEM — WINDOWS INSTALLER
:: Core system: zero external deps (Python stdlib only)
:: Optional: installs HuggingFace packages if requested
:: Logs to logs\install.log
:: ============================================================

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv
set LOG_DIR=%PROJECT_DIR%logs
set LOG_FILE=%LOG_DIR%\install.log
set PYTHON=python

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo. > "%LOG_FILE%"
call :log "======================================"
call :log "AGENTIC AI SYSTEM INSTALLER"
call :log "Started: %date% %time%"
call :log "======================================"

:: Check Python
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    call :log "ERROR: Python not found. Install Python 3.10+ from https://python.org"
    echo ERROR: Python not found.
    exit /b 1
)
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do call :log "Python: %%v"

:: ── Core: create venv ──────────────────────────────────────
call :log ""
call :log "Step 1: Creating virtual environment..."
echo [1/4] Creating virtual environment...

if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
%PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 ( call :log "ERROR: venv creation failed"; exit /b 1 )

:: ── Core: upgrade pip ──────────────────────────────────────
call :log "Step 2: Upgrading pip..."
echo [2/4] Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1

:: ── Core: init memory DB ───────────────────────────────────
call :log ""
call :log "Step 3: Initializing memory database..."
echo [3/4] Initializing memory database...
"%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'%PROJECT_DIR%'); from memory.memory_store import init_db; init_db(); print('Memory DB ready.')" >> "%LOG_FILE%" 2>&1

:: ── Optional: HuggingFace backend ──────────────────────────
call :log ""
call :log "Step 4: Checking LLM provider selection..."
echo [4/4] Checking provider selection...

"%VENV_DIR%\Scripts\python.exe" -c "
import json, sys
with open(r'%PROJECT_DIR%configs/config.json') as f:
    cfg = json.load(f)
provider = cfg['llm'].get('provider','anthropic')
print(provider)
" > "%TEMP%\provider.txt" 2>nul

set /p PROVIDER=<"%TEMP%\provider.txt"
call :log "Configured provider: %PROVIDER%"

if "%PROVIDER%"=="huggingface" (
    call :log "HuggingFace provider selected — installing ML packages..."
    echo Installing HuggingFace packages (this may take several minutes and ~2-4GB disk)...
    "%VENV_DIR%\Scripts\pip.exe" install transformers torch accelerate sentencepiece >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        call :log "WARNING: HuggingFace install had errors. See %LOG_FILE%"
        echo WARNING: Some HuggingFace packages failed. Check %LOG_FILE%
    ) else (
        call :log "HuggingFace packages installed."
        echo HuggingFace packages installed.
        call :log "Models will auto-download to models\cache on first use."
        echo Models will download on first use (~1-4 GB).
    )
) else if "%PROVIDER%"=="ollama" (
    call :log "Ollama provider selected — no pip install needed."
    echo Ollama selected. No pip install needed.
    echo Make sure Ollama is running: https://ollama.com
    echo Then pull your model: ollama pull llama3
) else (
    call :log "Anthropic provider selected — no pip install needed."
    echo Anthropic selected. No pip install needed.
    echo Set env var ANTHROPIC_API_KEY to enable full LLM mode.
)

:: ── Done ───────────────────────────────────────────────────
call :log ""
call :log "======================================"
call :log "SETUP COMPLETE — %date% %time%"
call :log "======================================"
call :log "Run: venv\Scripts\activate"
call :log "     python main.py --ui"
call :log "     python main.py --validate"

echo.
echo ============================================
echo  SETUP COMPLETE
echo ============================================
echo  Provider: %PROVIDER%
echo.
echo  To start:
echo    venv\Scripts\activate
echo    python main.py --ui          (web dashboard)
echo    python main.py --validate    (run tests)
echo    python main.py --goal "..."  (run a goal)
echo.
echo  Switch provider anytime in configs\config.json
echo  Full log: %LOG_FILE%
echo ============================================
echo.
pause
exit /b 0

:log
echo %~1 >> "%LOG_FILE%"
echo %~1
goto :eof

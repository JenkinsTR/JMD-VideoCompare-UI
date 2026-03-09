@echo off
REM Launch JMD Video Compare UI without building (for testing)
REM Uses .venv if present, otherwise system Python

set SCRIPT_DIR=%~dp0
set APP_DIR=%SCRIPT_DIR%JMD-VideoCompare-UI
set REQ_FILE=%SCRIPT_DIR%requirements.txt
set FIRST_ARG=%~1
cd /d "%APP_DIR%"

set CLI_HEADLESS=0
if /I "%FIRST_ARG%"=="process" set CLI_HEADLESS=1
if /I "%FIRST_ARG%"=="ffmpeg-test" set CLI_HEADLESS=1
if /I "%FIRST_ARG%"=="--version" set CLI_HEADLESS=1
if /I "%FIRST_ARG%"=="-V" set CLI_HEADLESS=1
if /I "%FIRST_ARG%"=="--help" set CLI_HEADLESS=1
if /I "%FIRST_ARG%"=="-h" set CLI_HEADLESS=1

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo Using venv...
    if "%CLI_HEADLESS%"=="0" (
        "%SCRIPT_DIR%.venv\Scripts\python.exe" -c "import PyQt6" >nul 2>&1
        if errorlevel 1 (
            echo PyQt6 not found in venv. Installing dependencies...
            "%SCRIPT_DIR%.venv\Scripts\python.exe" -m pip install -r "%REQ_FILE%"
            if errorlevel 1 goto :end
        )
    )
    "%SCRIPT_DIR%.venv\Scripts\python.exe" app.py %*
) else (
    echo Using system Python...
    if "%CLI_HEADLESS%"=="0" (
        python -c "import PyQt6" >nul 2>&1
        if errorlevel 1 (
            echo PyQt6 not found in system Python. Installing dependencies...
            python -m pip install -r "%REQ_FILE%"
            if errorlevel 1 goto :end
        )
    )
    python app.py %*
)

:end
if errorlevel 1 pause

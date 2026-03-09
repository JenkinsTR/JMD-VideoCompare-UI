@echo off
REM Build JMD Video Compare UI into executable
REM Requires: pip install pyinstaller

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%JMD-VideoCompare-UI"

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo Using venv...
    "%SCRIPT_DIR%.venv\Scripts\pip.exe" install pyinstaller pyqt6
    "%SCRIPT_DIR%.venv\Scripts\pyinstaller.exe" JMD-VideoCompare-UI.spec
) else (
    echo Using system Python...
    pip install pyinstaller pyqt6
    pyinstaller JMD-VideoCompare-UI.spec
)

if errorlevel 1 pause

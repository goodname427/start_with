@echo off
cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 (
    start "" python "%~dp0start_with_gui.py"
) else (
    start "" pythonw "%~dp0start_with_gui.py"
)

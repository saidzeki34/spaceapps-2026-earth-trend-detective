@echo off
rem Starts RivaScope with the project's own Python environment. Double-click it, or run it from a terminal.
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m mountain_water.ui %*
) else (
  python -m mountain_water.ui %*
)
if errorlevel 1 pause

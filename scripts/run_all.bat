@echo off
setlocal

REM Double-click launcher for Windows.
REM It delegates to scripts\run_all.ps1 and keeps the window open.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_all.ps1"

if errorlevel 1 (
    echo.
    echo Script failed. Read the error above, because computers still refuse to explain themselves politely.
) else (
    echo.
    echo Script finished successfully.
)

pause

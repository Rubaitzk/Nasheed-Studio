@echo off
setlocal
cd /d "%~dp0"
echo ==========================================================
echo  Creating Desktop Shortcut for NCN Studio...
echo ==========================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Could not automatically create the shortcut.
    echo Please make sure Windows PowerShell is enabled on your system.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo You can now launch NCN Studio directly from your desktop.
echo.
pause

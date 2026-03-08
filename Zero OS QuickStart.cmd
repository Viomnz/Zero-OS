@echo off
setlocal
cd /d "%~dp0"
title Zero OS QuickStart
echo Zero OS QuickStart
echo.
echo Step 1: Running first-run setup...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zero_os_launcher.ps1" first-run
if errorlevel 1 (
  echo.
  echo First-run failed. Review the output above.
  pause
  exit /b 1
)
echo.
echo Step 2: Opening Zero OS UI...
python "%~dp0zero_os_ui.py"
if errorlevel 1 (
  echo.
  echo UI launch failed. Try opening zero_os_shell.html manually.
  pause
  exit /b 1
)
exit /b 0

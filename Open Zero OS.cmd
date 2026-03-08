@echo off
setlocal
cd /d "%~dp0"
title Open Zero OS
python "%~dp0zero_os_ui.py"
if errorlevel 1 (
  echo.
  echo Zero OS UI failed to open.
  echo Try double-clicking zero_os_shell.html or run Zero OS QuickStart.cmd first.
  pause
  exit /b 1
)
exit /b 0

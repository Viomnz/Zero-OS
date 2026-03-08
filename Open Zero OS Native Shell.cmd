@echo off
setlocal
cd /d "%~dp0"
title Zero OS Native Shell
if exist "%~dp0native_ui\ZeroOS.NativeShell\publish\ZeroOS.NativeShell.exe" (
  start "" "%~dp0native_ui\ZeroOS.NativeShell\publish\ZeroOS.NativeShell.exe"
  exit /b 0
)
echo Native Shell publish build not found.
echo Opening the universal Zero OS UI instead.
python "%~dp0zero_os_ui.py"
if errorlevel 1 (
  echo.
  echo Zero OS UI failed to open.
  pause
  exit /b 1
)
exit /b 0

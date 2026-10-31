@echo off
setlocal
cd /d "%~dp0"
if not exist "data\hwtrace.sqlite3" (
  echo Database not found: %~dp0data\hwtrace.sqlite3
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 dashboard.py --db "data\hwtrace.sqlite3" --open-browser
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.12 or newer is required and was not found on PATH.
    pause
    exit /b 1
  )
  python dashboard.py --db "data\hwtrace.sqlite3" --open-browser
)
if errorlevel 1 (
  echo Dashboard could not start. Check the message above.
  pause
)

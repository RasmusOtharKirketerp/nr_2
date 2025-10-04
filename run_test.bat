@echo off
setlocal
set SCRIPT_DIR=%~dp0
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%\.venv\Scripts\python.exe" -m pytest %*
) else (
    python -m pytest %*
)
endlocal

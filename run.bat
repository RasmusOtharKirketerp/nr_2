@echo off
REM Simplest possible launcher: ensures src on PYTHONPATH then forwards all args.
set PYTHONPATH=%CD%\src
if exist .\.venv\Scripts\python.exe (
    set PY_CMD=.\.venv\Scripts\python.exe
) else (
    set PY_CMD=python
)
if "%*"=="" (
    echo Usage examples:
    echo   run --web --debug
    echo   run --daemon
    echo   run --fetch
    exit /b 1
)
%PY_CMD% -m newsreader.main %*
exit /b %errorlevel%

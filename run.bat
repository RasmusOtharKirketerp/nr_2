@echo off
setlocal
REM Simplest possible launcher: ensures src on PYTHONPATH then forwards all args.
set PYTHONPATH=%CD%\src
if exist .\.venv\Scripts\python.exe (
    set PY_CMD=.\.venv\Scripts\python.exe
) else (
    set PY_CMD=python
)

if not defined NEWSREADER_LOCAL_PORT (
    set NEWSREADER_LOCAL_PORT=8100
)

if "%*"=="" (
    echo Starting Newsreader daemon...
    start "Newsreader Daemon" "%PY_CMD%" -m newsreader.main --daemon
    echo Starting Newsreader web UI on port %NEWSREADER_LOCAL_PORT%...
    start "Newsreader Web" "%PY_CMD%" -m newsreader.main --web --debug --host 127.0.0.1 --port %NEWSREADER_LOCAL_PORT%
    exit /b 0
)

"%PY_CMD%" -m newsreader.main %*
exit /b %errorlevel%

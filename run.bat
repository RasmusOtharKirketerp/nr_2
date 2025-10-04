@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul 2>&1

set "PYTHONPATH=%SCRIPT_DIR%src"
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PY_CMD=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

if not defined NEWSREADER_LOCAL_PORT (
    set "NEWSREADER_LOCAL_PORT=8100"
)

set "DAEMON_PID_FILE=%SCRIPT_DIR%var\news_daemon.pid"

if "%~1"=="" goto launch_stack

set "FIRST_ARG=%~1"
shift
call :map_alias "%FIRST_ARG%" CMD_ARGS

:collect_args
if "%~1"=="" goto run_passthrough
set "CMD_ARGS=%CMD_ARGS% %~1"
shift
goto collect_args

:run_passthrough
echo Running: %PY_CMD% -m newsreader.main %CMD_ARGS%
"%PY_CMD%" -m newsreader.main %CMD_ARGS%
set "EXITCODE=%errorlevel%"
goto epilogue

:launch_stack
call :ensure_daemon_running
echo Starting Newsreader web UI on 127.0.0.1:%NEWSREADER_LOCAL_PORT%...
start "Newsreader Web" "%PY_CMD%" -m newsreader.main --web --debug --host 127.0.0.1 --port %NEWSREADER_LOCAL_PORT%
set "EXITCODE=0"
goto epilogue

:ensure_daemon_running
set "NEED_START=1"
set "EXISTING_PID="
if exist "%DAEMON_PID_FILE%" (
    set /p "EXISTING_PID=" < "%DAEMON_PID_FILE%"
    if defined EXISTING_PID (
        for /f "tokens=1" %%P in ('tasklist /FI "PID eq %EXISTING_PID%" /NH') do (
            if /I not "%%P"=="INFO:" set "NEED_START=0"
        )
    )
    if "%NEED_START%"=="1" (
        del "%DAEMON_PID_FILE%" >nul 2>&1
    )
)
if "%NEED_START%"=="1" (
    echo Starting Newsreader daemon...
    start "Newsreader Daemon" "%PY_CMD%" -m newsreader.main --daemon
) else (
    echo Newsreader daemon already running.
)
exit /b 0

:map_alias
set "ARG=%~1"
set "DEST=%~2"
set "VALUE=%ARG%"
if /I "%ARG%"=="web" set "VALUE=--web"
if /I "%ARG%"=="daemon" set "VALUE=--daemon"
if /I "%ARG%"=="fetch" set "VALUE=--fetch"
if /I "%ARG%"=="stats" set "VALUE=--stats"
if /I "%ARG%"=="cleanup" set "VALUE=--cleanup"
if /I "%ARG%"=="create-admin" set "VALUE=--create-admin"
if /I "%ARG%"=="create-user" set "VALUE=--create-user"
set "%DEST%=%VALUE%"
exit /b 0

:epilogue
popd >nul 2>&1
endlocal & exit /b %EXITCODE%

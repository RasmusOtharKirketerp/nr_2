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
echo Starting Newsreader stack on 127.0.0.1:%NEWSREADER_LOCAL_PORT%...
"%PY_CMD%" -m newsreader.main --stack --host 127.0.0.1 --port %NEWSREADER_LOCAL_PORT% --debug --verbose
set "EXITCODE=%errorlevel%"
goto epilogue

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
if /I "%ARG%"=="stack" set "VALUE=--stack"
set "%DEST%=%VALUE%"
exit /b 0

:epilogue
popd >nul 2>&1
endlocal & exit /b %EXITCODE%

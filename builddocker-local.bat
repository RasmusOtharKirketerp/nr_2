@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Build and (re)start local newsreader stack using docker compose.
REM Requirements: Docker Desktop installed and running.

set COMPOSE_FILE=docker\docker-compose.yml
set IMAGE_NAME=newsreader:latest
set SERVICE=stack
set DOCKER_CMD=docker
set COMPOSE_CMD=docker compose

REM Parse flags
set CLEAN=0
:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="--clean" set CLEAN=1& shift & goto parse
if /I "%~1"=="-c" set CLEAN=1& shift & goto parse
if /I "%~1"=="--help" goto usage
if /I "%~1"=="-h" goto usage
shift
goto parse
:after_parse

REM Ensure compose file exists
if not exist "%COMPOSE_FILE%" (
  echo [error] Compose file not found: %COMPOSE_FILE%
  exit /b 1
)

REM Optionally remove old image
if %CLEAN%==1 (
  echo [clean] Removing existing image %IMAGE_NAME% if present...
  %DOCKER_CMD% image rm %IMAGE_NAME% 1>nul 2>nul
)

REM Build image
echo [build] Building image %IMAGE_NAME% ...
%COMPOSE_CMD% -f %COMPOSE_FILE% build --pull || goto :fail

REM Bring up stack (detached)
echo [up] Starting service '%SERVICE%' (and dependencies) ...
%COMPOSE_CMD% -f %COMPOSE_FILE% up -d %SERVICE% || goto :fail

REM Show status
echo.
echo [status] Active containers:
%DOCKER_CMD% ps --filter "name=newsreader" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo [logs] Tailing logs (Ctrl+C to stop)...
%COMPOSE_CMD% -f %COMPOSE_FILE% logs -f %SERVICE%
exit /b 0

:usage
echo Usage: builddocker-local.bat [--clean]
echo.
echo   --clean, -c   Remove existing image before rebuilding
echo   --help,  -h   Show this help
exit /b 0

:fail
echo [fatal] Build or startup failed (exit code %errorlevel%).
exit /b %errorlevel%

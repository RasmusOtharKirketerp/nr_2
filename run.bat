@echo off
setlocal

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
	call "venv\Scripts\activate.bat"
)

REM Upgrade pip and install project dependencies
python -m pip install --upgrade pip
if errorlevel 1 goto :error

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

REM Ensure src/ is on the module search path for package imports
set "PYTHONPATH=%cd%\src"

REM Launch the Flask web application
python -m newsreader.main --web
if errorlevel 1 goto :error

pause
goto :eof

:error
echo.
echo An error occurred while preparing or launching the app. See messages above.
pause

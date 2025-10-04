@echo off
setlocal

REM Configure environment for the live article ingestion test.
set "RUN_REAL_ARTICLE_TEST=1"
set "REAL_ARTICLE_URL=https://nyheder.tv2.dk/politik/2025-10-04-v-formand-vil-have-aendringer-i-pensionssystemet"

REM Prefer the project virtual environment if it exists.
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Unable to locate %%PYTHON%% - ensure the virtual environment is created.>&2
    exit /b 1
)

echo Running real-article integration test against %REAL_ARTICLE_URL%
"%PYTHON%" -m pytest tests\test_integration_real_article.py -s %*
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%

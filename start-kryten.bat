@echo off
REM Start script for Kryten CyTube Connector
REM Usage: start-kryten.bat [config-file]

setlocal

REM Set default config file
set CONFIG_FILE=config.json

REM Allow config file override via command line argument
if not "%~1"=="" set CONFIG_FILE=%~1

REM Change to script directory
cd /d "%~dp0"

REM Check if config file exists
if not exist "%CONFIG_FILE%" (
    echo ERROR: Configuration file not found: %CONFIG_FILE%
    exit /b 1
)

echo Starting Kryten CyTube Connector...
echo Configuration: %CONFIG_FILE%
echo Press Ctrl+C to stop
echo.

REM Run Kryten as Python module
python -m kryten "%CONFIG_FILE%"

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% equ 0 (
    echo.
    echo Kryten stopped cleanly
) else (
    echo.
    echo Kryten exited with error code: %EXIT_CODE%
)

exit /b %EXIT_CODE%

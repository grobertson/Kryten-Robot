#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start the Kryten CyTube Connector service.

.DESCRIPTION
    This script starts the Kryten CyTube connector, which bridges CyTube chat 
    to a NATS event bus. It loads configuration from config.json and handles
    graceful shutdown on Ctrl+C.

.PARAMETER ConfigFile
    Path to the JSON configuration file. Default: config.json

.PARAMETER LogLevel
    Override the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    If not specified, uses the log_level from config file.

.EXAMPLE
    .\start-kryten.ps1
    Start Kryten with default config.json

.EXAMPLE
    .\start-kryten.ps1 -ConfigFile custom-config.json
    Start Kryten with a custom configuration file

.EXAMPLE
    .\start-kryten.ps1 -LogLevel DEBUG
    Start Kryten with DEBUG logging

.NOTES
    Requirements:
    - Python 3.8 or higher
    - Required Python packages (install via pip)
    
    Exit Codes:
    0 - Clean shutdown
    1 - Error occurred
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ConfigFile = "config.json",
    
    [Parameter()]
    [ValidateSet('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')]
    [string]$LogLevel
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Get script directory and set working directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

try {
    # Validate configuration file exists
    if (-not (Test-Path $ConfigFile)) {
        Write-Error "Configuration file not found: $ConfigFile"
        exit 1
    }

    Write-Host "Starting Kryten CyTube Connector..." -ForegroundColor Cyan
    Write-Host "Configuration: $ConfigFile" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""

    # Clear PYTHONPATH to avoid conflicts with development versions
    $env:PYTHONPATH = ""
    
    # Build Python command arguments
    $pythonArgs = @("-m", "kryten")
    if (Test-Path $ConfigFile) {
        $pythonArgs += @("--config", $ConfigFile)
    }
    
    # Set log level environment variable if specified
    if ($LogLevel) {
        Write-Host "Log level override: $LogLevel" -ForegroundColor Yellow
        $env:KRYTEN_LOG_LEVEL = $LogLevel
    }

    # Run Python module
    # The -m flag tells Python to run the module as a script
    & python @pythonArgs

    # Capture exit code
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "`nKryten stopped cleanly" -ForegroundColor Green
    } else {
        Write-Host "`nKryten exited with error code: $exitCode" -ForegroundColor Red
    }

    exit $exitCode

} catch {
    Write-Error "Failed to start Kryten: $_"
    exit 1
} finally {
    # Restore original directory
    Pop-Location
}

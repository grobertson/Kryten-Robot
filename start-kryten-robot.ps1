#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Kryten-Robot with automatic environment management
.DESCRIPTION
    This script ensures a working Python virtual environment exists and is properly
    configured before running Kryten-Robot. It will create or repair the environment
    if needed, providing clear error messages when issues occur.
.PARAMETER ConfigFile
    Path to configuration file (default: config.json)
.PARAMETER LogLevel
    Override log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
.EXAMPLE
    .\start-kryten-robot.ps1
.EXAMPLE
    .\start-kryten-robot.ps1 -ConfigFile config-420grindhouse.json -LogLevel DEBUG
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$ConfigFile = "config.json",
    
    [Parameter()]
    [ValidateSet('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')]
    [string]$LogLevel
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Configuration
$VenvPath = Join-Path $ScriptDir ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"
$RequirementsFile = Join-Path $ScriptDir "requirements.txt"
$ConfigPath = Join-Path $ScriptDir $ConfigFile

# Color output functions
function Write-Success { param($Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Write-Info { param($Message) Write-Host "ℹ $Message" -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }
function Write-ErrorMsg { param($Message) Write-Host "✗ $Message" -ForegroundColor Red }

# Check if Python is available
function Test-PythonAvailable {
    try {
        $pythonCmd = Get-Command python -ErrorAction Stop
        $version = & python --version 2>&1
        if ($version -match "Python 3\.(1[1-9]|[2-9]\d)") {
            Write-Success "Found $version at $($pythonCmd.Source)"
            return $true
        } else {
            Write-ErrorMsg "Python 3.11+ required, found: $version"
            return $false
        }
    } catch {
        Write-ErrorMsg "Python not found in PATH"
        Write-Info "Install Python 3.11+ from https://www.python.org/"
        return $false
    }
}

# Check if venv is valid
function Test-VenvValid {
    param($Path)
    
    if (-not (Test-Path $Path)) {
        return $false
    }
    
    $pythonExe = Join-Path $Path "Scripts\python.exe"
    $pipExe = Join-Path $Path "Scripts\pip.exe"
    
    if (-not (Test-Path $pythonExe) -or -not (Test-Path $pipExe)) {
        Write-Warning "Virtual environment incomplete or corrupted"
        return $false
    }
    
    # Test if python actually works
    try {
        $null = & $pythonExe -c "import sys" 2>&1
        return $true
    } catch {
        Write-Warning "Virtual environment Python is not functional"
        return $false
    }
}

# Create virtual environment
function New-VirtualEnvironment {
    param($Path)
    
    Write-Info "Creating virtual environment at $Path"
    
    try {
        & python -m venv $Path
        
        if (-not (Test-VenvValid $Path)) {
            throw "Failed to create valid virtual environment"
        }
        
        Write-Success "Virtual environment created successfully"
        return $true
    } catch {
        Write-ErrorMsg "Failed to create virtual environment: $_"
        return $false
    }
}

# Install or update requirements
function Install-Requirements {
    param($PipExe, $RequirementsPath)
    
    if (-not (Test-Path $RequirementsPath)) {
        Write-ErrorMsg "Requirements file not found: $RequirementsPath"
        return $false
    }
    
    Write-Info "Installing/updating dependencies from requirements.txt"
    
    try {
        & $PipExe install --upgrade pip --quiet
        & $PipExe install -r $RequirementsPath --upgrade
        
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed with exit code $LASTEXITCODE"
        }
        
        Write-Success "Dependencies installed successfully"
        return $true
    } catch {
        Write-ErrorMsg "Failed to install dependencies: $_"
        Write-Info "Try manually: $PipExe install -r $RequirementsPath"
        return $false
    }
}

# Verify critical packages are installed
function Test-CriticalPackagesInstalled {
    param($PythonExe)
    
    $packages = @('nats', 'socketio', 'aiohttp', 'websockets')
    $allInstalled = $true
    
    foreach ($pkg in $packages) {
        try {
            $null = & $PythonExe -c "import $pkg" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "$pkg package is installed"
            } else {
                Write-Warning "$pkg package not found"
                $allInstalled = $false
            }
        } catch {
            Write-Warning "$pkg package not importable"
            $allInstalled = $false
        }
    }
    
    return $allInstalled
}

# Main execution
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Kryten-Robot (CyTube Connector) Startup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
if (-not (Test-PythonAvailable)) {
    exit 1
}

# Step 2: Check configuration file
if (-not (Test-Path $ConfigPath)) {
    Write-ErrorMsg "Configuration file not found: $ConfigPath"
    Write-Info "Available config files:"
    Get-ChildItem -Path $ScriptDir -Filter "config*.json" | ForEach-Object {
        Write-Info "  - $($_.Name)"
    }
    exit 1
}
Write-Success "Configuration file found: $ConfigFile"

# Step 3: Check/Create venv
if (-not (Test-VenvValid $VenvPath)) {
    Write-Warning "Virtual environment needs to be created or repaired"
    
    # Remove corrupted venv if it exists
    if (Test-Path $VenvPath) {
        Write-Info "Removing corrupted virtual environment"
        try {
            Remove-Item -Recurse -Force $VenvPath -ErrorAction Stop
        } catch {
            Write-ErrorMsg "Could not remove corrupted venv (may be in use)"
            Write-Info "Please close all terminals/processes using: $VenvPath"
            Write-Info "Then delete manually or restart your computer"
            exit 1
        }
    }
    
    if (-not (New-VirtualEnvironment $VenvPath)) {
        exit 1
    }
}

# Step 4: Install/verify dependencies
if (-not (Test-CriticalPackagesInstalled $VenvPython)) {
    Write-Info "Installing dependencies"
    if (-not (Install-Requirements $VenvPip $RequirementsFile)) {
        exit 1
    }
    
    # Verify again after installation
    if (-not (Test-CriticalPackagesInstalled $VenvPython)) {
        Write-ErrorMsg "Some required packages still missing after installation"
        exit 1
    }
}

# Step 5: Set PYTHONPATH to ensure local modules are found
$env:PYTHONPATH = $ScriptDir

# Step 6: Run the application
Write-Host ""
Write-Host "Starting Kryten-Robot..." -ForegroundColor Green
if (Test-Path $ConfigPath) {
    Write-Host "Config: $ConfigPath" -ForegroundColor Gray
    $configArg = @("--config", $ConfigPath)
} else {
    Write-Host "Using default config paths" -ForegroundColor Gray
    $configArg = @()
}
if ($LogLevel) {
    Write-Host "Log Level: $LogLevel" -ForegroundColor Gray
    $env:KRYTEN_LOG_LEVEL = $LogLevel
}
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

try {
    & $VenvPython -m kryten @configArg
    
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    if ($exitCode -eq 0) {
        Write-Success "Kryten-Robot stopped cleanly"
    } else {
        Write-ErrorMsg "Kryten-Robot exited with error code: $exitCode"
    }
    
    exit $exitCode
} catch {
    Write-Host ""
    Write-ErrorMsg "Failed to execute Kryten-Robot: $_"
    Write-Info "Check logs for details"
    exit 1
}

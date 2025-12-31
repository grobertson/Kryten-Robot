# Kryten-Robot PyPI Publishing Script
# Version: 0.5.1
# 
# This script automates building and publishing kryten-robot to PyPI.
# It handles cleaning, building, and optionally publishing the package.

param(
    [switch]$Build,
    [switch]$Publish,
    [switch]$TestPyPI,
    [switch]$Clean,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Colors
$InfoColor = "Green"
$WarnColor = "Yellow"
$ErrorColor = "Red"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $InfoColor
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor $WarnColor
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $ErrorColor
}

function Show-Help {
    Write-Host @"
Kryten-Robot PyPI Publishing Script
====================================

Usage: .\publish.ps1 [OPTIONS]

Options:
    -Clean      Clean build artifacts (dist/, build/, *.egg-info/)
    -Build      Build the package (creates wheel and source distribution)
    -TestPyPI   Publish to TestPyPI (for testing before production)
    -Publish    Publish to production PyPI
    -Help       Show this help message

Examples:
    # Clean and build
    .\publish.ps1 -Clean -Build

    # Build and publish to TestPyPI
    .\publish.ps1 -Build -TestPyPI

    # Build and publish to production PyPI
    .\publish.ps1 -Build -Publish

    # Just clean
    .\publish.ps1 -Clean

Prerequisites:
    1. Poetry installed: pip install poetry
    2. PyPI API token configured: poetry config pypi-token.pypi YOUR-TOKEN
    3. (Optional) TestPyPI token: poetry config pypi-token.testpypi YOUR-TOKEN

"@
}

# Show help if requested or no parameters
if ($Help -or (-not ($Build -or $Publish -or $TestPyPI -or $Clean))) {
    Show-Help
    exit 0
}

Write-Info "Kryten-Robot PyPI Publishing Script"
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check Poetry is installed
try {
    $poetryVersion = poetry --version 2>$null
    Write-Info "Poetry version: $poetryVersion"
} catch {
    Write-Error "Poetry is not installed or not in PATH"
    Write-Host "Install with: pip install poetry"
    exit 1
}

# Read version from pyproject.toml
if (Test-Path "pyproject.toml") {
    $version = (Select-String -Path "pyproject.toml" -Pattern 'version = "(.*)"').Matches.Groups[1].Value
    Write-Info "Package version: $version"
} else {
    Write-Error "pyproject.toml not found"
    exit 1
}

# Clean build artifacts
if ($Clean) {
    Write-Info "Cleaning build artifacts..."
    $paths = @("dist", "build", "*.egg-info", "kryten.egg-info")
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
            Write-Info "Removed: $path"
        }
    }
    Write-Info "Clean complete"
}

# Build package
if ($Build) {
    Write-Info "Building package..."
    Write-Host ""
    
    try {
        poetry build
        Write-Host ""
        Write-Info "Build complete!"
        
        # Show what was built
        if (Test-Path "dist") {
            Write-Info "Built packages:"
            Get-ChildItem "dist" | ForEach-Object {
                Write-Host "  - $($_.Name)" -ForegroundColor Cyan
            }
        }
    } catch {
        Write-Error "Build failed: $_"
        exit 1
    }
}

# Publish to TestPyPI
if ($TestPyPI) {
    Write-Host ""
    Write-Info "Publishing to TestPyPI..."
    Write-Warn "This will upload to https://test.pypi.org/"
    
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Info "Cancelled"
        exit 0
    }
    
    try {
        # Configure TestPyPI repository if not already done
        poetry config repositories.testpypi https://test.pypi.org/legacy/ 2>$null
        
        poetry publish -r testpypi
        Write-Host ""
        Write-Info "Published to TestPyPI!"
        Write-Info "View at: https://test.pypi.org/project/kryten-robot/$version/"
        Write-Info "Install with: pip install --index-url https://test.pypi.org/simple/ kryten-robot"
    } catch {
        Write-Error "TestPyPI publish failed: $_"
        Write-Warn "Make sure you have configured TestPyPI token:"
        Write-Host "  poetry config pypi-token.testpypi YOUR-TOKEN"
        exit 1
    }
}

# Publish to production PyPI
if ($Publish) {
    Write-Host ""
    Write-Warn "Publishing to PRODUCTION PyPI..."
    Write-Warn "This will make version $version publicly available!"
    Write-Host ""
    
    $confirm = Read-Host "Are you sure? (yes/N)"
    if ($confirm -ne "yes") {
        Write-Info "Cancelled (you must type 'yes' to confirm)"
        exit 0
    }
    
    try {
        poetry publish
        Write-Host ""
        Write-Info "Published to PyPI!"
        Write-Info "View at: https://pypi.org/project/kryten-robot/$version/"
        Write-Info "Install with: pip install kryten-robot"
        Write-Info "Upgrade with: pip install --upgrade kryten-robot"
    } catch {
        Write-Error "PyPI publish failed: $_"
        Write-Warn "Make sure you have configured PyPI token:"
        Write-Host "  poetry config pypi-token.pypi YOUR-TOKEN"
        exit 1
    }
}

Write-Host ""
Write-Info "Done!"

#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VENV_PATH="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_PATH/bin/python"
VENV_PIP="$VENV_PATH/bin/pip"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
CONFIG_FILE="${1:-config.json}"
CONFIG_PATH="$SCRIPT_DIR/$CONFIG_FILE"

# Color output functions
print_success() { echo -e "\033[32m✓ $1\033[0m"; }
print_info() { echo -e "\033[36mℹ $1\033[0m"; }
print_warning() { echo -e "\033[33m⚠ $1\033[0m"; }
print_error() { echo -e "\033[31m✗ $1\033[0m"; }

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found in PATH"
        print_info "Install Python 3.11+ from your package manager"
        return 1
    fi
    
    local version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)
    
    if [[ $major -eq 3 && $minor -ge 11 ]] || [[ $major -gt 3 ]]; then
        print_success "Found Python $version"
        return 0
    else
        print_error "Python 3.11+ required, found: $version"
        return 1
    fi
}

# Check if venv is valid
check_venv() {
    local path=$1
    
    if [[ ! -d "$path" ]]; then
        return 1
    fi
    
    if [[ ! -f "$path/bin/python" ]] || [[ ! -f "$path/bin/pip" ]]; then
        print_warning "Virtual environment incomplete or corrupted"
        return 1
    fi
    
    # Test if python actually works
    if ! "$path/bin/python" -c "import sys" &> /dev/null; then
        print_warning "Virtual environment Python is not functional"
        return 1
    fi
    
    return 0
}

# Create virtual environment
create_venv() {
    local path=$1
    
    print_info "Creating virtual environment at $path"
    
    if ! python3 -m venv "$path"; then
        print_error "Failed to create virtual environment"
        return 1
    fi
    
    if ! check_venv "$path"; then
        print_error "Created venv is not valid"
        return 1
    fi
    
    print_success "Virtual environment created successfully"
    return 0
}

# Install or update requirements
install_requirements() {
    local pip_exe=$1
    local requirements_path=$2
    
    if [[ ! -f "$requirements_path" ]]; then
        print_error "Requirements file not found: $requirements_path"
        return 1
    fi
    
    print_info "Installing/updating dependencies from requirements.txt"
    
    if ! "$pip_exe" install --upgrade pip --quiet; then
        print_error "Failed to upgrade pip"
        return 1
    fi
    
    if ! "$pip_exe" install -r "$requirements_path" --upgrade; then
        print_error "Failed to install dependencies"
        print_info "Try manually: $pip_exe install -r $requirements_path"
        return 1
    fi
    
    print_success "Dependencies installed successfully"
    return 0
}

# Verify critical packages are installed
check_critical_packages() {
    local python_exe=$1
    local all_installed=0
    
    for pkg in nats socketio aiohttp websockets; do
        if "$python_exe" -c "import $pkg" &> /dev/null; then
            print_success "$pkg package is installed"
        else
            print_warning "$pkg package not found"
            all_installed=1
        fi
    done
    
    return $all_installed
}

# Main execution
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Kryten-Robot (CyTube Connector) Startup"
echo "═══════════════════════════════════════════════════════"
echo ""

# Step 1: Check Python
if ! check_python; then
    exit 1
fi

# Step 2: Check configuration file
if [[ ! -f "$CONFIG_PATH" ]]; then
    print_error "Configuration file not found: $CONFIG_PATH"
    print_info "Available config files:"
    for f in "$SCRIPT_DIR"/config*.json; do
        if [[ -f "$f" ]]; then
            print_info "  - $(basename "$f")"
        fi
    done
    exit 1
fi
print_success "Configuration file found: $CONFIG_FILE"

# Step 3: Check/Create venv
if ! check_venv "$VENV_PATH"; then
    print_warning "Virtual environment needs to be created or repaired"
    
    # Remove corrupted venv if it exists
    if [[ -d "$VENV_PATH" ]]; then
        print_info "Removing corrupted virtual environment"
        if ! rm -rf "$VENV_PATH"; then
            print_error "Could not remove corrupted venv"
            print_info "Delete manually: rm -rf $VENV_PATH"
            exit 1
        fi
    fi
    
    if ! create_venv "$VENV_PATH"; then
        exit 1
    fi
fi

# Step 4: Install/verify dependencies
if ! check_critical_packages "$VENV_PYTHON"; then
    print_info "Installing dependencies"
    if ! install_requirements "$VENV_PIP" "$REQUIREMENTS_FILE"; then
        exit 1
    fi
    
    # Verify again after installation
    if ! check_critical_packages "$VENV_PYTHON"; then
        print_error "Some required packages still missing after installation"
        exit 1
    fi
fi

# Step 5: Clear PYTHONPATH to avoid conflicts, then set for local modules
export PYTHONPATH=""
export PYTHONPATH="$SCRIPT_DIR"

# Step 6: Run the application
echo ""
echo -e "\033[32mStarting Kryten-Robot...\033[0m"
if [[ -f "$CONFIG_PATH" ]]; then
    echo -e "\033[90mConfig: $CONFIG_PATH\033[0m"
    CONFIG_ARG="--config $CONFIG_PATH"
else
    echo -e "\033[90mUsing default config paths\033[0m"
    CONFIG_ARG=""
fi
if [[ -n "$KRYTEN_LOG_LEVEL" ]]; then
    echo -e "\033[90mLog Level: $KRYTEN_LOG_LEVEL\033[0m"
fi
echo -e "\033[90mPress Ctrl+C to stop\033[0m"
echo ""

exec $VENV_PYTHON -m kryten $CONFIG_ARG

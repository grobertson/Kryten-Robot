#!/bin/bash
# Kryten Robot Installation Script
# Version: 0.5.1
# 
# This script installs Kryten Robot as a systemd service.
# It handles user creation, directory setup, virtual environment,
# and systemd service configuration.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_DIR="/opt/kryten"
INSTALL_DIR="${BASE_DIR}/Kryten-Robot"
CONFIG_DIR="${BASE_DIR}/etc"
LOG_DIR="${BASE_DIR}/logs"
SERVICE_USER="kryten"
SERVICE_GROUP="kryten"
VENV_DIR="${INSTALL_DIR}/venv"
SYSTEMD_DIR="/etc/systemd/system"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

print_info "Kryten Robot Installation Script v0.5.1"
echo "========================================"
echo ""

# Step 1: Create system user if it doesn't exist
print_info "Step 1: Creating system user..."
if id "$SERVICE_USER" &>/dev/null; then
    print_warn "User '$SERVICE_USER' already exists"
else
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
    print_info "Created user '$SERVICE_USER'"
fi

# Step 2: Create directories
print_info "Step 2: Creating directories..."
mkdir -p "$BASE_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
print_info "Created directories: $INSTALL_DIR, $CONFIG_DIR, $LOG_DIR"

# Step 3: Check for Python 3.11+
print_info "Step 3: Checking Python version..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON_CMD="$cmd"
            print_info "Found Python $VERSION at $(which $cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    print_error "Python 3.11 or higher is required but not found"
    print_error "Please install Python 3.11+ and try again"
    exit 1
fi

# Step 4: Create virtual environment
print_info "Step 4: Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    print_warn "Virtual environment already exists at $VENV_DIR"
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        print_info "Recreated virtual environment"
    else
        print_info "Using existing virtual environment"
    fi
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    print_info "Created virtual environment at $VENV_DIR"
fi

# Step 5: Install/upgrade kryten-robot from PyPI
print_info "Step 5: Installing kryten-robot from PyPI..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install --upgrade kryten-robot
print_info "Installed kryten-robot"

# Step 6: Create example config if none exists
print_info "Step 6: Checking configuration..."
CONFIG_FILE="$CONFIG_DIR/kryten-robot-config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f "./config.example.json" ]; then
        cp "./config.example.json" "$CONFIG_FILE"
        print_info "Created kryten-robot-config.json from example"
        print_warn "IMPORTANT: Edit $CONFIG_FILE with your settings before starting the service"
    else
        # Create minimal config
        cat > "$INSTALL_DIR/config.json" <<'EOF'
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "YOUR_CHANNEL",
    "user": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  },
  "nats": {
    "servers": ["nats://localhost:4222"],
    "max_reconnect_attempts": 10,
    "reconnect_time_wait": 5
  },
  "health": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 28080
  },
  "commands": {
    "enabled": true
  },
  "logging": {
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
      "standard": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      }
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "level": "INFO",
        "formatter": "standard",
        "stream": "ext://sys.stdout"
      },
      "file": {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "DEBUG",
        "formatter": "standard",
        "filename": "/opt/kryten/logs/kryten-robot.log",
        "maxBytes": 10485760,
        "backupCount": 5
      }
    },
    "root": {
      "level": "INFO",
      "handlers": ["console", "file"]
    }
  },
  "log_level": "INFO"
}
EOF
        print_info "Created minimal kryten-robot-config.json"
        print_warn "IMPORTANT: Edit $CONFIG_FILE with your settings before starting the service"
    fi
else
    print_info "Configuration file already exists at $CONFIG_FILE"
fi

# Step 7: Set ownership
print_info "Step 7: Setting ownership..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$BASE_DIR"
print_info "Set ownership to $SERVICE_USER:$SERVICE_GROUP"

# Step 8: Install systemd service
print_info "Step 8: Installing systemd service..."
if [ -f "./systemd/kryten.service" ]; then
    cp "./systemd/kryten.service" "$SYSTEMD_DIR/kryten.service"
    systemctl daemon-reload
    print_info "Installed systemd service"
else
    print_warn "systemd/kryten.service not found in current directory"
    print_warn "You may need to manually install the service file"
fi

# Step 9: Summary and next steps
echo ""
print_info "Installation complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit configuration: sudo nano $CONFIG_FILE"
echo "  2. Enable service:     sudo systemctl enable kryten"
echo "  3. Start service:      sudo systemctl start kryten"
echo "  4. Check status:       sudo systemctl status kryten"
echo "  5. View logs:          sudo journalctl -u kryten -f"
echo "  6. Or view log file:   sudo tail -f $LOG_DIR/kryten-robot.log"
echo ""
echo "To upgrade in the future:"
echo "  sudo $VENV_DIR/bin/pip install --upgrade kryten-robot"
echo "  sudo systemctl restart kryten"
echo ""
print_warn "Remember to configure NATS server before starting Kryten!"
print_warn "See systemd/README.md for NATS setup instructions."

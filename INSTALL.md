# Quick Installation Guide

## Installation Options

### Option 1: PyPI (Recommended for Production)

Install the latest release from PyPI:

```bash
pip install kryten-robot
```

Upgrade to latest version:

```bash
pip install --upgrade kryten-robot
```

### Option 2: systemd Service (Linux Production Deployment)

For automated Linux server deployment with systemd:

```bash
# Clone repository
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot

# Run installer (requires root)
sudo bash install.sh
```

This will:
- Create `/opt/kryten` base directory
- Create `/opt/kryten/Kryten-Robot` for the application
- Create `/opt/kryten/etc` for configuration files
- Create `/opt/kryten/logs` for all log files
- Create `kryten` system user
- Set up Python virtual environment
- Install kryten-robot from PyPI
- Install systemd service
- Create example config file

After installation:

```bash
# Edit configuration
sudo nano /opt/kryten/etc/kryten-robot-config.json

# Enable and start service
sudo systemctl enable kryten
sudo systemctl start kryten

# Check status
sudo systemctl status kryten

# View logs
sudo journalctl -u kryten -f
```

### Option 3: Development Installation

For development or contributing:

```bash
# Clone repository
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install in editable mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Configuration

All installations require a `config.json` file. See `config.example.json` for a template.

Minimum configuration:

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "your-channel",
    "user": "bot-username",
    "password": "bot-password"
  },
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "health": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 28080
  },
  "commands": {
    "enabled": true
  },
  "log_level": "INFO"
}
```

## Running

### Command Line

```bash
# Using installed command
kryten-robot config.json

# Or as Python module
python -m kryten config.json

# With custom log level
kryten-robot config.json --log-level DEBUG
```

### As systemd Service

```bash
# Start
sudo systemctl start kryten

# Stop
sudo systemctl stop kryten

# Restart
sudo systemctl restart kryten

# Status
sudo systemctl status kryten

# Logs
sudo journalctl -u kryten -f
```

## Verification

Check health endpoint:

```bash
curl http://localhost:28080/health
```

Expected response:

```json
{
  "status": "healthy",
  "cytube_connected": true,
  "nats_connected": true,
  "channel": "your-channel",
  "uptime_seconds": 42.5
}
```

## Upgrading

### PyPI Installation

```bash
pip install --upgrade kryten-robot
```

### systemd Service

```bash
# Upgrade package
sudo /opt/kryten/Kryten-Robot/venv/bin/pip install --upgrade kryten-robot

# Restart service
sudo systemctl restart kryten

# Verify new version
sudo journalctl -u kryten -n 20
```

## Troubleshooting

### Can't connect to CyTube

- Verify credentials in `config.json`
- Check CyTube server is accessible
- Ensure bot account exists and has channel access

### Can't connect to NATS

- Verify NATS server is running: `nats-server -v`
- Check NATS server URL in `config.json`
- Verify firewall rules allow connection

### Service won't start (systemd)

```bash
# Check service status
sudo systemctl status kryten

# View recent logs
sudo journalctl -u kryten -n 50

# Check configuration
sudo -u kryten /opt/kryten/Kryten-Robot/venv/bin/python -m kryten /opt/kryten/etc/kryten-robot-config.json
```

## Next Steps

- See `README.md` for full documentation
- See `KRYTEN_ARCHITECTURE.md` for architecture overview
- See `systemd/README.md` for detailed systemd setup
- See `PUBLISHING.md` for publishing to PyPI

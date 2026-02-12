# Kryten-Robot v0.9.1 Release Notes

## Overview

Version 0.9.1 adds support for connecting to CyTube as a guest user, with automatic command safety controls.

## Changes in v0.9.1

### New Features

- ✅ **Guest Mode Support**
  - Connect to CyTube as a guest user without credentials
  - Set `"guest_mode": true` in configuration
  - Commands are automatically force-disabled in guest mode for safety
  - Guest name can be customized via `user` field (defaults to "Guest")
  - Perfect for read-only monitoring or public channels

### Configuration Updates

- ✅ **New `guest_mode` Option**
  - Added to `CytubeConfig` in configuration
  - Documented in `CONFIG.md` with examples
  - Updated example configs: `config.example.json`, `kryten/config.example.json`

### Security

- 🔒 **Command Safety**
  - Commands are unconditionally disabled when `guest_mode: true`
  - Prevents accidental command execution with guest credentials
  - Clear logging indicates when guest mode is active

### Developer Experience

- 📝 **Enhanced Logging**
  - Startup banner shows "Mode: GUEST (commands disabled)"
  - Ready message indicates guest mode status
  - Clear warnings if commands are disabled due to guest mode

## Example Configuration

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "YourChannel",
    "guest_mode": true,
    "user": "KrytenGuest"
  }
}
```

---

# Kryten-Robot v0.5.1 Release Notes

## Overview

Version 0.5.1 adds proper PyPI packaging and systemd service installation support, making production deployment significantly easier.

## Changes in v0.5.1

### New Features

- ✅ **Automated Installation Script** (`install.sh`)
  - Creates system user and directories
  - Sets up Python virtual environment
  - Installs from PyPI automatically
  - Configures systemd service
  - Creates example configuration

- ✅ **Publishing Automation** (`publish.ps1`, `publish.sh`)
  - Automates build and publish process
  - Supports TestPyPI for testing
  - Clean and rebuild commands
  - Confirmation prompts for production

- ✅ **Installation Documentation** (`INSTALL.md`)
  - Quick start guide
  - Multiple installation options
  - Upgrade procedures
  - Troubleshooting

### Package Configuration

- ✅ **Config File Protection**
  - `config.json` and `config-*.json` excluded from source control
  - Excluded from package distribution
  - `config.example.json` included as template

- ✅ **Distribution Contents**
  - Python package with all modules
  - systemd service files
  - Installation script
  - Documentation (README, INSTALL, KRYTEN_ARCHITECTURE)
  - Example configuration

### Bug Fixes

- 🐛 **Fixed Startup Banner Error**
  - Fixed "Action cannot be empty after normalization" error on Linux
  - Issue was in `print_startup_banner()` calling `build_command_subject()` with wildcard
  - Wildcard was being normalized to empty string, causing validation error

## Changes in v0.5.0

### Architecture Updates

- ✅ **Unified Command Pattern**
  - All services now use single command subject: `kryten.{service}.command`
  - Consistent request/response format across all services
  - Command routing via `command` field in payload

- ✅ **State Query API**
  - Request/reply pattern for querying channel state
  - Commands: `state.emotes`, `state.playlist`, `state.userlist`, `state.user`, `state.profiles`, `state.all`, `system.health`
  - Supports correlation IDs for distributed tracing

- ✅ **Documentation**
  - `KRYTEN_ARCHITECTURE.md` - Comprehensive architecture overview
  - `STATE_QUERY_IMPLEMENTATION.md` - State query API details
  - `LIFECYCLE_EVENTS.md` - Connection lifecycle events

### Breaking Changes

- ⚠️ **Command Subject Changed**
  - Old: `kryten.commands.cytube.{channel}.{action}`
  - New: `kryten.robot.command`
  - Requires updating any services that send commands to Kryten-Robot

## Installation

### From PyPI (New!)

```bash
# Install latest version
pip install kryten-robot

# Upgrade existing installation
pip install --upgrade kryten-robot
```

### systemd Service (New!)

```bash
# Clone repository
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot

# Run installer
sudo bash install.sh

# Configure and start
sudo nano /opt/kryten/config.json
sudo systemctl enable kryten
sudo systemctl start kryten
```

### From Source

```bash
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot
pip install -e .
```

## Upgrading from v0.4.x

1. **Update Code**
   - Update command subjects from `kryten.commands.cytube.*` to `kryten.robot.command`
   - Update command payload format to include `service` and `command` fields

2. **Install v0.5.1**
   ```bash
   pip install --upgrade kryten-robot
   ```

3. **Restart Services**
   ```bash
   # If using systemd
   sudo systemctl restart kryten
   
   # If running manually
   kryten-robot config.json
   ```

## Publishing to PyPI

For maintainers:

### Using PowerShell Script

```powershell
# Clean and build
.\publish.ps1 -Clean -Build

# Test on TestPyPI
.\publish.ps1 -TestPyPI

# Publish to production
.\publish.ps1 -Publish
```

### Using Bash Script

```bash
# Clean and build
./publish.sh --clean --build

# Test on TestPyPI
./publish.sh --testpypi

# Publish to production
./publish.sh --publish
```

### Manual Process

```bash
# Configure PyPI token (first time only)
poetry config pypi-token.pypi YOUR-TOKEN

# Build and publish
poetry build
poetry publish
```

## Configuration

All installations require a `config.json` file. Minimum configuration:

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

## Verification

Check service is running:

```bash
# Health check
curl http://localhost:28080/health

# systemd status
sudo systemctl status kryten

# View logs
sudo journalctl -u kryten -f
```

## Documentation

- `README.md` - Main documentation
- `INSTALL.md` - Installation guide
- `KRYTEN_ARCHITECTURE.md` - Architecture overview
- `STATE_QUERY_IMPLEMENTATION.md` - State query API
- `LIFECYCLE_EVENTS.md` - Connection lifecycle
- `PUBLISHING.md` - Publishing to PyPI
- `systemd/README.md` - systemd setup details

## Support

- GitHub Issues: https://github.com/grobertson/kryten-robot/issues
- Repository: https://github.com/grobertson/kryten-robot
- PyPI: https://pypi.org/project/kryten-robot/

## Credits

Kryten Robot Team

## License

MIT License - See LICENSE file for details

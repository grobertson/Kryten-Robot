# Kryten-Robot v1.1.3 Release Notes

## Overview

Version 1.1.3 enhances guest mode to operate as a truly passive observer without requiring NATS infrastructure.

## Changes in v1.1.3

### New Features

- ✅ **Guest Mode Now Fully Passive**
  - No NATS connection established when `guest_mode: true`
  - No event publishing or broadcasting to message bus
  - Disables all NATS-dependent components (lifecycle, service registry, state manager, command handlers)
  - Bot now operates as pure observer - connects to CyTube and receives events locally only
  - Health monitoring remains active for basic connectivity checks
  - Perfect for monitoring channels without requiring infrastructure

### Improvements

- ✅ **Codebase Cleanup**
  - Removed unused temporary files and old utility scripts
  - Removed obsolete patch files
  - Removed setup.py (now using pyproject.toml exclusively)

### Technical Details

**Guest Mode Architecture:**
- CyTube connection: ✅ Active (anonymous, no username)
- Event reception: ✅ Active (local only)
- Event publishing: ❌ Disabled (no NATS broadcast)
- NATS connection: ❌ Disabled
- State persistence: ❌ Disabled (no KV stores)
- Command handling: ❌ Disabled
- Lifecycle events: ❌ Disabled
- Health endpoint: ✅ Active

### Use Cases

- Monitor channels without affecting message bus
- Observe events for debugging without side effects
- Run without NATS infrastructure dependency
- Lightweight passive monitoring scenarios

### Configuration

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "your-channel",
    "guest_mode": true
  }
}
```

### Testing

- ✅ All 50 unit tests passing
- ✅ Tested with live CyTube connection in guest mode
- ✅ Verified no NATS connection attempts
- ✅ Verified no event publishing

---

# Kryten-Robot v1.0.2 Release Notes

## Overview

Version 1.0.2 fixes anonymous guest mode to properly connect without sending login credentials.

## Changes in v1.0.2

### Bug Fixes

- ✅ **Fixed Anonymous Guest Mode Connection**
  - Anonymous guest mode now properly skips the login event entirely
  - Previously attempted to send empty login payload, causing server timeout
  - Bot now simply joins channel without authentication (matching CyTube's anonymous protocol)
  - Anonymous guests remain invisible in channel user list as intended
  - Commands remain force-disabled in guest mode for safety

### Technical Details

- Modified `_authenticate_user()` to skip login when `guest_mode: true`
- User rank automatically set to 0 (anonymous guest)
- No breaking changes - existing configurations work unchanged
- Matches CyTube's behavior for anonymous web clients

### Testing

- ✅ All 50 unit tests passing
- ✅ Tested with live CyTube connection in guest mode
- ✅ Successfully receives events without appearing in user list

### Configuration

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "your-channel",
    "guest_mode": true
  }
}
```

---

# Kryten-Robot v1.0.1 Release Notes

## Overview

Version 1.0.1 improves reconnection behavior by suppressing historical chat message floods.

## Changes in v1.0.1

### Improvements

- ✅ **Suppress Historical Chat on Reconnect**
  - CyTube sends historical chat messages when clients reconnect (for catch-up)
  - This flood of old messages is now automatically suppressed for 3 seconds after reconnection
  - Only applies to reconnections - initial connection still receives full history
  - Prevents unnecessary processing of stale chat data
  - Improves performance and reduces noise in logs/NATS events

### Technical Details

- Added `_suppress_chat_history` flag to track reconnection state
- Chat messages filtered during 3-second suppression window
- All other event types process normally
- Suppression automatically clears after delay

### Testing

- ✅ All 50 unit tests passing
- ✅ Backward compatible - no breaking changes

---

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

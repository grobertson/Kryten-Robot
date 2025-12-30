# Kryten-Robot

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/kryten-robot.svg)](https://pypi.org/project/kryten-robot/)

**Kryten-Robot** is a CyTube to NATS bridge connector that connects to CyTube chat servers via Socket.IO and publishes all events to a NATS message bus. This enables building distributed microservice architectures around CyTube channels.

## Overview

Kryten-Robot acts as the central bridge between CyTube and your microservices:

- **Connects** to CyTube servers via Socket.IO
- **Publishes** all CyTube events to NATS with structured subjects
- **Subscribes** to command subjects to control CyTube
- **Maintains** connection health with automatic reconnection
- **Tracks** channel state (users, playlist, emotes)
- **Exposes** state query API via NATS request/reply

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│   CyTube    │◄───────►│ Kryten-Robot │◄───────►│   NATS Server   │
│   Server    │ Socket  │   (Bridge)   │  Pub/   │                 │
└─────────────┘  .IO    └──────────────┘  Sub    └─────────────────┘
                                                          ▲
                                                          │
                    ┌─────────────────────────────────────┴──────────┐
                    │                                                 │
              ┌─────▼──────┐    ┌──────────────┐    ┌──────────────┐
              │ kryten-cli │    │kryten-       │    │  Your Custom │
              │  (Control) │    │userstats     │    │ Microservice │
              └────────────┘    └──────────────┘    └──────────────┘
```

## Features

- ✅ **Full CyTube Event Coverage**: All Socket.IO events published to NATS
- ✅ **Unified Command Pattern**: Single subject per service (`kryten.robot.command`)
- ✅ **State Management**: Real-time tracking of users, playlist, emotes
- ✅ **State Query API**: Request/reply for current channel state
- ✅ **Connection Resilience**: Automatic reconnection with exponential backoff
- ✅ **Health Monitoring**: HTTP health endpoint for orchestration
- ✅ **Correlation IDs**: Distributed tracing support
- ✅ **Structured Logging**: JSON logs with correlation context

## Installation

### From PyPI

```bash
pip install kryten-robot
```

### As systemd Service (Linux)

For production deployments on Linux with systemd:

```bash
# Clone the repository
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot

# Run installation script (requires root)
sudo bash install.sh
```

The installer will:
- Create system user and directories
- Set up Python virtual environment
- Install kryten-robot from PyPI
- Configure systemd service
- Create example config file

See `systemd/README.md` for detailed setup instructions.

### From Source

```bash
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot
pip install -e .
```

### With Poetry

```bash
uv add kryten-robot
```

## Quick Start

### 1. Create Configuration File

Create `config.json`:

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "your-channel",
    "user": "your-bot-username",
    "password": "your-bot-password"
  },
  "nats": {
    "servers": ["nats://localhost:4222"],
    "user": null,
    "password": null,
    "max_reconnect_attempts": 60,
    "reconnect_time_wait": 2
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
    "format": "text",
    "correlation_id": true
  },
  "log_level": "INFO"
}
```

### 2. Run Kryten-Robot

```bash
# Using the installed command
kryten-robot config.json

# Or with Python module
python -m kryten config.json

# With custom log level
kryten-robot config.json --log-level DEBUG
```

### 3. Verify Operation

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

## NATS Subject Structure

### Event Publishing

All CyTube events are published to:
```
kryten.events.cytube.{channel}.{event_name}
```

Examples:
- `kryten.events.cytube.420grindhouse.chatmsg` - Chat messages
- `kryten.events.cytube.420grindhouse.adduser` - User joins
- `kryten.events.cytube.420grindhouse.userleave` - User leaves
- `kryten.events.cytube.420grindhouse.changeMedia` - Video changes

### Command Subscription

Kryten-Robot accepts commands on:
```
kryten.robot.command
```

Command payload:
```json
{
  "service": "robot",
  "command": "state.userlist",
  "correlation_id": "optional-trace-id"
}
```

Available commands:
- `state.emotes` - Get all channel emotes
- `state.playlist` - Get current playlist
- `state.userlist` - Get all users in channel
- `state.user` - Get specific user info (requires `username` param)
- `state.profiles` - Get all user profiles
- `state.all` - Get complete channel state
- `system.health` - Get system health status
- `system.channels` - Get list of connected channels
- `system.version` - Get Kryten-Robot version

## Configuration Reference

### CyTube Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `domain` | string | Yes | CyTube server domain (e.g., "cytu.be") |
| `channel` | string | Yes | Channel name to connect to |
| `user` | string | Yes | Bot account username |
| `password` | string | Yes | Bot account password |

### NATS Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `servers` | array | Yes | - | NATS server URLs |
| `user` | string | No | null | NATS authentication user |
| `password` | string | No | null | NATS authentication password |
| `max_reconnect_attempts` | int | No | 60 | Max reconnection attempts |
| `reconnect_time_wait` | int | No | 2 | Seconds between reconnect attempts |

### Health Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | No | true | Enable HTTP health endpoint |
| `host` | string | No | "0.0.0.0" | Health endpoint bind address |
| `port` | int | No | 28080 | Health endpoint port |

### Commands Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | No | true | Enable command subscriber |

### Logging Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `format` | string | No | "text" | Log format: "text" or "json" |
| `correlation_id` | bool | No | true | Include correlation IDs |

### Root Level

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `log_level` | string | No | "INFO" | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |

## Running as a Service

### Systemd (Linux)

See [systemd/README.md](systemd/README.md) for complete systemd service configuration.

Quick setup:
```bash
sudo cp systemd/kryten-robot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kryten-robot
sudo systemctl start kryten-robot
```

### Windows Service

Use NSSM (Non-Sucking Service Manager):
```powershell
nssm install kryten-robot "C:\Python311\python.exe" "-m kryten config.json"
nssm set kryten-robot AppDirectory "C:\opt\kryten-robot"
nssm start kryten-robot
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/grobertson/kryten-robot.git
cd kryten-robot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=kryten --cov-report=html
```

### Code Quality

```bash
# Format code
black kryten/

# Lint
ruff check kryten/

# Type checking
mypy kryten/
```

## Integration Examples

### Using kryten-py Library

```python
from kryten import KrytenClient, KrytenConfig

config = KrytenConfig.from_json("config.json")

async with KrytenClient(config) as client:
    # Query current userlist
    response = await client.nats_request(
        "kryten.robot.command",
        {"service": "robot", "command": "state.userlist"}
    )
    
    if response["success"]:
        users = response["data"]["users"]
        print(f"Users online: {len(users)}")
```

### Using kryten-cli

```bash
# Get current playlist
kryten list queue

# Get all users
kryten list users

# Get channel emotes
kryten list emotes
```

## Architecture Documentation

- **[KRYTEN_ARCHITECTURE.md](KRYTEN_ARCHITECTURE.md)** - System architecture and patterns
- **[STATE_QUERY_IMPLEMENTATION.md](STATE_QUERY_IMPLEMENTATION.md)** - State query API details
- **[LIFECYCLE_EVENTS.md](LIFECYCLE_EVENTS.md)** - Lifecycle event handling
- **[AUDIT_LOGGING.md](AUDIT_LOGGING.md)** - Audit logging implementation

## Troubleshooting

### Connection Issues

**Problem**: Kryten-Robot won't connect to CyTube
- Verify credentials in config.json
- Check if channel name is correct
- Ensure CyTube server is accessible

**Problem**: NATS connection failures
- Verify NATS server is running: `nats-server -v`
- Check NATS server URL in config
- Test NATS connectivity: `nats-cli pub test "hello"`

### Performance Issues

**Problem**: High memory usage
- Check for excessive event backlog
- Verify NATS consumers are processing events
- Monitor with health endpoint: `curl http://localhost:28080/health`

**Problem**: Events not being published
- Check log level is INFO or DEBUG
- Verify NATS subjects with `nats-cli sub "kryten.events.>"`
- Check correlation logs for event flow

## Requirements

- Python 3.11 or higher
- NATS server 2.9.0 or higher
- CyTube server (any version with Socket.IO support)

## Related Projects

- **[kryten-py](https://github.com/grobertson/kryten-py)** - Python library for building Kryten microservices
- **[kryten-userstats](https://github.com/grobertson/kryten-userstats)** - User statistics tracking service
- **[kryten-cli](https://github.com/grobertson/kryten-cli)** - Command-line control interface

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run tests and linting (`pytest && black . && ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/grobertson/kryten-robot/issues)
- **Documentation**: [GitHub Repository](https://github.com/grobertson/kryten-robot)

## Changelog

### v0.5.0 (2025-12-08)

**Major Changes:**
- ✅ Unified command pattern: All services now use `kryten.{service}.command`
- ✅ State query API: Request/reply interface for channel state
- ✅ Fixed startup banner bug with wildcard normalization
- ✅ PyPI packaging: Now installable via `pip install kryten-robot`

**API Updates:**
- Changed: Command subjects from `kryten.commands.cytube.*` to `kryten.robot.command`
- Added: State query commands (state.emotes, state.playlist, etc.)
- Added: System health command via NATS

**Documentation:**
- Added: KRYTEN_ARCHITECTURE.md with comprehensive architecture overview
- Updated: All examples to use unified command pattern
- Added: PyPI publication workflow

---

**Built with ❤️ for the CyTube community**

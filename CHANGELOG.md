# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.3] - 2025-12-28

### Fixed
- **Command Handling Overlap**: Fixed race condition where `RobotCommandHandler` would erroneously reply with "Unknown command" for valid `system.channels` requests intended for `StateQueryHandler`. Both handlers now ignore unknown commands instead of sending error replies.

## [0.7.2] - 2025-12-28

### Changed
- **Test Suite Updates**: Updated tests to match client-side subject builder changes (`kryten.robot.command` instead of `kryten.command.robot`).

## [0.6.13] - 2025-12-15

### Added

- **System Services Command**: `system.services` command in StateQueryHandler
  - Lists all registered microservices with version, hostname, and status
  - Shows health and metrics endpoint URLs for each service
  - Returns active vs stale service counts (stale = no heartbeat in 90+ seconds)

- **Enhanced Service Registration Logging**: Improved log output when services register
  - Logs health and metrics ports when services register or restart
  - Format: `Service registered: name vX.Y.Z on hostname | health=:port/path | metrics=:port/path`

### Changed

- **ServiceInfo Extended**: Added health/metrics endpoint fields
  - `health_port`, `health_path`, `metrics_port`, `metrics_path`
  - `health_url` and `metrics_url` properties for full URLs
  - Endpoints extracted from lifecycle event metadata

## [0.6.12] - 2025-12-15

### Fixed

- **System Stats API Response Keys**: Fixed `system.stats` command to return correct keys
  - `events.total_published` instead of `events.published`
  - `commands.total_received` instead of `commands.received`
  - `commands.succeeded` instead of `commands.executed`
  - `commands.rate_5min` was missing, now included
  - `connections.cytube.connected_since` instead of `uptime_seconds` (now ISO8601 timestamp)
  - `connections.nats.connected_since` instead of `uptime_seconds` (now ISO8601 timestamp)
  - `connections.nats.connected_url` instead of `server`
  - `state.users`, `state.playlist`, `state.emotes` instead of verbose names
  - These changes align with kryten-py client documentation and kryten-cli expectations

## [0.6.9] - 2025-12-13

### Changed

- **Sync release**: Version sync with kryten ecosystem (kryten-py 0.9.4, kryten-cli 2.3.1, kryten-userstats 0.5.1)

## [0.5.4] - 2025-12-09

### Added

- **Version Discovery**: Added `system.version` command to StateQueryHandler
  - Returns semantic version string of running Kryten-Robot instance
  - Enables client applications to check compatibility
  - Allows enforcement of minimum server version requirements
  - Useful for feature detection and graceful degradation

## [0.5.3] - 2025-12-09

### Added

- **Channel Discovery**: Added `system.channels` command to StateQueryHandler
  - Returns list of connected channels for auto-discovery by CLI tools
  - Enables kryten-cli to automatically find available channels
  - Structured for future multi-channel support

## [0.5.2] - 2025-12-09

### Changed

- **Compatibility**: Lowered minimum Python version requirement from 3.11 to 3.10
  - No Python 3.11+ specific features are used in the codebase
  - Dependencies support Python 3.10

## [0.5.1] - 2025-12-08

### Fixed

- **Startup Banner**: Fixed wildcard normalization bug that caused "Action cannot be empty after normalization" error
  - Issue occurred when displaying startup banner with action wildcards
  - Now properly handles action normalization before displaying

### Added

- **Installation**: Added systemd service integration for Linux deployments
  - New `install.sh` script for automated installation
  - Systemd service file with proper permissions and logging
  - Standardized directory structure: /opt/kryten/{etc,logs,Kryten-Robot}
  
- **PyPI Publishing**: Added GitHub Actions workflow for automated PyPI releases
  - Triggers on GitHub release publication
  - Uses trusted publishing (OIDC) for secure deployments
  - Automated version management via poetry

### Changed

- **Configuration**: Standardized config file naming with service prefix
  - Config files now use pattern: `{service}-config.json`
  - Example: `kryten-robot-config.json`

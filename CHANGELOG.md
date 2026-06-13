# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.0] - 2026-06-13

### Added
- **AFK state is now tracked live via the `setAFK` event** — `StateManager` previously only captured a user's `meta.afk` flag at join time (from `userlist`/`addUser`), so it went stale as soon as a user toggled AFK afterward. The connector now subscribes to CyTube's `setAFK` event and a new `StateManager.set_user_afk(username, afk)` merges the flag into the stored user's `meta` in place — preserving rank, profile, and other `meta` keys — and persists it to the `*_userlist` KV bucket. Unknown users and no-op toggles are skipped (no redundant KV write). This lets downstream consumers (e.g. kryten-webqueue presence-based refunds) rely on `state.user`'s `meta.afk` being current.

## [1.9.0] - 2026-06-07

### Added
- **`uid` on persisted now-playing state** — The `current` key in the `kryten_{channel}_playlist` KV bucket now includes the playlist `uid` of the now-playing item. CyTube's `changeMedia` payload carries only media metadata (`id`, `title`, `seconds`, `type`) with no uid; the uid arrives separately via the `setCurrent` event (emitted immediately before `changeMedia` on every media change). `StateManager` now listens for `setCurrent`, tracks the authoritative current uid, and stamps it onto the persisted now-playing object. If no uid is known it falls back to matching the media against the cached playlist by `id`/`type`. This lets downstream consumers (e.g. kryten-webqueue) map the now-playing item back to its playlist position for relative queue insertion.

## [1.8.0] - 2026-06-04

### Changed
- **`addvideo` now reports CyTube `queueFail` in the command response** — `_handle_add_video` registers a `queueFail` callback alongside the existing `queue` callback. When CyTube rejects the media (e.g. a manifest URL that returns HTTP 302), the command resolves immediately with `{success: false, error: <reason>, queue_fail: {...}}` instead of waiting out the 8-second timeout. The failure reason (matched to the requested media id when available) becomes the single source of truth so callers no longer have to listen on the `queueFail` events channel. The event is still published to `kryten.events.cytube.channel-z.queuefail` for backward compatibility.

## [0.8.1] - 2025-12-31

### Changed
- **Release**: Patch version bump for ecosystem synchronization.

## [0.8.0] - 2025-12-31

### Changed
- **Release**: Minor version bump for coordinated ecosystem release.

## [0.7.5] - 2025-12-31

### Fixed
- **Linting**: Fixed linting and typing issues in test scripts (`scripts/`).
- **CI**: Enforced clean linting state for CI/CD.

## [0.7.4] - 2025-12-31

### Fixed
- **CI/Linting Compliance**: Fixed 100+ mypy type errors, resolved ruff linting issues, and applied black formatting.
- **Test Suite Stability**: Removed broken tests and organized manual scripts into `scripts/` directory.
- **Health Monitor**: Fixed attribute error in health monitor server by introducing `KrytenHealthServer` class.

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

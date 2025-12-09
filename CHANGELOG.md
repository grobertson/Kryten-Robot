# Changelog

All notable changes to Kryten-Robot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

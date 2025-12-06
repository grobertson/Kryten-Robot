# TASK-001: Initialize Python Project Structure

**Sprint**: 1 (Foundation & Core Infrastructure)  
**Estimated Duration**: 2-4 hours  
**Prerequisites**: None  
**Related Specifications**: 
- [Architecture Specification](./spec-architecture-design.md) - Section 4.5 (Project Structure)
- [Requirements](./requirements.md) - Implementation Notes

## Objective

Set up the foundational Python project structure with proper package organization, configuration files, and development tooling.

## Context

This task establishes the base project layout that all subsequent development will build upon. The structure follows Python best practices with a src-layout pattern using the `llm_bot` package name.

## Requirements

### Directory Structure

Create the following directory structure:

```
llm/
├── spec/                        # (Already exists - specification documents)
│   ├── requirements.md
│   ├── spec-architecture-design.md
│   ├── spec-configuration.md
│   ├── spec-data-contracts.md
│   ├── spec-observability.md
│   └── spec-triggers-ratelimiting.md
├── llm_bot/                     # Main package
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   ├── config.py                # Configuration loading (Sprint 1)
│   ├── nats_client.py           # NATS connection (Sprint 1)
│   ├── event_handler.py         # Event processing (Sprint 2)
│   ├── context_window.py        # Chat context management (Sprint 2)
│   ├── triggers/                # Trigger implementations (Sprint 3)
│   │   ├── __init__.py
│   │   ├── base.py              # Base trigger class
│   │   ├── mention.py           # Mention trigger
│   │   ├── keyword.py           # Keyword trigger
│   │   ├── contextual.py        # Contextual trigger
│   │   └── pm.py                # PM trigger
│   ├── llm_client.py            # LLM API client (Sprint 4)
│   ├── response_processor.py   # Response filtering (Sprint 4)
│   ├── rate_limiter.py          # Rate limit enforcement (Sprint 3)
│   ├── health.py                # Health and metrics HTTP server (Sprint 6)
│   ├── logging_config.py        # Logging setup (Sprint 1)
│   └── shutdown_handler.py      # Graceful shutdown (Sprint 6)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_context_window.py
│   │   ├── test_triggers.py
│   │   ├── test_rate_limiter.py
│   │   └── test_response_processor.py
│   └── integration/
│       ├── __init__.py
│       ├── test_event_flow.py
│       └── test_multi_channel.py
├── config.example.yaml          # Example configuration
├── .gitignore                   # Git ignore patterns
├── pyproject.toml               # Package metadata and build config
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
└── README.md                    # Project overview
```

### File Contents

#### `llm_bot/__init__.py`

```python
"""
LLM Chat Bot - OpenAI-compatible LLM integration with CyTube via NATS.

This package provides a standalone daemon that monitors CyTube chat activity
through NATS messaging and responds intelligently using Large Language Models.
"""

__version__ = "0.1.0"
__author__ = "Kryten Robot Team"
```

#### `llm_bot/__main__.py`

```python
"""Entry point for the LLM Chat Bot application."""

import sys
import asyncio


def main():
    """Main entry point (placeholder for Sprint 6)."""
    print("LLM Chat Bot - Starting...")
    print("Entry point will be implemented in Sprint 6 (TASK-052)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### `tests/__init__.py`

```python
"""Test suite for LLM Chat Bot."""
```

#### `tests/conftest.py`

```python
"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_config():
    """Sample configuration for testing (placeholder)."""
    return {
        "nats": {
            "servers": ["nats://localhost:4222"]
        },
        "channels": [
            {"name": "testchannel", "enabled": True}
        ],
        "bot": {
            "username": "TestBot",
            "aliases": ["bot"]
        }
    }
```

#### `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Configuration
config.yaml
*.env
.env

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db
```

#### `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "llm-chat-bot"
version = "0.1.0"
description = "OpenAI-compatible LLM integration with CyTube via NATS"
readme = "README.md"
requires-python = ">=3.11"
authors = [
    {name = "Kryten Robot Team"}
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "nats-py>=2.6.0",
    "httpx>=0.25.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.5.0",
    "pyyaml>=6.0.0",
    "prometheus-client>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-aiohttp>=1.0.5",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "flake8>=6.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
llm-bot = "llm_bot.__main__:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.black]
line-length = 100
target-version = ['py311']

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

#### `README.md`

```markdown
# LLM Chat Bot

OpenAI-compatible LLM integration with CyTube chat through NATS messaging.

## Overview

A standalone Python daemon that monitors CyTube chat activity and responds intelligently using Large Language Models while maintaining tight control over response frequency, length, and relevance.

**Key Design Principle**: NATS is the only integration point. This bot never directly connects to CyTube - all communication flows through the Kryten connector via NATS.

## Architecture

```
CyTube <-> Kryten Connector <-> NATS <-> LLM Bot <-> LLM API
```

## Requirements

- Python 3.11 or higher
- NATS server (localhost or remote)
- Kryten connector (publishing CyTube events to NATS)
- OpenAI-compatible LLM API

## Installation

(To be completed in later sprints)

## Configuration

(To be completed in later sprints)

## Running

(To be completed in later sprints)

## Development

See [spec/](./spec/) directory for detailed specifications.

## License

(To be determined)
```

## Implementation Steps

1. **Create main package directory**
   ```powershell
   New-Item -ItemType Directory -Path "llm_bot" -Force
   New-Item -ItemType Directory -Path "llm_bot/triggers" -Force
   ```

2. **Create test directories**
   ```powershell
   New-Item -ItemType Directory -Path "tests/unit" -Force
   New-Item -ItemType Directory -Path "tests/integration" -Force
   ```

3. **Create all `__init__.py` files**
   ```powershell
   New-Item -ItemType File -Path "llm_bot/__init__.py"
   New-Item -ItemType File -Path "llm_bot/triggers/__init__.py"
   New-Item -ItemType File -Path "tests/__init__.py"
   New-Item -ItemType File -Path "tests/unit/__init__.py"
   New-Item -ItemType File -Path "tests/integration/__init__.py"
   ```

4. **Create entry point and configuration files**
   - Create `llm_bot/__main__.py` with placeholder main function
   - Create `tests/conftest.py` with basic pytest fixtures
   - Create `.gitignore` with Python patterns
   - Create `pyproject.toml` with project metadata
   - Create `README.md` with overview

5. **Create placeholder module files** (empty for now, will be implemented in later sprints)
   ```powershell
   # These files can be empty initially
   New-Item -ItemType File -Path "llm_bot/config.py"
   New-Item -ItemType File -Path "llm_bot/nats_client.py"
   New-Item -ItemType File -Path "llm_bot/event_handler.py"
   New-Item -ItemType File -Path "llm_bot/context_window.py"
   New-Item -ItemType File -Path "llm_bot/llm_client.py"
   New-Item -ItemType File -Path "llm_bot/response_processor.py"
   New-Item -ItemType File -Path "llm_bot/rate_limiter.py"
   New-Item -ItemType File -Path "llm_bot/health.py"
   New-Item -ItemType File -Path "llm_bot/logging_config.py"
   New-Item -ItemType File -Path "llm_bot/shutdown_handler.py"
   ```

6. **Verify structure**
   ```powershell
   tree /F llm_bot
   tree /F tests
   ```

## Acceptance Criteria

- [ ] All directories created with correct structure
- [ ] All `__init__.py` files present
- [ ] `pyproject.toml` contains correct metadata and dependencies
- [ ] `.gitignore` excludes appropriate files
- [ ] `llm_bot/__main__.py` runs without errors: `python -m llm_bot`
- [ ] README.md contains project overview
- [ ] Project structure matches specification document

## Testing

```powershell
# Verify package can be imported
python -c "import llm_bot; print(llm_bot.__version__)"

# Verify entry point runs
python -m llm_bot

# Expected output: "LLM Chat Bot - Starting..."
```

## Notes

- All placeholder files should have docstrings but no implementation
- The structure is designed to support incremental development across sprints
- Module files will be populated in subsequent tasks
- The `spec/` directory already exists and should not be modified

## Next Tasks

- **TASK-002**: Define and install dependencies in requirements.txt
- **TASK-003**: Implement Config model with Pydantic validation

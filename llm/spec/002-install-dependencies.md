# TASK-002: Define and Install Dependencies

**Sprint**: 1 (Foundation & Core Infrastructure)  
**Estimated Duration**: 1-2 hours  
**Prerequisites**: TASK-001 (Project structure initialized)  
**Related Specifications**: 
- [Requirements](./requirements.md) - Technology Stack

## Objective

Define all production and development dependencies and create a reproducible Python virtual environment with all required packages installed.

## Context

This task sets up the dependency management for the project, ensuring all team members and deployment environments have consistent package versions. We use both `requirements.txt` (for production) and `requirements-dev.txt` (for development/testing).

## Requirements

### Production Dependencies

Create `requirements.txt` with the following packages:

```txt
# NATS messaging client
nats-py==2.7.0

# HTTP client for LLM API calls (async)
httpx==0.27.0

# HTTP server for health/metrics endpoints (async)
aiohttp==3.9.3

# Data validation and settings management
pydantic==2.6.1
pydantic-settings==2.1.0

# YAML configuration parsing
ruamel.yaml==0.18.6

# Prometheus metrics
prometheus-client==0.19.0

# Python 3.11+ requirement marker
# Minimum Python version enforced by pyproject.toml
```

### Development Dependencies

Create `requirements-dev.txt` with the following packages:

```txt
# Include all production dependencies
-r requirements.txt

# Testing framework
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-aiohttp==1.0.5
pytest-cov==4.1.0
pytest-timeout==2.2.0

# Code formatting
black==24.1.1

# Linting
flake8==7.0.0
flake8-docstrings==1.7.0

# Type checking
mypy==1.8.0
types-pyyaml==6.0.12.12

# Development tools
ipython==8.20.0
```

### Package Justification

| Package | Purpose | Why This Version |
|---------|---------|------------------|
| `nats-py` | NATS client for event subscription/publishing | Latest stable with async support |
| `httpx` | Async HTTP client for LLM API calls | Modern async client, better than aiohttp for client requests |
| `aiohttp` | Async HTTP server for health/metrics | Industry standard for async web servers |
| `pydantic` | Data validation for config and events | v2 for better performance and features |
| `ruamel.yaml` | YAML parsing with comment preservation | Better than PyYAML for config files with comments |
| `prometheus-client` | Metrics collection and exposition | Official Prometheus client |
| `pytest` | Testing framework | Industry standard |
| `pytest-asyncio` | Async test support | Required for async/await tests |
| `black` | Code formatting | Consistent code style |
| `mypy` | Static type checking | Catch type errors early |

## Implementation Steps

### 1. Create requirements.txt

```powershell
# Navigate to project root (llm directory)
cd llm

# Create requirements.txt file
@"
# NATS messaging client
nats-py==2.7.0

# HTTP client for LLM API calls (async)
httpx==0.27.0

# HTTP server for health/metrics endpoints (async)
aiohttp==3.9.3

# Data validation and settings management
pydantic==2.6.1
pydantic-settings==2.1.0

# YAML configuration parsing
ruamel.yaml==0.18.6

# Prometheus metrics
prometheus-client==0.19.0
"@ | Out-File -FilePath requirements.txt -Encoding utf8
```

### 2. Create requirements-dev.txt

```powershell
@"
# Include all production dependencies
-r requirements.txt

# Testing framework
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-aiohttp==1.0.5
pytest-cov==4.1.0
pytest-timeout==2.2.0

# Code formatting
black==24.1.1

# Linting
flake8==7.0.0
flake8-docstrings==1.7.0

# Type checking
mypy==1.8.0
types-pyyaml==6.0.12.12

# Development tools
ipython==8.20.0
"@ | Out-File -FilePath requirements-dev.txt -Encoding utf8
```

### 3. Create Python Virtual Environment

```powershell
# Create virtual environment with Python 3.11+
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Verify Python version (must be 3.11+)
python --version
# Expected: Python 3.11.x or 3.12.x
```

### 4. Upgrade pip

```powershell
# Upgrade pip to latest version
python -m pip install --upgrade pip
```

### 5. Install Dependencies

```powershell
# Install development dependencies (includes production deps via -r)
pip install -r requirements-dev.txt

# Verify installation
pip list
```

### 6. Generate Lock File (Optional but Recommended)

```powershell
# Generate pip freeze output for exact versions
pip freeze > requirements-lock.txt

# This file can be used for reproducible deployments
```

### 7. Verify Installations

```powershell
# Test key imports
python -c "import nats; print('nats-py:', nats.__version__)"
python -c "import httpx; print('httpx:', httpx.__version__)"
python -c "import aiohttp; print('aiohttp:', aiohttp.__version__)"
python -c "import pydantic; print('pydantic:', pydantic.__version__)"
python -c "from ruamel.yaml import YAML; print('ruamel.yaml: OK')"
python -c "import prometheus_client; print('prometheus_client: OK')"
python -c "import pytest; print('pytest:', pytest.__version__)"
```

### 8. Update .gitignore for Virtual Environment

Ensure `.gitignore` includes virtual environment patterns (should already be present from TASK-001):

```
# Virtual environments
venv/
ENV/
env/
.venv
```

## Acceptance Criteria

- [ ] `requirements.txt` created with all production dependencies
- [ ] `requirements-dev.txt` created with all development dependencies
- [ ] Virtual environment created successfully
- [ ] All dependencies installed without errors
- [ ] All packages can be imported in Python
- [ ] `pip list` shows correct versions of all packages
- [ ] Python version is 3.11 or higher
- [ ] Virtual environment excluded from git via `.gitignore`

## Testing

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run verification script
python -c @"
import sys
assert sys.version_info >= (3, 11), 'Python 3.11+ required'

# Test production imports
import nats
import httpx
import aiohttp
import pydantic
from ruamel.yaml import YAML
import prometheus_client

# Test dev imports
import pytest
import black
import mypy

print('✓ All dependencies installed successfully')
print(f'✓ Python version: {sys.version}')
"@
```

## Troubleshooting

### Issue: Python Version Too Old

**Symptom**: `python --version` shows Python 3.10 or earlier

**Solution**:
```powershell
# Download and install Python 3.11+ from python.org
# Or use pyenv/conda to manage Python versions

# Verify correct Python in PATH
where.exe python
```

### Issue: Package Installation Fails

**Symptom**: `pip install` fails with compilation errors

**Solution**:
```powershell
# Update pip and setuptools
python -m pip install --upgrade pip setuptools wheel

# Try installing again
pip install -r requirements-dev.txt
```

### Issue: Import Errors After Installation

**Symptom**: `ImportError` when testing imports

**Solution**:
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall packages
pip install --force-reinstall -r requirements-dev.txt
```

## Notes

- Pin exact versions in `requirements.txt` for reproducibility
- Use `pip install -r requirements-dev.txt` for development
- Use `pip install -r requirements.txt` for production deployments
- Consider using `pip-tools` or `poetry` for more advanced dependency management in the future
- The `requirements-lock.txt` file captures the exact dependency tree for deployments

## Next Tasks

- **TASK-003**: Implement Config model with Pydantic validation
- **TASK-004**: Implement environment variable substitution

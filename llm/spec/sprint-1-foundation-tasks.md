# Sprint 1 Tasks: Foundation & Core Infrastructure

**Duration**: 2 weeks  
**Focus**: Project setup, configuration system, NATS integration, data models, and observability foundation

## Overview

Sprint 1 establishes the foundational infrastructure for the LLM Chat Bot. By the end of this sprint, you should have a runnable (though minimally functional) bot with proper configuration loading, NATS connectivity, and observability endpoints.

## Tasks in This Sprint

### TASK-004: Implement Environment Variable Substitution

**Estimated Duration**: 2-3 hours  
**Prerequisites**: TASK-003  
**Related Specs**: [Configuration Specification](./spec-configuration.md) - Section 4.1, 9

**Objective**: Implement `${VAR_NAME}` substitution in YAML configuration before Pydantic parsing.

**Implementation Pattern**:

```python
# In llm_bot/config.py, add before Config class:

import os
import re

def substitute_env_vars(yaml_content: str) -> str:
    """
    Substitute ${VAR_NAME} patterns with environment variable values.
    
    Args:
        yaml_content: Raw YAML content as string
        
    Returns:
        YAML content with substitutions applied
        
    Raises:
        ValueError: If referenced environment variable not found
    """
    pattern = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')
    
    def replacer(match):
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            raise ValueError(
                f"Environment variable '{var_name}' not found. "
                f"Required for configuration substitution."
            )
        return value
    
    return pattern.sub(replacer, yaml_content)
```

**Testing**:

```python
# tests/unit/test_config.py

def test_env_var_substitution():
    os.environ['TEST_API_KEY'] = 'secret-key-123'
    yaml_content = "api_key: ${TEST_API_KEY}"
    result = substitute_env_vars(yaml_content)
    assert result == "api_key: secret-key-123"

def test_missing_env_var_raises():
    yaml_content = "api_key: ${MISSING_VAR}"
    with pytest.raises(ValueError, match="MISSING_VAR"):
        substitute_env_vars(yaml_content)
```

**Acceptance Criteria**:
- [ ] Regex matches ${VAR_NAME} pattern
- [ ] Substitutes with os.environ.get()
- [ ] Raises ValueError if variable not found
- [ ] Handles multiple substitutions in one file
- [ ] Tests pass

---

### TASK-005: Implement Config.load() with YAML Parsing

**Estimated Duration**: 3-4 hours  
**Prerequisites**: TASK-004  
**Related Specs**: [Configuration Specification](./spec-configuration.md) - Section 4.5

**Objective**: Implement static method to load YAML file, apply substitution, and parse into Config model.

**Implementation Pattern**:

```python
# In llm_bot/config.py, add to Config class:

from ruamel.yaml import YAML
from pathlib import Path

class Config(BaseModel):
    # ... existing fields ...
    
    @classmethod
    def load(cls, config_path: str | Path) -> "Config":
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml file
            
        Returns:
            Validated Config instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config invalid or env vars missing
            ValidationError: If Pydantic validation fails
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        # Read YAML content
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        
        # Apply environment variable substitution
        yaml_content = substitute_env_vars(yaml_content)
        
        # Parse YAML
        yaml = YAML()
        config_dict = yaml.load(yaml_content)
        
        # Validate with Pydantic
        return cls(**config_dict)
```

**Testing**:

```python
# tests/unit/test_config.py

def test_config_load_valid_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
nats:
  servers:
    - nats://localhost:4222
channels:
  - name: test
    enabled: true
bot:
  username: TestBot
llm_api:
  base_url: https://api.openai.com/v1
  api_key: sk-test
  model: gpt-4o-mini
""")
    
    config = Config.load(config_file)
    assert config.bot.username == "TestBot"
    assert len(config.channels) == 1

def test_config_load_missing_file():
    with pytest.raises(FileNotFoundError):
        Config.load("nonexistent.yaml")
```

**Acceptance Criteria**:
- [ ] Loads YAML file from path
- [ ] Applies environment variable substitution
- [ ] Parses with ruamel.yaml
- [ ] Validates with Pydantic
- [ ] Raises appropriate errors
- [ ] Tests pass

---

### TASK-006: Create config.example.yaml

**Estimated Duration**: 2-3 hours  
**Prerequisites**: TASK-005  
**Related Specs**: [Configuration Specification](./spec-configuration.md) - Section 4.1

**Objective**: Create comprehensive example configuration file with inline comments.

**Implementation Pattern**:

Copy the complete YAML schema from spec-configuration.md Section 4.1 into `config.example.yaml` at the project root. Ensure all sections are documented with comments.

**File Structure**:
```yaml
# NATS connection settings
nats:
  # List of NATS server URLs (required)
  servers:
    - nats://localhost:4222
  # Optional: NATS authentication
  user: null
  password: null  # Use ${NATS_PASSWORD} for env var substitution
  connect_timeout: 5
  max_reconnect_attempts: 5

# CyTube channels to monitor (required, at least one)
channels:
  - name: mainchannel
    enabled: true
    # Optional per-channel overrides...

# Bot identity (required)
bot:
  username: MyBot
  aliases:
    - bot
    - assistant

# LLM API configuration (required)
llm_api:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}  # Environment variable substitution
  model: gpt-4o-mini
  # ... rest of config with comments ...
```

**Testing**:
```powershell
# Verify example config is valid
python -c "from llm_bot.config import Config; Config.load('config.example.yaml')"
```

**Acceptance Criteria**:
- [ ] Contains all configuration sections
- [ ] Inline comments explain each field
- [ ] Uses ${ENV_VAR} for sensitive values
- [ ] Provides examples for all trigger types
- [ ] File validates without errors (with env vars set)

---

### TASK-007: Implement Configuration Reload (SIGHUP)

**Estimated Duration**: 3-4 hours  
**Prerequisites**: TASK-005  
**Related Specs**: [Configuration Specification](./spec-configuration.md) - Section 4.4

**Objective**: Implement SIGHUP signal handler to reload configuration without restart.

**Implementation Pattern**:

```python
# In llm_bot/config.py or new llm_bot/config_reload.py:

import signal
import asyncio
from typing import Callable, Optional
from pathlib import Path

class ConfigReloader:
    """Handles configuration reload on SIGHUP signal."""
    
    def __init__(
        self,
        config_path: Path,
        on_reload: Callable[[Config], None]
    ):
        self.config_path = config_path
        self.on_reload = on_reload
        self.current_config: Optional[Config] = None
        
    def setup_signal_handler(self):
        """Register SIGHUP handler (POSIX only)."""
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._handle_sighup)
    
    def _handle_sighup(self, signum, frame):
        """Handle SIGHUP signal."""
        asyncio.create_task(self.reload_config())
    
    async def reload_config(self):
        """
        Reload configuration from file.
        
        Steps:
        1. Load new config file
        2. Validate new config
        3. Wait for in-flight operations (max 5s)
        4. Swap config atomically
        5. Call on_reload callback
        """
        try:
            # Load and validate new config
            new_config = Config.load(self.config_path)
            
            # Wait for in-flight operations
            await asyncio.sleep(0.1)  # Brief pause
            
            # Swap config
            old_config = self.current_config
            self.current_config = new_config
            
            # Notify callback
            if self.on_reload:
                self.on_reload(new_config)
                
            print(f"Configuration reloaded successfully")
            
        except Exception as e:
            print(f"Config reload failed: {e}")
            # Keep old config on failure
```

**Testing**:

```python
# tests/unit/test_config_reload.py

import signal
import os

def test_config_reload(tmp_path):
    config_file = tmp_path / "config.yaml"
    # Write initial config...
    
    reloaded = []
    def on_reload(config):
        reloaded.append(config)
    
    reloader = ConfigReloader(config_file, on_reload)
    
    # Trigger reload
    asyncio.run(reloader.reload_config())
    
    assert len(reloaded) == 1
```

**Acceptance Criteria**:
- [ ] Registers SIGHUP handler on POSIX systems
- [ ] Loads new config file
- [ ] Validates before applying
- [ ] Keeps old config if new config invalid
- [ ] Calls on_reload callback
- [ ] Tests pass

---

### TASK-008: Implement NATSClient Class

**Estimated Duration**: 4-6 hours  
**Prerequisites**: TASK-003  
**Related Specs**: [Architecture Specification](./spec-architecture-design.md) - Section 4.1

**Objective**: Implement async NATS client with connection management, subscription, and publishing.

**Implementation Pattern**:

```python
# llm_bot/nats_client.py

import asyncio
import nats
from nats.aio.client import Client as NATS
from typing import Callable, Optional, List
import logging

logger = logging.getLogger(__name__)

class NATSClient:
    """Async NATS client for event subscription and command publishing."""
    
    def __init__(self, config: NATSConfig):
        self.config = config
        self.nc: Optional[NATS] = None
        self._subscriptions = {}
        
    async def connect(self) -> None:
        """
        Connect to NATS with exponential backoff retry.
        
        Raises:
            ConnectionError: If all retry attempts exhausted
        """
        self.nc = NATS()
        
        for attempt in range(self.config.max_reconnect_attempts):
            try:
                await self.nc.connect(
                    servers=self.config.servers,
                    user=self.config.user,
                    password=self.config.password,
                    connect_timeout=self.config.connect_timeout,
                )
                logger.info("Connected to NATS")
                return
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(
                    f"NATS connection failed (attempt {attempt + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
        
        raise ConnectionError("Failed to connect to NATS after all retries")
    
    async def subscribe(
        self,
        subject: str,
        callback: Callable
    ) -> None:
        """Subscribe to NATS subject with callback."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")
            
        sub = await self.nc.subscribe(subject, cb=callback)
        self._subscriptions[subject] = sub
        logger.info(f"Subscribed to: {subject}")
    
    async def publish(
        self,
        subject: str,
        data: bytes,
        headers: Optional[dict] = None
    ) -> None:
        """Publish message to NATS subject."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")
            
        await self.nc.publish(subject, data, headers=headers)
    
    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self.nc is not None and self.nc.is_connected
    
    async def disconnect(self) -> None:
        """Gracefully disconnect from NATS."""
        if self.nc:
            await self.nc.drain()
            await self.nc.close()
            logger.info("Disconnected from NATS")
```

**Testing**:

```python
# tests/unit/test_nats_client.py

@pytest.mark.asyncio
async def test_nats_connect():
    config = NATSConfig(servers=["nats://localhost:4222"])
    client = NATSClient(config)
    
    # Note: Requires NATS server running for integration test
    # For unit test, mock nats.connect()
```

**Acceptance Criteria**:
- [ ] Connects to NATS with config
- [ ] Implements exponential backoff retry
- [ ] Subscribe method stores subscriptions
- [ ] Publish method sends messages
- [ ] is_connected() checks connection state
- [ ] disconnect() drains and closes
- [ ] Logging at appropriate levels

---

## Remaining Sprint 1 Tasks

### TASK-009 through TASK-015

Follow the same pattern as above for:

- **TASK-009**: Correlation ID extraction/generation
- **TASK-010**: Dynamic subscription management
- **TASK-011**: NATS event Pydantic models (see spec-data-contracts.md Section 4.1)
- **TASK-012**: NATS command Pydantic models (see spec-data-contracts.md Section 4.2)
- **TASK-013**: Internal data structures (see spec-data-contracts.md Section 4.3)
- **TASK-014**: Structured JSON logging (see spec-observability.md Section 4.1)
- **TASK-015**: Prometheus metrics (see spec-observability.md Section 4.3)

Each task should follow this structure:
1. Extract requirements from specification
2. Write implementation with type hints
3. Add logging statements
4. Write unit tests
5. Verify acceptance criteria

## Sprint 1 Completion Criteria

By the end of Sprint 1, you should be able to:

- [ ] Load configuration from YAML file
- [ ] Substitute environment variables in config
- [ ] Connect to NATS server
- [ ] Subscribe to event subjects
- [ ] Publish command messages
- [ ] Parse NATS events into Pydantic models
- [ ] Generate structured JSON logs
- [ ] Expose Prometheus metrics
- [ ] Run basic integration test: receive event, log it, publish response

## Integration Test for Sprint 1

```python
# tests/integration/test_sprint1_foundation.py

@pytest.mark.asyncio
async def test_end_to_end_foundation():
    """Test complete Sprint 1 integration."""
    
    # Load config
    config = Config.load("config.example.yaml")
    
    # Connect to NATS
    client = NATSClient(config.nats)
    await client.connect()
    assert client.is_connected()
    
    # Subscribe to test subject
    received = []
    async def handler(msg):
        received.append(msg)
    
    await client.subscribe("test.subject", handler)
    
    # Publish test message
    await client.publish("test.subject", b'{"test": "data"}')
    
    # Wait for message
    await asyncio.sleep(0.1)
    assert len(received) == 1
    
    # Disconnect
    await client.disconnect()
```

## Next Sprint

**Sprint 2**: Event Processing & Context Management (Tasks 016-022)

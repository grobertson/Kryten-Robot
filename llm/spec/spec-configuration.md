---
title: LLM Chat Bot Configuration Specification
version: 1.0
date_created: 2025-12-03
owner: Development Team
tags: [configuration, yaml, validation, reload]
---

# Introduction

This specification defines the configuration format, validation rules, and runtime reload behavior for the LLM Chat Bot. The configuration uses YAML format with support for inline comments and environment variable substitution.

## 1. Purpose & Scope

**Purpose**: Define the complete YAML configuration schema, validation rules, environment variable substitution, and runtime reload mechanism.

**Scope**: This specification covers:
- YAML configuration file structure
- Required and optional fields
- Validation rules and error handling
- Environment variable substitution syntax
- Runtime configuration reload (SIGHUP)
- Per-channel configuration overrides
- Default values and fallbacks

**Audience**: Software engineers implementing configuration loading, validation, and reload logic. DevOps engineers deploying and configuring the bot.

**Assumptions**:
- Configuration file named `config.yaml` in current directory or specified via `--config` flag
- YAML 1.2 syntax
- Environment variables available at process startup
- SIGHUP signal support on POSIX systems

## 2. Definitions

- **YAML**: Human-readable data serialization format
- **Environment Variable**: OS-level variable (e.g., `OPENAI_API_KEY`)
- **Substitution**: Replacing `${VAR_NAME}` with environment variable value
- **Validation**: Checking configuration against schema rules
- **Reload**: Re-loading configuration without process restart
- **Override**: Per-channel setting that replaces global default
- **Fallback**: Default value used when optional field missing

## 3. Requirements, Constraints & Guidelines

### Configuration Requirements

- **REQ-001**: Configuration SHALL use YAML format with inline comments
- **REQ-002**: Configuration SHALL support environment variable substitution (`${VAR_NAME}`)
- **REQ-003**: Configuration SHALL validate on load (fail fast if invalid)
- **REQ-004**: Configuration SHALL support per-channel overrides for triggers, prompts, models
- **REQ-005**: Configuration SHALL reload on SIGHUP without process restart

### Validation Constraints

- **CON-001**: Missing required fields MUST cause startup failure (exit code 1)
- **CON-002**: Invalid field values MUST cause startup failure with clear error message
- **CON-003**: Unknown fields MUST log warning but not fail (forward compatibility)
- **CON-004**: Environment variable substitution MUST fail if variable not set (no silent defaults)
- **CON-005**: Channel names MUST be unique (no duplicate channels)

### Configuration Guidelines

- **GUD-001**: Use descriptive comments for all top-level sections
- **GUD-002**: Provide `config.example.yaml` with all options documented
- **GUD-003**: Use reasonable defaults for optional fields
- **GUD-004**: Group related settings together (e.g., all rate limits in `rate_limits` section)
- **GUD-005**: Validate early (on load), not lazily (on use)

### Configuration Patterns

- **PAT-001**: Use nested dictionaries for logical grouping (e.g., `nats.servers`)
- **PAT-002**: Use arrays for lists of items (e.g., `channels`, `triggers`)
- **PAT-003**: Use lowercase_with_underscores for field names
- **PAT-004**: Use seconds for all time values (consistency)
- **PAT-005**: Use snake_case for field names, not camelCase

## 4. Interfaces & Data Contracts

### 4.1 Complete Configuration Schema

```yaml
# NATS connection settings
nats:
  # List of NATS server URLs
  servers:
    - nats://localhost:4222
  # Optional: NATS username (can use ${ENV_VAR})
  user: null
  # Optional: NATS password (can use ${ENV_VAR})
  password: null
  # Optional: Connection timeout in seconds
  connect_timeout: 5
  # Optional: Max reconnection attempts (0 = infinite)
  max_reconnect_attempts: 5

# CyTube channels to monitor (can specify multiple)
channels:
  - name: mainchannel
    enabled: true
    # Optional: Per-channel system prompt (overrides global)
    system_prompt: null
    # Optional: Per-channel LLM model (overrides global)
    llm_model: null
    # Optional: Per-channel triggers (overrides global)
    triggers: null
  
  - name: testchannel
    enabled: false

# Bot identity
bot:
  # Bot username (must match CyTube account)
  username: MyBot
  # Alternate names the bot responds to (case-insensitive)
  aliases:
    - bot
    - assistant

# LLM API configuration
llm_api:
  # Base URL for OpenAI-compatible API
  base_url: https://api.openai.com/v1
  # API key (use environment variable for security)
  api_key: ${OPENAI_API_KEY}
  # Model identifier
  model: gpt-4o-mini
  # Request timeout in seconds
  timeout_seconds: 30
  # Number of retry attempts on failure
  retry_attempts: 2
  # Delay between retries in seconds
  retry_delay_seconds: 1
  # Optional: System prompt (bot personality)
  system_prompt: |
    You are a helpful chat participant in a video watching community.
    Keep responses under 200 characters.
    Be concise, friendly, and relevant.
    Avoid repeating yourself.
  # Optional: User prompt template ({context_window}, {trigger_message} variables)
  user_prompt_template: |
    Recent chat:
    {context_window}
    
    Respond to: {trigger_message}
  # Optional: Include context in prompts
  include_context_in_prompt: true
  # Optional: Max context messages in prompt (most recent)
  max_context_messages: 20
  # Optional: LLM request parameters
  parameters:
    temperature: 0.7
    max_tokens: 100
    top_p: 0.9
    frequency_penalty: 0.5
    presence_penalty: 0.3
    stop:
      - "\n\n"
      - "User:"
      - "Assistant:"

# Trigger configurations (global defaults)
triggers:
  - type: mention
    enabled: true
    fire_probability: 1.0
    cooldown_seconds: 10
    rate_limit:
      max_per_user_per_minute: 2
      max_per_channel_per_minute: 5
  
  - type: keyword
    enabled: true
    keywords:
      - bot help
      - what do you think
      - any suggestions
    case_sensitive: false
    fire_probability: 0.3
    cooldown_seconds: 60
    rate_limit:
      max_per_hour: 10
  
  - type: contextual
    enabled: false  # Disabled by default (expensive)
    evaluation_interval_seconds: 120
    fire_probability: 0.1
    min_messages_since_last_bot_message: 5
    participation_prompt: "Based on this chat, would it be natural for you to add a comment? Reply ONLY 'yes' or 'no'."
    rate_limit:
      max_per_hour: 5
  
  - type: pm
    enabled: true
    fire_probability: 1.0
    cooldown_seconds: 5
    rate_limit:
      max_per_user_per_minute: 3

# Global rate limiting (applies across all triggers)
rate_limits:
  # Max bot messages per channel per time period
  max_per_channel_per_minute: 5
  max_per_channel_per_hour: 30
  # Max triggers per user per time period (spans all channels)
  max_per_user_per_minute: 3
  max_per_user_per_hour: 10
  # Global cooldown between any bot messages (seconds)
  global_cooldown_seconds: 5
  # Cooldown after media change (seconds)
  media_change_cooldown_seconds: 30

# Response processing and filtering
response_processing:
  # Max response length in characters
  max_response_length: 200
  # Truncation strategy: "hard" (cut at limit) or "sentence" (cut at sentence)
  truncation_strategy: sentence
  # Strip markdown formatting
  strip_markdown: true
  # Replace newlines with spaces
  collapse_newlines: true
  # Content filtering
  content_filter:
    enabled: true
    # Block responses containing these patterns (regex)
    block_patterns:
      - "http://"
      - "https://"
    # Block responses containing these keywords
    block_keywords:
      - inappropriate
      - offensive
    # Optional: Require responses to contain these keywords
    require_keywords: []
    # Min/max word count
    min_word_count: 2
    max_word_count: 50
  # Quality checks
  quality_checks_enabled: true
  # Check last N bot messages for duplicates
  deduplicate_window: 10
  # Optional: Fallback responses if LLM fails
  fallback_responses_enabled: false
  fallback_responses:
    - "Sorry, I'm having trouble responding right now."
    - "Let me think about that..."

# Context window settings
context_window:
  # Number of messages to retain per channel
  size: 50
  # Max age of messages in seconds (older messages dropped)
  max_age_seconds: 3600
  # Include usernames in context
  include_usernames: true
  # Include relative timestamps in context
  include_timestamps: false

# Health and metrics HTTP server
health:
  # Enable HTTP server
  enabled: true
  # Host to bind to (localhost for security)
  host: 127.0.0.1
  # Port to bind to
  port: 8080

# Logging configuration
log_level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 4.2 Required Fields

These fields MUST be present:

- `nats.servers` (array, min 1 server)
- `channels` (array, min 1 channel)
- `bot.username` (string)
- `llm_api.base_url` (string)
- `llm_api.api_key` (string, can use `${VAR}`)
- `llm_api.model` (string)

### 4.3 Optional Fields with Defaults

| Field | Default | Description |
|-------|---------|-------------|
| `nats.user` | `null` | NATS username |
| `nats.password` | `null` | NATS password |
| `nats.connect_timeout` | `5` | Connection timeout (seconds) |
| `nats.max_reconnect_attempts` | `5` | Max reconnect attempts |
| `bot.aliases` | `[]` | Alternate bot names |
| `llm_api.timeout_seconds` | `30` | LLM API timeout |
| `llm_api.retry_attempts` | `2` | Retry count |
| `llm_api.retry_delay_seconds` | `1` | Retry delay |
| `llm_api.system_prompt` | (default) | Bot personality |
| `llm_api.include_context_in_prompt` | `true` | Include chat history |
| `llm_api.max_context_messages` | `20` | Max context in prompt |
| `triggers` | (mention+pm only) | Trigger configs |
| `rate_limits.global_cooldown_seconds` | `5` | Min time between messages |
| `response_processing.max_response_length` | `200` | Max chars |
| `response_processing.strip_markdown` | `true` | Remove markdown |
| `context_window.size` | `50` | Messages per channel |
| `context_window.max_age_seconds` | `3600` | Max age (1 hour) |
| `health.enabled` | `true` | Enable HTTP server |
| `health.host` | `127.0.0.1` | Bind host |
| `health.port` | `8080` | Bind port |
| `log_level` | `INFO` | Logging level |

### 4.4 Per-Channel Overrides

Channels can override these global settings:

```yaml
channels:
  - name: gaming
    enabled: true
    # Override global system prompt
    system_prompt: "You are an enthusiastic gaming community member."
    # Override global model
    llm_model: gpt-4
    # Override global triggers (replaces, not merges)
    triggers:
      - type: mention
        fire_probability: 1.0
      - type: keyword
        keywords: ["gg", "nice play"]
        fire_probability: 0.5
```

**Override Behavior**:
- If field is `null` or omitted, use global default
- If field is specified, completely replace global setting (no merge)
- Triggers are replaced entirely (not merged with global)

### 4.5 Environment Variable Substitution

**Syntax**: `${VARIABLE_NAME}`

**Examples**:
```yaml
llm_api:
  api_key: ${OPENAI_API_KEY}
  base_url: ${LLM_API_URL}

nats:
  user: ${NATS_USER}
  password: ${NATS_PASSWORD}
```

**Behavior**:
- Substitution occurs during config load (before validation)
- If environment variable not set, fail with clear error message
- Supports substitution in any string field
- No default values (must be explicit in environment)

**Error Handling**:
```python
# If OPENAI_API_KEY not set:
raise ValueError(
    "Environment variable 'OPENAI_API_KEY' not found. "
    "Required by field 'llm_api.api_key'"
)
```

## 5. Acceptance Criteria

- **AC-001**: Given valid config.yaml, When bot starts, Then loads without error
- **AC-002**: Given missing required field, When bot starts, Then exits with code 1 and logs field name
- **AC-003**: Given invalid YAML syntax, When bot starts, Then exits with code 1 and logs line number
- **AC-004**: Given ${MISSING_VAR}, When bot starts, Then exits with code 1 and logs variable name
- **AC-005**: Given SIGHUP signal, When bot running, Then reloads config without restart
- **AC-006**: Given invalid reload config, When SIGHUP received, Then logs error and continues with old config
- **AC-007**: Given per-channel override, When trigger evaluates, Then uses channel-specific config
- **AC-008**: Given unknown field, When bot starts, Then logs warning but continues

## 6. Test Automation Strategy

- **Test Levels**: Unit tests for config loading, validation, override merging
- **Frameworks**: pytest, pytest-mock
- **Test Data**: YAML fixtures for valid/invalid configs
- **Validation Tests**: Test all required fields, type validation, range validation
- **Substitution Tests**: Mock environment variables, test substitution
- **Reload Tests**: Mock SIGHUP, verify config reloaded
- **Override Tests**: Verify channel config replaces global config

## 7. Rationale & Context

### Why YAML over JSON?

**Advantages of YAML**:
- Inline comments for documentation
- More human-friendly (no quotes for strings)
- Multi-line strings with `|` and `>`
- Better for configuration files

**Disadvantages**:
- More complex parsing (indentation-sensitive)
- Slower than JSON
- Multiple ways to represent same data

**Decision**: YAML's readability and comment support outweigh performance concerns for configuration files.

### Why Environment Variables for Secrets?

**Security Best Practices**:
- Never commit secrets to version control
- Environment variables are standard for containers/cloud
- Easy to rotate secrets without code changes
- Supported by systemd, Docker, Kubernetes

**Alternative Considered**: Separate secrets file
- Requires additional file management
- Harder to secure (file permissions)
- Not standard in containerized environments

### Why Fail Fast on Missing Variables?

**Philosophy**: Explicit is better than implicit.

**Alternatives Considered**:
1. Use empty string as default → Silent failures
2. Use placeholder like "MISSING" → Runtime errors
3. Allow `${VAR:-default}` syntax → More complex

**Decision**: Fail fast with clear error message. Easier to debug at startup than runtime.

### Why Per-Channel Overrides Replace (Not Merge)?

**Simplicity**: Easier to reason about. Channel config is self-contained.

**Example Confusion with Merge**:
```yaml
# Global
triggers:
  - type: mention
  - type: keyword

# Channel (merge would add, not replace)
channels:
  - name: test
    triggers:
      - type: pm  # Did user want mention+keyword+pm or just pm?
```

**Decision**: Replace semantics are clearer. If you want global + extra, repeat the global config.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Environment Variables - OS-provided key-value store

### Technology Platform Dependencies

- **PLT-001**: PyYAML or ruamel.yaml - YAML parsing library
- **PLT-002**: Python os.environ - Environment variable access
- **PLT-003**: Pydantic - Configuration validation

## 9. Examples & Edge Cases

### Example: Minimal Config

```yaml
nats:
  servers:
    - nats://localhost:4222

channels:
  - name: mychannel
    enabled: true

bot:
  username: MyBot

llm_api:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini
```

### Example: Full Config with Overrides

```yaml
# See section 4.1 for complete example
```

### Edge Case: Invalid YAML Syntax

```yaml
nats:
  servers:
    - nats://localhost:4222
  user: "admin
# Missing closing quote

# Error: Invalid YAML syntax at line 4
```

### Edge Case: Missing Required Field

```yaml
nats:
  servers:
    - nats://localhost:4222

# Missing 'channels' field

# Error: Required field 'channels' is missing
```

### Edge Case: Invalid Type

```yaml
nats:
  servers: "nats://localhost:4222"  # Should be array, not string

# Error: Field 'nats.servers' must be array, got string
```

### Edge Case: Missing Environment Variable

```yaml
llm_api:
  api_key: ${MISSING_API_KEY}

# Error: Environment variable 'MISSING_API_KEY' not found
```

### Edge Case: Config Reload with Error

```python
async def handle_sighup():
    logger.info("SIGHUP received, reloading config")
    
    try:
        new_config = Config.load("config.yaml")
        new_config.validate()
    except Exception as e:
        logger.error("Config reload failed, keeping old config", error=str(e))
        return  # Keep old config
    
    # Update config atomically
    app.config = new_config
    await update_channels(new_config.channels)
    logger.info("Config reloaded successfully")
```

### Edge Case: Duplicate Channel Names

```yaml
channels:
  - name: gaming
    enabled: true
  - name: gaming  # Duplicate!
    enabled: false

# Error: Duplicate channel name 'gaming'
```

### Edge Case: Empty Channels Array

```yaml
channels: []  # No channels

# Error: At least one channel required
```

## 10. Validation Criteria

- **VAL-001**: All required fields present and non-null
- **VAL-002**: All string fields non-empty (unless explicitly optional)
- **VAL-003**: All numeric fields within valid ranges (e.g., port 1-65535)
- **VAL-004**: All array fields contain at least one element (where required)
- **VAL-005**: Channel names match pattern `[a-z0-9_-]+`
- **VAL-006**: No duplicate channel names
- **VAL-007**: All environment variables resolve successfully
- **VAL-008**: Trigger types are valid enum values

## 11. Related Specifications / Further Reading

- [Architecture Specification](./spec-architecture-design.md) - How configuration is used
- [Data Contracts Specification](./spec-data-contracts.md) - Configuration data structures
- [Triggers Specification](./spec-triggers-ratelimiting.md) - Trigger configuration details

**External References**:
- [YAML 1.2 Specification](https://yaml.org/spec/1.2/)
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## Configuration Loading Flow

```python
import os
import yaml
from pydantic import BaseModel, ValidationError

class Config(BaseModel):
    """Root configuration model."""
    nats: NatsConfig
    channels: List[ChannelConfig]
    bot: BotConfig
    llm_api: LLMApiConfig
    # ... other fields

    @classmethod
    def load(cls, path: str) -> 'Config':
        """Load and validate configuration from YAML file."""
        # 1. Read YAML file
        with open(path, 'r') as f:
            raw_yaml = f.read()
        
        # 2. Substitute environment variables
        raw_yaml = cls._substitute_env_vars(raw_yaml)
        
        # 3. Parse YAML
        data = yaml.safe_load(raw_yaml)
        
        # 4. Validate with Pydantic
        try:
            config = cls(**data)
        except ValidationError as e:
            # Pretty-print errors
            for error in e.errors():
                field = '.'.join(str(x) for x in error['loc'])
                msg = error['msg']
                print(f"Config error in field '{field}': {msg}")
            raise SystemExit(1)
        
        # 5. Additional validation
        config._validate_unique_channels()
        
        return config
    
    @staticmethod
    def _substitute_env_vars(yaml_str: str) -> str:
        """Replace ${VAR} with environment variable values."""
        import re
        
        def replacer(match):
            var_name = match.group(1)
            if var_name not in os.environ:
                raise ValueError(
                    f"Environment variable '{var_name}' not found. "
                    f"Required by configuration."
                )
            return os.environ[var_name]
        
        return re.sub(r'\$\{(\w+)\}', replacer, yaml_str)
    
    def _validate_unique_channels(self):
        """Ensure no duplicate channel names."""
        names = [ch.name for ch in self.channels]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate channel names: {duplicates}")
```

---

## Version History

- **v1.0** - 2025-12-03 - Initial configuration specification

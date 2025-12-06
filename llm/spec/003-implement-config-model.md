# TASK-003: Implement Config Model with Pydantic Validation

**Sprint**: 1 (Foundation & Core Infrastructure)  
**Estimated Duration**: 4-6 hours  
**Prerequisites**: TASK-002 (Dependencies installed)  
**Related Specifications**:

- [Configuration Specification](./spec-configuration.md) - Complete schema and validation rules
- [Data Contracts Specification](./spec-data-contracts.md) - Validation patterns

## Objective

Implement comprehensive Pydantic models for configuration validation, including all nested structures for NATS, channels, bot identity, LLM API, triggers, rate limits, response processing, context window, and health settings.

## Context

The configuration system is the foundation of the bot's behavior. Using Pydantic v2 provides automatic validation, type safety, default values, and clear error messages when configuration is invalid.

## Requirements

### Configuration Structure

The Config model must support all fields defined in `spec-configuration.md` Section 4.1.

### Pydantic Models Hierarchy

```
Config (root)
├── NATSConfig
├── List[ChannelConfig]
├── BotConfig
├── LLMAPIConfig
│   └── LLMParametersConfig
├── List[TriggerConfig]
├── RateLimitsConfig
├── ResponseProcessingConfig
│   └── ContentFilterConfig
├── ContextWindowConfig
└── HealthConfig
```

## Implementation

Create `llm_bot/config.py` with the following content:

```python
"""Configuration models and loading logic for LLM Chat Bot."""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)
import re


class TriggerType(str, Enum):
    """Trigger type enumeration."""

    MENTION = "mention"
    KEYWORD = "keyword"
    CONTEXTUAL = "contextual"
    PM = "pm"


class TruncationStrategy(str, Enum):
    """Response truncation strategy."""

    HARD = "hard"  # Cut at exact limit
    SENTENCE = "sentence"  # Cut at sentence boundary


# ============================================================================
# NATS Configuration
# ============================================================================


class NATSConfig(BaseModel):
    """NATS connection configuration."""

    model_config = ConfigDict(extra="forbid")

    servers: List[str] = Field(
        ...,
        description="List of NATS server URLs",
        min_length=1,
    )
    user: Optional[str] = Field(
        default=None,
        description="NATS username (optional)",
    )
    password: Optional[str] = Field(
        default=None,
        description="NATS password (optional)",
    )
    connect_timeout: int = Field(
        default=5,
        description="Connection timeout in seconds",
        gt=0,
    )
    max_reconnect_attempts: int = Field(
        default=5,
        description="Maximum reconnection attempts (0 = infinite)",
        ge=0,
    )

    @field_validator("servers")
    @classmethod
    def validate_servers(cls, v: List[str]) -> List[str]:
        """Validate NATS server URLs."""
        for url in v:
            if not url.startswith(("nats://", "tls://")):
                raise ValueError(f"Invalid NATS URL: {url}")
        return v


# ============================================================================
# Channel Configuration
# ============================================================================


class ChannelConfig(BaseModel):
    """Per-channel configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        description="Channel name",
        pattern=r"^[a-z0-9_-]+$",
    )
    enabled: bool = Field(
        default=True,
        description="Whether to monitor this channel",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Channel-specific system prompt (overrides global)",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Channel-specific LLM model (overrides global)",
    )
    triggers: Optional[List["TriggerConfig"]] = Field(
        default=None,
        description="Channel-specific triggers (replaces global)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate channel name format."""
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError(
                f"Invalid channel name: {v}. "
                "Must contain only lowercase letters, numbers, underscores, hyphens"
            )
        return v


# ============================================================================
# Bot Configuration
# ============================================================================


class BotConfig(BaseModel):
    """Bot identity configuration."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        ...,
        description="Bot username",
        min_length=1,
        max_length=50,
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternate names the bot responds to",
    )


# ============================================================================
# LLM API Configuration
# ============================================================================


class LLMParametersConfig(BaseModel):
    """LLM API request parameters."""

    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(
        default=0.7,
        description="Sampling temperature",
        ge=0.0,
        le=2.0,
    )
    max_tokens: int = Field(
        default=100,
        description="Maximum tokens to generate",
        gt=0,
    )
    top_p: float = Field(
        default=0.9,
        description="Nucleus sampling threshold",
        ge=0.0,
        le=1.0,
    )
    frequency_penalty: float = Field(
        default=0.5,
        description="Frequency penalty",
        ge=-2.0,
        le=2.0,
    )
    presence_penalty: float = Field(
        default=0.3,
        description="Presence penalty",
        ge=-2.0,
        le=2.0,
    )
    stop: List[str] = Field(
        default_factory=lambda: ["\\n\\n", "User:", "Assistant:"],
        description="Stop sequences",
    )


class LLMAPIConfig(BaseModel):
    """LLM API configuration."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(
        ...,
        description="LLM API base URL",
    )
    api_key: str = Field(
        ...,
        description="LLM API key (use ${ENV_VAR} for substitution)",
    )
    model: str = Field(
        ...,
        description="Model identifier",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Request timeout in seconds",
        gt=0,
    )
    retry_attempts: int = Field(
        default=2,
        description="Number of retry attempts",
        ge=0,
    )
    retry_delay_seconds: int = Field(
        default=1,
        description="Delay between retries in seconds",
        ge=0,
    )
    system_prompt: str = Field(
        default=(
            "You are a helpful chat participant in a video watching community. "
            "Keep responses under 200 characters. "
            "Be concise, friendly, and relevant. "
            "Avoid repeating yourself."
        ),
        description="Default system prompt",
    )
    user_prompt_template: str = Field(
        default="Recent chat:\\n{context}\\n\\nRespond to: {message}",
        description="Template for user prompt",
    )
    include_context_in_prompt: bool = Field(
        default=True,
        description="Include chat context in prompts",
    )
    max_context_messages: int = Field(
        default=20,
        description="Maximum context messages in prompt",
        gt=0,
    )
    parameters: LLMParametersConfig = Field(
        default_factory=LLMParametersConfig,
        description="LLM generation parameters",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base URL: {v}")
        return v.rstrip("/")


# ============================================================================
# Trigger Configuration
# ============================================================================


class TriggerConfig(BaseModel):
    """Trigger configuration."""

    model_config = ConfigDict(extra="forbid")

    type: TriggerType = Field(
        ...,
        description="Trigger type",
    )
    enabled: bool = Field(
        default=True,
        description="Whether trigger is enabled",
    )
    fire_probability: float = Field(
        default=1.0,
        description="Probability of firing (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    cooldown_seconds: int = Field(
        default=10,
        description="Cooldown after firing",
        ge=0,
    )

    # Keyword trigger fields
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Keywords to match (keyword trigger only)",
    )
    case_sensitive: bool = Field(
        default=False,
        description="Case-sensitive keyword matching",
    )

    # Contextual trigger fields
    evaluation_interval_seconds: Optional[int] = Field(
        default=None,
        description="Evaluation interval (contextual trigger only)",
        gt=0,
    )
    min_messages_since_last_bot_message: Optional[int] = Field(
        default=None,
        description="Minimum messages since last bot message",
        ge=0,
    )
    participation_prompt: Optional[str] = Field(
        default=None,
        description="LLM prompt for participation evaluation",
    )

    # Rate limits (per-trigger)
    rate_limit_per_user_per_minute: Optional[int] = Field(
        default=None,
        description="Max triggers per user per minute",
        gt=0,
    )
    rate_limit_per_user_per_hour: Optional[int] = Field(
        default=None,
        description="Max triggers per user per hour",
        gt=0,
    )
    rate_limit_per_channel_per_hour: Optional[int] = Field(
        default=None,
        description="Max triggers per channel per hour",
        gt=0,
    )

    @model_validator(mode="after")
    def validate_trigger_fields(self) -> "TriggerConfig":
        """Validate trigger-specific fields."""
        if self.type == TriggerType.KEYWORD:
            if not self.keywords:
                raise ValueError("Keyword trigger requires 'keywords' field")

        if self.type == TriggerType.CONTEXTUAL:
            if self.evaluation_interval_seconds is None:
                raise ValueError(
                    "Contextual trigger requires 'evaluation_interval_seconds'"
                )
            if self.min_messages_since_last_bot_message is None:
                raise ValueError(
                    "Contextual trigger requires 'min_messages_since_last_bot_message'"
                )
            if not self.participation_prompt:
                raise ValueError(
                    "Contextual trigger requires 'participation_prompt'"
                )

        return self


# ============================================================================
# Rate Limits Configuration
# ============================================================================


class RateLimitsConfig(BaseModel):
    """Global rate limits configuration."""

    model_config = ConfigDict(extra="forbid")

    max_per_user_per_minute: int = Field(
        default=3,
        description="Max bot messages per user per minute (spans channels)",
        gt=0,
    )
    max_per_user_per_hour: int = Field(
        default=10,
        description="Max bot messages per user per hour (spans channels)",
        gt=0,
    )
    max_per_channel_per_minute: int = Field(
        default=5,
        description="Max bot messages per channel per minute",
        gt=0,
    )
    max_per_channel_per_hour: int = Field(
        default=30,
        description="Max bot messages per channel per hour",
        gt=0,
    )
    global_cooldown_seconds: int = Field(
        default=10,
        description="Minimum seconds between any bot messages",
        ge=0,
    )
    media_change_cooldown_seconds: int = Field(
        default=30,
        description="Silence period after media changes",
        ge=0,
    )


# ============================================================================
# Response Processing Configuration
# ============================================================================


class ContentFilterConfig(BaseModel):
    """Content filtering configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable content filtering",
    )
    block_patterns: List[str] = Field(
        default_factory=lambda: ["http://", "https://"],
        description="Regex patterns to block",
    )
    block_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to block (case-insensitive)",
    )
    min_word_count: int = Field(
        default=2,
        description="Minimum word count",
        ge=0,
    )
    max_word_count: int = Field(
        default=50,
        description="Maximum word count",
        gt=0,
    )


class ResponseProcessingConfig(BaseModel):
    """Response processing configuration."""

    model_config = ConfigDict(extra="forbid")

    max_length: int = Field(
        default=200,
        description="Maximum response length in characters",
        gt=0,
    )
    truncation_strategy: TruncationStrategy = Field(
        default=TruncationStrategy.SENTENCE,
        description="Truncation strategy",
    )
    content_filter: ContentFilterConfig = Field(
        default_factory=ContentFilterConfig,
        description="Content filtering settings",
    )
    quality_checks_enabled: bool = Field(
        default=True,
        description="Enable quality checks",
    )
    deduplicate_window: int = Field(
        default=10,
        description="Check last N messages for duplicates",
        gt=0,
    )
    strip_markdown: bool = Field(
        default=True,
        description="Remove markdown formatting",
    )
    collapse_newlines: bool = Field(
        default=True,
        description="Replace newlines with spaces",
    )


# ============================================================================
# Context Window Configuration
# ============================================================================


class ContextWindowConfig(BaseModel):
    """Context window configuration."""

    model_config = ConfigDict(extra="forbid")

    size: int = Field(
        default=50,
        description="Number of messages to retain",
        gt=0,
    )
    max_age_seconds: int = Field(
        default=3600,
        description="Maximum age of messages",
        gt=0,
    )
    include_usernames: bool = Field(
        default=True,
        description="Include usernames in context",
    )
    include_timestamps: bool = Field(
        default=False,
        description="Include relative timestamps",
    )


# ============================================================================
# Health Configuration
# ============================================================================


class HealthConfig(BaseModel):
    """Health and metrics HTTP server configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable health/metrics HTTP server",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Bind host",
    )
    port: int = Field(
        default=8080,
        description="Bind port",
        gt=0,
        lt=65536,
    )


# ============================================================================
# Root Configuration
# ============================================================================


class Config(BaseModel):
    """Root configuration model."""

    model_config = ConfigDict(extra="forbid")

    nats: NATSConfig = Field(
        ...,
        description="NATS connection settings",
    )
    channels: List[ChannelConfig] = Field(
        ...,
        description="Channels to monitor",
        min_length=1,
    )
    bot: BotConfig = Field(
        ...,
        description="Bot identity",
    )
    llm_api: LLMAPIConfig = Field(
        ...,
        description="LLM API settings",
    )
    triggers: List[TriggerConfig] = Field(
        default_factory=list,
        description="Global trigger configurations",
    )
    rate_limits: RateLimitsConfig = Field(
        default_factory=RateLimitsConfig,
        description="Global rate limits",
    )
    response_processing: ResponseProcessingConfig = Field(
        default_factory=ResponseProcessingConfig,
        description="Response processing settings",
    )
    context_window: ContextWindowConfig = Field(
        default_factory=ContextWindowConfig,
        description="Context window settings",
    )
    health: HealthConfig = Field(
        default_factory=HealthConfig,
        description="Health endpoint settings",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )

    @model_validator(mode="after")
    def validate_unique_channels(self) -> "Config":
        """Ensure channel names are unique."""
        channel_names = [ch.name for ch in self.channels]
        if len(channel_names) != len(set(channel_names)):
            raise ValueError("Duplicate channel names found")
        return self

    @model_validator(mode="after")
    def validate_triggers(self) -> "Config":
        """Ensure at least one trigger is configured (global or per-channel)."""
        if not self.triggers:
            # Check if any channel has triggers
            has_channel_triggers = any(
                ch.triggers for ch in self.channels if ch.enabled
            )
            if not has_channel_triggers:
                raise ValueError(
                    "At least one trigger must be configured "
                    "(either global or per-channel)"
                )
        return self


# Placeholder for Config.load() - will be implemented in TASK-005
```

## Acceptance Criteria

- [ ] All Pydantic models defined with correct field types
- [ ] All field validators implemented (URLs, patterns, ranges)
- [ ] Model validators implemented (unique channels, trigger requirements)
- [ ] Enums defined for TriggerType and TruncationStrategy
- [ ] Default values match specification
- [ ] Nested models properly structured
- [ ] Type hints on all fields
- [ ] Docstrings on all models and fields

## Testing

Create `tests/unit/test_config.py`:

```python
"""Unit tests for configuration models."""

import pytest
from pydantic import ValidationError
from llm_bot.config import (
    Config,
    NATSConfig,
    ChannelConfig,
    BotConfig,
    TriggerConfig,
    TriggerType,
)


def test_minimal_valid_config():
    """Test minimal valid configuration."""
    config_dict = {
        "nats": {
            "servers": ["nats://localhost:4222"],
        },
        "channels": [
            {"name": "testchannel", "enabled": True}
        ],
        "bot": {
            "username": "TestBot",
        },
        "llm_api": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o-mini",
        },
    }

    config = Config(**config_dict)
    assert config.nats.servers == ["nats://localhost:4222"]
    assert len(config.channels) == 1
    assert config.channels[0].name == "testchannel"


def test_invalid_channel_name():
    """Test channel name validation."""
    with pytest.raises(ValidationError) as exc_info:
        ChannelConfig(name="Invalid Name!", enabled=True)

    assert "Invalid channel name" in str(exc_info.value)


def test_duplicate_channels():
    """Test duplicate channel detection."""
    config_dict = {
        "nats": {"servers": ["nats://localhost:4222"]},
        "channels": [
            {"name": "channel1", "enabled": True},
            {"name": "channel1", "enabled": True},  # Duplicate
        ],
        "bot": {"username": "Bot"},
        "llm_api": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o-mini",
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        Config(**config_dict)

    assert "Duplicate channel names" in str(exc_info.value)


def test_keyword_trigger_requires_keywords():
    """Test keyword trigger validation."""
    with pytest.raises(ValidationError) as exc_info:
        TriggerConfig(
            type=TriggerType.KEYWORD,
            enabled=True,
            fire_probability=0.5,
        )

    assert "keywords" in str(exc_info.value).lower()


def test_contextual_trigger_requires_fields():
    """Test contextual trigger validation."""
    with pytest.raises(ValidationError) as exc_info:
        TriggerConfig(
            type=TriggerType.CONTEXTUAL,
            enabled=True,
        )

    assert "evaluation_interval_seconds" in str(exc_info.value).lower()
```

Run tests:

```powershell
pytest tests/unit/test_config.py -v
```

## Next Tasks

- **TASK-004**: Implement environment variable substitution
- **TASK-005**: Implement Config.load() with YAML parsing

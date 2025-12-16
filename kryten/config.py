"""Dataclass-Based Configuration Loader for Kryten.

This module provides strongly typed configuration objects for CyTube and NATS
settings loaded from JSON, with environment variable override support.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Valid log levels (mirrors Python logging module)
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Environment variable names for overrides
ENV_CYTUBE_USER = "KRYTEN_CYTUBE_USER"
ENV_CYTUBE_PASSWORD = "KRYTEN_CYTUBE_PASSWORD"
ENV_NATS_URL = "KRYTEN_NATS_URL"


@dataclass
class CytubeConfig:
    """Configuration for CyTube connection.

    Attributes:
        domain: CyTube server domain (e.g., "cytu.be").
        channel: Channel name to join.
        channel_password: Optional password for password-protected channels.
        user: Optional username for authentication.
        password: Optional password for user authentication.
        aggressive_reconnect: If True, attempt to reconnect when kicked instead
            of shutting down. Default: False.

    Examples:
        >>> cfg = CytubeConfig(domain="cytu.be", channel="test")
        >>> print(cfg.domain)
        cytu.be
    """

    domain: str
    channel: str
    channel_password: str | None = None
    user: str | None = None
    password: str | None = None
    aggressive_reconnect: bool = False


@dataclass
class NatsConfig:
    """Configuration for NATS connection.

    Attributes:
        servers: List of NATS server URLs (e.g., ["nats://localhost:4222"]).
        user: Optional username for authentication.
        password: Optional password for authentication.
        connect_timeout: Connection timeout in seconds. Default: 10.
        reconnect_time_wait: Wait time between reconnects in seconds. Default: 2.
        max_reconnect_attempts: Maximum reconnection attempts. Default: 10.
        allow_reconnect: Enable automatic reconnection. Default: True.

    Examples:
        >>> cfg = NatsConfig(servers=["nats://localhost:4222"])
        >>> print(cfg.connect_timeout)
        10
    """

    servers: list[str]
    user: str | None = None
    password: str | None = None
    connect_timeout: int = 10
    reconnect_time_wait: int = 2
    max_reconnect_attempts: int = 10
    allow_reconnect: bool = True


@dataclass
class CommandsConfig:
    """Configuration for bidirectional command execution.

    Attributes:
        enabled: Whether command subscriptions are enabled. Default: False.

    Examples:
        >>> cfg = CommandsConfig(enabled=True)
        >>> print(cfg.enabled)
        True
    """

    enabled: bool = False


@dataclass
class HealthConfig:
    """Configuration for health monitoring endpoint.

    Attributes:
        enabled: Whether health endpoint is enabled. Default: True.
        host: Host to bind health server. Default: "0.0.0.0".
        port: Port for health server. Default: 8080.

    Examples:
        >>> cfg = HealthConfig(enabled=True, port=8080)
        >>> print(cfg.port)
        8080
    """

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class LoggingConfig:
    """Configuration for specialized logging.

    Attributes:
        base_path: Base directory for all log files. Default: "./logs".
        admin_operations: Filename for admin operations log. Default: "admin-operations.log".
        playlist_operations: Filename for playlist operations log. Default: "playlist-operations.log".
        chat_messages: Filename for chat message log. Default: "chat-messages.log".
        command_audit: Filename for command audit log. Default: "command-audit.log".
        connection_events: Filename for connection event log. Default: "connection-events.log".

    Examples:
        >>> cfg = LoggingConfig(base_path="/var/log/kryten")
        >>> print(cfg.admin_operations)
        admin-operations.log
    """

    base_path: str = "./logs"
    admin_operations: str = "admin-operations.log"
    playlist_operations: str = "playlist-operations.log"
    chat_messages: str = "chat-messages.log"
    command_audit: str = "command-audit.log"
    connection_events: str = "connection-events.log"


@dataclass
class StateCountingConfig:
    """Configuration for state counting and filtering.

    Attributes:
        users_exclude_afk: Exclude AFK users from count. Default: False.
        users_min_rank: Minimum rank to include in count (0=all). Default: 0.
        playlist_exclude_temp: Exclude temporary items from count. Default: False.
        playlist_max_duration: Maximum duration (seconds) to include (0=no limit). Default: 0.
        emotes_only_enabled: Only count enabled emotes. Default: False.

    Examples:
        >>> cfg = StateCountingConfig(users_exclude_afk=True, users_min_rank=1)
        >>> print(cfg.users_exclude_afk)
        True
    """

    users_exclude_afk: bool = False
    users_min_rank: int = 0
    playlist_exclude_temp: bool = False
    playlist_max_duration: int = 0
    emotes_only_enabled: bool = False


@dataclass
class KrytenConfig:
    """Top-level configuration for Kryten connector.

    Attributes:
        cytube: CyTube connection configuration.
        nats: NATS connection configuration.
        commands: Command subscription configuration.
        health: Health monitoring configuration.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            Default: "INFO".
        logging: Specialized logging configuration.
        state_counting: State counting and filtering configuration.

    Examples:
        >>> cytube = CytubeConfig(domain="cytu.be", channel="test")
        >>> nats = NatsConfig(url="nats://localhost:4222")
        >>> cfg = KrytenConfig(cytube=cytube, nats=nats)
        >>> print(cfg.log_level)
        INFO
    """

    cytube: CytubeConfig
    nats: NatsConfig
    commands: CommandsConfig = field(default_factory=CommandsConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    log_level: str = "INFO"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    state_counting: StateCountingConfig = field(default_factory=StateCountingConfig)


def _normalize_string(value: str) -> str:
    """Normalize string by stripping whitespace.

    Args:
        value: String to normalize.

    Returns:
        Normalized string with leading/trailing whitespace removed.
    """
    return value.strip()


def _validate_log_level(level: str) -> None:
    """Validate log level is one of the accepted values.

    Args:
        level: Log level to validate.

    Raises:
        ValueError: If log level is not valid.
    """
    if level not in VALID_LOG_LEVELS:
        valid_str = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(
            f"Invalid log_level: '{level}'. Expected one of: {valid_str}"
        )


def _load_cytube_config(data: dict) -> CytubeConfig:
    """Load and validate CyTube configuration from dict.

    Args:
        data: Dictionary containing cytube configuration.

    Returns:
        Validated CytubeConfig instance.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    if "cytube" not in data:
        raise ValueError("Missing required section: cytube")

    cytube_data = data["cytube"]
    if not isinstance(cytube_data, dict):
        raise ValueError("Section 'cytube' must be a dictionary")

    # Check required fields
    required_fields = ["domain", "channel"]
    for required_field in required_fields:
        if required_field not in cytube_data:
            raise ValueError(f"Missing required field: cytube.{required_field}")

    # Extract and normalize required fields
    domain = _normalize_string(str(cytube_data["domain"]))
    channel = _normalize_string(str(cytube_data["channel"]))

    # Extract optional fields with environment overrides
    channel_password = cytube_data.get("channel_password")
    if channel_password is not None:
        channel_password = _normalize_string(str(channel_password))

    user = cytube_data.get("user")
    if user is not None:
        user = _normalize_string(str(user))
    # Environment override for user
    if ENV_CYTUBE_USER in os.environ:
        user = os.environ[ENV_CYTUBE_USER]

    password = cytube_data.get("password")
    if password is not None:
        password = _normalize_string(str(password))
    # Environment override for password
    if ENV_CYTUBE_PASSWORD in os.environ:
        password = os.environ[ENV_CYTUBE_PASSWORD]

    # Extract aggressive_reconnect option (default: False)
    aggressive_reconnect = bool(cytube_data.get("aggressive_reconnect", False))

    return CytubeConfig(
        domain=domain,
        channel=channel,
        channel_password=channel_password,
        user=user,
        password=password,
        aggressive_reconnect=aggressive_reconnect,
    )


def _load_nats_config(data: dict) -> NatsConfig:
    """Load and validate NATS configuration from dict.

    Args:
        data: Dictionary containing nats configuration.

    Returns:
        Validated NatsConfig instance.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    if "nats" not in data:
        raise ValueError("Missing required section: nats")

    nats_data = data["nats"]
    if not isinstance(nats_data, dict):
        raise ValueError("Section 'nats' must be a dictionary")

    # Check required fields - support both 'servers' and legacy 'url'
    servers = []
    if "servers" in nats_data:
        servers_value = nats_data["servers"]
        if isinstance(servers_value, list):
            servers = [_normalize_string(str(s)) for s in servers_value]
        elif isinstance(servers_value, str):
            servers = [_normalize_string(servers_value)]
        else:
            raise ValueError("Field 'nats.servers' must be a string or list of strings")
    elif "url" in nats_data:
        # Legacy support for single 'url' field
        servers = [_normalize_string(str(nats_data["url"]))]
    else:
        raise ValueError("Missing required field: nats.servers (or nats.url)")

    if not servers:
        raise ValueError("Field 'nats.servers' cannot be empty")

    # Environment override for servers (first server only for backward compatibility)
    if ENV_NATS_URL in os.environ:
        servers = [os.environ[ENV_NATS_URL]]

    # Extract optional fields
    user = nats_data.get("user")
    if user is not None:
        user = _normalize_string(str(user))

    password = nats_data.get("password")
    if password is not None:
        password = _normalize_string(str(password))

    connect_timeout = int(nats_data.get("connect_timeout", 10))
    reconnect_time_wait = int(nats_data.get("reconnect_time_wait", 2))
    max_reconnect_attempts = int(nats_data.get("max_reconnect_attempts", 10))
    allow_reconnect = bool(nats_data.get("allow_reconnect", True))

    return NatsConfig(
        servers=servers,
        user=user,
        password=password,
        connect_timeout=connect_timeout,
        reconnect_time_wait=reconnect_time_wait,
        max_reconnect_attempts=max_reconnect_attempts,
        allow_reconnect=allow_reconnect,
    )


def _load_commands_config(data: dict) -> CommandsConfig:
    """Load and validate commands configuration from dict.

    Args:
        data: Dictionary containing commands configuration.

    Returns:
        Validated CommandsConfig instance.

    Raises:
        ValueError: If configuration is invalid.
    """
    if "commands" not in data:
        # Commands section is optional, return defaults
        return CommandsConfig()

    commands_data = data["commands"]
    if not isinstance(commands_data, dict):
        raise ValueError("Section 'commands' must be a dictionary")

    enabled = bool(commands_data.get("enabled", False))

    return CommandsConfig(enabled=enabled)


def _load_health_config(data: dict) -> HealthConfig:
    """Load and validate health configuration from dict.

    Args:
        data: Dictionary containing health configuration.

    Returns:
        Validated HealthConfig instance.

    Raises:
        ValueError: If configuration is invalid.
    """
    if "health" not in data:
        # Health section is optional, return defaults
        return HealthConfig()

    health_data = data["health"]
    if not isinstance(health_data, dict):
        raise ValueError("Section 'health' must be a dictionary")

    enabled = bool(health_data.get("enabled", True))
    host = str(health_data.get("host", "0.0.0.0"))
    port = int(health_data.get("port", 8080))

    return HealthConfig(enabled=enabled, host=host, port=port)


def load_config(path: Path | str) -> KrytenConfig:
    """Load and validate configuration from JSON file.

    Reads JSON configuration file, validates structure and types, applies
    environment variable overrides, and returns strongly-typed configuration
    object.

    Environment Variables:
        KRYTEN_CYTUBE_USER: Override cytube.user
        KRYTEN_CYTUBE_PASSWORD: Override cytube.password
        KRYTEN_NATS_URL: Override nats.url

    Args:
        path: Path to JSON configuration file (string or Path object).

    Returns:
        Validated KrytenConfig instance with normalized values.

    Raises:
        FileNotFoundError: If configuration file does not exist.
        ValueError: If configuration is invalid or missing required fields.
        json.JSONDecodeError: If file contains malformed JSON.

    Examples:
        >>> cfg = load_config('config.json')
        >>> print(cfg.cytube.domain)
        cytu.be

        >>> # With environment override
        >>> os.environ['KRYTEN_CYTUBE_PASSWORD'] = 'secret'
        >>> cfg = load_config('config.json')
        >>> print(cfg.cytube.password)
        secret
    """
    # Convert to Path if string
    config_path = Path(path) if isinstance(path, str) else path

    # Check file exists
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load JSON
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Configuration file must contain a JSON object")

    # Load subsections
    cytube = _load_cytube_config(data)
    nats = _load_nats_config(data)
    commands = _load_commands_config(data)
    health = _load_health_config(data)

    # Load log level with validation
    log_level = data.get("log_level", "INFO")
    if not isinstance(log_level, str):
        raise ValueError("Field 'log_level' must be a string")

    log_level = log_level.upper()  # Normalize to uppercase
    _validate_log_level(log_level)

    # Load logging configuration
    logging_config = LoggingConfig()
    if "logging" in data:
        logging_data = data["logging"]
        if isinstance(logging_data, dict):
            logging_config = LoggingConfig(
                base_path=logging_data.get("base_path", "./logs"),
                admin_operations=logging_data.get("admin_operations", "admin-operations.log"),
                playlist_operations=logging_data.get("playlist_operations", "playlist-operations.log"),
                chat_messages=logging_data.get("chat_messages", "chat-messages.log"),
                command_audit=logging_data.get("command_audit", "command-audit.log"),
            )

    # Load state counting configuration
    state_counting_config = StateCountingConfig()
    if "state_counting" in data:
        state_data = data["state_counting"]
        if isinstance(state_data, dict):
            state_counting_config = StateCountingConfig(
                users_exclude_afk=state_data.get("users_exclude_afk", False),
                users_min_rank=state_data.get("users_min_rank", 0),
                playlist_exclude_temp=state_data.get("playlist_exclude_temp", False),
                playlist_max_duration=state_data.get("playlist_max_duration", 0),
                emotes_only_enabled=state_data.get("emotes_only_enabled", False),
            )

    return KrytenConfig(
        cytube=cytube,
        nats=nats,
        commands=commands,
        health=health,
        log_level=log_level,
        logging=logging_config,
        state_counting=state_counting_config,
    )


__all__ = [
    "CytubeConfig",
    "NatsConfig",
    "CommandsConfig",
    "HealthConfig",
    "LoggingConfig",
    "StateCountingConfig",
    "KrytenConfig",
    "load_config",
]

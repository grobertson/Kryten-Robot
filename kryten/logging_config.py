"""Structured logging configuration for Kryten.

This module provides logging configuration with structured output (JSON or text),
correlation ID tracking, sensitive data redaction, and configurable verbosity
for development and production environments.

Examples:
    Development setup with text format:
        >>> from bot.kryten.logging_config import LoggingConfig, setup_logging
        >>> config = LoggingConfig(level="DEBUG", format="text", output="console")
        >>> setup_logging(config)
        >>> logger = get_logger(__name__)
        >>> logger.debug("Debug information")

    Production setup with JSON format:
        >>> config = LoggingConfig(
        ...     level="INFO",
        ...     format="json",
        ...     output="file",
        ...     file_path="/var/log/kryten/kryten.log",
        ...     component_levels={"nats_client": "DEBUG"}
        ... )
        >>> setup_logging(config)

    Component-specific log levels:
        >>> config = LoggingConfig(
        ...     level="INFO",
        ...     component_levels={"bot.kryten.nats_client": "DEBUG"}
        ... )
        >>> setup_logging(config)
        >>> # nats_client logs DEBUG, others log INFO+

Note:
    Sensitive data (passwords, tokens, API keys) are automatically redacted.
"""

import json
import logging
import logging.config
import logging.handlers
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .correlation import CorrelationFilter


@dataclass
class LoggingConfig:
    """Configuration for Kryten logging system.

    Attributes:
        level: Global log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format: Output format ("json" or "text").
        output: Output destination ("console" or "file").
        file_path: Path to log file (required if output="file").
        max_bytes: Maximum log file size before rotation (default 10MB).
        backup_count: Number of backup files to keep (default 5).
        component_levels: Per-component log levels (e.g., {"nats_client": "DEBUG"}).

    Examples:
        >>> config = LoggingConfig(level="INFO", format="json")
        >>> config = LoggingConfig(
        ...     level="WARNING",
        ...     format="text",
        ...     output="file",
        ...     file_path="/var/log/kryten.log"
        ... )
    """

    level: str = "INFO"
    format: str = "json"  # or "text"
    output: str = "console"  # or "file"
    file_path: str | None = None
    max_bytes: int = 10_485_760  # 10MB
    backup_count: int = 5
    component_levels: dict[str, str] = field(default_factory=dict)


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log messages.

    Redacts patterns matching passwords, tokens, API keys, and other
    sensitive values to prevent credential leakage.

    Examples:
        >>> logger.addFilter(SensitiveDataFilter())
        >>> logger.info("password=secret123")
        # Output: "password=***REDACTED***"
    """

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        (re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE), "password=***REDACTED***"),
        (re.compile(r"token\s*[=:]\s*\S+", re.IGNORECASE), "token=***REDACTED***"),
        (re.compile(r"api[_-]?key\s*[=:]\s*\S+", re.IGNORECASE), "api_key=***REDACTED***"),
        (re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE), "secret=***REDACTED***"),
        (re.compile(r"auth\s*[=:]\s*\S+", re.IGNORECASE), "auth=***REDACTED***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log record message.

        Args:
            record: Log record to filter.

        Returns:
            True (always allows record through after redaction).
        """
        if hasattr(record, "msg"):
            msg = str(record.msg)
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                msg = pattern.sub(replacement, msg)
            record.msg = msg

        return True


class JSONFormatter(logging.Formatter):
    """Formatter that outputs logs as single-line JSON.

    Includes standard fields: timestamp, level, logger, message, correlation_id,
    component, service.

    Examples:
        >>> formatter = JSONFormatter()
        >>> handler.setFormatter(formatter)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            Single-line JSON string.
        """
        # Extract component from logger name (e.g., "bot.kryten.nats_client" -> "nats_client")
        component = record.name.split(".")[-1] if "." in record.name else record.name

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "N/A"),
            "component": component,
            "service": "kryten",
        }

        # Include source location in DEBUG mode
        if record.levelno == logging.DEBUG:
            log_data["file"] = record.filename
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Formatter that outputs logs as human-readable text.

    Format: timestamp LEVEL [component] [correlation_id=ID] message

    Examples:
        >>> formatter = TextFormatter()
        >>> handler.setFormatter(formatter)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text.

        Args:
            record: Log record to format.

        Returns:
            Formatted text string.
        """
        # Extract component from logger name
        component = record.name.split(".")[-1] if "." in record.name else record.name

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Get correlation ID
        correlation_id = getattr(record, "correlation_id", "N/A")

        # Build message
        message = f"{timestamp} {record.levelname} [{component}] [correlation_id={correlation_id}] {record.getMessage()}"

        # Include source location in DEBUG mode
        if record.levelno == logging.DEBUG:
            message += f" ({record.filename}:{record.lineno})"

        # Include exception info if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


def setup_logging(config: LoggingConfig) -> None:
    """Configure Python logging system with structured output.

    Sets up handlers, formatters, and filters based on configuration.
    Applies CorrelationFilter and SensitiveDataFilter to all loggers.

    Args:
        config: Logging configuration.

    Raises:
        ValueError: If output="file" but file_path not provided.

    Examples:
        >>> config = LoggingConfig(level="INFO", format="json")
        >>> setup_logging(config)
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    # Validate configuration
    if config.output == "file" and not config.file_path:
        raise ValueError("file_path required when output='file'")

    # Choose formatter
    if config.format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Create handlers
    handlers = {}

    if config.output == "console":
        # Console output: INFO+ to stdout, WARNING+ to stderr
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)
        stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
        handlers["stdout"] = stdout_handler

        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(formatter)
        handlers["stderr"] = stderr_handler

    else:  # file
        # File output with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        handlers["file"] = file_handler

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Allow all, filter at handler level

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add new handlers
    for handler in handlers.values():
        handler.addFilter(CorrelationFilter())
        handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(handler)

    # Set global level
    logging.getLogger().setLevel(getattr(logging, config.level.upper()))

    # Set component-specific levels
    for component, level in config.component_levels.items():
        logger_name = f"bot.kryten.{component}" if not component.startswith("bot.") else component
        logging.getLogger(logger_name).setLevel(getattr(logging, level.upper()))


def get_logger(name: str) -> logging.Logger:
    """Get logger with standard configuration.

    Returns a logger that inherits from the root logger configuration,
    including CorrelationFilter and SensitiveDataFilter.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Event processed")

        >>> logger = get_logger("bot.kryten.connector")
        >>> logger.debug("Connection details")
    """
    return logging.getLogger(name)


__all__ = [
    "LoggingConfig",
    "setup_logging",
    "get_logger",
    "SensitiveDataFilter",
    "JSONFormatter",
    "TextFormatter",
]

"""Correlation ID tracking for distributed tracing.

This module provides correlation ID generation and propagation throughout the
event pipeline, enabling distributed tracing and debugging across Kryten
components and downstream consumers.

Correlation IDs are UUID4 strings that uniquely identify an event's journey
through the system, from Socket.IO receipt through NATS publishing.

Examples:
    Basic usage with context management:
        >>> from bot.kryten.correlation import CorrelationContext
        >>> with CorrelationContext() as corr_id:
        ...     logger.info("Processing event")  # corr_id in log
        ...     process_event()

    Manual context control:
        >>> from bot.kryten.correlation import (
        ...     generate_correlation_id,
        ...     set_correlation_context,
        ...     get_correlation_context,
        ... )
        >>> correlation_id = generate_correlation_id()
        >>> set_correlation_context(correlation_id)
        >>> logger.info("Event received")  # correlation_id in log

    Async task isolation:
        >>> async def task1():
        ...     set_correlation_context(generate_correlation_id())
        ...     await process()
        ...     # Each task has its own correlation ID
        >>> await asyncio.gather(task1(), task1())

Note:
    Correlation IDs must not contain PII (Personally Identifiable Information).
    They are purely for operational tracing and debugging.
"""

import logging
import uuid
from contextvars import ContextVar

# Context-local storage for correlation ID (thread-safe, async-aware)
_correlation_context: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """Generate a new UUID4 correlation ID.

    Returns a lowercase UUID4 string without hyphens for compactness.
    Format: 32 hexadecimal characters (e.g., "550e8400e29b41d4a716446655440000").

    Returns:
        Lowercase UUID4 string without hyphens.

    Examples:
        >>> corr_id = generate_correlation_id()
        >>> len(corr_id)
        32
        >>> all(c in '0123456789abcdef' for c in corr_id)
        True
    """
    return uuid.uuid4().hex


def set_correlation_context(correlation_id: str) -> None:
    """Set correlation ID for the current async context.

    The correlation ID will be accessible to the current task and any tasks
    spawned from it, but isolated from other concurrent tasks.

    Args:
        correlation_id: Correlation ID to set in current context.

    Examples:
        >>> set_correlation_context("550e8400e29b41d4a716446655440000")
        >>> get_correlation_context()
        '550e8400e29b41d4a716446655440000'
    """
    _correlation_context.set(correlation_id)


def get_correlation_context() -> str | None:
    """Get correlation ID from the current async context.

    Returns None if no correlation ID has been set in the current context.

    Returns:
        Current correlation ID, or None if not set.

    Examples:
        >>> set_correlation_context("test-id")
        >>> get_correlation_context()
        'test-id'
        >>> # In a different task with no context set
        >>> get_correlation_context()
        None
    """
    return _correlation_context.get()


def clear_correlation_context() -> None:
    """Clear correlation ID from the current async context.

    Resets the context to None. Useful for cleanup after processing.

    Examples:
        >>> set_correlation_context("test-id")
        >>> get_correlation_context()
        'test-id'
        >>> clear_correlation_context()
        >>> get_correlation_context()
        None
    """
    _correlation_context.set(None)


class CorrelationContext:
    """Context manager for correlation ID scope.

    Automatically generates a correlation ID (or uses provided one) and sets
    it in the context. Cleans up the context on exit.

    Attributes:
        correlation_id: The correlation ID for this context.

    Examples:
        Auto-generate correlation ID:
            >>> with CorrelationContext() as corr_id:
            ...     print(f"Correlation ID: {corr_id}")
            ...     # Process event with correlation
            Correlation ID: 550e8400e29b41d4a716446655440000

        Use existing correlation ID:
            >>> existing_id = "abc123def456"
            >>> with CorrelationContext(existing_id) as corr_id:
            ...     assert corr_id == existing_id
            ...     # Process with existing correlation
    """

    def __init__(self, correlation_id: str | None = None):
        """Initialize correlation context.

        Args:
            correlation_id: Optional correlation ID. If None, generates new one.
        """
        self.correlation_id = correlation_id or generate_correlation_id()
        self._token = None

    def __enter__(self) -> str:
        """Enter context, setting correlation ID.

        Returns:
            The correlation ID for this context.
        """
        self._token = _correlation_context.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context, cleaning up correlation ID.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.
        """
        if self._token is not None:
            _correlation_context.reset(self._token)

    async def __aenter__(self) -> str:
        """Async enter context, setting correlation ID.

        Returns:
            The correlation ID for this context.
        """
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit context, cleaning up correlation ID.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.
        """
        self.__exit__(exc_type, exc_val, exc_tb)


class CorrelationFilter(logging.Filter):
    """Logging filter that injects correlation ID into log records.

    Adds a 'correlation_id' attribute to each LogRecord with the current
    context's correlation ID. If no correlation ID is set, uses 'N/A'.

    Usage:
        >>> import logging
        >>> logger = logging.getLogger("myapp")
        >>> logger.addFilter(CorrelationFilter())
        >>> formatter = logging.Formatter(
        ...     '%(asctime)s - %(levelname)s - [correlation_id=%(correlation_id)s] - %(message)s'
        ... )
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(formatter)
        >>> logger.addHandler(handler)
        >>> with CorrelationContext():
        ...     logger.info("Event processed")  # Includes correlation_id

    Examples:
        Setup logging with correlation:
            >>> logger = logging.getLogger(__name__)
            >>> logger.addFilter(CorrelationFilter())
            >>> set_correlation_context("test-123")
            >>> logger.info("Processing")  # Log includes correlation_id=test-123

        Without correlation context:
            >>> logger.info("Starting")  # Log includes correlation_id=N/A
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record.

        Args:
            record: Log record to modify.

        Returns:
            True (always allows record through).
        """
        record.correlation_id = get_correlation_context() or "N/A"
        return True


__all__ = [
    "generate_correlation_id",
    "set_correlation_context",
    "get_correlation_context",
    "clear_correlation_context",
    "CorrelationContext",
    "CorrelationFilter",
]

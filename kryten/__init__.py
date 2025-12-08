"""Kryten CyTube Connector Package.

This package provides a standalone Socket.IO client that connects to CyTube
chat servers and publishes events to NATS for consumption by Rosey-Robot plugins.
"""

from pathlib import Path
from typing import Final


def _read_version() -> str:
    """Read version from VERSION file at repository root.
    
    Returns:
        Semantic version string, or "0.1.0-dev" if file unavailable.
    """
    try:
        version_file = Path(__file__).parent.parent.parent / "VERSION"
        version_text = version_file.read_text(encoding="utf-8")
        return version_text.strip()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return "0.1.0-dev"


__version__: Final[str] = _read_version()
"""Semantic version of the Kryten connector package."""


def get_version() -> str:
    """Return the semantic version string.
    
    Returns:
        Version string in MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-suffix format.
    
    Example:
        >>> from bot import kryten
        >>> kryten.get_version()
        '0.5.0'
    """
    return __version__


from .command_subscriber import CommandSubscriber
from .config import CytubeConfig, KrytenConfig, NatsConfig, load_config
from .connection_watchdog import ConnectionWatchdog
from .correlation import (
    CorrelationContext,
    CorrelationFilter,
    clear_correlation_context,
    generate_correlation_id,
    get_correlation_context,
    set_correlation_context,
)
from .cytube_connector import CytubeConnector
from .cytube_event_sender import CytubeEventSender
from .event_publisher import EventPublisher
from .health_monitor import (
    HealthMonitor,
    HealthStatus,
)
from .lifecycle_events import LifecycleEventPublisher
from .logging_config import (
    LoggingConfig,
    get_logger,
    setup_logging,
)
from .nats_client import NatsClient
from .raw_event import RawEvent
from .shutdown_handler import (
    ShutdownHandler,
    ShutdownPhase,
    ShutdownResult,
)
from .state_manager import StateManager
from .state_query_handler import StateQueryHandler
from .subject_builder import (
    SUBJECT_PREFIX,
    build_event_subject,
    build_subject,
    parse_subject,
    sanitize_token,
)


__all__ = [
    "__version__",
    "get_version",
    "CommandSubscriber",
    "ConnectionWatchdog",
    "CytubeConfig",
    "KrytenConfig",
    "NatsConfig",
    "load_config",
    "CorrelationContext",
    "CorrelationFilter",
    "clear_correlation_context",
    "generate_correlation_id",
    "get_correlation_context",
    "set_correlation_context",
    "CytubeConnector",
    "CytubeEventSender",
    "EventPublisher",
    "HealthMonitor",
    "HealthStatus",
    "LifecycleEventPublisher",
    "LoggingConfig",
    "get_logger",
    "setup_logging",
    "NatsClient",
    "RawEvent",
    "ShutdownHandler",
    "ShutdownPhase",
    "ShutdownResult",
    "StateManager",
    "StateQueryHandler",
    "SUBJECT_PREFIX",
    "build_subject",
    "build_event_subject",
    "parse_subject",
    "sanitize_token",
]

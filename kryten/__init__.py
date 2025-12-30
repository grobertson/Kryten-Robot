"""Kryten CyTube Connector Package.

This package provides a standalone Socket.IO client that connects to CyTube
chat servers and publishes events to NATS for consumption by Rosey-Robot plugins.
"""

from importlib.metadata import version as _get_pkg_version, PackageNotFoundError

try:
    __version__ = _get_pkg_version("kryten-robot")
except PackageNotFoundError:
    __version__ = "0.0.0"

__author__ = "Kryten Robot Team"
__license__ = "MIT"


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
from .state_updater import StateUpdater
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
    "StateUpdater",
    "SUBJECT_PREFIX",
    "build_subject",
    "build_event_subject",
    "parse_subject",
    "sanitize_token",
]

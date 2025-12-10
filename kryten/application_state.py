"""Application State - Shared runtime state for system management.

This module provides the ApplicationState class that holds references to all
major components and runtime state needed for system management commands.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Optional

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from .config import KrytenConfig
    from .cytube_connector import CytubeConnector
    from .nats_client import NatsClient
    from .event_publisher import EventPublisher
    from .command_subscriber import CommandSubscriber
    from .state_manager import StateManager


class ApplicationState:
    """Shared application state for runtime operations and system management.
    
    Holds references to all major components and runtime state needed for
    stats collection, configuration reload, and graceful shutdown.
    
    Attributes:
        config_path: Path to the configuration file.
        config: Loaded configuration object.
        shutdown_event: Event to signal graceful shutdown.
        start_time: Unix timestamp when application started.
        event_publisher: EventPublisher instance (set after initialization).
        command_subscriber: CommandSubscriber instance (set after initialization).
        connector: CytubeConnector instance (set after initialization).
        nats_client: NatsClient instance (set after initialization).
        state_manager: StateManager instance (set after initialization).
        
    Examples:
        >>> from .config import load_config
        >>> config = load_config("config.json")
        >>> app_state = ApplicationState("config.json", config)
        >>> 
        >>> # Later, after component initialization
        >>> app_state.connector = connector
        >>> app_state.nats_client = nats_client
        >>> 
        >>> # Check uptime
        >>> uptime = time.time() - app_state.start_time
    """
    
    def __init__(self, config_path: str, config: 'KrytenConfig'):
        """Initialize application state.
        
        Args:
            config_path: Path to configuration file.
            config: Loaded configuration object.
        """
        self.config_path = config_path
        self.config = config
        self.shutdown_event = asyncio.Event()
        self.start_time = time.time()
        
        # Component references (set by main after initialization)
        self.event_publisher: Optional['EventPublisher'] = None
        self.command_subscriber: Optional['CommandSubscriber'] = None
        self.connector: Optional['CytubeConnector'] = None
        self.nats_client: Optional['NatsClient'] = None
        self.state_manager: Optional['StateManager'] = None
    
    def get_uptime(self) -> float:
        """Get application uptime in seconds.
        
        Returns:
            Seconds since application started.
            
        Examples:
            >>> uptime = app_state.get_uptime()
            >>> print(f"Uptime: {uptime / 3600:.1f} hours")
        """
        return time.time() - self.start_time
    
    def request_shutdown(self, reason: str = "Unknown") -> None:
        """Request graceful shutdown of the application.
        
        Args:
            reason: Reason for shutdown (for logging).
            
        Examples:
            >>> app_state.request_shutdown("User requested")
        """
        if not self.shutdown_event.is_set():
            self.shutdown_event.set()


__all__ = ["ApplicationState"]

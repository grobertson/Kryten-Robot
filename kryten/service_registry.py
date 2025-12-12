"""Service Registry - Track and monitor Kryten microservices.

This module provides service discovery and health monitoring for the Kryten
ecosystem. It subscribes to lifecycle events from all services and maintains
an inventory of active services with their heartbeat status.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .nats_client import NatsClient


@dataclass
class ServiceInfo:
    """Information about a registered service.
    
    Attributes:
        name: Service name (e.g., "userstats", "moderator")
        version: Service version string
        hostname: Hostname where service is running
        first_seen: Timestamp when service was first discovered
        last_heartbeat: Timestamp of most recent heartbeat
        last_startup: Timestamp of most recent startup event
        heartbeat_count: Total number of heartbeats received
        metadata: Additional service-specific metadata
    """
    name: str
    version: str
    hostname: str
    first_seen: datetime
    last_heartbeat: datetime
    last_startup: datetime
    heartbeat_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def seconds_since_heartbeat(self) -> float:
        """Calculate seconds since last heartbeat."""
        return (datetime.now(UTC) - self.last_heartbeat).total_seconds()
    
    @property
    def is_stale(self) -> bool:
        """Check if service appears offline (no heartbeat in 90 seconds)."""
        return self.seconds_since_heartbeat > 90
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "hostname": self.hostname,
            "first_seen": self.first_seen.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "last_startup": self.last_startup.isoformat(),
            "heartbeat_count": self.heartbeat_count,
            "seconds_since_heartbeat": self.seconds_since_heartbeat,
            "is_stale": self.is_stale,
            "metadata": self.metadata,
        }


class ServiceRegistry:
    """Monitor and track Kryten microservices.
    
    Subscribes to lifecycle events from all services and maintains a registry
    of active services with their health status.
    
    Subscriptions:
        - kryten.lifecycle.*.startup - Service startup notifications
        - kryten.lifecycle.*.heartbeat - Service heartbeat events
        - kryten.lifecycle.*.shutdown - Service shutdown notifications
    
    Attributes:
        nats_client: NATS client for subscriptions
        logger: Logger instance
        services: Dictionary of registered services by name
    
    Examples:
        >>> registry = ServiceRegistry(nats_client, logger)
        >>> await registry.start()
        >>> services = registry.get_active_services()
        >>> await registry.stop()
    """
    
    def __init__(
        self,
        nats_client: NatsClient,
        logger: logging.Logger,
    ):
        """Initialize service registry.
        
        Args:
            nats_client: NATS client for event subscriptions
            logger: Logger for structured output
        """
        self._nats = nats_client
        self._logger = logger
        self._running = False
        
        # Service tracking
        self._services: dict[str, ServiceInfo] = {}
        self._lock = asyncio.Lock()
        
        # Subscriptions
        self._startup_sub = None
        self._heartbeat_sub = None
        self._shutdown_sub = None
        
        # Callbacks for service events
        self._on_service_registered: Callable[[ServiceInfo], None] | None = None
        self._on_service_heartbeat: Callable[[ServiceInfo], None] | None = None
        self._on_service_shutdown: Callable[[str], None] | None = None
    
    @property
    def is_running(self) -> bool:
        """Check if registry is running."""
        return self._running
    
    @property
    def service_count(self) -> int:
        """Get count of registered services."""
        return len(self._services)
    
    def on_service_registered(self, callback: Callable[[ServiceInfo], None]) -> None:
        """Register callback for when new service is discovered.
        
        Args:
            callback: Function to call with ServiceInfo when service registers
        """
        self._on_service_registered = callback
    
    def on_service_heartbeat(self, callback: Callable[[ServiceInfo], None]) -> None:
        """Register callback for service heartbeat events.
        
        Args:
            callback: Function to call with ServiceInfo on each heartbeat
        """
        self._on_service_heartbeat = callback
    
    def on_service_shutdown(self, callback: Callable[[str], None]) -> None:
        """Register callback for service shutdown events.
        
        Args:
            callback: Function to call with service name on shutdown
        """
        self._on_service_shutdown = callback
    
    async def start(self) -> None:
        """Start service registry and subscribe to lifecycle events."""
        if self._running:
            self._logger.warning("Service registry already running")
            return
        
        self._running = True
        
        try:
            # Subscribe to startup events from all services
            self._startup_sub = await self._nats.subscribe_request_reply(
                "kryten.lifecycle.*.startup",
                callback=self._handle_startup
            )
            self._logger.info("Subscribed to kryten.lifecycle.*.startup")
            
            # Subscribe to heartbeat events from all services
            self._heartbeat_sub = await self._nats.subscribe_request_reply(
                "kryten.lifecycle.*.heartbeat",
                callback=self._handle_heartbeat
            )
            self._logger.info("Subscribed to kryten.lifecycle.*.heartbeat")
            
            # Subscribe to shutdown events from all services
            self._shutdown_sub = await self._nats.subscribe_request_reply(
                "kryten.lifecycle.*.shutdown",
                callback=self._handle_shutdown
            )
            self._logger.info("Subscribed to kryten.lifecycle.*.shutdown")
            
            self._logger.info("Service registry started")
            
        except Exception as e:
            self._logger.error(f"Failed to start service registry: {e}", exc_info=True)
            self._running = False
            raise
    
    async def stop(self) -> None:
        """Stop service registry and unsubscribe from events."""
        if not self._running:
            return
        
        self._running = False
        
        # Unsubscribe from all events
        for sub in [self._startup_sub, self._heartbeat_sub, self._shutdown_sub]:
            if sub:
                try:
                    await sub.unsubscribe()
                except Exception as e:
                    self._logger.warning(f"Error unsubscribing: {e}")
        
        self._startup_sub = None
        self._heartbeat_sub = None
        self._shutdown_sub = None
        
        self._logger.info("Service registry stopped")
    
    async def _handle_startup(self, msg) -> None:
        """Handle service startup event."""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            service_name = data.get("service")
            
            if not service_name:
                return
            
            # Extract service information
            version = data.get("version", "unknown")
            hostname = data.get("hostname", "unknown")
            timestamp = datetime.fromisoformat(data.get("timestamp", datetime.now(UTC).isoformat()))
            
            async with self._lock:
                is_new = service_name not in self._services
                
                if is_new:
                    # New service discovered
                    service_info = ServiceInfo(
                        name=service_name,
                        version=version,
                        hostname=hostname,
                        first_seen=timestamp,
                        last_heartbeat=timestamp,
                        last_startup=timestamp,
                        metadata=data,
                    )
                    self._services[service_name] = service_info
                    self._logger.info(
                        f"Service registered: {service_name} v{version} on {hostname}"
                    )
                    
                    # Trigger callback
                    if self._on_service_registered:
                        try:
                            self._on_service_registered(service_info)
                        except Exception as e:
                            self._logger.error(f"Error in service registered callback: {e}")
                else:
                    # Service restarted
                    service_info = self._services[service_name]
                    service_info.version = version
                    service_info.hostname = hostname
                    service_info.last_startup = timestamp
                    service_info.last_heartbeat = timestamp
                    service_info.metadata = data
                    self._logger.info(
                        f"Service restarted: {service_name} v{version} on {hostname}"
                    )
        
        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid startup event JSON: {e}")
        except Exception as e:
            self._logger.error(f"Error handling startup event: {e}", exc_info=True)
    
    async def _handle_heartbeat(self, msg) -> None:
        """Handle service heartbeat event."""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            service_name = data.get("service")
            
            if not service_name:
                return
            
            timestamp = datetime.fromisoformat(data.get("timestamp", datetime.now(UTC).isoformat()))
            
            async with self._lock:
                if service_name in self._services:
                    service_info = self._services[service_name]
                    service_info.last_heartbeat = timestamp
                    service_info.heartbeat_count += 1
                    
                    self._logger.debug(
                        f"Heartbeat from {service_name} "
                        f"(count: {service_info.heartbeat_count})"
                    )
                    
                    # Trigger callback
                    if self._on_service_heartbeat:
                        try:
                            self._on_service_heartbeat(service_info)
                        except Exception as e:
                            self._logger.error(f"Error in heartbeat callback: {e}")
                else:
                    # Heartbeat from unknown service - log warning
                    self._logger.warning(
                        f"Heartbeat from unregistered service: {service_name} "
                        "(may have missed startup event)"
                    )
        
        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid heartbeat event JSON: {e}")
        except Exception as e:
            self._logger.error(f"Error handling heartbeat event: {e}", exc_info=True)
    
    async def _handle_shutdown(self, msg) -> None:
        """Handle service shutdown event."""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            service_name = data.get("service")
            reason = data.get("reason", "Unknown")
            
            if not service_name:
                return
            
            async with self._lock:
                if service_name in self._services:
                    del self._services[service_name]
                    self._logger.info(f"Service shutdown: {service_name} ({reason})")
                    
                    # Trigger callback
                    if self._on_service_shutdown:
                        try:
                            self._on_service_shutdown(service_name)
                        except Exception as e:
                            self._logger.error(f"Error in shutdown callback: {e}")
        
        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid shutdown event JSON: {e}")
        except Exception as e:
            self._logger.error(f"Error handling shutdown event: {e}", exc_info=True)
    
    def get_service(self, name: str) -> ServiceInfo | None:
        """Get information about a specific service.
        
        Args:
            name: Service name
            
        Returns:
            ServiceInfo if service is registered, None otherwise
        """
        return self._services.get(name)
    
    def get_all_services(self) -> list[ServiceInfo]:
        """Get information about all registered services.
        
        Returns:
            List of ServiceInfo objects for all services
        """
        return list(self._services.values())
    
    def get_active_services(self) -> list[ServiceInfo]:
        """Get only active services (not stale).
        
        Returns:
            List of ServiceInfo objects for services with recent heartbeats
        """
        return [s for s in self._services.values() if not s.is_stale]
    
    def get_stale_services(self) -> list[ServiceInfo]:
        """Get services that appear offline (stale heartbeats).
        
        Returns:
            List of ServiceInfo objects for services with stale heartbeats
        """
        return [s for s in self._services.values() if s.is_stale]


__all__ = ["ServiceRegistry", "ServiceInfo"]

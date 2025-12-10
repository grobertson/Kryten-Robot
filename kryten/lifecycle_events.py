"""Lifecycle Event Publisher for Kryten Services.

This module provides lifecycle event publishing for Kryten services, including:
- Service startup/shutdown events
- Connection/disconnection events
- Groupwide restart coordination

These events allow other Kryten services to monitor system health and coordinate
restarts across the service group.
"""

import json
import logging
import socket
from datetime import UTC, datetime
from typing import Any

from .nats_client import NatsClient


class LifecycleEventPublisher:
    """Publisher for service lifecycle events.

    Publishes events for service startup, shutdown, connection changes, and
    subscribes to groupwide restart notices.

    Subject patterns:
        - kryten.lifecycle.{service}.startup
        - kryten.lifecycle.{service}.shutdown
        - kryten.lifecycle.{service}.connected
        - kryten.lifecycle.{service}.disconnected
        - kryten.lifecycle.group.restart (broadcast to all services)

    Attributes:
        service_name: Name of this service (e.g., "robot", "userstats")
        nats_client: NATS client for publishing events.
        logger: Logger instance.

    Examples:
        >>> lifecycle = LifecycleEventPublisher("robot", nats_client, logger)
        >>> await lifecycle.start()
        >>> await lifecycle.publish_startup()
        >>> # ... service runs ...
        >>> await lifecycle.publish_shutdown()
        >>> await lifecycle.stop()
    """

    def __init__(
        self,
        service_name: str,
        nats_client: NatsClient,
        logger: logging.Logger,
        version: str = "unknown",
    ):
        """Initialize lifecycle event publisher.

        Args:
            service_name: Name of this service (robot, userstats, etc.).
            nats_client: NATS client for event publishing.
            logger: Logger for structured output.
            version: Service version string.
        """
        self._service_name = service_name
        self._nats = nats_client
        self._logger = logger
        self._version = version
        self._running = False
        self._subscription = None
        self._restart_callback: callable | None = None

        # Service metadata
        self._hostname = socket.gethostname()
        self._start_time: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Check if lifecycle publisher is running."""
        return self._running

    async def start(self) -> None:
        """Start lifecycle event publisher and subscribe to group events."""
        if self._running:
            self._logger.warning("Lifecycle event publisher already running")
            return

        self._running = True
        self._start_time = datetime.now(UTC)

        # Subscribe to groupwide restart notices
        try:
            self._subscription = await self._nats.subscribe(
                "kryten.lifecycle.group.restart",
                callback=self._handle_restart_notice
            )
            self._logger.info("Subscribed to groupwide restart notices")
        except Exception as e:
            self._logger.error(f"Failed to subscribe to restart notices: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop lifecycle event publisher."""
        if not self._running:
            return

        if self._subscription:
            try:
                await self._subscription.unsubscribe()
            except Exception as e:
                self._logger.warning(f"Error unsubscribing from restart notices: {e}")

        self._subscription = None
        self._running = False

    def on_restart_notice(self, callback: callable) -> None:
        """Register callback for groupwide restart notices.

        Args:
            callback: Async function to call when restart notice received.
                      Signature: async def callback(data: dict) -> None
        """
        self._restart_callback = callback

    async def _handle_restart_notice(self, msg) -> None:
        """Handle incoming groupwide restart notice."""
        try:
            data = json.loads(msg.data.decode('utf-8'))

            # Extract restart parameters
            initiator = data.get('initiator', 'unknown')
            reason = data.get('reason', 'No reason provided')
            delay_seconds = data.get('delay_seconds', 5)

            self._logger.warning(
                f"Groupwide restart notice received from {initiator}: {reason} "
                f"(restarting in {delay_seconds}s)"
            )

            # Call registered callback if any
            if self._restart_callback:
                try:
                    await self._restart_callback(data)
                except Exception as e:
                    self._logger.error(f"Error in restart callback: {e}", exc_info=True)

        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid restart notice JSON: {e}")
        except Exception as e:
            self._logger.error(f"Error handling restart notice: {e}", exc_info=True)

    def _build_base_payload(self) -> dict[str, Any]:
        """Build base event payload with common metadata."""
        uptime = None
        if self._start_time:
            uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        return {
            "service": self._service_name,
            "version": self._version,
            "hostname": self._hostname,
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": uptime,
        }

    async def publish_startup(self, **extra_data) -> None:
        """Publish service startup event.

        Args:
            **extra_data: Additional key-value pairs to include in event.
        """
        subject = f"kryten.lifecycle.{self._service_name}.startup"
        payload = self._build_base_payload()
        payload.update(extra_data)

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            await self._nats.publish(subject, data_bytes)
            self._logger.info(f"Published startup event to {subject}")
        except Exception as e:
            self._logger.error(f"Failed to publish startup event: {e}", exc_info=True)

    async def publish_shutdown(self, reason: str = "Normal shutdown", **extra_data) -> None:
        """Publish service shutdown event.

        Args:
            reason: Reason for shutdown.
            **extra_data: Additional key-value pairs to include in event.
        """
        subject = f"kryten.lifecycle.{self._service_name}.shutdown"
        payload = self._build_base_payload()
        payload["reason"] = reason
        payload.update(extra_data)

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            await self._nats.publish(subject, data_bytes)
            self._logger.info(f"Published shutdown event to {subject}")
        except Exception as e:
            self._logger.error(f"Failed to publish shutdown event: {e}", exc_info=True)

    async def publish_connected(self, target: str, **extra_data) -> None:
        """Publish connection established event.

        Args:
            target: Connection target (e.g., "CyTube", "NATS", "Database").
            **extra_data: Additional key-value pairs to include in event.
        """
        subject = f"kryten.lifecycle.{self._service_name}.connected"
        payload = self._build_base_payload()
        payload["target"] = target
        payload.update(extra_data)

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            await self._nats.publish(subject, data_bytes)
            self._logger.debug(f"Published connected event to {subject}")
        except Exception as e:
            self._logger.error(f"Failed to publish connected event: {e}", exc_info=True)

    async def publish_disconnected(self, target: str, reason: str = "Unknown", **extra_data) -> None:
        """Publish connection lost event.

        Args:
            target: Connection target (e.g., "CyTube", "NATS").
            reason: Reason for disconnection.
            **extra_data: Additional key-value pairs to include in event.
        """
        subject = f"kryten.lifecycle.{self._service_name}.disconnected"
        payload = self._build_base_payload()
        payload["target"] = target
        payload["reason"] = reason
        payload.update(extra_data)

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            await self._nats.publish(subject, data_bytes)
            self._logger.warning(f"Published disconnected event to {subject}")
        except Exception as e:
            self._logger.error(f"Failed to publish disconnected event: {e}", exc_info=True)

    async def publish_group_restart(
        self,
        reason: str,
        delay_seconds: int = 5,
        initiator: str | None = None,
        **extra_data
    ) -> None:
        """Publish groupwide restart notice to all Kryten services.

        Args:
            reason: Reason for restart (e.g., "Configuration update").
            delay_seconds: Seconds to wait before restarting.
            initiator: Service/user initiating restart.
            **extra_data: Additional key-value pairs to include in event.
        """
        subject = "kryten.lifecycle.group.restart"
        payload = {
            "initiator": initiator or self._service_name,
            "reason": reason,
            "delay_seconds": delay_seconds,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        payload.update(extra_data)

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            await self._nats.publish(subject, data_bytes)
            self._logger.warning(
                f"Published groupwide restart notice: {reason} "
                f"(delay: {delay_seconds}s)"
            )
        except Exception as e:
            self._logger.error(f"Failed to publish restart notice: {e}", exc_info=True)


__all__ = ["LifecycleEventPublisher"]

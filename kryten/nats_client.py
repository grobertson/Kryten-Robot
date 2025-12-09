"""NATS Client Wrapper for Event Publishing and Subscriptions.

This module provides an asynchronous NATS client wrapper with connection
lifecycle management, automatic reconnection, and error handling.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable

import nats
from nats.aio.client import Client as NATS
from nats.aio.subscription import Subscription

from .config import NatsConfig
from .errors import ConnectionError, NotConnectedError


class NatsClient:
    """Asynchronous NATS client wrapper with lifecycle management.

    Provides a clean interface for connecting to NATS servers and publishing
    messages with automatic reconnection and error handling.

    Attributes:
        config: NATS connection configuration.
        logger: Logger instance for structured logging.
        is_connected: Whether currently connected to NATS.
        stats: Publishing statistics (messages, bytes, errors).

    Examples:
        >>> config = NatsConfig(servers=["nats://localhost:4222"])
        >>> async with NatsClient(config, logger) as client:
        ...     await client.publish("test.subject", b"hello")
    """

    def __init__(self, config: NatsConfig, logger: logging.Logger):
        """Initialize NATS client.

        Args:
            config: NATS connection configuration.
            logger: Logger for structured output.
        """
        self.config = config
        self.logger = logger
        self._nc: Optional[NATS] = None
        self._connected = False

        # Statistics tracking
        self._messages_published = 0
        self._bytes_sent = 0
        self._errors = 0

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to NATS.

        Returns:
            True if connected and client is active, False otherwise.
        """
        return self._connected and self._nc is not None and self._nc.is_connected

    @property
    def stats(self) -> Dict[str, int]:
        """Get publishing statistics.

        Returns:
            Dictionary with 'messages_published', 'bytes_sent', 'errors' counts.

        Examples:
            >>> stats = client.stats
            >>> print(f"Published: {stats['messages_published']}")
        """
        return {
            'messages_published': self._messages_published,
            'bytes_sent': self._bytes_sent,
            'errors': self._errors,
        }

    async def connect(self) -> None:
        """Establish connection to NATS servers.

        Attempts to connect to configured NATS servers with automatic
        reconnection support if enabled.

        Raises:
            ConnectionError: If connection cannot be established.
            asyncio.CancelledError: If connection is cancelled.

        Examples:
            >>> client = NatsClient(config, logger)
            >>> await client.connect()
            >>> assert client.is_connected
        """
        if self._connected:
            self.logger.warning("Already connected to NATS, ignoring connect() call")
            return

        self.logger.info(
            "Connecting to NATS",
            extra={"servers": self.config.servers}
        )

        try:
            # Create NATS client
            self._nc = NATS()

            # Configure connection options
            options = {
                "servers": self.config.servers,
                "connect_timeout": self.config.connect_timeout,
                "max_reconnect_attempts": self.config.max_reconnect_attempts if self.config.allow_reconnect else 0,
                "reconnect_time_wait": self.config.reconnect_time_wait,
                "allow_reconnect": self.config.allow_reconnect,
                "error_cb": self._error_callback,
                "disconnected_cb": self._disconnected_callback,
                "reconnected_cb": self._reconnected_callback,
                "closed_cb": self._closed_callback,
            }

            # Add credentials if provided
            if self.config.user and self.config.password:
                options["user"] = self.config.user
                options["password"] = self.config.password
                self.logger.debug("Using NATS credentials for authentication")

            # Connect
            await self._nc.connect(**options)

            self._connected = True
            self.logger.info(
                "Connected to NATS",
                extra={
                    "servers": self.config.servers,
                    "server_info": self._nc.connected_server_version
                }
            )

        except asyncio.CancelledError:
            self.logger.warning("NATS connection cancelled")
            await self._cleanup()
            raise

        except Exception as e:
            self.logger.error(
                "Failed to connect to NATS",
                extra={"servers": self.config.servers, "error": str(e)}
            )
            await self._cleanup()
            raise ConnectionError(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Drain and close NATS connection gracefully.

        Flushes pending messages before disconnecting. Safe to call
        multiple times or when not connected.

        Examples:
            >>> await client.connect()
            >>> await client.disconnect()
            >>> assert not client.is_connected
        """
        if not self._connected:
            self.logger.debug("Not connected to NATS, disconnect() is a no-op")
            return

        self.logger.info("Disconnecting from NATS")

        await self._cleanup()

        self.logger.info("Disconnected from NATS")

    async def _cleanup(self) -> None:
        """Clean up resources and reset state.

        Internal method for draining, closing connection, and resetting state.
        """
        self._connected = False

        if self._nc:
            try:
                # Drain to flush pending messages
                await self._nc.drain()
            except Exception as e:
                self.logger.warning(f"Error draining NATS connection: {e}")

            try:
                # Close connection
                if not self._nc.is_closed:
                    await self._nc.close()
            except Exception as e:
                self.logger.warning(f"Error closing NATS connection: {e}")

            finally:
                self._nc = None

    async def publish(self, subject: str, data: bytes) -> None:
        """Publish message to NATS subject.

        Args:
            subject: NATS subject name (e.g., "cytube.events.chatMsg").
            data: Message payload as bytes.

        Raises:
            NotConnectedError: If not connected to NATS.
            ValueError: If subject is empty or data is not bytes.

        Examples:
            >>> await client.publish("test.subject", b"hello world")
        """
        if not self.is_connected:
            raise NotConnectedError("Not connected to NATS server")

        if not subject:
            raise ValueError("Subject cannot be empty")

        if not isinstance(data, bytes):
            raise ValueError("Data must be bytes")

        try:
            await self._nc.publish(subject, data)
            self._messages_published += 1
            self._bytes_sent += len(data)

            self.logger.debug(
                "Published message to NATS",
                extra={"subject": subject, "size": len(data)}
            )

        except Exception as e:
            self._errors += 1
            self.logger.error(
                "Failed to publish message",
                extra={"subject": subject, "error": str(e)}
            )
            raise

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[str, bytes], Awaitable[None]]
    ) -> Subscription:
        """Subscribe to NATS subject with callback.

        Args:
            subject: NATS subject pattern (e.g., "cytube.commands.>").
            callback: Async callback function(subject: str, data: bytes).

        Returns:
            Subscription object that can be used to unsubscribe.

        Raises:
            NotConnectedError: If not connected to NATS.
            ValueError: If subject is empty or callback is not callable.

        Examples:
            >>> async def handler(subject: str, data: bytes):
            ...     print(f"Received on {subject}: {data}")
            >>> sub = await client.subscribe("test.>", handler)
        """
        if not self.is_connected:
            raise NotConnectedError("Not connected to NATS server")

        if not subject:
            raise ValueError("Subject cannot be empty")

        if not callable(callback):
            raise ValueError("Callback must be callable")

        try:
            # NATS callback receives a Msg object, we need to adapt it
            async def nats_callback(msg):
                await callback(msg.subject, msg.data)

            subscription = await self._nc.subscribe(subject, cb=nats_callback)

            self.logger.debug(
                "Subscribed to NATS subject",
                extra={"subject": subject}
            )

            return subscription

        except Exception as e:
            self._errors += 1
            self.logger.error(
                "Failed to subscribe to subject",
                extra={"subject": subject, "error": str(e)}
            )
            raise

    async def subscribe_request_reply(
        self,
        subject: str,
        callback: Callable[[Any], Awaitable[None]]
    ) -> Subscription:
        """Subscribe to NATS subject for request-reply pattern.

        Unlike regular subscribe, this passes the full NATS Msg object to the callback,
        allowing access to msg.reply for sending responses.

        Args:
            subject: NATS subject pattern (e.g., "kryten.robot.command").
            callback: Async callback function(msg: Msg) that receives full message.

        Returns:
            Subscription object that can be used to unsubscribe.

        Raises:
            NotConnectedError: If not connected to NATS.
            ValueError: If subject is empty or callback is not callable.

        Examples:
            >>> async def handler(msg):
            ...     request = json.loads(msg.data.decode())
            ...     response = {"result": "ok"}
            ...     await nats.publish(msg.reply, json.dumps(response).encode())
            >>> sub = await client.subscribe_request_reply("kryten.robot.command", handler)
        """
        if not self.is_connected:
            raise NotConnectedError("Not connected to NATS server")

        if not subject:
            raise ValueError("Subject cannot be empty")

        if not callable(callback):
            raise ValueError("Callback must be callable")

        try:
            # Pass the full msg object directly to callback
            subscription = await self._nc.subscribe(subject, cb=callback)

            self.logger.debug(
                "Subscribed to NATS subject (request-reply)",
                extra={"subject": subject}
            )

            return subscription

        except Exception as e:
            self._errors += 1
            self.logger.error(
                "Failed to subscribe to subject",
                extra={"subject": subject, "error": str(e)}
            )
            raise

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from NATS subject.

        Args:
            subscription: Subscription object from subscribe().

        Examples:
            >>> sub = await client.subscribe("test.>", handler)
            >>> await client.unsubscribe(sub)
        """
        if subscription:
            try:
                await subscription.unsubscribe()
                self.logger.debug("Unsubscribed from NATS subject")
            except Exception as e:
                self.logger.warning(f"Error unsubscribing: {e}")

    async def _error_callback(self, error: Exception) -> None:
        """Callback for NATS connection errors.

        Args:
            error: Exception that occurred.
        """
        self.logger.error(f"NATS error: {error}")
        self._errors += 1

    async def _disconnected_callback(self) -> None:
        """Callback when disconnected from NATS."""
        self.logger.warning("Disconnected from NATS server")
        self._connected = False

    async def _reconnected_callback(self) -> None:
        """Callback when reconnected to NATS."""
        self.logger.info("Reconnected to NATS server")
        self._connected = True

    async def _closed_callback(self) -> None:
        """Callback when NATS connection is closed."""
        self.logger.info("NATS connection closed")
        self._connected = False

    async def __aenter__(self):
        """Async context manager entry.

        Automatically connects when entering the context.

        Returns:
            Self for use in context.

        Examples:
            >>> async with NatsClient(config, logger) as client:
            ...     await client.publish("test", b"data")
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit.

        Ensures disconnect is called even if an exception occurs.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.

        Returns:
            False to propagate exceptions.
        """
        await self.disconnect()
        return False


__all__ = ["NatsClient"]

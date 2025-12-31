"""CyTube Connector Core Lifecycle Management.

This module provides the asynchronous CytubeConnector responsible for connecting,
authenticating, and joining CyTube channels with proper lifecycle management.
"""

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp

from .config import CytubeConfig
from .errors import AuthenticationError, ConnectionError, NotConnectedError
from .socket_io import SocketIO, SocketIOResponse


class CytubeConnector:
    """Asynchronous CyTube connector with lifecycle management.

    Orchestrates Socket.IO connection, authentication, and channel joining
    with exponential backoff retry logic and rate limiting handling.

    Attributes:
        config: CyTube connection configuration.
        logger: Logger instance for structured logging.
        is_connected: Whether connector is currently connected.

    Examples:
        >>> config = CytubeConfig(domain="cytu.be", channel="test")
        >>> async with CytubeConnector(config, logger) as connector:
        ...     # connector is connected
        ...     pass
        >>> # connector is automatically disconnected
    """

    def __init__(
        self,
        config: CytubeConfig,
        logger: logging.Logger,
        socket_factory: Callable | None = None,
    ):
        """Initialize CyTube connector.

        Args:
            config: CyTube connection configuration.
            logger: Logger for structured output.
            socket_factory: Optional factory for creating SocketIO instances
                (for dependency injection in tests).
        """
        self.config = config
        self.logger = logger
        self._socket_factory = socket_factory or SocketIO.connect
        self._socket: SocketIO | None = None
        self._connected = False
        self._user_rank: int = (
            0  # Track logged-in user's rank (0=guest, 1=registered, 2+=moderator/admin)
        )

        # Connection tracking
        self._connected_since: float | None = None
        self._reconnect_count: int = 0
        self._last_event_time: float | None = None

        # Event streaming support
        self._event_queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=1000)
        self._event_callbacks: dict[str, list[Callable[[str, dict], None]]] = {}
        self._messages_received = 0
        self._events_processed = 0
        self._consumer_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to CyTube.

        Returns:
            True if connected and socket is active, False otherwise.
        """
        return self._connected and self._socket is not None

    @property
    def user_rank(self) -> int:
        """Get the rank of the logged-in user.

        Returns:
            User rank: 0=guest, 1=registered, 2=moderator, 3+=admin.
        """
        return self._user_rank

    @property
    def connected_since(self) -> float | None:
        """Get timestamp when connection was established.

        Returns:
            Unix timestamp of connection time, or None if not connected.
        """
        return self._connected_since

    @property
    def reconnect_count(self) -> int:
        """Get number of reconnection attempts.

        Returns:
            Count of reconnection attempts since instance creation.
        """
        return self._reconnect_count

    @property
    def last_event_time(self) -> float | None:
        """Get timestamp of last received event.

        Returns:
            Unix timestamp of last event, or None if no events received.
        """
        return self._last_event_time

    @property
    def stats(self) -> dict[str, int]:
        """Get event streaming statistics.

        Returns:
            Dictionary with 'messages_received' and 'events_processed' counts.

        Examples:
            >>> stats = connector.stats
            >>> assert 'messages_received' in stats
            >>> assert 'events_processed' in stats
        """
        return {
            "messages_received": self._messages_received,
            "events_processed": self._events_processed,
        }

    async def emit(self, event: str, data: dict[str, Any]) -> None:
        """Emit an event to CyTube.

        Args:
            event: Event name.
            data: Event payload.

        Raises:
            NotConnectedError: If socket is not connected.
        """
        if not self._socket:
            raise NotConnectedError("Socket not connected")

        await self._socket.emit(event, data)

    async def connect(self) -> None:
        """Establish connection and authenticate with CyTube.

        Performs the following sequence:
        1. Fetch Socket.IO configuration from CyTube REST API
        2. Establish Socket.IO connection with exponential backoff retry
        3. Join channel (with password if configured)
        4. Authenticate user (registered or guest)

        Raises:
            ConnectionError: If connection cannot be established after retries.
            AuthenticationError: If authentication or channel join fails.
            asyncio.CancelledError: If connection is cancelled.

        Examples:
            >>> connector = CytubeConnector(config, logger)
            >>> await connector.connect()
            >>> assert connector.is_connected
        """
        if self._connected:
            self.logger.warning("Already connected, ignoring connect() call")
            return

        self.logger.info(
            "Connecting to CyTube",
            extra={"domain": self.config.domain, "channel": self.config.channel},
        )

        try:
            # Fetch Socket.IO endpoint configuration
            socket_config = await self._get_socket_config()
            socket_url = socket_config["url"]

            # Establish Socket.IO connection with retry
            self._socket = await self._socket_factory(
                url=socket_url,
                retry=0,  # We'll handle retries at this level
                qsize=100,
            )

            # Join channel
            await self._join_channel()

            # Authenticate user
            await self._authenticate_user()

            self._connected = True

            # Track connection timing
            import time

            if self._connected_since is not None:
                # This is a reconnection
                self._reconnect_count += 1
            self._connected_since = time.time()

            # Start event consumer task
            self._consumer_task = asyncio.create_task(self._consume_socket_events())

            # Request initial state from CyTube
            # This ensures KV stores are populated with complete state
            # even if bot starts after channel is already active
            await self._request_initial_state()

            self.logger.info(
                "Connected to CyTube",
                extra={
                    "domain": self.config.domain,
                    "channel": self.config.channel,
                    "user": self.config.user or "guest",
                },
            )

        except asyncio.CancelledError:
            self.logger.warning("Connection cancelled")
            await self._cleanup()
            raise

        except Exception as e:
            self.logger.error(
                "Failed to connect to CyTube",
                extra={
                    "domain": self.config.domain,
                    "channel": self.config.channel,
                    "error": str(e),
                },
            )
            await self._cleanup()
            raise

    async def disconnect(self) -> None:
        """Close connection gracefully.

        Closes the Socket.IO connection and cleans up resources.
        Safe to call multiple times or when not connected.

        Examples:
            >>> await connector.connect()
            >>> await connector.disconnect()
            >>> assert not connector.is_connected
        """
        if not self._connected:
            self.logger.debug("Not connected, disconnect() is a no-op")
            return

        self.logger.info(
            "Disconnecting from CyTube",
            extra={"domain": self.config.domain, "channel": self.config.channel},
        )

        await self._cleanup()

        self.logger.info("Disconnected from CyTube")

    async def _cleanup(self) -> None:
        """Clean up resources and reset state.

        Internal method for closing socket and resetting connection state.
        """
        self._connected = False
        self._connected_since = None

        # Cancel consumer task if running
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        if self._socket:
            try:
                await self._socket.close()
            except Exception as e:
                self.logger.warning(f"Error closing socket: {e}")
            finally:
                self._socket = None

    async def _get_socket_config(self) -> dict[str, Any]:
        """Fetch Socket.IO configuration from CyTube REST API.

        Queries the CyTube server for Socket.IO connection details including
        the WebSocket URL to use.

        Returns:
            Dictionary containing socket configuration with 'url' key.

        Raises:
            ConnectionError: If configuration cannot be fetched.

        Examples:
            >>> config = await connector._get_socket_config()
            >>> assert "url" in config
        """
        config_url = f"https://{self.config.domain}/socketconfig/{self.config.channel}.json"

        self.logger.debug(f"Fetching socket config from {config_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

            # Extract first server URL
            if "servers" not in data or not data["servers"]:
                raise ConnectionError("No servers in socket configuration")

            server = data["servers"][0]
            base_url = server["url"]

            # Construct Socket.IO URL
            socket_url = f"{base_url}/socket.io/"

            self.logger.debug(f"Socket.IO URL: {socket_url}")

            return {"url": socket_url}

        except aiohttp.ClientError as e:
            raise ConnectionError(f"Failed to fetch socket config: {e}") from e
        except (KeyError, IndexError) as e:
            raise ConnectionError(f"Invalid socket config format: {e}") from e

    async def _join_channel(self) -> None:
        """Send joinChannel event to enter the channel.

        Joins the configured channel, optionally providing channel password
        if one is configured.

        Raises:
            NotConnectedError: If socket is not connected.
            AuthenticationError: If channel password is incorrect.

        Examples:
            >>> await connector._join_channel()
        """
        if not self._socket:
            raise NotConnectedError("Socket not connected")

        self.logger.debug(f"Joining channel: {self.config.channel}")

        join_data = {"name": self.config.channel}

        # Add channel password if configured
        if self.config.channel_password:
            join_data["pw"] = self.config.channel_password

        # Send joinChannel event
        await self._socket.emit("joinChannel", join_data)

        # Wait for acknowledgment or error
        # CyTube sends 'needPassword' if password is wrong, or continues with channel data
        try:
            # Use a short timeout to see if we get immediate rejection
            response = await asyncio.wait_for(self._wait_for_channel_response(), timeout=2.0)

            if response and response[0] == "needPassword":
                raise AuthenticationError(
                    f"Invalid or missing password for channel: {self.config.channel}"
                )

        except TimeoutError:
            # Python 3.10 compat: asyncio.TimeoutError is separate from TimeoutError
            # No immediate rejection means join was accepted
            pass

        self.logger.debug(f"Joined channel: {self.config.channel}")

    async def _wait_for_channel_response(self) -> tuple[str, Any] | None:
        """Wait for channel-related response from server.

        Returns:
            Tuple of (event_name, data) if received, None on timeout.
        """
        if not self._socket:
            return None

        try:
            event, data = await self._socket.recv()
            return (event, data)
        except Exception:
            return None

    async def _authenticate_user(self) -> None:
        """Authenticate as registered user or guest.

        Sends login event with credentials (registered user) or just a name
        (guest user). Handles rate limiting for guest logins.

        Raises:
            NotConnectedError: If socket is not connected.
            AuthenticationError: If authentication fails.

        Examples:
            >>> await connector._authenticate_user()
        """
        if not self._socket:
            raise NotConnectedError("Socket not connected")

        if self.config.user and self.config.password:
            # Registered user authentication
            await self._authenticate_registered()
        else:
            # Guest authentication
            await self._authenticate_guest()

    async def _authenticate_registered(self) -> None:
        """Authenticate with username and password.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        if self._socket is None:
            raise NotConnectedError("Socket not connected")

        self.logger.debug(f"Authenticating as registered user: {self.config.user}")

        login_data = {
            "name": self.config.user,
            "pw": self.config.password,
        }

        # Create matcher for login response
        matcher = SocketIOResponse.match_event(r"^login$")

        # Send login event and wait for response
        response = await self._socket.emit("login", login_data, matcher, response_timeout=5.0)

        if not response:
            raise AuthenticationError("Login timeout - no response from server")

        event, data = response

        # Check if login was successful
        if not isinstance(data, dict) or not data.get("success"):
            error_msg = (
                data.get("error", "Unknown error") if isinstance(data, dict) else "Login failed"
            )
            raise AuthenticationError(f"Login failed: {error_msg}")

        # Store user rank from login response
        self._user_rank = data.get("rank", 1)  # Default to 1 (registered) if not provided
        self.logger.debug(f"Authenticated as: {self.config.user} (rank: {self._user_rank})")

    async def _authenticate_guest(self) -> None:
        """Authenticate as guest user.

        Handles rate limiting by parsing delay from error messages and
        automatically retrying after the specified wait period.

        Raises:
            AuthenticationError: If guest login fails after retries.
        """
        if self._socket is None:
            raise NotConnectedError("Socket not connected")

        guest_name = self.config.user or "Guest"
        self.logger.debug(f"Authenticating as guest: {guest_name}")

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            login_data = {"name": guest_name}

            # Create matcher for login response
            matcher = SocketIOResponse.match_event(r"^login$")

            # Send login event and wait for response
            response = await self._socket.emit("login", login_data, matcher, response_timeout=5.0)

            if not response:
                raise AuthenticationError("Guest login timeout - no response from server")

            event, data = response

            # Check if login was successful
            if isinstance(data, dict):
                if data.get("success"):
                    # Store user rank from login response (guests typically have rank 0)
                    self._user_rank = data.get("rank", 0)
                    self.logger.debug(
                        f"Authenticated as guest: {guest_name} (rank: {self._user_rank})"
                    )
                    return

                # Check for rate limiting
                error_msg = data.get("error", "")
                if "restricted" in error_msg.lower() or "wait" in error_msg.lower():
                    # Try to parse delay from message
                    delay = self._parse_rate_limit_delay(error_msg)

                    if delay and retry_count < max_retries - 1:
                        self.logger.warning(
                            f"Guest login rate limited, waiting {delay}s before retry"
                        )
                        await asyncio.sleep(delay)
                        retry_count += 1
                        continue

                raise AuthenticationError(f"Guest login failed: {error_msg}")

            retry_count += 1

        raise AuthenticationError("Guest login failed after maximum retries")

    def _parse_rate_limit_delay(self, error_message: str) -> int | None:
        """Parse rate limit delay from error message.

        Args:
            error_message: Error message from server (e.g., "restricted for 15 seconds").

        Returns:
            Delay in seconds if found, None otherwise.

        Examples:
            >>> delay = connector._parse_rate_limit_delay("restricted for 15 seconds")
            >>> assert delay == 15
        """
        # Pattern: "restricted for X seconds" or "wait X seconds"
        pattern = r"(?:restricted for|wait)\s+(\d+)\s+seconds?"
        match = re.search(pattern, error_message, re.IGNORECASE)

        if match:
            return int(match.group(1))

        return None

    async def _request_initial_state(self) -> None:
        """Request initial channel state from CyTube.

        Requests complete channel state after connecting:
        - Emits 'requestPlaylist' to get full playlist
        - Emits 'playerReady' to get currently playing media

        Note: CyTube automatically sends 'userlist' and 'emoteList' when
        joining a channel, so we don't need to explicitly request those.

        This ensures KV stores are populated with complete state even if
        the bot starts after the channel is already active, preventing
        gaps in state that would occur if we only relied on delta events.

        Raises:
            SocketIOError: If requests fail.
        """
        if not self._socket:
            self.logger.warning("Cannot request initial state: socket not connected")
            return

        self.logger.debug("Requesting initial state from CyTube")
        try:
            # Only request playlist if user has moderator+ permissions (rank >= 2)
            # CyTube restricts full playlist access to moderators and above
            if self._user_rank >= 2:
                await self._socket.emit("requestPlaylist", {})
                self.logger.debug(f"Playlist request sent (rank: {self._user_rank})")
            else:
                self.logger.debug(
                    f"Skipping playlist request - insufficient permissions (rank: {self._user_rank}, need >= 2)"
                )

            # Request current media state (available to all users)
            # CyTube will respond with 'changeMedia' event
            await self._socket.emit("playerReady", {})
            self.logger.debug("Player ready signal sent")

            # Give CyTube a moment to respond with state
            # The responses will be handled by the event consumer task
            await asyncio.sleep(0.5)

            self.logger.info("Initial state requested from CyTube")

        except Exception as e:
            # Don't fail connection if state request fails
            # We'll still get delta updates going forward
            self.logger.warning(f"Failed to request initial state: {e}")

    async def __aenter__(self):
        """Async context manager entry.

        Automatically connects when entering the context.

        Returns:
            Self for use in context.

        Examples:
            >>> async with CytubeConnector(config, logger) as connector:
            ...     assert connector.is_connected
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

    async def _consume_socket_events(self) -> None:
        """Internal task that consumes events from socket and queues them.

        Runs as a background task from connect() until disconnect().
        Handles queue overflow by dropping oldest events with warnings.
        Detects socket closure and marks connector as disconnected.
        """
        from .socket_io import ConnectionClosed as SocketIOConnectionClosed

        try:
            while self._connected and self._socket:
                try:
                    event_name, payload = await self._socket.recv()
                    self._messages_received += 1

                    # Track last event time
                    import time

                    self._last_event_time = time.time()

                    # Try to queue event, drop oldest if full
                    try:
                        self._event_queue.put_nowait((event_name, payload))
                    except asyncio.QueueFull:
                        # Drop oldest event and log warning
                        try:
                            self._event_queue.get_nowait()
                            self.logger.warning(
                                "Event queue full, dropping oldest event",
                                extra={"queue_size": self._event_queue.qsize()},
                            )
                        except asyncio.QueueEmpty:
                            pass
                        # Try to add new event again
                        try:
                            self._event_queue.put_nowait((event_name, payload))
                        except asyncio.QueueFull:
                            self.logger.error("Failed to queue event after drop")

                    # Fire registered callbacks
                    self._fire_callbacks(event_name, payload)

                except asyncio.CancelledError:
                    self.logger.debug("Event consumer cancelled")
                    break

                except SocketIOConnectionClosed as e:
                    # Socket has been closed by server or network issue
                    self.logger.warning(
                        f"Socket connection closed: {e}", extra={"was_connected": self._connected}
                    )
                    # Mark as disconnected so reconnection logic can kick in
                    self._connected = False
                    # Fire a synthetic disconnect event for listeners
                    self._fire_callbacks("_connection_lost", {"reason": str(e)})
                    break

                except Exception as e:
                    # Check if socket is in error state
                    if self._socket and self._socket.error is not None:
                        self.logger.warning(
                            f"Socket entered error state: {self._socket.error}",
                            extra={"last_event": e},
                        )
                        self._connected = False
                        self._fire_callbacks(
                            "_connection_lost", {"reason": str(self._socket.error)}
                        )
                        break

                    self.logger.error(f"Error consuming socket event: {e}")
                    # Continue processing other events unless disconnected
                    if not self._connected:
                        break

        except asyncio.CancelledError:
            self.logger.debug("Consumer task cancelled")
        except Exception as e:
            self.logger.error(f"Consumer task error: {e}", exc_info=True)
        finally:
            if self._connected:
                self.logger.warning("Consumer task exiting while still marked connected")
                self._connected = False
            self.logger.info("Event consumer task stopped")

    def _fire_callbacks(self, event_name: str, payload: dict) -> None:
        """Execute registered callbacks for an event.

        Args:
            event_name: Name of the event.
            payload: Event payload data.
        """
        callbacks = self._event_callbacks.get(event_name, [])

        for callback in callbacks:
            try:
                callback(event_name, payload)
            except Exception as e:
                self.logger.error(f"Error in event callback for '{event_name}': {e}", exc_info=True)

    def on_event(self, event_name: str, callback: Callable[[str, dict], None]) -> None:
        """Register callback for specific event type.

        The callback will be invoked synchronously for each matching event
        before it is yielded by recv_events(). Exceptions in callbacks are
        logged but do not affect event processing.

        Args:
            event_name: Name of event to listen for (e.g., 'chatMsg').
            callback: Function accepting (event_name, payload).

        Examples:
            >>> def on_chat(event, data):
            ...     print(f"Chat: {data.get('msg')}")
            >>> connector.on_event('chatMsg', on_chat)
        """
        if event_name not in self._event_callbacks:
            self._event_callbacks[event_name] = []

        if callback not in self._event_callbacks[event_name]:
            self._event_callbacks[event_name].append(callback)
            self.logger.debug(f"Registered callback for event: {event_name}")

    def off_event(self, event_name: str, callback: Callable[[str, dict], None]) -> None:
        """Unregister callback for specific event type.

        Args:
            event_name: Name of event to stop listening for.
            callback: Previously registered callback function.

        Examples:
            >>> connector.off_event('chatMsg', on_chat)
        """
        if event_name in self._event_callbacks:
            try:
                self._event_callbacks[event_name].remove(callback)
                self.logger.debug(f"Unregistered callback for event: {event_name}")

                # Clean up empty callback lists
                if not self._event_callbacks[event_name]:
                    del self._event_callbacks[event_name]
            except ValueError:
                self.logger.warning(f"Callback not found for event: {event_name}")

    async def recv_events(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Async generator yielding raw CyTube events.

        Yields events in FIFO order as (event_name, payload) tuples.
        Stops cleanly when disconnect() is called or connection is lost.

        Yields:
            Tuple of (event_name, payload) for each received event.

        Raises:
            ConnectionError: If socket disconnects unexpectedly.
            NotConnectedError: If called before connect().

        Examples:
            >>> async for event_name, payload in connector.recv_events():
            ...     print(f"{event_name}: {payload}")
        """
        if not self._connected:
            raise NotConnectedError("Must connect before receiving events")

        try:
            while self._connected:
                try:
                    # Wait for event with timeout to check connection status
                    event_name, payload = await asyncio.wait_for(
                        self._event_queue.get(), timeout=1.0
                    )
                    self._events_processed += 1
                    yield event_name, payload

                except TimeoutError:
                    # Python 3.10 compatibility: asyncio.TimeoutError is separate from TimeoutError
                    # In Python 3.11+, they are the same, but we need to catch both for 3.10
                    # No event received, check if still connected
                    if not self._connected:
                        break
                    continue

        except asyncio.CancelledError:
            self.logger.debug("Event iteration cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error in event iteration: {e}", exc_info=True)
            raise ConnectionError(f"Event stream error: {e}") from e
        finally:
            self.logger.debug("Event iteration stopped")


__all__ = ["CytubeConnector"]

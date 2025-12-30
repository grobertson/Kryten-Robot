"""Standalone Socket.IO Transport Layer for Kryten.

This module provides a self-contained asynchronous Socket.IO v2 client
implementation tuned for CyTube communication. It handles the Socket.IO
handshake, websocket upgrade, heartbeat management, and event marshaling
without depending on legacy shared modules.
"""

import asyncio
import json
import logging
import re
from collections.abc import Callable
from time import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from websockets.client import WebSocketClientProtocol
else:
    WebSocketClientProtocol = object

import websockets
from websockets.exceptions import (
    ConnectionClosed as WebSocketConnectionClosed,
)
from websockets.exceptions import (
    InvalidHandshake,
    InvalidState,
    PayloadTooBig,
    WebSocketProtocolError,
)

# ============================================================================
# Exception Classes
# ============================================================================


class SocketIOError(Exception):
    """Base class for all Socket.IO transport exceptions."""


class ConnectionFailed(SocketIOError):
    """Exception raised when connection to server fails."""


class ConnectionClosed(SocketIOError):
    """Exception raised when connection to server is closed."""


class PingTimeout(ConnectionClosed):
    """Exception raised when server fails to respond to ping within timeout."""


# ============================================================================
# Utility Functions
# ============================================================================


async def default_get(url: str) -> str:
    """Default HTTP GET implementation using aiohttp.

    Parameters
    ----------
    url : str
        URL to fetch.

    Returns
    -------
    str
        Response text.
    """
    try:
        import aiohttp
    except ImportError as ex:
        raise ImportError(
            "aiohttp is required for HTTP polling. "
            "Install with: pip install aiohttp"
        ) from ex

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


def _current_task(loop: asyncio.AbstractEventLoop) -> asyncio.Task | None:
    """Get the current task, compatible with Python 3.6+.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        Event loop.

    Returns
    -------
    asyncio.Task or None
        Current task if available.
    """
    try:
        return asyncio.current_task(loop)
    except AttributeError:
        # Python 3.6 compatibility
        return asyncio.Task.current_task(loop)  # type: ignore[attr-defined]


# ============================================================================
# Response Matching
# ============================================================================


class SocketIOResponse:
    """Socket.IO event response tracker.

    Tracks a pending response to an emitted event, matching incoming
    events against a predicate function and resolving a future when matched.

    Attributes
    ----------
    id : int
        Unique response identifier.
    match : Callable[[str, Any], bool]
        Predicate function matching (event_name, data) tuples.
    future : asyncio.Future
        Future resolved when matching response arrives.
    """

    MAX_ID = 2**32
    last_id = 0

    def __init__(self, match: Callable[[str, Any], bool]):
        """Initialize response tracker.

        Parameters
        ----------
        match : Callable[[str, Any], bool]
            Predicate function that returns True for matching events.
        """
        self.id = (self.__class__.last_id + 1) % self.MAX_ID
        self.__class__.last_id = self.id
        self.match = match
        self.future: asyncio.Future = asyncio.Future()

    def __eq__(self, other: object) -> bool:
        """Check equality based on ID or identity.

        Parameters
        ----------
        other : object
            Object to compare.

        Returns
        -------
        bool
            True if equal.
        """
        if isinstance(other, SocketIOResponse):
            return self is other
        if isinstance(other, int):
            return self.id == other
        return False

    def __str__(self) -> str:
        """String representation."""
        return f"<SocketIOResponse #{self.id}>"

    __repr__ = __str__

    def set(self, value: tuple[str, Any]) -> None:
        """Set the future result.

        Parameters
        ----------
        value : Tuple[str, Any]
            Event name and data tuple.
        """
        if not self.future.done():
            self.future.set_result(value)

    def cancel(self, ex: Exception | None = None) -> None:
        """Cancel the future or set exception.

        Parameters
        ----------
        ex : Exception or None, optional
            Exception to set on future. If None, cancels the future.
        """
        if not self.future.done():
            if ex is None:
                self.future.cancel()
            else:
                self.future.set_exception(ex)

    @staticmethod
    def match_event(
        ev: str | None = None, data: dict | None = None
    ) -> Callable[[str, Any], bool]:
        """Create a matcher for specific event name and/or data.

        Parameters
        ----------
        ev : str or None, optional
            Event name regex pattern. If None, matches any event.
        data : dict or None, optional
            Dictionary of key-value pairs that must match in response data.

        Returns
        -------
        Callable[[str, Any], bool]
            Matcher function.

        Examples
        --------
        >>> matcher = SocketIOResponse.match_event(r'^login$')
        >>> matcher('login', {'success': True})
        True
        >>> matcher('logout', {})
        False

        >>> matcher = SocketIOResponse.match_event(r'^chat', {'user': 'bot'})
        >>> matcher('chatMsg', {'user': 'bot', 'msg': 'hello'})
        True
        """

        def match(ev_: str, data_: Any) -> bool:
            """Match event name and data."""
            # Check event name pattern
            if ev is not None:
                if not re.match(ev, ev_):
                    return False

            # Check data constraints
            if data is not None:
                if not isinstance(data_, dict):
                    return False
                for key, value in data.items():
                    if data_.get(key) != value:
                        return False

            return True

        return match


# ============================================================================
# Socket.IO Client
# ============================================================================


class SocketIO:
    """Asynchronous Socket.IO v2 client.

    Provides low-level Socket.IO transport with automatic reconnection,
    heartbeat management, and event queue buffering. Designed for CyTube
    but usable with any Socket.IO v2 server.

    Attributes
    ----------
    websocket : websockets.client.WebSocketClientProtocol
        Underlying websocket connection.
    ping_interval : float
        Ping interval in seconds.
    ping_timeout : float
        Ping timeout in seconds.
    error : Exception or None
        Set when connection encounters fatal error.
    events : asyncio.Queue
        Queue of incoming (event_name, data) tuples.
    response : list of SocketIOResponse
        Pending response matchers.
    response_lock : asyncio.Lock
        Lock protecting response list.
    ping_task : asyncio.Task
        Background task sending periodic pings.
    recv_task : asyncio.Task
        Background task receiving and parsing frames.
    close_task : asyncio.Task or None
        Active close operation task.
    closing : asyncio.Event
        Set when close initiated.
    closed : asyncio.Event
        Set when close completed.
    ping_response : asyncio.Event
        Set when pong received.
    loop : asyncio.AbstractEventLoop
        Event loop.
    """

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        websocket: "WebSocketClientProtocol",
        config: dict,
        qsize: int,
        loop: asyncio.AbstractEventLoop,
    ):
        """Initialize Socket.IO client (use connect() instead).

        Parameters
        ----------
        websocket : WebSocketClientProtocol
            Connected websocket.
        config : dict
            Socket.IO configuration from handshake.
        qsize : int
            Event queue max size (0 = unbounded).
        loop : asyncio.AbstractEventLoop
            Event loop.
        """
        self.websocket = websocket
        self.loop = loop
        self._error: Exception | None = None
        self.closing = asyncio.Event()
        self.closed = asyncio.Event()
        self.ping_response = asyncio.Event()
        self.events: asyncio.Queue = asyncio.Queue(maxsize=qsize)
        self.response: list[SocketIOResponse] = []
        self.response_lock = asyncio.Lock()

        # Parse ping configuration from handshake
        self.ping_interval = max(1.0, config.get("pingInterval", 10000) / 1000.0)
        self.ping_timeout = max(1.0, config.get("pingTimeout", 10000) / 1000.0)

        # Start background tasks
        self.ping_task = self.loop.create_task(self._ping())
        self.recv_task = self.loop.create_task(self._recv())
        self.close_task: asyncio.Task | None = None

    @property
    def error(self) -> Exception | None:
        """Get current error state."""
        return self._error

    @error.setter
    def error(self, ex: Exception | None) -> None:
        """Set error state and initiate close if not already set.

        Parameters
        ----------
        ex : Exception or None
            Error that occurred.
        """
        if self._error is not None:
            self.logger.debug("error already set: %r", self._error)
            return

        self.logger.info("set error: %r", ex)
        self._error = ex

        if ex is not None and self.close_task is None:
            self.logger.debug("creating close task")
            self.close_task = self.loop.create_task(self.close())

    async def close(self) -> None:
        """Close the connection gracefully.

        Drains pending events, cancels background tasks, and closes
        the websocket. Safe to call multiple times.
        """
        self.logger.debug("close() called")

        # If already have close task and it's not us, wait for it
        if self.close_task is not None:
            if self.close_task is not _current_task(self.loop):
                self.logger.debug("waiting for existing close task")
                await self.close_task
                return

        # If already closed, return immediately
        if self.closed.is_set():
            self.logger.debug("already closed")
            return

        # If closing in progress, wait for completion
        if self.closing.is_set():
            self.logger.debug("already closing, waiting")
            await self.closed.wait()
            return

        self.closing.set()

        try:
            # Set error if not already set
            if self._error is None:
                self.logger.debug("setting default error")
                self._error = ConnectionClosed()

            # Signal event queue consumers
            self.logger.debug("queuing null event")
            try:
                self.events.put_nowait(None)
            except asyncio.QueueFull:
                pass

            # Cancel all pending responses
            self.logger.debug("cancelling %d pending responses", len(self.response))
            for res in self.response:
                res.cancel(self.error)
            self.response = []

            # Cancel background tasks
            self.logger.debug("cancelling background tasks")
            self.ping_task.cancel()
            self.recv_task.cancel()

            # Wait for tasks to finish
            self.logger.debug("waiting for task cancellation")
            await asyncio.gather(
                self.ping_task, self.recv_task, return_exceptions=True
            )

            # Clear ping state
            self.ping_response.clear()

            # Close websocket
            if self.websocket is not None:
                self.logger.debug("closing websocket")
                await self.websocket.close()

            # Drain event queue
            self.logger.debug("draining event queue")
            while not self.events.empty():
                try:
                    self.events.get_nowait()
                    self.events.task_done()
                except asyncio.QueueEmpty:
                    break

        finally:
            # Clean up references
            self.ping_task = None  # type: ignore[assignment]
            self.recv_task = None  # type: ignore[assignment]
            self.websocket = None  # type: ignore[assignment]
            self.closed.set()
            self.logger.info("close complete")

    async def recv(self) -> tuple[str, Any]:
        """Receive next event from queue.

        Returns
        -------
        Tuple[str, Any]
            Event name and data.

        Raises
        ------
        ConnectionClosed
            If connection is closed or closing.
        """
        if self.error is not None:
            raise self.error

        ev = await self.events.get()
        self.events.task_done()

        if ev is None:
            # Null sentinel indicates connection closed
            raise self.error or ConnectionClosed()

        return ev

    async def emit(
        self,
        event: str,
        data: Any,
        match_response: Callable[[str, Any], bool] | None = None,
        response_timeout: float | None = None,
    ) -> tuple[str, Any] | None:
        """Send an event, optionally waiting for response.

        Parameters
        ----------
        event : str
            Event name.
        data : Any
            Event data (must be JSON-serializable).
        match_response : Callable[[str, Any], bool] or None, optional
            Predicate function to match response event. If None, returns
            immediately after send.
        response_timeout : float or None, optional
            Timeout in seconds for response. If None, waits indefinitely.

        Returns
        -------
        Tuple[str, Any] or None
            Matched response (event_name, data) or None if timeout.

        Raises
        ------
        SocketIOError
            If send fails.
        ConnectionClosed
            If connection is closed.
        asyncio.CancelledError
            If operation is cancelled.

        Examples
        --------
        >>> # Fire and forget
        >>> await io.emit('chatMsg', {'msg': 'Hello'})

        >>> # Wait for response
        >>> matcher = SocketIOResponse.match_event(r'^login$')
        >>> response = await io.emit('login', {'name': 'bot'}, matcher, 3.0)
        """
        if self.error is not None:
            raise self.error

        # Encode Socket.IO frame: "42" + JSON array
        frame = "42" + json.dumps([event, data])
        self.logger.debug("emit: %s", frame)

        release = False
        response: SocketIOResponse | None = None

        try:
            # If waiting for response, register matcher
            if match_response is not None:
                await self.response_lock.acquire()
                release = True
                response = SocketIOResponse(match_response)
                self.logger.debug("registered response %s", response)
                self.response.append(response)

            # Send frame
            await self.websocket.send(frame)

            # If not waiting for response, done
            if match_response is None:
                return None

            # Release lock before waiting
            self.response_lock.release()
            release = False

            # Wait for response with optional timeout
            try:
                if response_timeout is not None:
                    res = await asyncio.wait_for(response.future, response_timeout)
                else:
                    res = await response.future

                self.logger.debug("response received: %r", res)
                return res

            except asyncio.CancelledError:
                self.logger.info("response cancelled for %s", event)
                raise

            except (TimeoutError, asyncio.TimeoutError):
                # Python 3.10 compat: asyncio.TimeoutError is separate from TimeoutError
                self.logger.info("response timeout for %s", event)
                response.cancel()
                return None

            finally:
                # Clean up response from list
                async with self.response_lock:
                    try:
                        self.response.remove(response)
                    except ValueError:
                        pass

        except asyncio.CancelledError:
            self.logger.error("emit cancelled")
            raise

        except Exception as ex:
            self.logger.error("emit error: %r", ex)
            if not isinstance(ex, SocketIOError):
                ex = SocketIOError(str(ex))
            raise ex

        finally:
            if release:
                self.response_lock.release()

    async def _ping(self) -> None:
        """Background task: Send periodic ping frames.

        Sends Engine.IO ping (frame "2") at intervals and expects pong
        (frame "3") within timeout. Sets error and initiates close on timeout.
        """
        try:
            dt = 0.0
            while self.error is None:
                # Sleep until next ping time
                await asyncio.sleep(max(self.ping_interval - dt, 0))

                self.logger.debug("sending ping")
                self.ping_response.clear()
                start_time = time()

                # Send ping frame
                await self.websocket.send("2")

                # Wait for pong
                await asyncio.wait_for(self.ping_response.wait(), self.ping_timeout)

                # Calculate actual round-trip time
                dt = max(time() - start_time, 0.0)
                self.logger.debug("pong received in %.3fs", dt)

        except asyncio.CancelledError:
            self.logger.debug("ping task cancelled")

        except (TimeoutError, asyncio.TimeoutError):
            # Python 3.10 compat: asyncio.TimeoutError is separate from TimeoutError
            self.logger.error("ping timeout")
            self.error = PingTimeout()

        except (OSError, WebSocketConnectionClosed, InvalidState, PayloadTooBig, WebSocketProtocolError) as ex:
            self.logger.error("ping error: %r", ex)
            self.error = ConnectionClosed(str(ex))

    async def _recv(self) -> None:  # noqa: C901 (protocol complexity)
        """Background task: Receive and parse Socket.IO frames.

        Parses Engine.IO and Socket.IO protocol frames, handles ping/pong,
        queues events, and matches responses. Sets error on protocol violations
        or connection closure.
        """
        try:
            while self.error is None:
                # Receive raw frame
                data = await self.websocket.recv()
                self.logger.debug("recv: %s", data)

                # Parse Engine.IO frame type
                if data.startswith("2"):
                    # Ping from server - respond with pong
                    payload = data[1:]
                    self.logger.debug("ping from server: %s", payload)
                    await self.websocket.send("3" + payload)

                elif data.startswith("3"):
                    # Pong from server
                    self.logger.debug("pong: %s", data[1:])
                    self.ping_response.set()

                elif data.startswith("4"):
                    # Socket.IO packet
                    await self._handle_socketio_packet(data)

                else:
                    self.logger.warning("unknown frame type: %s", data)

        except asyncio.CancelledError:
            self.logger.debug("recv task cancelled")
            if self.error is None:
                self.error = ConnectionClosed()

        except (OSError, WebSocketConnectionClosed, InvalidState, PayloadTooBig, WebSocketProtocolError) as ex:
            self.logger.warning(
                "Connection closed: %s - %s",
                type(ex).__name__,
                str(ex) or "no details"
            )
            self.error = ConnectionClosed(str(ex))

        except Exception as ex:
            self.logger.exception("Unexpected connection error")
            self.error = ConnectionClosed(str(ex))
            raise

    async def _handle_socketio_packet(self, data: str) -> None:
        """Parse and handle Socket.IO packet.

        Parameters
        ----------
        data : str
            Raw frame starting with "4".
        """
        try:
            packet_type = data[1] if len(data) > 1 else ""

            if packet_type == "0":
                # Connect packet
                self.logger.debug("socket.io connect")
                event = ""
                event_data = None

            elif packet_type == "1":
                # Disconnect packet - server is closing the connection
                self.logger.warning("Socket.IO disconnect packet received from server: %s", data[2:])
                # Set error to trigger connection closure
                self.error = ConnectionClosed("Server sent disconnect packet")
                return  # Don't process further, connection is closing

            elif packet_type == "2":
                # Event packet: "42[event, data, ...]"
                payload = json.loads(data[2:])

                if not isinstance(payload, list):
                    raise ValueError(f"event payload not array: {payload}")
                if len(payload) == 0:
                    raise ValueError("empty event array")

                # Parse event name and data
                if len(payload) == 1:
                    event, event_data = payload[0], None
                elif len(payload) == 2:
                    event, event_data = payload
                else:
                    event = payload[0]
                    event_data = payload[1:]

            else:
                self.logger.warning("unknown socket.io packet type: %s", data)
                return

            # Queue event for consumers
            self.logger.debug("event: %s %r", event, event_data)
            await self.events.put((event, event_data))

            # Check if any pending response matches
            for response in self.response:
                if response.match(event, event_data):
                    self.logger.debug("matched response %s", response)
                    response.set((event, event_data))
                    break

        except (ValueError, json.JSONDecodeError) as ex:
            self.logger.error("invalid socket.io packet %s: %r", data, ex)

    @classmethod
    async def _get_config(cls, url: str, get: Callable) -> dict:
        """Perform Socket.IO handshake to get session ID and config.

        Parameters
        ----------
        url : str
            Base Socket.IO URL (e.g., https://cytu.be/socket.io/).
        get : Callable
            HTTP GET coroutine.

        Returns
        -------
        dict
            Handshake response with 'sid', 'pingInterval', 'pingTimeout'.

        Raises
        ------
        InvalidHandshake
            If handshake response is invalid.
        """
        handshake_url = url + "?EIO=3&transport=polling"
        cls.logger.info("handshake GET: %s", handshake_url)

        response = await get(handshake_url)

        try:
            # Parse JSON from response (may have prefix)
            json_start = response.index("{")
            config = json.loads(response[json_start:])

            if "sid" not in config:
                raise ValueError(f"no sid in response: {config}")

            cls.logger.info("handshake sid=%s", config["sid"])
            return config

        except (ValueError, json.JSONDecodeError) as ex:
            raise InvalidHandshake(f"invalid handshake response: {response}") from ex

    @classmethod
    async def _connect(
        cls,
        url: str,
        qsize: int,
        loop: asyncio.AbstractEventLoop,
        get: Callable,
        connect: Callable,
    ) -> "SocketIO":
        """Establish Socket.IO connection (internal).

        Performs handshake, upgrades to websocket, and completes probe exchange.

        Parameters
        ----------
        url : str
            Base Socket.IO URL.
        qsize : int
            Event queue size.
        loop : asyncio.AbstractEventLoop
            Event loop.
        get : Callable
            HTTP GET coroutine.
        connect : Callable
            Websocket connect coroutine.

        Returns
        -------
        SocketIO
            Connected client.

        Raises
        ------
        InvalidHandshake
            If handshake or upgrade fails.
        """
        # Get session ID from handshake
        config = await cls._get_config(url, get)
        sid = config["sid"]

        # Construct websocket URL
        ws_url = url.replace("http", "ws", 1) + f"?EIO=3&transport=websocket&sid={sid}"
        cls.logger.info("websocket connect: %s", ws_url)

        # Connect websocket
        websocket = await connect(ws_url)

        try:
            # Send probe
            cls.logger.debug("sending probe")
            await websocket.send("2probe")

            # Expect probe response
            response = await websocket.recv()
            if response != "3probe":
                raise InvalidHandshake(
                    f'invalid probe response: "{response}" != "3probe"'
                )

            # Send upgrade
            cls.logger.debug("sending upgrade")
            await websocket.send("5")

            # Create client instance
            return SocketIO(websocket, config, qsize, loop)

        except Exception:
            await websocket.close()
            raise

    @classmethod
    async def connect(
        cls,
        url: str,
        retry: int = -1,
        retry_delay: float = 1.0,
        qsize: int = 0,
        loop: asyncio.AbstractEventLoop | None = None,
        get: Callable = default_get,
        connect: Callable = websockets.connect,
    ) -> "SocketIO":
        """Create a Socket.IO connection with retry logic.

        Parameters
        ----------
        url : str
            Base Socket.IO URL (e.g., https://cytu.be/socket.io/).
        retry : int, optional
            Maximum retry attempts (-1 = infinite). Default: -1.
        retry_delay : float, optional
            Delay between retries in seconds. Default: 1.0.
        qsize : int, optional
            Event queue max size (0 = unbounded). Default: 0.
        loop : asyncio.AbstractEventLoop or None, optional
            Event loop to use. If None, uses current loop.
        get : Callable, optional
            HTTP GET coroutine. Default: default_get (aiohttp).
        connect : Callable, optional
            Websocket connect coroutine. Default: websockets.connect.

        Returns
        -------
        SocketIO
            Connected client ready for emit/recv.

        Raises
        ------
        ConnectionFailed
            If all retry attempts fail.
        asyncio.CancelledError
            If connection attempt is cancelled.

        Examples
        --------
        >>> io = await SocketIO.connect('https://cytu.be/socket.io/')
        >>> await io.emit('joinChannel', {'name': 'test'})
        >>> event, data = await io.recv()
        >>> await io.close()
        """
        loop = loop or asyncio.get_event_loop()
        attempt = 0

        while True:
            try:
                io = await cls._connect(url, qsize, loop, get, connect)
                cls.logger.info("connected successfully")
                return io

            except asyncio.CancelledError:
                cls.logger.error(
                    "connect(%s) attempt %d/%d: cancelled", url, attempt + 1, retry + 1
                )
                raise

            except Exception as ex:
                cls.logger.error(
                    "connect(%s) attempt %d/%d: %r", url, attempt + 1, retry + 1, ex
                )

                # Check if exceeded retry limit
                if attempt == retry:
                    raise ConnectionFailed(str(ex)) from ex

            # Increment attempt and wait before retry
            attempt += 1
            await asyncio.sleep(retry_delay)

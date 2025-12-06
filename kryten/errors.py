"""Kryten Connection Error Hierarchy.

This module defines exception classes for connection, authentication, protocol,
and send failures, standardizing error handling across the Kryten connector.
"""

from typing import Final


class ConnectionError(Exception):  # noqa: A001 (shadows builtin but intentional)
    """Base exception for all connection-related errors.

    This is the root of Kryten's error hierarchy. Catching this exception
    will catch all Kryten-specific connection failures.

    Args:
        message: Human-readable error description.

    Examples:
        >>> try:
        ...     await connector.connect()
        ... except ConnectionError as e:
        ...     logger.error(f"Connection failed: {e}")

    Note:
        Most connection errors are transient and may succeed on retry.
        Check specific subclass types to determine retry strategy.
    """


class AuthenticationError(ConnectionError):
    """Authentication or login failed.

    Raised when credentials are rejected or login sequence fails.
    This typically indicates a configuration problem requiring manual
    intervention.

    Args:
        message: Human-readable error description.

    Examples:
        >>> if not logged_in:
        ...     raise AuthenticationError('Invalid CyTube password')

    Note:
        **Not recoverable by retry**. Requires credential update or
        account verification.
    """


class NotConnectedError(ConnectionError):
    """Operation requires an active connection.

    Raised when attempting operations (emit, recv, etc.) before calling
    connect() or after connection has been closed.

    Args:
        message: Human-readable error description.

    Examples:
        >>> if not self.socket:
        ...     raise NotConnectedError('Must call connect() first')

    Note:
        **Recoverable**. Call connect() to establish connection before
        retrying the operation.
    """


class SendError(ConnectionError):
    """Failed to send message or data.

    Raised when message transmission fails due to network issues,
    buffer overflow, or other transport problems.

    Args:
        message: Human-readable error description.

    Examples:
        >>> try:
        ...     await websocket.send(data)
        ... except websockets.ConnectionClosed as e:
        ...     raise SendError('Failed to send message') from e

    Note:
        **May be recoverable**. Check if connection is still active
        before deciding retry strategy.
    """


class ProtocolError(ConnectionError):
    """Platform protocol violation.

    Raised when Socket.IO or CyTube protocol expectations are violated,
    such as malformed frames, unexpected event sequences, or invalid
    handshake responses.

    Args:
        message: Human-readable error description.

    Examples:
        >>> if response != '3probe':
        ...     raise ProtocolError(f'Invalid probe response: {response}')

    Note:
        **Usually not recoverable**. Indicates client/server version
        mismatch or protocol implementation bug.
    """


class PingTimeout(ConnectionError):
    """Heartbeat timeout occurred.

    Raised when server fails to respond to ping within configured
    timeout period. Indicates connection may be dead or server
    is unresponsive.

    Args:
        message: Human-readable error description.

    Examples:
        >>> if not pong_received:
        ...     raise PingTimeout('Server did not respond to ping')

    Note:
        **Recoverable by reconnection**. Network may be temporarily
        disrupted. Attempt reconnect with backoff.
    """


class SocketIOError(ConnectionError):
    """Socket.IO transport error.

    General Socket.IO transport layer error for issues not covered
    by more specific exception types. May include websocket errors,
    handshake failures, or framing problems.

    Args:
        message: Human-readable error description.

    Examples:
        >>> try:
        ...     config = await get_handshake()
        ... except InvalidHandshake as e:
        ...     raise SocketIOError('Handshake failed') from e

    Note:
        **May be recoverable**. Check __cause__ attribute to determine
        if retry is appropriate based on underlying error.
    """


__all__: Final[list[str]] = [
    "ConnectionError",
    "AuthenticationError",
    "NotConnectedError",
    "SendError",
    "ProtocolError",
    "PingTimeout",
    "SocketIOError",
]

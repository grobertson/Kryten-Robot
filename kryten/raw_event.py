"""Raw Event Dataclass for CyTube Socket.IO Events.

This module defines the RawEvent dataclass for wrapping unparsed CyTube events
with metadata before publishing to NATS.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RawEvent:
    """Immutable container for raw Socket.IO events with metadata.

    Wraps CyTube Socket.IO events with timestamps, correlation IDs, and channel
    information for NATS publishing and distributed tracing.

    Attributes:
        event_name: Socket.IO event name (e.g., "chatMsg", "addUser").
        payload: Raw Socket.IO event data as dictionary.
        channel: CyTube channel name.
        domain: CyTube server domain (e.g., "cytu.be").
        timestamp: UTC ISO 8601 timestamp with microseconds.
        correlation_id: UUID4 for distributed tracing.

    Examples:
        >>> event = RawEvent(
        ...     event_name="chatMsg",
        ...     payload={"user": "bob", "msg": "hello"},
        ...     channel="lounge",
        ...     domain="cytu.be"
        ... )
        >>> json_bytes = event.to_bytes()
        >>> await nats_client.publish("cytube.events.chatMsg", json_bytes)
    """

    event_name: str
    payload: dict[str, Any]
    channel: str
    domain: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all fields as key-value pairs.

        Examples:
            >>> event = RawEvent("test", {}, "ch", "dom")
            >>> d = event.to_dict()
            >>> assert "event_name" in d
            >>> assert "timestamp" in d
        """
        return {
            "event_name": self.event_name,
            "payload": self.payload,
            "channel": self.channel,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string representation of the event.

        Examples:
            >>> event = RawEvent("chatMsg", {"msg": "hi"}, "ch", "dom")
            >>> json_str = event.to_json()
            >>> assert "chatMsg" in json_str
        """
        return json.dumps(self.to_dict())

    def to_bytes(self) -> bytes:
        """Serialize to UTF-8 encoded JSON bytes.

        Returns:
            UTF-8 encoded JSON bytes suitable for NATS publishing.

        Examples:
            >>> event = RawEvent("test", {}, "ch", "dom")
            >>> data = event.to_bytes()
            >>> assert isinstance(data, bytes)
        """
        return self.to_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawEvent":
        """Deserialize from dictionary.

        Args:
            data: Dictionary with event fields.

        Returns:
            RawEvent instance with fields from dictionary.

        Examples:
            >>> data = {
            ...     "event_name": "test",
            ...     "payload": {},
            ...     "channel": "ch",
            ...     "domain": "dom",
            ...     "timestamp": "2024-01-15T10:30:00.123456Z",
            ...     "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
            ... }
            >>> event = RawEvent.from_dict(data)
            >>> assert event.event_name == "test"
        """
        return cls(
            event_name=data["event_name"],
            payload=data["payload"],
            channel=data["channel"],
            domain=data["domain"],
            timestamp=data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
        )

    def __str__(self) -> str:
        """String representation for logging.

        Returns:
            Human-readable string with key event information.

        Examples:
            >>> event = RawEvent("chatMsg", {}, "lounge", "cytu.be")
            >>> s = str(event)
            >>> assert "chatMsg" in s
            >>> assert "lounge" in s
        """
        return (
            f"RawEvent(event={self.event_name}, channel={self.channel}, "
            f"domain={self.domain}, id={self.correlation_id[:8]}...)"
        )

    def __repr__(self) -> str:
        """Detailed representation for debugging.

        Returns:
            Full representation with all fields.

        Examples:
            >>> event = RawEvent("test", {}, "ch", "dom")
            >>> repr(event)  # doctest: +ELLIPSIS
            "RawEvent(event_name='test', ...)"
        """
        return (
            f"RawEvent(event_name={self.event_name!r}, "
            f"payload={self.payload!r}, channel={self.channel!r}, "
            f"domain={self.domain!r}, timestamp={self.timestamp!r}, "
            f"correlation_id={self.correlation_id!r})"
        )


__all__ = ["RawEvent"]

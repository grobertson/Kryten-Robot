"""NATS Subject Builder for CyTube Events.

This module provides utilities for constructing and parsing hierarchical NATS
subject strings following the format: cytube.events.{domain}.{channel}.{event_name}

Subject Format
--------------
cytube.events.{domain}.{channel}.{event_name}
            ^        ^         ^
            |        |         +-- Event type (e.g., chatMsg)
            |        +------------ Channel name (e.g., lounge)
            +--------------------- Domain (e.g., cytu.be)

Wildcard Subscriptions
----------------------
NATS supports wildcard subscriptions for flexible filtering:

- Single level wildcard (*):
  cytube.events.*.lounge.chatMsg  # All domains, lounge channel, chatMsg events

- Multi-level wildcard (>):
  cytube.events.cytu.be.>          # All events from cytu.be domain
  cytube.events.*.lounge.>         # All events from any domain's lounge channel

Examples
--------
>>> from bot.kryten import RawEvent
>>> from bot.kryten.subject_builder import build_subject, build_event_subject
>>>
>>> # Build subject from components
>>> subject = build_subject("cytu.be", "lounge", "chatMsg")
>>> print(subject)
'cytube.events.cytu.be.lounge.chatmsg'
>>>
>>> # Build subject from RawEvent
>>> event = RawEvent("chatMsg", {"user": "bob"}, "lounge", "cytu.be")
>>> subject = build_event_subject(event)
>>>
>>> # Parse subject back to components
>>> from bot.kryten.subject_builder import parse_subject
>>> components = parse_subject("cytube.events.cytu.be.lounge.chatMsg")
>>> print(components['domain'])
'cytu.be'
"""

import re
from typing import Dict

from .raw_event import RawEvent


SUBJECT_PREFIX = "cytube.events"
"""NATS subject prefix for all CyTube events."""

MAX_TOKEN_LENGTH = 100
"""Maximum length for individual subject tokens to prevent exceeding NATS limits."""


def sanitize_token(token: str) -> str:
    """Sanitize subject token for NATS compatibility.

    Converts to lowercase, replaces spaces with hyphens, and removes invalid
    characters including NATS wildcards (* and >).

    Args:
        token: Raw token string to sanitize.

    Returns:
        Sanitized token suitable for NATS subject.

    Examples:
        >>> sanitize_token("My Channel!")
        'my-channel'
        >>> sanitize_token("Test_Channel #1")
        'test_channel-1'
        >>> sanitize_token("café")
        'café'
    """
    if not token:
        return ""

    # Convert to lowercase
    token = token.lower()

    # Replace spaces with hyphens
    token = token.replace(" ", "-")

    # Remove NATS wildcard characters
    token = token.replace("*", "").replace(">", "")

    # Remove invalid characters for NATS subjects
    # Keep: alphanumeric (ASCII + Unicode), dots, hyphens, underscores
    # Remove: other special chars, but preserve UTF-8 letters
    # Simple approach: remove only problematic ASCII special chars
    invalid_chars = '!@#$%^&*()+=[]{|}\\:;"\'<>,?/'
    for char in invalid_chars:
        token = token.replace(char, "")

    # Truncate to prevent exceeding NATS subject length limit
    if len(token) > MAX_TOKEN_LENGTH:
        token = token[:MAX_TOKEN_LENGTH]

    return token


def build_subject(domain: str, channel: str, event_name: str) -> str:
    """Build NATS subject from event components.

    Constructs hierarchical subject following the format:
    cytube.events.{domain}.{channel}.{event_name}

    Domain is lowercased but NOT sanitized (to preserve dots in domain names).
    Channel and event_name are sanitized and normalized.

    Args:
        domain: CyTube server domain (e.g., "cytu.be").
        channel: Channel name (e.g., "lounge").
        event_name: Socket.IO event name (e.g., "chatMsg").

    Returns:
        Formatted NATS subject string.

    Raises:
        ValueError: If any component is empty after sanitization.

    Examples:
        >>> build_subject("cytu.be", "lounge", "chatMsg")
        'cytube.events.cytu.be.lounge.chatmsg'
        >>> build_subject("CYTU.BE", "Test Channel", "chatMsg")
        'cytube.events.cytu.be.test-channel.chatmsg'
    """
    # Domain is lowercased but not sanitized (preserve dots)
    domain_clean = domain.lower().strip()
    # Channel and event are sanitized
    channel_clean = sanitize_token(channel)
    event_clean = sanitize_token(event_name)

    # Validate components are not empty
    if not domain_clean:
        raise ValueError("Domain cannot be empty after sanitization")
    if not channel_clean:
        raise ValueError("Channel cannot be empty after sanitization")
    if not event_clean:
        raise ValueError("Event name cannot be empty after sanitization")

    # Build subject
    subject = f"{SUBJECT_PREFIX}.{domain_clean}.{channel_clean}.{event_clean}"

    # Final validation
    if len(subject) > 255:
        raise ValueError(f"Subject exceeds NATS limit of 255 characters: {len(subject)}")

    return subject


def build_event_subject(event: RawEvent) -> str:
    """Build NATS subject from RawEvent.

    Convenience function that extracts domain, channel, and event_name from
    a RawEvent instance and builds the subject string.

    Args:
        event: RawEvent instance with domain, channel, and event_name fields.

    Returns:
        Formatted NATS subject string.

    Examples:
        >>> from bot.kryten import RawEvent
        >>> event = RawEvent("chatMsg", {}, "lounge", "cytu.be")
        >>> build_event_subject(event)
        'cytube.events.cytu.be.lounge.chatmsg'
    """
    return build_subject(event.domain, event.channel, event.event_name)


def parse_subject(subject: str) -> Dict[str, str]:
    """Parse NATS subject into components.

    Extracts prefix, domain, channel, and event_name from a hierarchical
    subject string. Expected format: cytube.events.{domain}.{channel}.{event}

    Domain may contain dots (e.g., cytu.be). Uses TLD detection heuristic.

    Args:
        subject: NATS subject string to parse.

    Returns:
        Dictionary with keys: prefix, domain, channel, event_name.

    Raises:
        ValueError: If subject format is invalid or missing required components.

    Examples:
        >>> components = parse_subject("cytube.events.cytu.be.lounge.chatMsg")
        >>> components['domain']
        'cytu.be'
        >>> components['channel']
        'lounge'
        >>> components['event_name']
        'chatMsg'
    """
    if not subject:
        raise ValueError("Subject cannot be empty")

    # Check prefix first
    if not subject.startswith(SUBJECT_PREFIX + "."):
        raise ValueError(
            f"Invalid subject prefix: expected '{SUBJECT_PREFIX}.', "
            f"got '{subject[:20]}...'"
        )

    # Remove prefix to get remaining components
    remaining = subject[len(SUBJECT_PREFIX) + 1:]  # +1 for the dot

    # Split remaining part
    tokens = remaining.split(".")

    if len(tokens) < 3:
        raise ValueError(
            f"Invalid subject format: expected 'cytube.events.{{domain}}.{{channel}}.{{event}}', "
            f"got '{subject}'"
        )

    # Heuristic: Check if second token looks like a TLD
    # Common TLDs for CyTube servers
    tld_extensions = {"com", "be", "org", "net", "io", "tv", "gg", "me", "co"}

    if len(tokens) >= 2 and tokens[1] in tld_extensions:
        # Domain has TLD (e.g., cytu.be)
        domain = f"{tokens[0]}.{tokens[1]}"
        channel = tokens[2] if len(tokens) > 2 else ""
        event_name = ".".join(tokens[3:]) if len(tokens) > 3 else ""
    else:
        # Domain is single token (e.g., localhost)
        domain = tokens[0]
        channel = tokens[1] if len(tokens) > 1 else ""
        event_name = ".".join(tokens[2:]) if len(tokens) > 2 else ""

    if not channel or not event_name:
        raise ValueError(
            f"Invalid subject format: expected 'cytube.events.{{domain}}.{{channel}}.{{event}}', "
            f"got '{subject}'"
        )

    return {
        "prefix": SUBJECT_PREFIX,
        "domain": domain,
        "channel": channel,
        "event_name": event_name,
    }


__all__ = [
    "SUBJECT_PREFIX",
    "MAX_TOKEN_LENGTH",
    "sanitize_token",
    "build_subject",
    "build_event_subject",
    "parse_subject",
]

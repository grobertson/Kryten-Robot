"""Audit logging for admin, playlist, chat, command, and connection operations.

This module provides specialized loggers for tracking CyTube operations:
- Admin operations (rank changes, bans, filters, emotes, etc.)
- Playlist operations (queue, delete, move, shuffle, etc.)
- Chat messages (timestamped chat log)
- Command audit (all received commands with username and arguments)
- Connection events (connect, disconnect, reconnect, errors)

All logs are written in UTF-8 encoding.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    """Manages specialized audit loggers for different operation types.

    Creates and manages file handlers for:
    - Admin operations
    - Playlist operations
    - Chat messages
    - Command audit
    - Connection events

    All log files are UTF-8 encoded and use append mode.
    """

    def __init__(self, base_path: str, filenames: dict[str, str]):
        """Initialize audit logger.

        Args:
            base_path: Base directory for all log files.
            filenames: Dictionary mapping log types to filenames:
                - admin_operations
                - playlist_operations
                - chat_messages
                - command_audit
                - connection_events (optional)
        """
        self.base_path = Path(base_path)
        self.filenames = filenames

        # Create log directory if it doesn't exist
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create specialized loggers
        self.admin_logger = self._create_logger("admin", filenames["admin_operations"])
        self.playlist_logger = self._create_logger("playlist", filenames["playlist_operations"])
        self.chat_logger = self._create_logger("chat", filenames["chat_messages"])
        self.command_logger = self._create_logger("command", filenames["command_audit"])

        # Connection logger is optional for backward compatibility
        self.connection_logger: logging.Logger | None = None
        if "connection_events" in filenames:
            self.connection_logger = self._create_logger("connection", filenames["connection_events"])

    def _create_logger(self, name: str, filename: str) -> logging.Logger:
        """Create a specialized logger with file handler.

        Args:
            name: Logger name (used as suffix).
            filename: Log filename.

        Returns:
            Configured logger instance.
        """
        logger_name = f"bot.kryten.audit.{name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to root logger

        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()

        # Create file handler with UTF-8 encoding
        log_path = self.base_path / filename
        handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        handler.setLevel(logging.INFO)

        # Simple format: timestamp + message
        formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        return logger

    def log_admin_operation(
        self,
        operation: str,
        username: str | None = None,
        target: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Log an admin operation.

        Args:
            operation: Operation type (e.g., "setMotd", "ban", "setChannelRank").
            username: User who performed the operation (bot username).
            target: Target of the operation (username, filter name, etc.).
            details: Additional operation details.

        Example:
            >>> audit.log_admin_operation("ban", "BotAdmin", "SpamUser", {"duration": 3600})
        """
        parts = [f"[{operation}]"]
        if username:
            parts.append(f"by={username}")
        if target:
            parts.append(f"target={target}")
        if details:
            detail_str = " ".join(f"{k}={v}" for k, v in details.items())
            parts.append(detail_str)

        message = " ".join(parts)
        self.admin_logger.info(message)

    def log_playlist_operation(
        self,
        operation: str,
        username: str | None = None,
        media_title: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """Log a playlist operation.

        Args:
            operation: Operation type (e.g., "queue", "delete", "moveMedia").
            username: User who performed the operation.
            media_title: Title of media item.
            details: Additional operation details (position, duration, etc.).

        Example:
            >>> audit.log_playlist_operation("queue", "Alice", "Cool Video", {"duration": 300})
        """
        parts = [f"[{operation}]"]
        if username:
            parts.append(f"user={username}")
        if media_title:
            # Truncate long titles
            title = media_title[:100]
            parts.append(f"title=\"{title}\"")
        if details:
            detail_str = " ".join(f"{k}={v}" for k, v in details.items())
            parts.append(detail_str)

        message = " ".join(parts)
        self.playlist_logger.info(message)

    def log_chat_message(self, username: str, message: str, timestamp: datetime | None = None) -> None:
        """Log a chat message in IRC-style format.

        Args:
            username: Username of the message sender.
            message: Chat message text.
            timestamp: Optional timestamp (defaults to now).

        Format: HH:MM:SS <username>: message

        Example:
            >>> audit.log_chat_message("Alice", "Hello everyone!")
            # Output: 14:35:22 <Alice>: Hello everyone!
        """
        if timestamp is None:
            timestamp = datetime.now()

        time_str = timestamp.strftime("%H:%M:%S")
        formatted = f"{time_str} <{username}>: {message}"

        # Use a plain handler without timestamp prefix (we're adding it manually)
        # Remove all handlers temporarily
        handlers = self.chat_logger.handlers[:]
        self.chat_logger.handlers.clear()

        # Add handler without timestamp
        log_path = self.base_path / self.filenames["chat_messages"]
        handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.chat_logger.addHandler(handler)

        self.chat_logger.info(formatted)

        # Restore original handlers
        self.chat_logger.handlers.clear()
        self.chat_logger.handlers.extend(handlers)

    def log_command(
        self,
        command: str,
        username: str | None = None,
        arguments: dict[str, Any] | None = None,
        source: str = "NATS"
    ) -> None:
        """Log a received command.

        Args:
            command: Command name (e.g., "sendChat", "setMotd").
            username: Username associated with the command.
            arguments: Command arguments.
            source: Source of the command (e.g., "NATS", "internal").

        Example:
            >>> audit.log_command("sendChat", "bot", {"message": "Hello"}, "NATS")
        """
        parts = [f"[{source}]", f"command={command}"]
        if username:
            parts.append(f"user={username}")
        if arguments:
            # Sanitize sensitive data
            safe_args = {k: "***" if "password" in k.lower() else v for k, v in arguments.items()}
            args_str = " ".join(f"{k}={v}" for k, v in safe_args.items())
            parts.append(f"args=({args_str})")

        message = " ".join(parts)
        self.command_logger.info(message)

    def log_connection_event(
        self,
        event: str,
        target: str | None = None,
        details: dict[str, Any] | None = None,
        error: str | None = None
    ) -> None:
        """Log a connection event.

        Args:
            event: Event type (e.g., "connect", "disconnect", "reconnect", "error").
            target: Connection target (e.g., "CyTube", "NATS").
            details: Additional event details (domain, channel, etc.).
            error: Error message if applicable.

        Example:
            >>> audit.log_connection_event("disconnect", "CyTube", error="Connection reset by peer")
            >>> audit.log_connection_event("reconnect", "CyTube", {"domain": "cytu.be", "channel": "test"})
        """
        if self.connection_logger is None:
            return

        parts = [f"[{event.upper()}]"]
        if target:
            parts.append(f"target={target}")
        if details:
            detail_str = " ".join(f"{k}={v}" for k, v in details.items())
            parts.append(detail_str)
        if error:
            parts.append(f"error=\"{error}\"")

        message = " ".join(parts)
        self.connection_logger.info(message)


def create_audit_logger(base_path: str, filenames: dict[str, str]) -> AuditLogger:
    """Factory function to create audit logger.

    Args:
        base_path: Base directory for log files.
        filenames: Dictionary mapping log types to filenames.

    Returns:
        Configured AuditLogger instance.

    Example:
        >>> filenames = {
        ...     "admin_operations": "admin-ops.log",
        ...     "playlist_operations": "playlist-ops.log",
        ...     "chat_messages": "chat.log",
        ...     "command_audit": "commands.log"
        ... }
        >>> audit = create_audit_logger("/var/log/kryten", filenames)
    """
    return AuditLogger(base_path, filenames)


__all__ = ["AuditLogger", "create_audit_logger"]

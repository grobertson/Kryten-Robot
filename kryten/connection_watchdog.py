"""Connection Watchdog for detecting stale CyTube connections.

This module provides a watchdog that monitors connection health by tracking
regular events from CyTube (like media updates). If no events are received
for a configured timeout period, the watchdog triggers a reconnection.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime


class ConnectionWatchdog:
    """Monitors connection health using event heartbeats.

    CyTube servers send media update events on a regular schedule (typically
    every few seconds as media plays). This watchdog tracks these events and
    triggers a reconnection if too much time passes without receiving them.

    Attributes:
        timeout: Seconds without events before triggering reconnection.
        logger: Logger instance for structured logging.
        on_timeout: Async callback to invoke when timeout occurs.

    Examples:
        >>> async def handle_timeout():
        ...     print("Connection stale, reconnecting...")
        ...     await connector.disconnect()
        ...     await connector.connect()
        >>>
        >>> watchdog = ConnectionWatchdog(
        ...     timeout=60.0,
        ...     on_timeout=handle_timeout,
        ...     logger=logger
        ... )
        >>> await watchdog.start()
        >>>
        >>> # Feed events to watchdog
        >>> watchdog.pet()  # Call on each received event
        >>>
        >>> await watchdog.stop()
    """

    def __init__(
        self,
        timeout: float,
        on_timeout: Callable[[], Awaitable[None]],
        logger: logging.Logger,
        enabled: bool = True,
    ):
        """Initialize connection watchdog.

        Args:
            timeout: Seconds without events before triggering timeout.
            on_timeout: Async callback to invoke on timeout.
            logger: Logger for structured output.
            enabled: Whether watchdog is enabled (default: True).
        """
        self.timeout = timeout
        self.on_timeout = on_timeout
        self.logger = logger
        self.enabled = enabled

        self._last_event: datetime | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._timeouts_triggered = 0

    async def start(self) -> None:
        """Start watchdog monitoring.

        Launches background task that periodically checks event freshness.
        """
        if not self.enabled:
            self.logger.info("Watchdog disabled in configuration")
            return

        if self._running:
            self.logger.warning("Watchdog already running")
            return

        self._running = True
        self._last_event = datetime.now()
        self._task = asyncio.create_task(self._monitor_loop())

        self.logger.info(f"Connection watchdog started (timeout: {self.timeout}s)")

    async def stop(self) -> None:
        """Stop watchdog monitoring.

        Cancels background task and cleans up resources.
        """
        if not self._running:
            return

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self.logger.info(
            f"Connection watchdog stopped " f"(timeouts triggered: {self._timeouts_triggered})"
        )

    def pet(self) -> None:
        """Reset watchdog timer (called when event received).

        Call this method whenever a relevant event is received from CyTube
        to indicate the connection is still alive.

        Examples:
            >>> watchdog.pet()  # Connection is healthy
        """
        if not self.enabled or not self._running:
            return

        self._last_event = datetime.now()

    def is_stale(self) -> bool:
        """Check if connection appears stale.

        Returns:
            True if timeout period has elapsed without events.
        """
        if not self.enabled or self._last_event is None:
            return False

        elapsed = (datetime.now() - self._last_event).total_seconds()
        return elapsed >= self.timeout

    def time_since_last_event(self) -> float:
        """Get seconds since last event.

        Returns:
            Seconds since last event, or 0.0 if no events yet.
        """
        if self._last_event is None:
            return 0.0

        return (datetime.now() - self._last_event).total_seconds()

    @property
    def stats(self) -> dict:
        """Get watchdog statistics.

        Returns:
            Dictionary with timeout and health metrics.
        """
        return {
            "enabled": self.enabled,
            "timeout_seconds": self.timeout,
            "timeouts_triggered": self._timeouts_triggered,
            "seconds_since_last_event": self.time_since_last_event(),
            "is_stale": self.is_stale(),
        }

    async def _monitor_loop(self) -> None:
        """Background task monitoring connection health.

        Periodically checks if timeout has elapsed and triggers callback
        if connection appears stale.
        """
        check_interval = min(5.0, self.timeout / 4)  # Check 4x per timeout period

        try:
            while self._running:
                await asyncio.sleep(check_interval)

                if not self._running:
                    break

                if self.is_stale():
                    self.logger.warning(
                        f"Connection watchdog timeout triggered "
                        f"({self.time_since_last_event():.1f}s since last event)"
                    )

                    self._timeouts_triggered += 1

                    # Invoke timeout callback
                    try:
                        await self.on_timeout()
                    except Exception as e:
                        self.logger.error(f"Error in watchdog timeout handler: {e}", exc_info=True)

                    # Reset timer after callback
                    self._last_event = datetime.now()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Watchdog monitor loop error: {e}", exc_info=True)
        finally:
            self.logger.debug("Watchdog monitor loop stopped")


__all__ = ["ConnectionWatchdog"]

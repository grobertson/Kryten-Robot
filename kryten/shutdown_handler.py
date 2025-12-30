"""Graceful shutdown coordination for Kryten.

This module provides the ShutdownHandler that orchestrates clean termination
of all Kryten components in the correct order: publisher → connector → NATS → logging.

The handler enforces timeouts, tracks shutdown state, handles idempotent shutdown
requests, and returns metrics about the shutdown operation.

Examples:
    Basic shutdown:
        >>> handler = ShutdownHandler(publisher, connector, nats, logger)
        >>> result = await handler.shutdown()
        >>> if result.clean_exit:
        ...     print("Clean shutdown complete")

    With timeout:
        >>> try:
        ...     result = await asyncio.wait_for(handler.shutdown(), timeout=30.0)
        ... except asyncio.TimeoutError:
        ...     logger.critical("Shutdown timeout - forcing exit")

    As async context manager:
        >>> async with ShutdownHandler(publisher, connector, nats, logger) as handler:
        ...     # Application runs
        ...     pass
        >>> # Automatic shutdown on exit

Note:
    Shutdown is idempotent - calling shutdown() multiple times is safe.
    The first call executes the shutdown sequence, subsequent calls wait
    for the same result.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from .cytube_connector import CytubeConnector
from .event_publisher import EventPublisher
from .nats_client import NatsClient


class ShutdownPhase(Enum):
    """Shutdown execution phases.

    Tracks the progress of the shutdown sequence for logging and debugging.
    """
    IDLE = "idle"
    INITIATED = "initiated"
    DRAINING = "draining"
    DISCONNECTING = "disconnecting"
    FINALIZING = "finalizing"
    COMPLETE = "complete"


@dataclass
class ShutdownResult:
    """Result of shutdown operation with metrics.

    Provides visibility into the shutdown process for operational monitoring
    and debugging.

    Attributes:
        clean_exit: True if all components shut down gracefully within timeout.
        duration: Total time spent in shutdown (seconds).
        events_processed: Number of events processed before shutdown.
        errors: List of error messages encountered during shutdown.
        phase_timings: Time spent in each shutdown phase (seconds).

    Examples:
        >>> result = await handler.shutdown()
        >>> print(f"Clean: {result.clean_exit}, Duration: {result.duration:.2f}s")
        >>> if result.errors:
        ...     print(f"Errors: {result.errors}")
    """
    clean_exit: bool
    duration: float
    events_processed: int
    errors: list[str] = field(default_factory=list)
    phase_timings: dict = field(default_factory=dict)


class ShutdownHandler:
    """Coordinates graceful shutdown of Kryten components.

    Ensures clean termination by stopping components in reverse startup order:
    1. EventPublisher - Stop accepting new events, complete current batch
    2. CytubeConnector - Disconnect from CyTube server
    3. NatsClient - Drain pending messages, close connection
    4. Logging - Flush all log handlers

    The handler enforces timeouts at both component and total shutdown level,
    tracks shutdown state, and provides idempotent shutdown semantics.

    Args:
        publisher: EventPublisher instance to stop first.
        connector: CytubeConnector instance to disconnect second.
        nats_client: NatsClient instance to drain and disconnect third.
        logger: Logger instance for shutdown progress tracking.
        timeout: Total shutdown timeout in seconds (default: 30.0).
        component_timeout: Individual component timeout in seconds (default: 10.0).

    Examples:
        >>> handler = ShutdownHandler(publisher, connector, nats, logger)
        >>> result = await handler.shutdown()
        >>> if not result.clean_exit:
        ...     logger.error("Forced shutdown", extra={"errors": result.errors})
    """

    def __init__(
        self,
        publisher: EventPublisher,
        connector: CytubeConnector,
        nats_client: NatsClient,
        logger: logging.Logger,
        timeout: float = 30.0,
        component_timeout: float = 10.0,
    ):
        """Initialize shutdown handler with components and timeouts."""
        self._publisher = publisher
        self._connector = connector
        self._nats_client = nats_client
        self._logger = logger
        self._timeout = timeout
        self._component_timeout = component_timeout

        self._phase = ShutdownPhase.IDLE
        self._shutdown_task: asyncio.Task | None = None
        self._shutdown_result: ShutdownResult | None = None
        self._shutdown_lock = asyncio.Lock()

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is currently in progress.

        Returns:
            True if shutdown has been initiated but not completed.

        Examples:
            >>> handler.is_shutting_down
            False
            >>> asyncio.create_task(handler.shutdown())
            >>> handler.is_shutting_down
            True
        """
        return self._phase not in (ShutdownPhase.IDLE, ShutdownPhase.COMPLETE)

    async def shutdown(self) -> ShutdownResult:
        """Execute graceful shutdown sequence.

        Stops all components in reverse startup order with timeout enforcement.
        This method is idempotent - concurrent calls will wait for the same
        shutdown operation to complete and return the same result.

        Returns:
            ShutdownResult with metrics and status.

        Raises:
            asyncio.TimeoutError: If total shutdown exceeds configured timeout.

        Examples:
            >>> result = await handler.shutdown()
            >>> assert result.clean_exit
            >>> assert result.duration < 30.0
        """
        # Idempotent shutdown - if already shutting down, wait for result
        async with self._shutdown_lock:
            if self._shutdown_result is not None:
                self._logger.debug("Shutdown already complete, returning cached result")
                return self._shutdown_result

            if self._shutdown_task is not None:
                self._logger.debug("Shutdown in progress, waiting for completion")
                return await self._shutdown_task

            # First shutdown request - create task
            self._shutdown_task = asyncio.create_task(self._execute_shutdown())

        try:
            result = await asyncio.wait_for(self._shutdown_task, timeout=self._timeout)
            self._shutdown_result = result
            return result
        except (TimeoutError, asyncio.TimeoutError):
            # Python 3.10 compat: asyncio.TimeoutError is separate from TimeoutError
            self._logger.critical(
                "Shutdown timeout exceeded - forcing termination",
                extra={"timeout": self._timeout, "phase": self._phase.value}
            )
            result = ShutdownResult(
                clean_exit=False,
                duration=self._timeout,
                events_processed=self._publisher.stats.get("events_published", 0),
                errors=[f"Shutdown timeout exceeded ({self._timeout}s)"],
            )
            self._shutdown_result = result
            return result

    async def _execute_shutdown(self) -> ShutdownResult:
        """Execute the actual shutdown sequence.

        Internal method that performs the shutdown steps. Called by shutdown()
        to ensure only one execution happens even with concurrent calls.
        """
        start_time = time.time()
        errors: list[str] = []
        phase_timings: dict = {}

        try:
            # Phase 1: Initiate shutdown
            self._phase = ShutdownPhase.INITIATED
            self._logger.info("Graceful shutdown initiated")
            phase_start = time.time()

            events_processed = self._publisher.stats.get("events_published", 0)

            phase_timings["initiated"] = time.time() - phase_start

            # Phase 2: Stop publisher (drain in-flight events)
            self._phase = ShutdownPhase.DRAINING
            self._logger.info("Stopping event publisher")
            phase_start = time.time()

            try:
                await asyncio.wait_for(
                    self._publisher.stop(),
                    timeout=self._component_timeout
                )
                self._logger.info("Event publisher stopped cleanly")
            except (TimeoutError, asyncio.TimeoutError):
                error = f"Publisher stop timeout ({self._component_timeout}s)"
                self._logger.warning(error)
                errors.append(error)
            except Exception as e:
                error = f"Publisher stop error: {e}"
                self._logger.error(error, exc_info=True)
                errors.append(error)

            phase_timings["draining"] = time.time() - phase_start

            # Phase 3: Disconnect connector and NATS
            self._phase = ShutdownPhase.DISCONNECTING
            phase_start = time.time()

            # Disconnect CyTube connector
            self._logger.info("Disconnecting CyTube connector")
            try:
                await asyncio.wait_for(
                    self._connector.disconnect(),
                    timeout=self._component_timeout
                )
                self._logger.info("CyTube connector disconnected cleanly")
            except (TimeoutError, asyncio.TimeoutError):
                error = f"Connector disconnect timeout ({self._component_timeout}s)"
                self._logger.warning(error)
                errors.append(error)
            except Exception as e:
                error = f"Connector disconnect error: {e}"
                self._logger.error(error, exc_info=True)
                errors.append(error)

            # Disconnect NATS (includes drain)
            self._logger.info("Disconnecting NATS client")
            try:
                await asyncio.wait_for(
                    self._nats_client.disconnect(),
                    timeout=self._component_timeout
                )
                self._logger.info("NATS client disconnected cleanly")
            except (TimeoutError, asyncio.TimeoutError):
                error = f"NATS disconnect timeout ({self._component_timeout}s)"
                self._logger.warning(error)
                errors.append(error)
            except Exception as e:
                error = f"NATS disconnect error: {e}"
                self._logger.error(error, exc_info=True)
                errors.append(error)

            phase_timings["disconnecting"] = time.time() - phase_start

            # Phase 4: Flush logging
            self._phase = ShutdownPhase.FINALIZING
            self._logger.info("Flushing log handlers")
            phase_start = time.time()

            flush_errors = self._flush_logging()
            if flush_errors:
                for flush_error in flush_errors:
                    errors.append(flush_error)
                self._logger.error(f"Log flush errors: {flush_errors}")
            else:
                self._logger.info("Log handlers flushed cleanly")

            phase_timings["finalizing"] = time.time() - phase_start

            # Phase 5: Complete
            self._phase = ShutdownPhase.COMPLETE
            duration = time.time() - start_time
            clean_exit = len(errors) == 0

            self._logger.info(
                "Graceful shutdown complete",
                extra={
                    "clean_exit": clean_exit,
                    "duration": duration,
                    "events_processed": events_processed,
                    "error_count": len(errors),
                }
            )

            return ShutdownResult(
                clean_exit=clean_exit,
                duration=duration,
                events_processed=events_processed,
                errors=errors,
                phase_timings=phase_timings,
            )

        except Exception as e:
            # Unexpected error during shutdown
            duration = time.time() - start_time
            error = f"Unexpected shutdown error: {e}"
            self._logger.critical(error, exc_info=True)
            errors.append(error)

            return ShutdownResult(
                clean_exit=False,
                duration=duration,
                events_processed=self._publisher.stats.get("events_published", 0),
                errors=errors,
                phase_timings=phase_timings,
            )

    def _flush_logging(self) -> list[str]:
        """Flush and close all logging handlers.

        Ensures all buffered log messages are written before process exit.
        Safe to call even if handlers are already closed.

        Returns:
            List of error messages if any handlers fail to flush.
        """
        root_logger = logging.getLogger()
        errors = []

        for handler in root_logger.handlers[:]:  # Copy list to avoid modification during iteration
            try:
                handler.flush()
                # Note: We don't close handlers here because they might be used
                # by other loggers or the logging module might need them for
                # final cleanup messages. Let Python's shutdown handle that.
            except Exception as e:
                # Log to stderr if logging system is broken
                error_msg = f"Log flush error: {e}"
                print(f"Error flushing log handler {handler}: {e}", flush=True)
                errors.append(error_msg)

        return errors

    async def __aenter__(self) -> "ShutdownHandler":
        """Enter async context manager.

        Returns:
            Self for use in async with statement.

        Examples:
            >>> async with ShutdownHandler(pub, conn, nats, log) as handler:
            ...     # Application runs
            ...     pass
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit async context manager with automatic shutdown.

        Performs graceful shutdown on context exit. Does not suppress exceptions.

        Returns:
            False to propagate any exception.
        """
        if not self.is_shutting_down and self._shutdown_result is None:
            await self.shutdown()
        return False

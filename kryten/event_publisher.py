"""NATS Event Publisher for CyTube Events.

This module provides the EventPublisher component that bridges the CytubeConnector
event stream with NATS publishing, consuming raw events and publishing them to
appropriate NATS subjects.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from .cytube_connector import CytubeConnector
from .nats_client import NatsClient
from .raw_event import RawEvent
from .subject_builder import build_event_subject


class EventPublisher:
    """Bridge between CytubeConnector event stream and NATS publishing.

    Consumes events from a CytubeConnector's async iterator and publishes them
    to NATS with proper subject routing, error handling, and flow control.

    Attributes:
        connector: CytubeConnector providing event stream.
        nats_client: NatsClient for publishing to NATS.
        logger: Logger for structured output.
        batch_size: Number of events to batch (currently supports only 1).
        is_running: Whether publisher is actively running.
        stats: Publishing statistics.

    Examples:
        >>> connector = CytubeConnector(config, logger)
        >>> nats_client = NatsClient(nats_config, logger)
        >>> publisher = EventPublisher(connector, nats_client, logger)
        >>>
        >>> await connector.connect()
        >>> await nats_client.connect()
        >>> task = asyncio.create_task(publisher.run())
        >>> # Publisher now bridging events
        >>> await publisher.stop()
    """

    def __init__(
        self,
        connector: CytubeConnector,
        nats_client: NatsClient,
        logger: logging.Logger,
        batch_size: int = 1,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize event publisher.

        Args:
            connector: CytubeConnector instance providing event stream.
            nats_client: NatsClient instance for NATS publishing.
            logger: Logger for structured logging.
            batch_size: Events per batch (currently only 1 supported).
            retry_attempts: Number of retry attempts for transient failures.
            retry_delay: Initial delay between retries in seconds.
        """
        self.connector = connector
        self.nats_client = nats_client
        self.logger = logger
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # State
        self._running = False
        self._stop_requested = False

        # Statistics
        self._events_received = 0
        self._events_published = 0
        self._publish_errors = 0
        self._total_publish_time = 0.0

    @property
    def is_running(self) -> bool:
        """Check if publisher is actively running.

        Returns:
            True if publisher run loop is active, False otherwise.

        Examples:
            >>> publisher = EventPublisher(connector, nats, logger)
            >>> publisher.is_running
            False
            >>> # After starting run()
            >>> publisher.is_running
            True
        """
        return self._running

    @property
    def stats(self) -> Dict[str, Any]:
        """Get publishing statistics.

        Returns:
            Dictionary with events_received, events_published, publish_errors,
            average_publish_time_ms, and success_rate.

        Examples:
            >>> stats = publisher.stats
            >>> print(f"Published: {stats['events_published']}")
            >>> print(f"Success rate: {stats['success_rate']:.1%}")
        """
        avg_time_ms = 0.0
        if self._events_published > 0:
            avg_time_ms = (self._total_publish_time / self._events_published) * 1000

        success_rate = 0.0
        if self._events_received > 0:
            success_rate = self._events_published / self._events_received

        return {
            "events_received": self._events_received,
            "events_published": self._events_published,
            "publish_errors": self._publish_errors,
            "average_publish_time_ms": avg_time_ms,
            "success_rate": success_rate,
        }

    async def run(self) -> None:
        """Start publishing events from connector to NATS.

        Runs until stop() is called or an unrecoverable error occurs.
        Consumes events from connector's recv_events() iterator and publishes
        each to NATS with appropriate subject routing.

        Raises:
            asyncio.CancelledError: If task is cancelled.
            Exception: If connector or NATS encounters unrecoverable error.

        Examples:
            >>> task = asyncio.create_task(publisher.run())
            >>> await asyncio.sleep(10)
            >>> await publisher.stop()
        """
        if self._running:
            self.logger.warning("Publisher already running, ignoring run() call")
            return

        self._running = True
        self._stop_requested = False

        self.logger.info(
            "Event publisher started",
            extra={
                "batch_size": self.batch_size,
                "retry_attempts": self.retry_attempts,
            },
        )

        try:
            async for event_name, payload in self.connector.recv_events():
                # Check if stop requested
                if self._stop_requested:
                    self.logger.info("Stop requested, finishing current batch")
                    break

                self._events_received += 1

                # Create RawEvent wrapper
                raw_event = RawEvent(
                    event_name=event_name,
                    payload=payload,
                    channel=self.connector.config.channel,
                    domain=self.connector.config.domain,
                )

                # Log received event (with payload for error messages)
                if event_name == "errorMsg":
                    self.logger.error(
                        f"Received CyTube error: {payload}",
                        extra={
                            "event_name": event_name,
                            "error_payload": payload,
                            "correlation_id": raw_event.correlation_id,
                        },
                    )
                else:
                    self.logger.info(
                        f"Received event: {event_name}",
                        extra={
                            "event_name": event_name,
                            "correlation_id": raw_event.correlation_id,
                        },
                    )

                # Build NATS subject
                try:
                    subject = build_event_subject(raw_event)
                except ValueError as e:
                    # Log the problematic event and skip it
                    self.logger.warning(
                        f"Skipping event with invalid name: {e}",
                        extra={
                            "event_name": event_name,
                            "raw_event_name": event_name,
                            "payload_preview": str(payload)[:200],
                            "correlation_id": raw_event.correlation_id,
                        },
                    )
                    continue

                # Publish to NATS with retry
                await self._publish_with_retry(subject, raw_event)

        except asyncio.CancelledError:
            self.logger.info("Publisher cancelled")
            raise

        except Exception as e:
            self.logger.error(
                f"Publisher failed with error: {e}",
                extra={"error": str(e), "type": type(e).__name__},
            )
            raise

        finally:
            self._running = False
            self.logger.info(
                "Event publisher stopped",
                extra=self.stats,
            )

    async def stop(self) -> None:
        """Gracefully stop the publisher.

        Requests stop and waits for current batch to complete.
        Safe to call multiple times.

        Examples:
            >>> await publisher.stop()
            >>> assert not publisher.is_running
        """
        if not self._running:
            self.logger.debug("Publisher not running, stop() is a no-op")
            return

        self.logger.info("Requesting publisher stop")
        self._stop_requested = True

        # Wait for run loop to finish (with timeout)
        timeout = 5.0
        start_time = time.time()
        while self._running and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)

        if self._running:
            self.logger.warning("Publisher did not stop within timeout")

    async def _publish_with_retry(self, subject: str, event: RawEvent) -> None:
        """Publish event to NATS with retry logic.

        Args:
            subject: NATS subject string.
            event: RawEvent to publish.

        Logs errors and updates statistics.
        """
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.retry_attempts:
            try:
                start_time = time.time()

                # Serialize and publish
                event_bytes = event.to_bytes()
                await self.nats_client.publish(subject, event_bytes)

                # Track timing
                elapsed = time.time() - start_time
                self._total_publish_time += elapsed

                # Update stats
                self._events_published += 1

                # Log success
                self.logger.info(
                    f"Published event '{event.event_name}' to NATS subject: {subject}",
                    extra={
                        "subject": subject,
                        "event_name": event.event_name,
                        "correlation_id": event.correlation_id,
                        "size": len(event_bytes),
                        "elapsed_ms": elapsed * 1000,
                    },
                )

                return  # Success!

            except Exception as e:
                last_error = e
                attempt += 1

                if attempt <= self.retry_attempts:
                    # Retry with exponential backoff
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.logger.warning(
                        f"Publish failed, retrying in {delay}s (attempt {attempt}/{self.retry_attempts})",
                        extra={
                            "subject": subject,
                            "event_name": event.event_name,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        self._publish_errors += 1
        self.logger.error(
            "Publish failed permanently after retries",
            extra={
                "subject": subject,
                "event_name": event.event_name,
                "correlation_id": event.correlation_id,
                "attempts": self.retry_attempts + 1,
                "error": str(last_error),
            },
        )


__all__ = ["EventPublisher"]

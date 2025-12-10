"""Health monitoring system for Kryten.

This module provides HTTP health check endpoints and metrics tracking for
operational visibility and integration with orchestration platforms (Kubernetes, systemd).

The health monitor runs an HTTP server on a separate thread to avoid blocking
the async event loop, exposing:
- /health - JSON health status (200 OK or 503 Service Unavailable)
- /metrics - Prometheus-compatible metrics (optional)

Examples:
    Basic usage:
        >>> monitor = HealthMonitor(
        ...     connector=cytube_connector,
        ...     nats_client=nats_client,
        ...     publisher=event_publisher,
        ...     logger=logger,
        ...     port=8080
        ... )
        >>> monitor.start()
        >>> # Health available at http://localhost:8080/health
        >>> monitor.stop()

    Integration with Kubernetes:
        apiVersion: v1
        kind: Pod
        spec:
          containers:
          - name: kryten
            livenessProbe:
              httpGet:
                path: /health
                port: 8080
              initialDelaySeconds: 10
              periodSeconds: 30

Note:
    The health server runs on a separate thread to ensure health checks
    remain responsive even if the main event loop is busy or blocked.
"""

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Optional

from .cytube_connector import CytubeConnector
from .event_publisher import EventPublisher
from .nats_client import NatsClient

if TYPE_CHECKING:
    from .command_subscriber import CommandSubscriber


class HealthStatus:
    """Health status aggregator for Kryten components.

    Collects component states and metrics to determine overall health.

    Attributes:
        connector: CytubeConnector instance for connection status.
        nats_client: NatsClient instance for NATS status.
        publisher: EventPublisher instance for event processing status.
        command_subscriber: CommandSubscriber instance for command metrics (optional).
        start_time: Application start timestamp for uptime calculation.
    """

    def __init__(
        self,
        connector: CytubeConnector,
        nats_client: NatsClient,
        publisher: EventPublisher,
        command_subscriber: Optional["CommandSubscriber"] = None,
    ):
        """Initialize health status aggregator.

        Args:
            connector: CytubeConnector instance.
            nats_client: NatsClient instance.
            publisher: EventPublisher instance.
            command_subscriber: CommandSubscriber instance (optional).
        """
        self.connector = connector
        self.nats_client = nats_client
        self.publisher = publisher
        self.command_subscriber = command_subscriber
        self.start_time = time.time()

    def is_healthy(self) -> bool:
        """Check if all critical components are healthy.

        Returns:
            True if all components connected/running, False otherwise.

        Examples:
            >>> status = HealthStatus(connector, nats, publisher)
            >>> if status.is_healthy():
            ...     print("System healthy")
        """
        return (
            self.connector.is_connected
            and self.nats_client.is_connected
            and self.publisher.is_running
        )

    def get_status_dict(self) -> dict:
        """Get comprehensive health status as dictionary.

        Returns:
            Dictionary with status, uptime, components, and metrics.

        Examples:
            >>> status = HealthStatus(connector, nats, publisher)
            >>> data = status.get_status_dict()
            >>> print(data["status"])  # "healthy" or "unhealthy"
        """
        uptime = time.time() - self.start_time

        # Component states
        components = {
            "cytube_connector": "connected" if self.connector.is_connected else "disconnected",
            "nats_client": "connected" if self.nats_client.is_connected else "disconnected",
            "event_publisher": "running" if self.publisher.is_running else "stopped",
        }

        # Add command subscriber if enabled
        if self.command_subscriber:
            components["command_subscriber"] = "running" if self.command_subscriber.is_running else "stopped"

        # Aggregate metrics from components
        connector_stats = self.connector.stats
        nats_stats = self.nats_client.stats
        publisher_stats = self.publisher.stats

        metrics = {
            "events_received": connector_stats.get("events_processed", 0),
            "events_published": publisher_stats.get("events_published", 0),
            "publish_errors": publisher_stats.get("publish_errors", 0),
            "nats_bytes_sent": nats_stats.get("bytes_sent", 0),
        }

        # Add command metrics if subscriber enabled
        if self.command_subscriber:
            command_stats = self.command_subscriber.stats
            metrics["commands_processed"] = command_stats.get("commands_processed", 0)
            metrics["commands_failed"] = command_stats.get("commands_failed", 0)

        return {
            "status": "healthy" if self.is_healthy() else "unhealthy",
            "uptime_seconds": round(uptime, 2),
            "components": components,
            "metrics": metrics,
        }

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-compatible metrics.

        Returns:
            Prometheus text format metrics.

        Examples:
            >>> status = HealthStatus(connector, nats, publisher)
            >>> metrics = status.get_prometheus_metrics()
            >>> print(metrics)
            # HELP kryten_up Whether Kryten is up (1) or down (0)
            # TYPE kryten_up gauge
            kryten_up 1
            ...
        """
        uptime = time.time() - self.start_time
        is_healthy = 1 if self.is_healthy() else 0

        connector_stats = self.connector.stats
        nats_stats = self.nats_client.stats
        publisher_stats = self.publisher.stats

        lines = [
            "# HELP kryten_up Whether Kryten is up (1) or down (0)",
            "# TYPE kryten_up gauge",
            f"kryten_up {is_healthy}",
            "",
            "# HELP kryten_uptime_seconds Time since application start",
            "# TYPE kryten_uptime_seconds counter",
            f"kryten_uptime_seconds {uptime:.2f}",
            "",
            "# HELP kryten_events_received_total Events received from CyTube",
            "# TYPE kryten_events_received_total counter",
            f"kryten_events_received_total {connector_stats.get('events_processed', 0)}",
            "",
            "# HELP kryten_events_published_total Events published to NATS",
            "# TYPE kryten_events_published_total counter",
            f"kryten_events_published_total {publisher_stats.get('events_published', 0)}",
            "",
            "# HELP kryten_publish_errors_total Publishing errors",
            "# TYPE kryten_publish_errors_total counter",
            f"kryten_publish_errors_total {publisher_stats.get('publish_errors', 0)}",
            "",
            "# HELP kryten_nats_bytes_sent_total Bytes sent to NATS",
            "# TYPE kryten_nats_bytes_sent_total counter",
            f"kryten_nats_bytes_sent_total {nats_stats.get('bytes_sent', 0)}",
            "",
            "# HELP kryten_component_connected Component connection status (1=connected, 0=disconnected)",
            "# TYPE kryten_component_connected gauge",
            f"kryten_component_connected{{component=\"cytube\"}} {1 if self.connector.is_connected else 0}",
            f"kryten_component_connected{{component=\"nats\"}} {1 if self.nats_client.is_connected else 0}",
            f"kryten_component_connected{{component=\"publisher\"}} {1 if self.publisher.is_running else 0}",
        ]

        # Add command metrics if subscriber enabled
        if self.command_subscriber:
            command_stats = self.command_subscriber.stats
            lines.extend([
                f"kryten_component_connected{{component=\"command_subscriber\"}} {1 if self.command_subscriber.is_running else 0}",
                "",
                "# HELP kryten_commands_processed_total Commands received and executed",
                "# TYPE kryten_commands_processed_total counter",
                f"kryten_commands_processed_total {command_stats.get('commands_processed', 0)}",
                "",
                "# HELP kryten_commands_failed_total Commands that failed to execute",
                "# TYPE kryten_commands_failed_total counter",
                f"kryten_commands_failed_total {command_stats.get('commands_failed', 0)}",
            ])

        lines.append("")

        return "\n".join(lines)


class HealthRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health endpoints.

    Handles /health and /metrics endpoints, accessing the HealthStatus
    instance attached to the server.
    """

    # Suppress default logging (we use structured logging)
    def log_message(self, format, *args):
        """Override to suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests for health endpoints.

        Routes:
            /health - JSON health status
            /metrics - Prometheus metrics
        """
        try:
            if self.path == "/health":
                self._handle_health()
            elif self.path == "/metrics":
                self._handle_metrics()
            else:
                self._handle_not_found()
        except Exception as e:
            # Log error but don't let it crash the server
            if hasattr(self.server, 'logger'):
                self.server.logger.error(f"Health endpoint error: {e}", exc_info=True)
            self.send_error(500, "Internal Server Error")

    def _handle_health(self):
        """Handle /health endpoint.

        Returns 200 OK if healthy, 503 Service Unavailable if unhealthy.
        """
        status: HealthStatus = self.server.health_status
        status_dict = status.get_status_dict()

        # Determine HTTP status code
        http_status = 200 if status.is_healthy() else 503

        # Send response
        self.send_response(http_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response_json = json.dumps(status_dict, indent=2)
        self.wfile.write(response_json.encode("utf-8"))

    def _handle_metrics(self):
        """Handle /metrics endpoint.

        Returns Prometheus-compatible metrics.
        """
        status: HealthStatus = self.server.health_status
        metrics_text = status.get_prometheus_metrics()

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()

        self.wfile.write(metrics_text.encode("utf-8"))

    def _handle_not_found(self):
        """Handle unknown endpoints."""
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        error_dict = {
            "error": "Not Found",
            "message": "Available endpoints: /health, /metrics"
        }
        self.wfile.write(json.dumps(error_dict).encode("utf-8"))


class HealthMonitor:
    """Health monitoring system with HTTP server.

    Runs an HTTP server on a separate thread exposing health status and
    metrics for operational visibility and orchestration integration.

    Args:
        connector: CytubeConnector instance.
        nats_client: NatsClient instance.
        publisher: EventPublisher instance.
        command_subscriber: CommandSubscriber instance (optional).
        logger: Logger for health monitoring events.
        host: HTTP server bind address (default: "0.0.0.0").
        port: HTTP server port (default: 8080).

    Examples:
        >>> monitor = HealthMonitor(connector, nats, publisher, cmd_sub, logger)
        >>> monitor.start()
        >>> # Health check: curl http://localhost:8080/health
        >>> # Metrics: curl http://localhost:8080/metrics
        >>> monitor.stop()
    """

    def __init__(
        self,
        connector: CytubeConnector,
        nats_client: NatsClient,
        publisher: EventPublisher,
        logger: logging.Logger,
        command_subscriber: Optional["CommandSubscriber"] = None,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        """Initialize health monitor.

        Args:
            connector: CytubeConnector instance.
            nats_client: NatsClient instance.
            publisher: EventPublisher instance.
            logger: Logger instance.
            command_subscriber: CommandSubscriber instance (optional).
            host: Server bind address.
            port: Server port.
        """
        self.connector = connector
        self.nats_client = nats_client
        self.publisher = publisher
        self.command_subscriber = command_subscriber
        self.logger = logger
        self.host = host
        self.port = port

        self._health_status = HealthStatus(connector, nats_client, publisher, command_subscriber)
        self._server: HTTPServer | None = None
        self._server_thread: Thread | None = None
        self._running = False

    def start(self):
        """Start health monitoring HTTP server.

        Starts server on separate thread to avoid blocking event loop.
        Safe to call multiple times (no-op if already running).

        Examples:
            >>> monitor = HealthMonitor(connector, nats, publisher, logger)
            >>> monitor.start()
            >>> assert monitor.is_running
        """
        if self._running:
            self.logger.debug("Health monitor already running")
            return

        try:
            # Create HTTP server
            self._server = HTTPServer((self.host, self.port), HealthRequestHandler)
            self._server.health_status = self._health_status
            self._server.logger = self.logger

            # Start server on separate thread
            self._server_thread = Thread(
                target=self._run_server,
                daemon=True,
                name="health-monitor"
            )
            self._server_thread.start()

            self._running = True
            self.logger.info(
                "Health monitor started",
                extra={"host": self.host, "port": self.port}
            )

        except Exception as e:
            self.logger.error(f"Failed to start health monitor: {e}", exc_info=True)
            raise

    def _run_server(self):
        """Run HTTP server (called on separate thread).

        Internal method that serves requests until server is shut down.
        """
        try:
            self.logger.debug("Health monitor server thread started")
            self._server.serve_forever()
        except Exception as e:
            self.logger.error(f"Health monitor server error: {e}", exc_info=True)
        finally:
            self.logger.debug("Health monitor server thread exiting")

    def stop(self):
        """Stop health monitoring HTTP server.

        Shuts down server and waits for thread to exit.
        Safe to call multiple times (no-op if not running).

        Examples:
            >>> monitor.stop()
            >>> assert not monitor.is_running
        """
        if not self._running:
            self.logger.debug("Health monitor not running")
            return

        try:
            self.logger.info("Stopping health monitor")

            # Shutdown server
            if self._server:
                self._server.shutdown()
                self._server.server_close()

            # Wait for thread to exit
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5.0)
                if self._server_thread.is_alive():
                    self.logger.warning("Health monitor thread did not exit cleanly")

            self._running = False
            self.logger.info("Health monitor stopped")

        except Exception as e:
            self.logger.error(f"Error stopping health monitor: {e}", exc_info=True)
            raise

    @property
    def is_running(self) -> bool:
        """Check if health monitor is running.

        Returns:
            True if server is running, False otherwise.

        Examples:
            >>> monitor.start()
            >>> assert monitor.is_running
        """
        return self._running

    def __enter__(self):
        """Enter context manager (start server).

        Returns:
            Self for use in with statement.
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager (stop server).

        Returns:
            False to propagate any exception.
        """
        self.stop()
        return False

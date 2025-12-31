"""Main Entry Point for Kryten CyTube Connector.

This module provides the application orchestration logic for running Kryten
as a standalone service. It coordinates component initialization, handles
signals for graceful shutdown, and manages the application lifecycle.

Usage:
    python -m kryten
    python -m kryten --config /path/to/config.json
    python -m kryten --version
    python -m kryten --help

Default config locations (searched in order):
    - /etc/kryten/kryten-robot/config.json
    - ./config.json

Exit Codes:
    0: Clean shutdown
    1: Error occurred (configuration, connection, or runtime error)
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any, cast

from . import (
    CommandSubscriber,
    ConnectionWatchdog,
    CytubeConnector,
    CytubeEventSender,
    EventPublisher,
    HealthMonitor,
    LifecycleEventPublisher,
    LoggingConfig,
    NatsClient,
    StateManager,
    StateQueryHandler,
    __version__,
    load_config,
    setup_logging,
)
from .application_state import ApplicationState
from .audit_logger import create_audit_logger
from .errors import ConnectionError as KrytenConnectionError

# Module logger (configured after logging setup)
logger: logging.Logger | None = None


def print_startup_banner(config_path: str) -> None:
    """Print startup banner with version and configuration info.

    Args:
        config_path: Path to configuration file.
    """
    from . import load_config
    from .raw_event import RawEvent
    from .subject_builder import build_event_subject

    try:
        config = load_config(config_path)

        # Build example subjects to show what we'll subscribe/publish to
        from .subject_builder import normalize_token

        example_event = RawEvent(
            event_name="chatMsg",
            payload={},
            channel=config.cytube.channel,
            domain=config.cytube.domain,
        )
        event_subject = build_event_subject(example_event)
        # Build command subject base without wildcards (normalized channel removes special chars)
        command_base = f"kryten.commands.cytube.{normalize_token(config.cytube.channel)}"

        print("=" * 60)
        print(f"Kryten CyTube Connector v{__version__}")
        print("=" * 60)
        print(f"Config:  {Path(config_path).resolve()}")
        print(f"Domain:  {config.cytube.domain}")
        print(f"Channel: {config.cytube.channel}")
        print(f"NATS:    {config.nats.servers[0] if config.nats.servers else 'N/A'}")
        print("=" * 60)
        print("NATS Subjects:")
        print(f"  Publishing:  {event_subject.rsplit('.', 1)[0]}.*")
        print(f"  Subscribing: {command_base}.*")
        print("=" * 60)
        print()
    except Exception as e:
        print("=" * 60)
        print(f"Kryten CyTube Connector v{__version__}")
        print("=" * 60)
        print(f"Config:  {config_path}")
        print(f"Error loading config: {e}")
        print("=" * 60)
        print()


async def main(config_path: str) -> int:
    """Main orchestration function.

    Coordinates component initialization and lifecycle:
    1. Load configuration
    2. Initialize logging
    3. Connect to NATS
    4. Connect to CyTube
    5. Start event publisher
    6. Wait for shutdown signal
    7. Cleanup in reverse order

    Args:
        config_path: Path to JSON configuration file.

    Returns:
        Exit code (0=success, 1=error).
    """
    global logger

    # Variables to track initialized components for cleanup
    nats_client: NatsClient | None = None
    connector: CytubeConnector | None = None
    publisher: EventPublisher | None = None
    sender: CytubeEventSender | None = None
    cmd_subscriber: CommandSubscriber | None = None
    health_monitor: HealthMonitor | None = None
    watchdog: ConnectionWatchdog | None = None
    robot_cmd_handler = None  # RobotCommandHandler for system.ping etc
    app_state: ApplicationState | None = None  # Created after config load

    def signal_handler(signum: int, frame) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM).

        Sets shutdown event to trigger graceful shutdown.
        Signal handlers must not perform async operations directly.
        """
        signame = signal.Signals(signum).name
        sig_logger = logger
        if sig_logger:
            sig_logger.info(f"Received {signame}, initiating graceful shutdown")
        else:
            print(f"\nReceived {signame}, initiating graceful shutdown...")
        if app_state:
            app_state.shutdown_event.set()

    try:
        # REQ-002: Load configuration
        if logger:
            logger.info(f"Loading configuration from {config_path}")

        config = load_config(config_path)

        # REQ-003: Initialize logging before any other components
        logging_config = LoggingConfig(
            level=config.log_level,
            format="text",  # Text format for console readability
            output="console",
        )
        setup_logging(logging_config)

        # Get logger after setup
        logger = logging.getLogger("bot.kryten.main")
        assert logger is not None

        logger.info(f"Starting Kryten CyTube Connector v{__version__}")
        logger.info(f"Configuration loaded from {config_path}")
        logger.info(f"Log level: {config.log_level}")

        # Initialize audit logger
        audit_logger = create_audit_logger(
            base_path=config.logging.base_path,
            filenames={
                "admin_operations": config.logging.admin_operations,
                "playlist_operations": config.logging.playlist_operations,
                "chat_messages": config.logging.chat_messages,
                "command_audit": config.logging.command_audit,
                "connection_events": config.logging.connection_events,
            },
        )
        logger.info(f"Audit logging initialized: {config.logging.base_path}")
        logger.info(f"  - Admin operations: {config.logging.admin_operations}")
        logger.info(f"  - Playlist operations: {config.logging.playlist_operations}")
        logger.info(f"  - Chat messages: {config.logging.chat_messages}")
        logger.info(f"  - Command audit: {config.logging.command_audit}")
        logger.info(f"  - Connection events: {config.logging.connection_events}")

        # Create ApplicationState for system management
        app_state = ApplicationState(config_path=config_path, config=config)
        logger.info("Application state initialized")

        # REQ-006: Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("Signal handlers registered (SIGINT, SIGTERM)")

        # REQ-004: Connect to NATS before CyTube (event sink must be ready)
        logger.info(f"Connecting to NATS: {config.nats.servers}")
        nats_client = NatsClient(config.nats, logger)

        try:
            await nats_client.connect()
            app_state.nats_client = nats_client
            logger.info("Successfully connected to NATS")
            audit_logger.log_connection_event(
                "connect", "NATS", details={"servers": ",".join(config.nats.servers)}
            )
        except Exception as e:
            # AC-003: NATS connection failure exits with code 1
            logger.error(f"Failed to connect to NATS: {e}", exc_info=True)
            audit_logger.log_connection_event("error", "NATS", error=str(e))
            return 1

        # Start lifecycle event publisher
        lifecycle = LifecycleEventPublisher(
            service_name="robot", nats_client=nats_client, logger=logger, version=__version__
        )
        await lifecycle.start()

        # Publish startup event
        await lifecycle.publish_startup()

        # Register restart handler
        async def handle_restart_notice(data: dict):
            """Handle groupwide restart notice."""
            delay = data.get("delay_seconds", 5)
            logger.warning(f"Restart notice received, shutting down in {delay}s")
            await asyncio.sleep(delay)
            app_state.shutdown_event.set()

        lifecycle.on_restart_notice(handle_restart_notice)

        # Publish NATS connection event
        await lifecycle.publish_connected("NATS", servers=config.nats.servers)

        # Start service registry to track microservices
        from .service_registry import ServiceRegistry

        service_registry = ServiceRegistry(nats_client, logger)

        # Register callbacks for service events
        def on_service_registered(service_info):
            logger.info(
                f"🔵 Service registered: {service_info.name} v{service_info.version} "
                f"on {service_info.hostname}"
            )

        def on_service_heartbeat(service_info):
            # Only log every 10th heartbeat to avoid spam
            if service_info.heartbeat_count % 10 == 0:
                logger.debug(
                    f"💓 Heartbeat from {service_info.name} "
                    f"(count: {service_info.heartbeat_count})"
                )

        def on_service_shutdown(service_name):
            logger.warning(f"🔴 Service shutdown: {service_name}")

        service_registry.on_service_registered(on_service_registered)
        service_registry.on_service_heartbeat(on_service_heartbeat)
        service_registry.on_service_shutdown(on_service_shutdown)

        await service_registry.start()
        app_state.service_registry = service_registry

        # REQ-XXX: Start state manager BEFORE connecting to CyTube
        # This ensures callbacks are ready when initial state events arrive
        try:
            logger.info("Starting state manager")
            state_manager = StateManager(
                nats_client, config.cytube.channel, logger, counting_config=config.state_counting
            )
            await state_manager.start()
            app_state.state_manager = state_manager
            logger.info("State manager started - ready to persist channel state")
        except RuntimeError as e:
            logger.error(f"Failed to start state manager: {e}")
            logger.warning("Continuing without state persistence")
            state_manager = None

        # Connect to CyTube (automatically joins channel and authenticates)
        logger.info(f"Connecting to CyTube: {config.cytube.domain}/{config.cytube.channel}")
        connector = CytubeConnector(config.cytube, logger)
        app_state.connector = connector

        # Register state callbacks BEFORE connecting
        # so initial state events from _request_initial_state() are captured
        if state_manager:

            def handle_state_event(event_name: str, payload: Any) -> None:
                """Handle events that affect channel state."""

                async def update_state():
                    try:
                        logger.debug(f"State callback triggered: {event_name}")

                        if event_name == "emoteList":
                            await state_manager.update_emotes(cast(list[dict[str, Any]], payload))
                        elif event_name == "playlist":
                            # Full playlist or empty list
                            await state_manager.set_playlist(cast(list[dict[str, Any]], payload))
                        elif event_name == "queue":
                            # Single item added
                            item = payload.get("item", {})
                            after = payload.get("after")
                            await state_manager.add_playlist_item(item, after)
                        elif event_name == "delete":
                            uid = payload.get("uid")
                            if uid:
                                await state_manager.remove_playlist_item(uid)
                        elif event_name == "moveVideo":
                            from_uid = payload.get("from")
                            after = payload.get("after")
                            if from_uid and after is not None:
                                await state_manager.move_playlist_item(from_uid, str(after))
                        elif event_name == "userlist":
                            await state_manager.set_userlist(cast(list[dict[str, Any]], payload))
                        elif event_name == "addUser":
                            await state_manager.add_user(payload)
                        elif event_name == "userLeave":
                            name = payload.get("name")
                            if name:
                                await state_manager.remove_user(name)
                        elif event_name == "setUserRank":
                            # User rank changed - update user
                            name = payload.get("name")
                            rank = payload.get("rank")
                            if name is not None:
                                await state_manager.update_user({"name": name, "rank": rank})
                        elif event_name == "changeMedia":
                            # Currently playing media changed
                            await state_manager.update_current_media(payload)
                    except Exception as e:
                        logger.error(f"Error handling state event {event_name}: {e}", exc_info=True)

                # Schedule the async task
                asyncio.create_task(update_state())

            # Register state callbacks for relevant events
            state_events = [
                "emoteList",
                "playlist",
                "queue",
                "delete",
                "moveVideo",
                "userlist",
                "addUser",
                "userLeave",
                "setUserRank",
                "changeMedia",
            ]
            for event in state_events:
                connector.on_event(event, handle_state_event)

            logger.info("State callbacks registered")

        # Register chat message logging
        def handle_chat_message(event_name: str, payload: dict) -> None:
            """Log chat messages to audit log."""
            try:
                username = payload.get("username", "Unknown")
                message = payload.get("msg", "")
                # Use server timestamp if available, otherwise current time
                from datetime import datetime

                timestamp = datetime.now()
                audit_logger.log_chat_message(username, message, timestamp)
            except Exception as e:
                logger.error(f"Error logging chat message: {e}", exc_info=True)

        connector.on_event("chatMsg", handle_chat_message)
        logger.info("Chat message logging registered")

        # Placeholder for watchdog timeout handler (set properly after attempt_reconnect is defined)
        async def placeholder_timeout() -> None:
            """Placeholder - will be replaced after reconnect function is defined."""
            pass

        # Start connection watchdog to detect stale connections
        # Note: The watchdog timeout handler is defined later, after attempt_reconnect is available
        watchdog = ConnectionWatchdog(
            timeout=120.0,  # 2 minutes without events triggers reconnection
            on_timeout=placeholder_timeout,
            logger=logger,
            enabled=True,
        )
        await watchdog.start()
        logger.info("Connection watchdog monitoring CyTube health")

        # Feed events to watchdog to keep it alive
        def pet_watchdog(event_name: str, payload: dict) -> None:
            """Pet watchdog on any received event."""
            if watchdog:
                watchdog.pet()

        # Register watchdog feeder for common periodic events
        # Media events happen regularly as videos play
        for event in ["changeMedia", "mediaUpdate", "setCurrent", "chatMsg", "usercount"]:
            connector.on_event(event, pet_watchdog)

        try:
            await connector.connect()
            logger.info("Successfully connected to CyTube")
            audit_logger.log_connection_event(
                "connect",
                "CyTube",
                details={"domain": config.cytube.domain, "channel": config.cytube.channel},
            )

            # Publish CyTube connection event
            await lifecycle.publish_connected(
                "CyTube", domain=config.cytube.domain, channel=config.cytube.channel
            )
        except KrytenConnectionError as e:
            # AC-004: CyTube connection failure
            logger.error(f"Failed to connect to CyTube: {e}", exc_info=True)
            audit_logger.log_connection_event(
                "error",
                "CyTube",
                details={"domain": config.cytube.domain, "channel": config.cytube.channel},
                error=str(e),
            )
            # Cleanup
            await lifecycle.publish_shutdown(reason="Failed to connect to CyTube")
            await lifecycle.stop()
            if nats_client:
                await nats_client.disconnect()
            return 1

        # REQ-005: Start EventPublisher after both connector and NATS connected
        logger.info("Starting event publisher")
        publisher = EventPublisher(
            connector=connector,
            nats_client=nats_client,
            logger=logger,
            batch_size=1,
            retry_attempts=3,
            retry_delay=1.0,
        )
        app_state.event_publisher = publisher

        # Track reconnect task to avoid multiple concurrent reconnects
        reconnect_task: asyncio.Task | None = None

        # Declare publisher_task early so nonlocal reference works in attempt_reconnect
        publisher_task: asyncio.Task | None = None

        async def attempt_reconnect(reason: str = "unknown"):
            """Attempt to reconnect to CyTube after connection loss."""
            nonlocal reconnect_task
            try:
                # Log disconnection event
                audit_logger.log_connection_event(
                    "disconnect",
                    "CyTube",
                    details={"domain": config.cytube.domain, "channel": config.cytube.channel},
                    error=reason,
                )

                # Wait a bit before reconnecting to avoid rapid reconnect loops
                reconnect_delay = 5.0
                logger.info(
                    f"Waiting {reconnect_delay}s before attempting reconnect (reason: {reason})..."
                )
                await asyncio.sleep(reconnect_delay)

                # Stop the publisher first
                logger.info("Stopping event publisher for reconnect...")
                await publisher.stop()

                # Disconnect from CyTube (cleanup any remaining state)
                logger.info("Cleaning up CyTube connection for reconnect...")
                await connector.disconnect()

                # Attempt to reconnect
                logger.info("Attempting to reconnect to CyTube...")
                await connector.connect()
                logger.info("Successfully reconnected to CyTube")

                # Log successful reconnection
                audit_logger.log_connection_event(
                    "reconnect",
                    "CyTube",
                    details={
                        "domain": config.cytube.domain,
                        "channel": config.cytube.channel,
                        "reason": reason,
                    },
                )

                # Publish reconnection event via lifecycle
                if lifecycle and nats_client and nats_client.is_connected:
                    await lifecycle.publish_connected(
                        "CyTube",
                        domain=config.cytube.domain,
                        channel=config.cytube.channel,
                        note=f"Reconnected after: {reason}",
                    )

                # Restart the publisher
                nonlocal publisher_task
                publisher_task = asyncio.create_task(publisher.run())
                logger.info("Event publisher restarted after reconnect")

            except Exception as e:
                logger.error(f"Failed to reconnect to CyTube: {e}", exc_info=True)
                audit_logger.log_connection_event(
                    "error",
                    "CyTube",
                    details={"domain": config.cytube.domain, "channel": config.cytube.channel},
                    error=f"Reconnect failed: {e}",
                )
                logger.warning("Falling back to graceful shutdown for systemd restart")
                app_state.shutdown_event.set()
            finally:
                reconnect_task = None

        # Register kick handler - behavior depends on aggressive_reconnect setting
        def handle_kicked():
            """Handle being kicked from channel."""
            nonlocal reconnect_task
            if config.cytube.aggressive_reconnect:
                logger.warning(
                    "Kicked from channel - aggressive_reconnect enabled, attempting reconnect"
                )
                if reconnect_task is None or reconnect_task.done():
                    reconnect_task = asyncio.create_task(attempt_reconnect("kicked"))
                else:
                    logger.warning("Reconnect already in progress, ignoring duplicate kick")
            else:
                logger.warning(
                    "Kicked from channel - initiating graceful shutdown for systemd restart"
                )
                app_state.shutdown_event.set()

        publisher.on_kicked(handle_kicked)

        # Register connection loss handler for detecting CyTube disconnects
        def handle_connection_lost(event_name: str, payload: dict):
            """Handle CyTube connection loss (detected by socket closure)."""
            nonlocal reconnect_task
            reason = payload.get("reason", "connection lost")
            logger.warning(f"CyTube connection lost: {reason}")

            if config.cytube.aggressive_reconnect:
                logger.info("aggressive_reconnect enabled - attempting automatic reconnection")
                if reconnect_task is None or reconnect_task.done():
                    reconnect_task = asyncio.create_task(attempt_reconnect(reason))
                else:
                    logger.warning(
                        "Reconnect already in progress, ignoring duplicate connection loss"
                    )
            else:
                logger.warning("Initiating graceful shutdown for systemd restart")
                app_state.shutdown_event.set()

        connector.on_event("_connection_lost", handle_connection_lost)

        # Now set the proper watchdog timeout handler that respects aggressive_reconnect
        async def handle_watchdog_timeout():
            """Handle connection watchdog timeout by attempting reconnect or shutdown."""
            nonlocal reconnect_task
            logger.error("Connection watchdog timeout - no events received for 2+ minutes")
            audit_logger.log_connection_event(
                "timeout",
                "CyTube",
                details={"domain": config.cytube.domain, "channel": config.cytube.channel},
                error="Watchdog timeout - no events received",
            )

            if config.cytube.aggressive_reconnect:
                logger.info("aggressive_reconnect enabled - attempting reconnection")
                if reconnect_task is None or reconnect_task.done():
                    reconnect_task = asyncio.create_task(attempt_reconnect("watchdog timeout"))
                else:
                    logger.warning("Reconnect already in progress")
            else:
                logger.warning("Initiating graceful shutdown for systemd restart")
                app_state.shutdown_event.set()

        watchdog.on_timeout = handle_watchdog_timeout

        # Start publisher task
        publisher_task = asyncio.create_task(publisher.run())
        logger.info("Event publisher started")

        # Start command subscriber for bidirectional bridge
        if config.commands.enabled:
            logger.info("Starting command subscriber")
            sender = CytubeEventSender(connector, logger, audit_logger)
            cmd_subscriber = CommandSubscriber(
                sender,
                nats_client,
                logger,
                config.cytube.domain,
                config.cytube.channel,
                audit_logger,
            )
            await cmd_subscriber.start()
            logger.info("Command subscriber started")
        else:
            logger.info("Command subscriptions disabled in configuration")

        # Start state query handler for NATS queries (if state manager exists)
        if state_manager:
            try:
                logger.info("Starting state query handler")
                state_query_handler = StateQueryHandler(
                    state_manager=state_manager,
                    nats_client=nats_client,
                    logger=logger,
                    domain=config.cytube.domain,
                    channel=config.cytube.channel,
                    app_state=app_state,
                )
                await state_query_handler.start()
            except Exception as e:
                logger.error(f"Failed to start state query handler: {e}", exc_info=True)
                logger.warning("Continuing without state query endpoint")
                state_query_handler = None
        else:
            state_query_handler = None

        # Start user level query handler
        user_level_subscription = None
        try:
            import json

            async def handle_user_level_query(msg):
                """Handle NATS queries for logged-in user's level/rank."""
                try:
                    response = {
                        "success": True,
                        "rank": connector.user_rank,
                        "username": config.cytube.user or "guest",
                    }

                    if msg.reply:
                        response_bytes = json.dumps(response).encode("utf-8")
                        await nats_client.publish(msg.reply, response_bytes)
                        logger.debug(f"Sent user level response: rank={connector.user_rank}")

                except Exception as e:
                    logger.error(f"Error handling user level query: {e}", exc_info=True)
                    if msg.reply:
                        try:
                            error_response = {"success": False, "error": str(e)}
                            response_bytes = json.dumps(error_response).encode("utf-8")
                            await nats_client.publish(msg.reply, response_bytes)
                        except Exception as reply_error:
                            logger.error(f"Failed to send error response: {reply_error}")

            user_level_subject = f"kryten.user_level.{config.cytube.domain}.{config.cytube.channel}"
            user_level_subscription = await nats_client.subscribe_request_reply(
                subject=user_level_subject, callback=handle_user_level_query
            )
            logger.info(f"User level query handler listening on: {user_level_subject}")

        except Exception as e:
            logger.error(f"Failed to start user level query handler: {e}", exc_info=True)
            logger.warning("Continuing without user level query endpoint")

        # Start health monitor if enabled
        if config.health.enabled:
            logger.info(f"Starting health monitor on {config.health.host}:{config.health.port}")
            health_monitor = HealthMonitor(
                connector=connector,
                nats_client=nats_client,
                publisher=publisher,
                logger=logger,
                command_subscriber=cmd_subscriber,  # Pass command subscriber for metrics
                host=config.health.host,
                port=config.health.port,
            )
            health_monitor.start()
            logger.info(
                f"Health endpoint available at http://{config.health.host}:{config.health.port}/health"
            )
        else:
            logger.info("Health monitoring disabled in configuration")

        # Start robot command handler for system.ping etc
        from .robot_command_handler import RobotCommandHandler

        robot_cmd_handler = RobotCommandHandler(
            nats_client=nats_client,
            logger=logger,
            version=__version__,
            config=config,
            connector=connector,
            publisher=publisher,
            cmd_subscriber=cmd_subscriber,
            sender=sender,
        )
        await robot_cmd_handler.start()
        logger.info("Robot command handler started (kryten.robot.command)")

        # REQ-009: Log ready message
        logger.info("=" * 60)
        logger.info("Kryten is ready and processing events")
        if config.commands.enabled:
            logger.info("Bidirectional bridge active - can send and receive")
        else:
            logger.info("Receive-only mode - commands disabled")
        if config.health.enabled:
            logger.info(f"Health checks: http://{config.health.host}:{config.health.port}/health")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Publish startup complete event
        await lifecycle.publish_startup(
            domain=config.cytube.domain,
            channel=config.cytube.channel,
            commands_enabled=config.commands.enabled,
            health_enabled=config.health.enabled,
        )

        # Wait for shutdown signal
        await app_state.shutdown_event.wait()

        # REQ-007: Shutdown sequence (reverse order)
        logger.info("Beginning graceful shutdown")
        audit_logger.log_connection_event("shutdown", "kryten-robot", details={"type": "graceful"})

        # 0. Cancel any in-progress reconnect task
        if reconnect_task and not reconnect_task.done():
            logger.info("Cancelling in-progress reconnect task")
            reconnect_task.cancel()
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass
            logger.info("Reconnect task cancelled")

        # 0b. Stop watchdog first to prevent triggering during shutdown
        if watchdog:
            logger.info("Stopping connection watchdog")
            try:
                await watchdog.stop()
                logger.info("Connection watchdog stopped")
            except Exception as e:
                logger.error(f"Error stopping watchdog: {e}")

        # 1. Stop health monitor
        if health_monitor:
            logger.info("Stopping health monitor")
            try:
                health_monitor.stop()
                logger.info("Health monitor stopped")
            except Exception as e:
                logger.error(f"Error stopping health monitor: {e}")

        # 1b. Stop robot command handler
        if robot_cmd_handler:
            logger.info("Stopping robot command handler")
            try:
                await robot_cmd_handler.stop()
                logger.info("Robot command handler stopped")
            except Exception as e:
                logger.error(f"Error stopping robot command handler: {e}")

        # 2. Stop service registry
        if service_registry:
            logger.info("Stopping service registry")
            try:
                await service_registry.stop()
                logger.info("Service registry stopped")
            except Exception as e:
                logger.error(f"Error stopping service registry: {e}")

        # 3. Stop state query handler
        if state_query_handler:
            logger.info("Stopping state query handler")
            try:
                await state_query_handler.stop()
                logger.info("State query handler stopped")
            except Exception as e:
                logger.error(f"Error stopping state query handler: {e}")

        # 3b. Unsubscribe user level query handler
        if user_level_subscription:
            try:
                logger.info("Stopping user level query handler")
                if nats_client and nats_client.is_connected:
                    await nats_client.unsubscribe(user_level_subscription)
                logger.info("User level query handler stopped")
            except Exception as e:
                logger.error(f"Error stopping user level query handler: {e}")

        # 4. Stop state manager
        if state_manager:
            logger.info("Stopping state manager")
            try:
                await state_manager.stop()
                logger.info("State manager stopped")
            except Exception as e:
                logger.error(f"Error stopping state manager: {e}")

        # 5. Stop command subscriber
        if cmd_subscriber:
            logger.info("Stopping command subscriber")
            try:
                await cmd_subscriber.stop()
                logger.info("Command subscriber stopped")
            except Exception as e:
                logger.error(f"Error stopping command subscriber: {e}")

        # 6. Stop publisher (completes current event processing)
        if publisher:
            logger.info("Stopping event publisher")
            try:
                await publisher.stop()

                # Wait for publisher task to complete
                try:
                    await asyncio.wait_for(publisher_task, timeout=5.0)
                    logger.info("Event publisher stopped")
                except TimeoutError:
                    # Python 3.10 compat: asyncio.TimeoutError is separate from TimeoutError
                    logger.warning("Event publisher did not stop within timeout, cancelling")
                    publisher_task.cancel()
                    try:
                        await publisher_task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.error(f"Error stopping publisher: {e}")

        # 6. Disconnect from CyTube
        if connector:
            logger.info("Disconnecting from CyTube")
            try:
                await connector.disconnect()
                if lifecycle and nats_client and nats_client.is_connected:
                    await lifecycle.publish_disconnected("CyTube", reason="Graceful shutdown")
                logger.info("Disconnected from CyTube")
            except Exception as e:
                logger.error(f"Error disconnecting from CyTube: {e}")

        # 7. Publish shutdown event and stop lifecycle publisher
        if lifecycle:
            try:
                if nats_client and nats_client.is_connected:
                    await lifecycle.publish_shutdown(reason="Normal shutdown")
                await lifecycle.stop()
                logger.info("Lifecycle event publisher stopped")
            except Exception as e:
                logger.error(f"Error stopping lifecycle publisher: {e}")

        # 8. Disconnect from NATS
        if nats_client:
            logger.info("Disconnecting from NATS")
            try:
                await nats_client.disconnect()
                logger.info("Disconnected from NATS")
            except Exception as e:
                logger.error(f"Error disconnecting from NATS: {e}")

        logger.info("Graceful shutdown complete")

        # REQ-008: Exit with code 0 on clean shutdown
        return 0

    except FileNotFoundError:
        # AC-006: Config file missing
        fnf_logger = logger
        if fnf_logger:
            fnf_logger.error(f"Configuration file not found: {config_path}")
        else:
            print(f"ERROR: Configuration file not found: {config_path}", file=sys.stderr)
        return 1

    except json.JSONDecodeError as e:
        # Configuration JSON parse error
        json_logger = logger
        if json_logger:
            json_logger.error(f"Invalid JSON in configuration file: {e}")
        else:
            print(f"ERROR: Invalid JSON in configuration file: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        # AC-007: Unhandled exception
        exc_logger = logger
        if exc_logger:
            exc_logger.critical(f"Unhandled exception: {e}", exc_info=True)
        else:
            print(f"CRITICAL: Unhandled exception: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()

        # Cleanup any initialized components
        cleanup_logger = logger
        try:
            if watchdog:
                try:
                    await watchdog.stop()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error stopping watchdog during cleanup: {e}")
            if health_monitor:
                try:
                    health_monitor.stop()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error stopping health monitor during cleanup: {e}")
            if state_manager:
                try:
                    await state_manager.stop()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error stopping state manager during cleanup: {e}")
            if cmd_subscriber:
                try:
                    await cmd_subscriber.stop()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(
                            f"Error stopping command subscriber during cleanup: {e}"
                        )
            if publisher:
                try:
                    await publisher.stop()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error stopping publisher during cleanup: {e}")
            if connector:
                try:
                    await connector.disconnect()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error disconnecting connector during cleanup: {e}")
            if nats_client:
                try:
                    await nats_client.disconnect()
                except Exception as e:
                    if cleanup_logger:
                        cleanup_logger.error(f"Error disconnecting NATS during cleanup: {e}")
        except Exception as cleanup_error:
            if cleanup_logger:
                cleanup_logger.error(f"Error during cleanup: {cleanup_error}", exc_info=True)

        # REQ-008: Exit with code 1 on errors
        return 1


def cli() -> None:
    """Command-line interface entry point.

    Parses arguments and runs main orchestration function.
    Handles --version and --help flags.
    """
    # PAT-001: Use argparse for CLI
    parser = argparse.ArgumentParser(
        prog="python -m kryten",
        description="Kryten CyTube Connector - Bridges CyTube chat to NATS event bus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m kryten                             # Use default config locations
  python -m kryten --config /path/to/config.json
  python -m kryten --version
  python -m kryten --help

Default config locations (searched in order):
  - /etc/kryten/kryten-robot/config.json
  - ./config.json

Signals:
  SIGINT (Ctrl+C): Graceful shutdown
  SIGTERM: Graceful shutdown (for container orchestration)

Exit Codes:
  0: Clean shutdown
  1: Error (configuration, connection, or runtime)
        """,
    )

    # GUD-001: Version flag
    parser.add_argument("--version", action="version", version=f"Kryten v{__version__}")

    # REQ-002: Configuration file argument (optional with default)
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to JSON configuration file (default: /etc/kryten/kryten-robot/config.json or ./config.json)",
    )

    args = parser.parse_args()

    # GUD-002: Determine configuration file path
    if args.config:
        config_path = Path(args.config)
    else:
        # Try default locations in order
        default_paths = [Path("/etc/kryten/kryten-robot/config.json"), Path("config.json")]

        config_path = None
        for path in default_paths:
            if path.exists() and path.is_file():
                config_path = path
                break

        if not config_path:
            print("ERROR: No configuration file found.", file=sys.stderr)
            print("  Searched:", file=sys.stderr)
            for path in default_paths:
                print(f"    - {path}", file=sys.stderr)
            print("  Use --config to specify a custom path.", file=sys.stderr)
            sys.exit(1)

    # Validate configuration file exists
    assert config_path is not None
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    if not config_path.is_file():
        print(f"ERROR: Configuration path is not a file: {config_path}", file=sys.stderr)
        sys.exit(1)

    # Print startup banner
    print_startup_banner(str(config_path))

    # REQ-001: Run async main function
    try:
        exit_code = asyncio.run(main(str(config_path)))
    except KeyboardInterrupt:
        # Handle Ctrl+C during startup (before signal handlers registered)
        print("\nInterrupted during startup")
        exit_code = 1

    sys.exit(exit_code)


# PAT-001: Module execution guard
if __name__ == "__main__":
    cli()

"""State Query Handler - Respond to NATS queries for channel state.

This module provides a NATS request/reply endpoint that returns the current
channel state (emotes, playlist, userlist) as JSON.

Follows the unified command pattern: kryten.robot.command
Commands are dispatched based on the 'command' field in the request.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .application_state import ApplicationState
from .nats_client import NatsClient
from .state_manager import StateManager


class StateQueryHandler:
    """Handle NATS queries for channel state via unified command pattern.

    Subscribes to kryten.robot.command and responds to state queries.

    Supported commands:
        - state.emotes: Get emote list
        - state.playlist: Get playlist
        - state.userlist: Get user list
        - state.all: Get all state (emotes, playlist, userlist)
        - state.user: Get specific user info
        - state.profiles: Get all user profiles
        - system.health: Get service health status
        - system.channels: Get list of connected channels
        - system.version: Get Kryten-Robot version
        - system.stats: Get comprehensive runtime statistics
        - system.config: Get current configuration (passwords redacted)
        - system.ping: Simple alive check

    Attributes:
        state_manager: StateManager instance to query.
        nats_client: NATS client for subscriptions.
        logger: Logger instance.
        app_state: ApplicationState for runtime information.

    Examples:
        >>> handler = StateQueryHandler(state_manager, nats_client, logger, "cytu.be", "mychannel", app_state)
        >>> await handler.start()
        >>> # Send command to kryten.robot.command with {"service": "robot", "command": "state.emotes"}
        >>> await handler.stop()
    """

    def __init__(
        self,
        state_manager: StateManager,
        nats_client: NatsClient,
        logger: logging.Logger,
        domain: str,
        channel: str,
        app_state: ApplicationState | None = None,
    ):
        """Initialize state query handler.

        Args:
            state_manager: StateManager instance.
            nats_client: NATS client for subscriptions.
            logger: Logger for structured output.
            domain: CyTube domain name.
            channel: CyTube channel name.
            app_state: ApplicationState for system management features.
        """
        self._state_manager = state_manager
        self._nats = nats_client
        self._logger = logger
        self._domain = domain
        self._channel = channel
        self._app_state = app_state
        self._running = False
        self._subscription = None

        # Metrics
        self._queries_processed = 0
        self._queries_failed = 0

    @property
    def stats(self) -> dict:
        """Get query processing statistics."""
        return {
            "queries_processed": self._queries_processed,
            "queries_failed": self._queries_failed,
        }

    @property
    def is_running(self) -> bool:
        """Check if handler is running."""
        return self._running

    async def start(self) -> None:
        """Start listening for commands on unified subject."""
        if self._running:
            self._logger.warning("State query handler already running")
            return

        self._running = True

        # Subscribe to unified command subject using request-reply pattern
        subject = "kryten.robot.command"

        try:
            self._subscription = await self._nats.subscribe_request_reply(
                subject,
                callback=self._handle_command_msg
            )
            self._logger.info(f"State query handler listening on: {subject}")

        except Exception as e:
            self._logger.error(f"Failed to subscribe to command subject: {e}", exc_info=True)
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop listening for queries."""
        if not self._running:
            return

        self._logger.info("Stopping state query handler")

        if self._subscription:
            try:
                await self._subscription.unsubscribe()
            except Exception as e:
                self._logger.warning(f"Error unsubscribing: {e}")

        self._subscription = None
        self._running = False
        self._logger.info("State query handler stopped")

    async def _handle_command_msg(self, msg) -> None:
        """Handle incoming command message (actual implementation).

        Args:
            msg: NATS message object with data and reply subject.
        """
        try:
            # Parse request
            request = {}
            if msg.data:
                try:
                    request = json.loads(msg.data.decode('utf-8'))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON: {e}") from e

            command = request.get('command')
            if not command:
                raise ValueError("Missing 'command' field")

            # Check service field for routing (other services can ignore)
            service = request.get('service')
            if service and service != 'robot':
                # Not for us, ignore silently
                return

            # Dispatch to handler
            handler_map = {
                "state.emotes": self._handle_state_emotes,
                "state.playlist": self._handle_state_playlist,
                "state.userlist": self._handle_state_userlist,
                "state.all": self._handle_state_all,
                "state.user": self._handle_state_user,
                "state.profiles": self._handle_state_profiles,
                "system.health": self._handle_system_health,
                "system.channels": self._handle_system_channels,
                "system.version": self._handle_system_version,
                "system.stats": self._handle_system_stats,
                "system.services": self._handle_system_services,
                "system.config": self._handle_system_config,
                "system.ping": self._handle_system_ping,
                "system.shutdown": self._handle_system_shutdown,
                "system.reload": self._handle_system_reload,
            }

            handler = handler_map.get(command)
            if not handler:
                self._logger.debug(f"Ignoring unknown command: {command}")
                return

            # Execute handler
            result = await handler(request)

            # Build success response
            response = {
                "service": "robot",
                "command": command,
                "success": True,
                "data": result
            }

            # Send response
            if msg.reply:
                response_bytes = json.dumps(response).encode('utf-8')
                await self._nats.publish(msg.reply, response_bytes)
                self._logger.debug(f"Sent response for command '{command}'")

            self._queries_processed += 1

        except Exception as e:
            self._logger.error(f"Error handling command: {e}", exc_info=True)
            self._queries_failed += 1

            # Send error response if reply subject provided
            if msg.reply:
                try:
                    command = request.get('command', 'unknown')
                    error_response = {
                        "service": "robot",
                        "command": command,
                        "success": False,
                        "error": str(e)
                    }
                    response_bytes = json.dumps(error_response).encode('utf-8')
                    await self._nats.publish(msg.reply, response_bytes)
                except Exception as reply_error:
                    self._logger.error(f"Failed to send error response: {reply_error}")

    async def _handle_state_emotes(self, request: dict) -> dict:
        """Get emote list."""
        return {"emotes": self._state_manager.get_emotes()}

    async def _handle_state_playlist(self, request: dict) -> dict:
        """Get playlist."""
        return {"playlist": self._state_manager.get_playlist()}

    async def _handle_state_userlist(self, request: dict) -> dict:
        """Get user list."""
        return {"userlist": self._state_manager.get_userlist()}

    async def _handle_state_all(self, request: dict) -> dict:
        """Get all state (emotes, playlist, userlist)."""
        return {
            "emotes": self._state_manager.get_emotes(),
            "playlist": self._state_manager.get_playlist(),
            "userlist": self._state_manager.get_userlist(),
            "stats": self._state_manager.stats
        }

    async def _handle_state_user(self, request: dict) -> dict:
        """Get specific user info."""
        username = request.get('username')
        if not username:
            raise ValueError("username required")

        return {
            "user": self._state_manager.get_user(username),
            "profile": self._state_manager.get_user_profile(username)
        }

    async def _handle_state_profiles(self, request: dict) -> dict:
        """Get all user profiles."""
        return {"profiles": self._state_manager.get_all_profiles()}

    async def _handle_system_health(self, request: dict) -> dict:
        """Get service health status."""
        return {
            "service": "robot",
            "status": "healthy" if self._running else "unhealthy",
            "domain": self._domain,
            "channel": self._channel,
            "nats_connected": self._nats.is_connected,
            "queries_processed": self._queries_processed,
            "queries_failed": self._queries_failed,
        }

    async def _handle_system_channels(self, request: dict) -> dict:
        """Get list of connected channels.

        Returns information about all channels this robot instance is connected to.
        Currently supports single-channel mode, but structured for future multi-channel support.

        Returns:
            Dictionary with 'channels' key containing list of channel info dicts.
            Each channel dict contains: domain, channel, connected status.
        """
        return {
            "channels": [
                {
                    "domain": self._domain,
                    "channel": self._channel,
                    "connected": self._nats.is_connected
                }
            ]
        }

    async def _handle_system_version(self, request: dict) -> dict:
        """Get Kryten-Robot version information.

        Returns version string for client applications to check compatibility.
        Clients can use this to enforce minimum server version requirements.

        Returns:
            Dictionary with 'version' key containing semantic version string.
        """
        from . import __version__

        return {
            "version": __version__
        }

    async def _handle_system_stats(self, request: dict) -> dict:
        """Get comprehensive runtime statistics.

        Returns detailed statistics including event rates, command execution,
        connection status, memory usage, and state information.

        Returns:
            Dictionary containing nested statistics:
                - uptime_seconds: Total uptime
                - events: Published events and rates
                - commands: Command execution stats
                - queries: Query handler stats
                - connections: CyTube and NATS connection info
                - state: Channel state (users, playlist, emotes)
                - memory: Process memory usage
        """
        if not self._app_state:
            raise ValueError("ApplicationState not available for stats")

        # Calculate uptime
        uptime = self._app_state.get_uptime()

        # Get event publisher stats
        events_stats = {}
        if self._app_state.event_publisher:
            pub_stats = self._app_state.event_publisher.stats
            last_time = pub_stats.get('last_event_time')
            last_type = pub_stats.get('last_event_type')
            events_stats = {
                "total_published": pub_stats.get('events_published', 0),
                "failed": pub_stats.get('publish_errors', 0),
                "rate_1min": pub_stats.get('rate_1min', 0.0),
                "rate_5min": pub_stats.get('rate_5min', 0.0),
                "last_event_time": datetime.fromtimestamp(last_time, tz=timezone.utc).isoformat() if last_time else None,
                "last_event_type": last_type
            }

        # Get command subscriber stats
        commands_stats = {}
        if self._app_state.command_subscriber:
            cmd_stats = self._app_state.command_subscriber.stats
            last_time = cmd_stats.get('last_command_time')
            last_type = cmd_stats.get('last_command_type')
            commands_stats = {
                "total_received": cmd_stats.get('commands_processed', 0),
                "succeeded": cmd_stats.get('commands_succeeded', 0),
                "failed": cmd_stats.get('commands_failed', 0),
                "rate_1min": cmd_stats.get('rate_1min', 0.0),
                "rate_5min": cmd_stats.get('rate_5min', 0.0),
                "last_command_time": datetime.fromtimestamp(last_time, tz=timezone.utc).isoformat() if last_time else None,
                "last_command_type": last_type
            }

        # Get query handler stats (self)
        queries_stats = {
            "processed": self._queries_processed,
            "failed": self._queries_failed,
            "rate_1min": 0.0  # Could add StatsTracker here too if needed
        }

        # Get connection stats
        connections_stats = {}

        # CyTube connection
        cytube_stats = {"connected": False, "connected_since": None, "last_event_time": None, "reconnect_count": 0}
        if self._app_state.connector:
            connector = self._app_state.connector
            connected_since = connector.connected_since
            last_event = connector.last_event_time
            cytube_stats = {
                "connected": connector.is_connected,
                "connected_since": datetime.fromtimestamp(connected_since, tz=timezone.utc).isoformat() if connected_since else None,
                "last_event_time": datetime.fromtimestamp(last_event, tz=timezone.utc).isoformat() if last_event else None,
                "reconnect_count": connector.reconnect_count
            }

        # NATS connection
        nats_stats = {"connected": False, "connected_since": None, "connected_url": None, "reconnect_count": 0}
        if self._app_state.nats_client:
            nats = self._app_state.nats_client
            connected_since = nats.connected_since
            nats_stats = {
                "connected": nats.is_connected,
                "connected_since": datetime.fromtimestamp(connected_since, tz=timezone.utc).isoformat() if connected_since else None,
                "connected_url": nats.connected_url,
                "reconnect_count": nats.reconnect_count
            }

        connections_stats = {
            "cytube": cytube_stats,
            "nats": nats_stats
        }

        # Get state counts
        state_stats = {}
        if self._app_state.state_manager:
            sm = self._app_state.state_manager
            state_stats = {
                "users": sm.users_count(),
                "playlist": sm.playlist_count(),
                "emotes": sm.emotes_count()
            }

        # Get memory stats (if psutil available)
        memory_stats = {}
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                mem_info = process.memory_info()
                memory_stats = {
                    "rss_mb": mem_info.rss / (1024 * 1024),
                    "vms_mb": mem_info.vms / (1024 * 1024)
                }
            except Exception as e:
                self._logger.warning(f"Failed to get memory stats: {e}")
                memory_stats = {"error": str(e)}
        else:
            memory_stats = {"error": "psutil not available"}

        return {
            "uptime_seconds": uptime,
            "events": events_stats,
            "commands": commands_stats,
            "queries": queries_stats,
            "connections": connections_stats,
            "state": state_stats,
            "memory": memory_stats
        }

    async def _handle_system_services(self, request: dict) -> dict:
        """Get list of registered microservices.

        Returns information about all microservices that have registered with
        kryten-robot, including their version, hostname, health/metrics endpoints,
        and heartbeat status.

        Returns:
            Dictionary containing:
                - services: List of service dictionaries with:
                    - name: Service name
                    - version: Service version
                    - hostname: Host running the service
                    - first_seen: When service was first discovered
                    - last_heartbeat: Most recent heartbeat timestamp
                    - seconds_since_heartbeat: Seconds since last heartbeat
                    - is_stale: True if no heartbeat in 90+ seconds
                    - health_url: Full URL for health endpoint (if configured)
                    - metrics_url: Full URL for metrics endpoint (if configured)
                - count: Total number of registered services
                - active_count: Number of non-stale services
        """
        if not self._app_state:
            raise ValueError("ApplicationState not available for services")

        if not self._app_state.service_registry:
            return {"services": [], "count": 0, "active_count": 0}

        registry = self._app_state.service_registry
        services = registry.get_all_services()
        
        service_list = []
        active_count = 0
        
        for service in services:
            service_dict = service.to_dict()
            service_list.append(service_dict)
            if not service.is_stale:
                active_count += 1
        
        # Sort by name for consistent ordering
        service_list.sort(key=lambda s: s["name"])
        
        return {
            "services": service_list,
            "count": len(service_list),
            "active_count": active_count
        }

    async def _handle_system_config(self, request: dict) -> dict:
        """Get current effective configuration.

        Returns the running configuration with sensitive fields redacted.
        Useful for debugging and verifying configuration changes.

        Returns:
            Dictionary containing configuration sections with passwords redacted.
        """
        if not self._app_state:
            raise ValueError("ApplicationState not available for config")

        config = self._app_state.config

        # Build sanitized config response
        return {
            "cytube": {
                "domain": config.cytube.domain,
                "channel": config.cytube.channel,
                "user": config.cytube.user,
                "password": "***REDACTED***"
            },
            "nats": {
                "servers": config.nats.servers,
                "user": config.nats.user,
                "password": "***REDACTED***" if config.nats.password else None,
                "max_reconnect_attempts": config.nats.max_reconnect_attempts,
                "reconnect_time_wait": config.nats.reconnect_time_wait
            },
            "health": {
                "enabled": config.health.enabled,
                "host": config.health.host,
                "port": config.health.port
            },
            "commands": {
                "enabled": config.commands.enabled
            },
            "logging": {
                "base_path": config.logging.base_path,
                "admin_operations": config.logging.admin_operations,
                "playlist_operations": config.logging.playlist_operations,
                "chat_messages": config.logging.chat_messages,
                "command_audit": config.logging.command_audit
            },
            "log_level": config.log_level
        }

    async def _handle_system_ping(self, request: dict) -> dict:
        """Simple alive check.

        Ultra-lightweight health check that proves NATS connectivity and
        responsiveness. Faster than full health check.

        Returns:
            Dictionary with pong=True, timestamp, uptime, service, and version.
        """
        from . import __version__

        uptime = self._app_state.get_uptime() if self._app_state else 0

        return {
            "pong": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime,
            "service": "robot",
            "version": __version__
        }

    async def _handle_system_shutdown(self, request: dict) -> dict:
        """Initiate graceful shutdown.

        Schedules a graceful shutdown after optional delay. The shutdown is
        performed by setting the application's shutdown_event, which triggers
        the normal cleanup sequence in __main__.py.

        Args:
            request: Request dict with optional 'delay_seconds' (0-300) and 'reason'

        Returns:
            Dictionary containing:
                - success: Always True (if validation passes)
                - message: Acknowledgment message
                - delay_seconds: Actual delay applied
                - shutdown_time: ISO8601 timestamp when shutdown will occur

        Raises:
            ValueError: If delay is invalid or ApplicationState not available
        """
        if not self._app_state:
            raise ValueError("ApplicationState not available for shutdown")

        # Parse and validate delay
        delay_seconds = request.get('delay_seconds', 0)

        # Convert to int/float if needed
        try:
            delay_seconds = float(delay_seconds)
        except (TypeError, ValueError) as e:
            raise ValueError("delay_seconds must be a number") from e

        # Validate range
        if delay_seconds < 0 or delay_seconds > 300:
            raise ValueError("delay_seconds must be between 0 and 300")

        delay_seconds = int(delay_seconds)
        reason = request.get('reason', 'Remote shutdown via system.shutdown')

        # Calculate shutdown time
        shutdown_time = datetime.now(timezone.utc).timestamp() + delay_seconds
        shutdown_time_iso = datetime.fromtimestamp(shutdown_time, tz=timezone.utc).isoformat()

        # Log the shutdown request
        self._logger.warning(
            f"Shutdown requested: delay={delay_seconds}s, reason={reason}, "
            f"scheduled_time={shutdown_time_iso}"
        )

        # Schedule shutdown
        async def trigger_shutdown():
            """Wait for delay then trigger shutdown event."""
            if delay_seconds > 0:
                self._logger.info(f"Waiting {delay_seconds}s before shutdown...")
                await asyncio.sleep(delay_seconds)

            self._logger.warning(f"Triggering shutdown: {reason}")
            self._app_state.shutdown_event.set()

        # Create task to handle shutdown (non-blocking)
        asyncio.create_task(trigger_shutdown())

        return {
            "success": True,
            "message": "Shutdown initiated",
            "delay_seconds": delay_seconds,
            "shutdown_time": shutdown_time_iso,
            "reason": reason
        }

    async def _handle_system_reload(self, request: dict) -> dict:
        """Reload configuration.

        Attempts to reload configuration from file. Only "safe" changes are
        applied - settings that can be updated without breaking connections.

        Safe changes:
            - log_level: Immediately updates logging level
            - nats.user/password: Will apply on next reconnect
            - health settings: Would require health server restart (not implemented)

        Unsafe changes (rejected):
            - cytube.domain, cytube.channel, cytube.user: Would break connection

        Args:
            request: Request dict with optional 'config_path'

        Returns:
            Dictionary containing:
                - success: Whether reload succeeded
                - message: Human-readable result message
                - changes: Dict of what changed (key: "old -> new")
                - errors: List of validation errors if failed

        Raises:
            ValueError: If ApplicationState not available
        """
        if not self._app_state:
            raise ValueError("ApplicationState not available for reload")

        from .config import load_config

        # Determine config path
        config_path = request.get('config_path', self._app_state.config_path)

        try:
            # Load new configuration
            self._logger.info(f"Loading configuration from {config_path}")
            new_config = load_config(config_path)

            # Track changes
            changes = {}
            errors = []
            old_config = self._app_state.config

            # Check for unsafe changes
            if new_config.cytube.domain != old_config.cytube.domain:
                errors.append("Cannot change cytube.domain without restart")

            if new_config.cytube.channel != old_config.cytube.channel:
                errors.append("Cannot change cytube.channel without restart")

            if new_config.cytube.user != old_config.cytube.user:
                errors.append("Cannot change cytube.user without restart")

            # If there are errors, reject the reload
            if errors:
                self._logger.warning(f"Configuration reload rejected: {errors}")
                return {
                    "success": False,
                    "message": "Configuration validation failed",
                    "changes": {},
                    "errors": errors
                }

            # Apply safe changes

            # 1. Log level change
            if new_config.log_level != old_config.log_level:
                old_level = old_config.log_level
                new_level = new_config.log_level
                changes["log_level"] = f"{old_level} -> {new_level}"

                # Update logging level
                numeric_level = getattr(logging, new_level.upper(), None)
                if numeric_level:
                    logging.getLogger().setLevel(numeric_level)
                    self._logger.info(f"Updated log level to {new_level}")

            # 2. NATS credentials (will apply on next reconnect)
            if (new_config.nats.user != old_config.nats.user or
                new_config.nats.password != old_config.nats.password):
                changes["nats.credentials"] = "updated (will apply on next reconnect)"

            # 3. NATS servers
            if new_config.nats.servers != old_config.nats.servers:
                changes["nats.servers"] = "updated (will apply on next reconnect)"

            # Update stored config
            self._app_state.config = new_config

            self._logger.info(f"Configuration reloaded successfully: {changes}")

            return {
                "success": True,
                "message": "Configuration reloaded successfully",
                "changes": changes,
                "errors": []
            }

        except FileNotFoundError:
            error_msg = f"Configuration file not found: {config_path}"
            self._logger.error(error_msg)
            return {
                "success": False,
                "message": "Configuration reload failed",
                "changes": {},
                "errors": [error_msg]
            }

        except Exception as e:
            error_msg = f"Failed to load configuration: {str(e)}"
            self._logger.error(f"Configuration reload error: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Configuration reload failed",
                "changes": {},
                "errors": [error_msg]
            }


__all__ = ["StateQueryHandler"]

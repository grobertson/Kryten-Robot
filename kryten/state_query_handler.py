"""State Query Handler - Respond to NATS queries for channel state.

This module provides a NATS request/reply endpoint that returns the current
channel state (emotes, playlist, userlist) as JSON.

Follows the unified command pattern: kryten.robot.command
Commands are dispatched based on the 'command' field in the request.
"""

import json
import logging

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
    
    Attributes:
        state_manager: StateManager instance to query.
        nats_client: NATS client for subscriptions.
        logger: Logger instance.
    
    Examples:
        >>> handler = StateQueryHandler(state_manager, nats_client, logger, "cytu.be", "mychannel")
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
    ):
        """Initialize state query handler.
        
        Args:
            state_manager: StateManager instance.
            nats_client: NATS client for subscriptions.
            logger: Logger for structured output.
            domain: CyTube domain name.
            channel: CyTube channel name.
        """
        self._state_manager = state_manager
        self._nats = nats_client
        self._logger = logger
        self._domain = domain
        self._channel = channel
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
                    raise ValueError(f"Invalid JSON: {e}")
            
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
            }
            
            handler = handler_map.get(command)
            if not handler:
                raise ValueError(f"Unknown command: {command}")
            
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


__all__ = ["StateQueryHandler"]

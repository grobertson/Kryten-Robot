"""State Query Handler - Respond to NATS queries for channel state.

This module provides a NATS request/reply endpoint that returns the current
channel state (emotes, playlist, userlist) as JSON.
"""

import json
import logging

from .nats_client import NatsClient
from .state_manager import StateManager


class StateQueryHandler:
    """Handle NATS queries for channel state.
    
    Subscribes to cytube.state.{domain}.{channel} and responds with
    current emotes, playlist, and userlist.
    
    Attributes:
        state_manager: StateManager instance to query.
        nats_client: NATS client for subscriptions.
        logger: Logger instance.
    
    Examples:
        >>> handler = StateQueryHandler(state_manager, nats_client, logger, "cytu.be", "mychannel")
        >>> await handler.start()
        >>> # Queries to cytube.state.cytu.be.mychannel will return state
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
        """Start listening for state queries."""
        if self._running:
            self._logger.warning("State query handler already running")
            return
        
        self._running = True
        
        # Subscribe to state query subject
        subject = f"cytube.state.{self._domain}.{self._channel}"
        
        try:
            self._subscription = await self._nats.subscribe(
                subject,
                callback=self._handle_query
            )
            self._logger.info(f"State query handler listening on: {subject}")
        
        except Exception as e:
            self._logger.error(f"Failed to subscribe to state queries: {e}", exc_info=True)
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
    
    async def _handle_query(self, msg) -> None:
        """Handle incoming state query.
        
        Args:
            msg: NATS message with optional request params.
        """
        try:
            # Parse request (if any parameters provided)
            request = {}
            if msg.data:
                try:
                    request = json.loads(msg.data.decode('utf-8'))
                except json.JSONDecodeError:
                    pass
            
            # Get requested state
            requested_keys = request.get('keys', ['emotes', 'playlist', 'userlist'])
            username = request.get('username')  # For specific user/profile queries
            
            response_data = {}
            if 'emotes' in requested_keys or not requested_keys:
                response_data['emotes'] = self._state_manager.get_emotes()
            if 'playlist' in requested_keys or not requested_keys:
                response_data['playlist'] = self._state_manager.get_playlist()
            if 'userlist' in requested_keys or not requested_keys:
                response_data['userlist'] = self._state_manager.get_userlist()
            
            # Handle specific user query
            if username:
                response_data['user'] = self._state_manager.get_user(username)
                response_data['profile'] = self._state_manager.get_user_profile(username)
            
            # Handle profiles query
            if 'profiles' in requested_keys:
                response_data['profiles'] = self._state_manager.get_all_profiles()
            
            # Build response
            response = {
                "success": True,
                "data": response_data,
                "stats": self._state_manager.stats
            }
            
            # Send response
            if msg.reply:
                response_bytes = json.dumps(response).encode('utf-8')
                await self._nats.publish(msg.reply, response_bytes)
                self._logger.debug(f"Sent state response to {msg.reply}")
            
            self._queries_processed += 1
        
        except Exception as e:
            self._logger.error(f"Error handling state query: {e}", exc_info=True)
            self._queries_failed += 1
            
            # Send error response if reply subject provided
            if msg.reply:
                try:
                    error_response = {
                        "success": False,
                        "error": str(e)
                    }
                    response_bytes = json.dumps(error_response).encode('utf-8')
                    await self._nats.publish(msg.reply, response_bytes)
                except Exception as reply_error:
                    self._logger.error(f"Failed to send error response: {reply_error}")


__all__ = ["StateQueryHandler"]

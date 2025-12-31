"""State Updater - Subscribe to CyTube events and update StateManager.

This module bridges the EventPublisher and StateManager by subscribing to
relevant CyTube events and updating the state KV stores accordingly.
"""

import logging
from typing import Any

from .nats_client import NatsClient
from .state_manager import StateManager
from .subject_builder import build_subject


class StateUpdater:
    """Subscribe to CyTube events and update state KV stores.

    Listens for events like playlist, userlist, emotes, queue, delete, etc.
    and calls appropriate StateManager methods to keep KV stores synchronized.

    Attributes:
        nats_client: NATS client for subscriptions.
        state_manager: StateManager to update.
        channel: CyTube channel name.
        domain: CyTube domain.
        logger: Logger instance.

    Examples:
        >>> updater = StateUpdater(nats_client, state_manager, "mychannel", "cytu.be", logger)
        >>> await updater.start()
        >>> # Receives events and updates state automatically
        >>> await updater.stop()
    """

    def __init__(
        self,
        nats_client: NatsClient,
        state_manager: StateManager,
        channel: str,
        domain: str,
        logger: logging.Logger,
    ):
        """Initialize state updater.

        Args:
            nats_client: NATS client instance.
            state_manager: StateManager to update.
            channel: CyTube channel name.
            domain: CyTube domain.
            logger: Logger for structured output.
        """
        self._nats = nats_client
        self._state = state_manager
        self._channel = channel
        self._domain = domain
        self._logger = logger
        self._running = False
        self._subscriptions: list[Any] = []

    @property
    def is_running(self) -> bool:
        """Check if updater is running.

        Returns:
            True if started and processing events, False otherwise.
        """
        return self._running

    async def start(self) -> None:
        """Start state updater and subscribe to events.

        Subscribes to relevant CyTube events for the configured channel/domain.

        Raises:
            RuntimeError: If NATS is not connected or StateManager not started.
        """
        if self._running:
            self._logger.debug("State updater already running")
            return

        if not self._nats.is_connected:
            raise RuntimeError("NATS client not connected")

        if not self._state.is_running:
            raise RuntimeError("StateManager not started")

        if self._nats._nc is None:
            raise RuntimeError("NATS client internal connection is None")

        try:
            self._logger.info(f"Starting state updater for {self._domain}/{self._channel}")

            # Subscribe to playlist events
            subject = build_subject(self._domain, self._channel, "playlist")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_playlist)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            subject = build_subject(self._domain, self._channel, "queue")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_queue)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            subject = build_subject(self._domain, self._channel, "delete")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_delete)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            subject = build_subject(self._domain, self._channel, "moveVideo")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_move_video)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            # Subscribe to userlist events
            subject = build_subject(self._domain, self._channel, "userlist")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_userlist)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            subject = build_subject(self._domain, self._channel, "addUser")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_add_user)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            subject = build_subject(self._domain, self._channel, "userLeave")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_user_leave)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            # Subscribe to emotes event
            subject = build_subject(self._domain, self._channel, "emoteList")
            sub = await self._nats._nc.subscribe(subject, cb=self._handle_emote_list)
            self._subscriptions.append(sub)
            self._logger.debug(f"Subscribed to {subject}")

            self._running = True
            self._logger.info("State updater started successfully")

        except Exception as e:
            self._logger.error(f"Failed to start state updater: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop state updater and unsubscribe from events.

        Gracefully unsubscribes from all event subscriptions.
        Safe to call multiple times.
        """
        if not self._running:
            return

        try:
            self._logger.info("Stopping state updater")

            # Unsubscribe from all subscriptions
            for sub in self._subscriptions:
                try:
                    await sub.unsubscribe()
                except Exception as e:
                    self._logger.warning(f"Error unsubscribing: {e}")

            self._subscriptions.clear()
            self._running = False

            self._logger.info("State updater stopped")

        except Exception as e:
            self._logger.error(f"Error stopping state updater: {e}", exc_info=True)

    # ========================================================================
    # Event Handlers
    # ========================================================================

    async def _handle_playlist(self, msg) -> None:
        """Handle 'playlist' event (initial playlist load).

        Args:
            msg: NATS message with playlist data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())

            # Extract playlist items from event payload
            playlist = data.get("payload", [])

            await self._state.set_playlist(playlist)

        except Exception as e:
            self._logger.error(f"Error handling playlist event: {e}", exc_info=True)

    async def _handle_queue(self, msg) -> None:
        """Handle 'queue' event (video added to playlist).

        Args:
            msg: NATS message with queue data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())
            payload = data.get("payload", {})

            item = payload.get("item", {})
            after = payload.get("after")

            await self._state.add_playlist_item(item, after)

        except Exception as e:
            self._logger.error(f"Error handling queue event: {e}", exc_info=True)

    async def _handle_delete(self, msg) -> None:
        """Handle 'delete' event (video removed from playlist).

        Args:
            msg: NATS message with delete data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())
            payload = data.get("payload", {})

            uid = payload.get("uid")
            if uid:
                await self._state.remove_playlist_item(uid)

        except Exception as e:
            self._logger.error(f"Error handling delete event: {e}", exc_info=True)

    async def _handle_move_video(self, msg) -> None:
        """Handle 'moveVideo' event (video moved in playlist).

        Args:
            msg: NATS message with move data.
        """
        self._logger.info("DEBUG: _handle_move_video called")
        try:
            import json

            data = json.loads(msg.data.decode())
            payload = data.get("payload", {})

            self._logger.info(f"DEBUG: moveVideo payload: {payload}")

            from_uid = payload.get("from")
            after = payload.get("after")

            if from_uid is not None and after is not None:
                await self._state.move_playlist_item(from_uid, after)
            else:
                self._logger.warning(f"DEBUG: Missing from/after in moveVideo: {payload}")

        except Exception as e:
            self._logger.error(f"Error handling moveVideo event: {e}", exc_info=True)

    async def _handle_userlist(self, msg) -> None:
        """Handle 'userlist' event (initial user list load).

        Args:
            msg: NATS message with userlist data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())

            # Extract users from event payload
            users = data.get("payload", [])

            await self._state.set_userlist(users)

        except Exception as e:
            self._logger.error(f"Error handling userlist event: {e}", exc_info=True)

    async def _handle_add_user(self, msg) -> None:
        """Handle 'addUser' event (user joined channel).

        Args:
            msg: NATS message with user data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())
            payload = data.get("payload", {})

            await self._state.add_user(payload)

        except Exception as e:
            self._logger.error(f"Error handling addUser event: {e}", exc_info=True)

    async def _handle_user_leave(self, msg) -> None:
        """Handle 'userLeave' event (user left channel).

        Args:
            msg: NATS message with username data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())
            payload = data.get("payload", {})

            username = payload.get("name")
            if username:
                await self._state.remove_user(username)

        except Exception as e:
            self._logger.error(f"Error handling userLeave event: {e}", exc_info=True)

    async def _handle_emote_list(self, msg) -> None:
        """Handle 'emoteList' event (channel emotes loaded).

        Args:
            msg: NATS message with emote list data.
        """
        try:
            import json

            data = json.loads(msg.data.decode())

            # Extract emotes from event payload
            emotes = data.get("payload", [])

            await self._state.update_emotes(emotes)

        except Exception as e:
            self._logger.error(f"Error handling emoteList event: {e}", exc_info=True)

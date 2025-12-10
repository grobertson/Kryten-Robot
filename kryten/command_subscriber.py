"""NATS Command Subscriber - Listen for commands and execute on CyTube.

This module subscribes to NATS command subjects and routes them to the
CytubeEventSender to execute on CyTube channels.
"""

import json
import logging
from typing import Any

from .cytube_event_sender import CytubeEventSender
from .nats_client import NatsClient
from .stats_tracker import StatsTracker


class CommandSubscriber:
    """Subscribe to NATS commands and execute them on CyTube.

    Routes commands from NATS to CytubeEventSender methods, handling
    JSON parsing, validation, and error logging.

    Attributes:
        sender: CyTube event sender instance.
        nats_client: NATS client for subscriptions.
        logger: Logger instance.
        channel: CyTube channel name for subject filtering.

    Examples:
        >>> subscriber = CommandSubscriber(sender, nats_client, logger, "cytu.be", "mychannel")
        >>> await subscriber.start()
        >>> # Commands sent to cytube.commands.cytu.be.mychannel.* will be executed
        >>> await subscriber.stop()
    """

    def __init__(
        self,
        sender: CytubeEventSender,
        nats_client: NatsClient,
        logger: logging.Logger,
        domain: str,
        channel: str,
        audit_logger=None,
    ):
        """Initialize command subscriber.

        Args:
            sender: CyTube event sender instance.
            nats_client: NATS client for subscriptions.
            logger: Logger for structured output.
            domain: CyTube domain name.
            channel: CyTube channel name.
            audit_logger: Optional AuditLogger for command tracking.
        """
        self._sender = sender
        self._nats = nats_client
        self._logger = logger
        self._domain = domain
        self._channel = channel
        self._audit_logger = audit_logger
        self._running = False
        self._subscription = None

        # Metrics tracking
        self._commands_processed = 0
        self._commands_succeeded = 0
        self._commands_failed = 0

        # Rate tracking
        self._stats_tracker = StatsTracker()

    @property
    def stats(self) -> dict[str, Any]:
        """Get command processing statistics.

        Returns:
            Dictionary with commands_processed, commands_succeeded,
            commands_failed counts, and rate information.

        Examples:
            >>> stats = subscriber.stats
            >>> print(f"Processed: {stats['commands_processed']}")
            >>> print(f"Success rate: {stats['commands_succeeded'] / stats['commands_processed']}")
            >>> print(f"Rate (1m): {stats['rate_1min']:.2f}/sec")
        """
        last_time, last_type = self._stats_tracker.get_last()

        return {
            "commands_processed": self._commands_processed,
            "commands_succeeded": self._commands_succeeded,
            "commands_failed": self._commands_failed,
            "rate_1min": self._stats_tracker.get_rate(60),
            "rate_5min": self._stats_tracker.get_rate(300),
            "last_command_time": last_time,
            "last_command_type": last_type,
        }

    @property
    def is_running(self) -> bool:
        """Check if subscriber is running.

        Returns:
            True if subscribed and processing commands, False otherwise.
        """
        return self._running

    async def start(self) -> None:
        """Start subscribing to command subjects.

        Subscribes to kryten.commands.cytube.{channel}.> to receive all commands
        for this channel.
        """
        if self._running:
            self._logger.warning("Command subscriber already running")
            return

        self._running = True

        # Import here to use the updated function
        from .subject_builder import normalize_token

        # Subscribe to all commands for this channel (domain normalized out)
        channel_normalized = normalize_token(self._channel)
        subject = f"kryten.commands.cytube.{channel_normalized}.>"
        self._subscription = await self._nats.subscribe(subject, self._handle_command)

        self._logger.info(f"Command subscriber started on subject: {subject}")

    async def stop(self) -> None:
        """Stop command subscriptions."""
        if not self._running:
            return

        self._running = False

        if self._subscription:
            await self._nats.unsubscribe(self._subscription)
            self._subscription = None

        self._logger.info("Command subscriber stopped")

    async def _handle_command(self, subject: str, data: bytes) -> None:
        """Handle incoming command message.

        Args:
            subject: NATS subject the command was received on.
            data: Message payload (JSON).
        """
        try:
            # Parse command JSON
            command = json.loads(data.decode())
            action = command.get("action")
            params = command.get("data", {})

            if not action:
                self._logger.warning(f"Command missing 'action' field on {subject}")
                return

            self._logger.info(f"Received command '{action}' on {subject}")

            # Audit log the command
            if self._audit_logger:
                # Extract username from params if available
                username = params.get("username") or params.get("name") or "system"
                self._audit_logger.log_command(
                    command=action,
                    username=username,
                    arguments=params,
                    source="NATS"
                )

            # Route to appropriate sender method
            success = await self._route_command(action, params)

            # Update metrics
            self._commands_processed += 1
            if success:
                self._commands_succeeded += 1
                self._stats_tracker.record(action)
                self._logger.debug(f"Command '{action}' executed successfully")
            else:
                self._commands_failed += 1
                self._logger.warning(f"Command '{action}' execution failed")

        except json.JSONDecodeError as e:
            self._commands_failed += 1
            self._logger.error(f"Invalid JSON in command on {subject}: {e}")
        except Exception as e:
            self._commands_failed += 1
            self._logger.error(f"Error handling command on {subject}: {e}", exc_info=True)

    async def _route_command(self, action: str, params: dict[str, Any]) -> bool:
        """Route command to appropriate sender method.

        Args:
            action: Action name (e.g., "chat", "queue", "kick").
            params: Action parameters.

        Returns:
            True if command executed successfully, False otherwise.
        """
        try:
            # Chat actions
            if action == "chat":
                return await self._sender.send_chat(**params)
            elif action == "pm":
                return await self._sender.send_pm(**params)

            # Playlist actions
            elif action == "queue" or action == "add_video":
                # Handle both old format (url) and new format (type + id)
                if "type" in params and "id" in params:
                    # New format from kryten-py: {"type": "yt", "id": "abc123", "pos": "end"}
                    # Check if this is a grindhouse URL that needs transformation
                    media_id = params.get("id")
                    media_type = params.get("type")

                    # If type is "cu" and id looks like a grindhouse view URL, transform it
                    if media_type == "cu" and isinstance(media_id, str) and "420grindhouse.com/view?m=" in media_id:
                        # Transform to custom media format with JSON API URL
                        import re
                        pattern = r'https?://(?:www\.)?420grindhouse\.com/view\?m=([A-Za-z0-9_-]+)'
                        match = re.match(pattern, media_id)
                        if match:
                            media_id_code = match.group(1)
                            media_id = f"https://www.420grindhouse.com/api/v1/media/cytube/{media_id_code}.json?format=json"
                            media_type = "cm"
                            self._logger.info(f"Transformed grindhouse URL in command subscriber: type={media_type}, id={media_id}")

                    return await self._sender.add_video(
                        media_type=media_type,
                        media_id=media_id,
                        position=params.get("pos", "end"),
                        temp=params.get("temp", False)
                    )
                else:
                    # Old format: {"url": "yt:abc123", "position": "end", "temp": False}
                    return await self._sender.add_video(**params)
            elif action == "delete" or action == "delete_video":
                # CyTube expects UID as raw number, not wrapped in object
                # The event sender will handle conversion to int
                return await self._sender.delete_video(**params)
            elif action == "move" or action == "move_video":
                # Map 'from' to 'uid' if needed (event sender expects 'uid' parameter)
                if "from" in params and "uid" not in params:
                    params["uid"] = params.pop("from")
                # Event sender will handle UID type conversions
                return await self._sender.move_video(**params)
            elif action == "jump" or action == "jump_to":
                # Event sender will handle UID type conversion
                return await self._sender.jump_to(**params)
            elif action == "clear" or action == "clear_playlist":
                return await self._sender.clear_playlist()
            elif action == "shuffle" or action == "shuffle_playlist":
                return await self._sender.shuffle_playlist()
            elif action == "set_temp" or action == "setTemp":
                # Event sender expects uid parameter and handles type conversion
                return await self._sender.set_temp(**params)

            # Playback actions
            elif action == "pause":
                return await self._sender.pause()
            elif action == "play":
                return await self._sender.play()
            elif action == "seek" or action == "seek_to":
                return await self._sender.seek_to(**params)

            # Moderation actions
            elif action == "kick" or action == "kick_user":
                return await self._sender.kick_user(**params)
            elif action == "ban" or action == "ban_user":
                return await self._sender.ban_user(**params)
            elif action == "voteskip":
                return await self._sender.voteskip()
            elif action == "assignLeader" or action == "assign_leader":
                return await self._sender.assign_leader(**params)
            elif action == "mute" or action == "mute_user":
                return await self._sender.mute_user(**params)
            elif action == "smute" or action == "shadow_mute" or action == "shadow_mute_user":
                return await self._sender.shadow_mute_user(**params)
            elif action == "unmute" or action == "unmute_user":
                return await self._sender.unmute_user(**params)
            elif action == "playNext" or action == "play_next":
                return await self._sender.play_next()

            # Phase 2: Admin commands (rank 3+)
            elif action == "setMotd" or action == "set_motd":
                return await self._sender.set_motd(**params)
            elif action == "setChannelCSS" or action == "set_channel_css":
                return await self._sender.set_channel_css(**params)
            elif action == "setChannelJS" or action == "set_channel_js":
                return await self._sender.set_channel_js(**params)
            elif action == "setOptions" or action == "set_options":
                return await self._sender.set_options(**params)
            elif action == "setPermissions" or action == "set_permissions":
                return await self._sender.set_permissions(**params)
            elif action == "updateEmote" or action == "update_emote":
                return await self._sender.update_emote(**params)
            elif action == "removeEmote" or action == "remove_emote":
                return await self._sender.remove_emote(**params)
            elif action == "addFilter" or action == "add_filter":
                return await self._sender.add_filter(**params)
            elif action == "updateFilter" or action == "update_filter":
                return await self._sender.update_filter(**params)
            elif action == "removeFilter" or action == "remove_filter":
                return await self._sender.remove_filter(**params)

            # Phase 3: Advanced admin commands (rank 2-4+)
            elif action == "newPoll" or action == "new_poll":
                return await self._sender.new_poll(**params)
            elif action == "vote":
                return await self._sender.vote(**params)
            elif action == "closePoll" or action == "close_poll":
                return await self._sender.close_poll()
            elif action == "setChannelRank" or action == "set_channel_rank":
                return await self._sender.set_channel_rank(**params)
            elif action == "requestChannelRanks" or action == "request_channel_ranks":
                return await self._sender.request_channel_ranks()
            elif action == "requestBanlist" or action == "request_banlist":
                return await self._sender.request_banlist()
            elif action == "unban":
                return await self._sender.unban(**params)
            elif action == "readChanLog" or action == "read_chan_log":
                return await self._sender.read_chan_log(**params)
            elif action == "searchLibrary" or action == "search_library":
                return await self._sender.search_library(**params)
            elif action == "deleteFromLibrary" or action == "delete_from_library":
                return await self._sender.delete_from_library(**params)

            else:
                self._logger.warning(f"Unknown action: {action}")
                return False

        except TypeError as e:
            self._logger.error(f"Invalid parameters for action '{action}': {e}")
            return False
        except Exception as e:
            self._logger.error(f"Error executing action '{action}': {e}", exc_info=True)
            return False


__all__ = ["CommandSubscriber"]

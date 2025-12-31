"""NATS command handler for kryten-robot service.

Handles system commands on the kryten.robot.command subject, including:
- system.ping - Service discovery and health check
- system.health - Detailed health status
- system.stats - Service statistics
"""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from nats.aio.subscription import Subscription

from .nats_client import NatsClient


class RobotCommandHandler:
    """Handles system commands on kryten.robot.command subject."""

    def __init__(
        self,
        nats_client: NatsClient,
        logger: logging.Logger,
        version: str = "unknown",
        config: Any = None,
        connector: Any = None,
        publisher: Any = None,
        cmd_subscriber: Any = None,
        sender: Any = None,
    ):
        """Initialize robot command handler.

        Args:
            nats_client: NatsClient instance for NATS operations
            logger: Logger instance
            version: Service version string
            config: KrytenConfig for accessing health port etc
            connector: CytubeConnector for connection status
            publisher: EventPublisher for stats
            cmd_subscriber: CommandSubscriber for stats
            sender: CytubeEventSender for sending messages
        """
        self.nats = nats_client
        self.logger = logger
        self.version = version
        self.config = config
        self.connector = connector
        self.publisher = publisher
        self.cmd_subscriber = cmd_subscriber
        self.sender = sender

        self._subscription: Subscription | None = None
        self._commands_processed = 0

    async def start(self) -> None:
        """Subscribe to command subject."""
        # New style subject: kryten.robot.command
        subject = "kryten.robot.command"
        self._subscription = await self.nats.subscribe_request_reply(subject, self._handle_command)
        self.logger.info(f"Robot command handler subscribed to {subject}")

    async def stop(self) -> None:
        """Unsubscribe from command subject."""
        if self._subscription:
            await self.nats.unsubscribe(self._subscription)
            self._subscription = None
        self.logger.info("Robot command handler stopped")

    async def _handle_command(self, msg) -> None:
        """Handle incoming command messages.

        Args:
            msg: NATS message with .data and .reply
        """
        self._commands_processed += 1

        try:
            request = json.loads(msg.data.decode())
            command = request.get("command", "")

            if not command:
                await self._send_response(
                    msg.reply,
                    {
                        "service": "robot",
                        "success": False,
                        "error": "Missing 'command' field",
                    },
                )
                return

            # Check service routing
            service = request.get("service")
            if service and service not in ("robot", "system"):
                await self._send_response(
                    msg.reply,
                    {
                        "service": "robot",
                        "success": False,
                        "error": f"Command intended for '{service}', not 'robot'",
                    },
                )
                return

            # Dispatch command
            handlers = {
                "system.ping": self._handle_ping,
                "system.health": self._handle_health,
                "system.stats": self._handle_stats,
                "playlist.move": self._handle_playlist_move,
                "playlist.queue": self._handle_playlist_queue,
                "playlist.delete": self._handle_playlist_delete,
                # Robot control commands
                "restart": self._handle_restart,
                "halt": self._handle_halt,
                "reconnect": self._handle_reconnect,
                "say": self._handle_say,
                "pm": self._handle_pm,
                "mute": self._handle_mute,
                "smute": self._handle_smute,
                "kick": self._handle_kick,
                "ban": self._handle_ban,
                "unkick": self._handle_unkick,  # Note: Cytube doesn't have unkick, but unban.
                # Playlist commands
                "addvideo": self._handle_add_video,
                "rmvideo": self._handle_delete_video,
                "mvvideo": self._handle_move_video,
                "jump": self._handle_jump,
                "clear": self._handle_clear,
                "shuffle": self._handle_shuffle,
                "settemp": self._handle_set_temp,
                "pause": self._handle_pause,
                "play": self._handle_play,
                "seek": self._handle_seek,
                "voteskip": self._handle_voteskip,
                "assignLeader": self._handle_assign_leader,
            }

            handler = handlers.get(command)
            if not handler:
                self.logger.debug(f"Ignoring unknown command: {command}")
                return

            # Extract arguments from request for standard format handlers
            # Some existing handlers might expect the full request, so we check
            args = request.get("args", {})
            if command.startswith("system.") or command.startswith("playlist."):
                result = await handler(request)
            else:
                result = await handler(args)

            await self._send_response(
                msg.reply,
                {
                    "service": "robot",
                    "command": command,
                    "success": True,
                    "data": result,
                },
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in command: {e}")
            await self._send_response(
                msg.reply,
                {
                    "service": "robot",
                    "success": False,
                    "error": f"Invalid JSON: {e}",
                },
            )
        except Exception as e:
            self.logger.error(f"Error handling command: {e}", exc_info=True)
            await self._send_response(
                msg.reply,
                {
                    "service": "robot",
                    "success": False,
                    "error": str(e),
                },
            )

    async def _handle_restart(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle restart command."""
        self.logger.info("Restart command received")
        # In a real service, this might trigger a graceful shutdown/restart
        # For now, we'll just log it and potentially trigger a reconnect
        if self.connector:
            await self.connector.disconnect()
            # The watchdog or main loop should handle reconnection
        return {"message": "Restarting connection"}

    async def _handle_halt(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle halt command."""
        self.logger.info("Halt command received")
        if self.connector:
            await self.connector.disconnect()
        return {"message": "Halting connection"}

    async def _handle_reconnect(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle reconnect command."""
        self.logger.info("Reconnect command received")
        if self.connector:
            await self.connector.disconnect()
            # Watchdog will pick it up
        return {"message": "Reconnecting"}

    async def _handle_say(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle say command."""
        message = args.get("message") or args.get("msg")
        if not message:
            raise ValueError("Missing message")

        if self.sender:
            await self.sender.send_chat(message)
            return {"success": True}

        if self.connector:
            # Fallback if sender not provided but connector is (though connector doesn't have send_chat directly usually)
            # Keeping for compatibility if connector was patched, but preferably use sender
            try:
                await self.connector.send_chat(message)
                return {"success": True}
            except AttributeError:
                pass

        raise RuntimeError("Not connected or sender not available")

    async def _handle_pm(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle PM command."""
        username = args.get("username") or args.get("to")
        message = args.get("message") or args.get("msg")

        if not username or not message:
            raise ValueError("Missing username or message")

        if self.sender:
            await self.sender.send_pm(username, message)
            return {"success": True}

        if self.connector:
            # Fallback/Legacy check
            try:
                await self.connector.send_pm(username, message)
                return {"success": True}
            except AttributeError:
                pass

        raise RuntimeError("Not connected or sender not available")

    async def _handle_mute(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle mute command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        username = args.get("username") or args.get("name")
        if not username:
            raise ValueError("Missing username")

        success = await self.sender.mute_user(username)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to mute user"}

    async def _handle_smute(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle shadow mute command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        username = args.get("username") or args.get("name")
        if not username:
            raise ValueError("Missing username")

        success = await self.sender.shadow_mute_user(username)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to shadow mute user"}

    async def _handle_kick(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle kick command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        username = args.get("username") or args.get("name")
        reason = args.get("reason", "")
        if not username:
            raise ValueError("Missing username")

        success = await self.sender.kick_user(username, reason)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to kick user"}

    async def _handle_ban(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle ban command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        username = args.get("username") or args.get("name")
        reason = args.get("reason", "")
        if not username:
            raise ValueError("Missing username")

        success = await self.sender.ban_user(username, reason)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to ban user"}

    async def _handle_unkick(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle unkick/unban command."""
        return {"error": "Not implemented in handler yet"}

    async def _handle_add_video(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle add video command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        # Map args to add_video parameters
        # args might contain: type, id, pos, temp OR url
        # client.py sends: type, id, pos, temp

        success = await self.sender.add_video(
            url=args.get("url"),
            media_type=args.get("type"),
            media_id=args.get("id"),
            position=args.get("pos", "end"),
            temp=args.get("temp", True),
        )

        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to add video"}

    async def _handle_delete_video(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle delete video command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        uid = args.get("uid")
        if uid is None:
            raise ValueError("Missing uid")

        success = await self.sender.delete_video(uid)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to delete video"}

    async def _handle_move_video(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle move video command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        # client.py sends: from, after
        uid = args.get("from")
        after = args.get("after")

        if uid is None or after is None:
            raise ValueError("Missing 'from' or 'after'")

        success = await self.sender.move_video(uid, after)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to move video"}

    async def _handle_jump(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle jump to video command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        uid = args.get("uid")
        if uid is None:
            raise ValueError("Missing uid")

        success = await self.sender.jump_to(uid)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to jump to video"}

    async def _handle_clear(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle clear playlist command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        success = await self.sender.clear_playlist()
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to clear playlist"}

    async def _handle_shuffle(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle shuffle playlist command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        success = await self.sender.shuffle_playlist()
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to shuffle playlist"}

    async def _handle_set_temp(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle set temporary command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        uid = args.get("uid")
        temp = args.get("temp")

        if uid is None or temp is None:
            raise ValueError("Missing uid or temp")

        success = await self.sender.set_temp(uid, temp)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to set temp"}

    async def _handle_pause(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle pause command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        success = await self.sender.pause()
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to pause"}

    async def _handle_play(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle play command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        success = await self.sender.play()
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to play"}

    async def _handle_seek(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle seek command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        time_val = args.get("time")
        if time_val is None:
            raise ValueError("Missing time")

        success = await self.sender.seek_to(time_val)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to seek"}

    async def _handle_voteskip(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle voteskip command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        success = await self.sender.voteskip()
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to voteskip"}

    async def _handle_assign_leader(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle assign leader command."""
        if not self.sender:
            raise RuntimeError("CytubeEventSender not available")

        name = args.get("name", "")
        success = await self.sender.assign_leader(name)
        if success:
            return {"success": True}
        return {"success": False, "error": "Failed to assign leader"}

    async def _send_response(self, reply_to: str | None, response: dict) -> None:
        """Send response to reply subject.

        Args:
            reply_to: Reply subject
            response: Response dict to send
        """
        if reply_to:
            try:
                data = json.dumps(response).encode()
                await self.nats.publish(reply_to, data)
            except Exception as e:
                self.logger.error(f"Failed to send response: {e}")

    async def _handle_ping(self, request: dict) -> dict:
        """Handle system.ping - Simple liveness check with metadata."""
        uptime_seconds = self._get_nats_uptime()

        result = {
            "pong": True,
            "service": "robot",
            "version": self.version,
            "uptime_seconds": uptime_seconds,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Add metrics endpoint if health is enabled
        if self.config and self.config.health.enabled:
            result["metrics_endpoint"] = (
                f"http://{self.config.health.host}:{self.config.health.port}/health"
            )

        # Add CyTube connection info
        if self.connector:
            result["cytube_connected"] = self.connector.is_connected
            if self.connector.is_connected:
                result["channel"] = self.config.cytube.channel if self.config else "unknown"
                result["domain"] = self.config.cytube.domain if self.config else "unknown"

        return result

    async def _handle_health(self, request: dict) -> dict:
        """Handle system.health - Detailed health status."""
        uptime_seconds = self._get_nats_uptime()

        health = {
            "service": "robot",
            "status": "healthy",
            "version": self.version,
            "uptime_seconds": uptime_seconds,
        }

        # NATS status
        health["nats_connected"] = self.nats.is_connected
        health["nats_reconnect_count"] = self.nats.reconnect_count

        # CyTube status
        if self.connector:
            health["cytube_connected"] = self.connector.is_connected
            if self.config:
                health["channel"] = self.config.cytube.channel
                health["domain"] = self.config.cytube.domain

        # Metrics endpoint
        if self.config and self.config.health.enabled:
            health["metrics_endpoint"] = (
                f"http://{self.config.health.host}:{self.config.health.port}/health"
            )

        return health

    async def _handle_playlist_move(self, request: dict) -> dict:
        """Handle playlist.move command.

        Payload should contain:
        - from_uid: UID of item to move
        - after_uid: UID of item to place after (or "prepend"/"append")
        """
        payload = request.get("payload", {})
        from_uid = payload.get("from_uid")
        after_uid = payload.get("after_uid")

        if not from_uid or not after_uid:
            raise ValueError("Missing from_uid or after_uid in payload")

        if not self.connector or not self.connector.is_connected:
            raise RuntimeError("CytubeConnector not connected")

        # CyTube expects: { "from": uid, "after": uid }
        await self.connector.emit("moveVideo", {"from": from_uid, "after": after_uid})

        self.logger.info(f"Sent moveVideo command: {from_uid} after {after_uid}")
        return {"status": "sent", "from_uid": from_uid, "after_uid": after_uid}

    async def _handle_playlist_queue(self, request: dict) -> dict:
        """Handle playlist.queue command (add item)."""
        payload = request.get("payload", {})
        item = payload.get("item")

        if not item:
            raise ValueError("Missing item in payload")

        if not self.connector or not self.connector.is_connected:
            raise RuntimeError("CytubeConnector not connected")

        await self.connector.emit("queue", {"media": item})
        return {"status": "sent", "title": item.get("title", "unknown")}

    async def _handle_playlist_delete(self, request: dict) -> dict:
        """Handle playlist.delete command."""
        payload = request.get("payload", {})
        uid = payload.get("uid")

        if not uid:
            raise ValueError("Missing uid in payload")

        if not self.connector or not self.connector.is_connected:
            raise RuntimeError("CytubeConnector not connected")

        await self.connector.emit("delete", {"uid": uid})
        return {"status": "sent", "uid": uid}

    async def _handle_stats(self, request: dict) -> dict:
        """Handle system.stats - Service statistics."""
        uptime_seconds = self._get_nats_uptime()

        stats = {
            "service": "robot",
            "version": self.version,
            "uptime_seconds": uptime_seconds,
            "commands_processed": self._commands_processed,
        }

        # NATS stats
        nats_stats = self.nats.stats
        stats["messages_published"] = nats_stats.get("messages_published", 0)
        stats["bytes_sent"] = nats_stats.get("bytes_sent", 0)
        stats["nats_errors"] = nats_stats.get("errors", 0)

        # Event publisher stats
        if self.publisher:
            stats["events_published"] = getattr(self.publisher, "_event_count", 0)

        # Command subscriber stats
        if self.cmd_subscriber:
            cmd_stats = self.cmd_subscriber.stats
            stats["cytube_commands_processed"] = cmd_stats.get("commands_processed", 0)
            stats["cytube_commands_succeeded"] = cmd_stats.get("commands_succeeded", 0)
            stats["cytube_commands_failed"] = cmd_stats.get("commands_failed", 0)

        return stats

    def _get_nats_uptime(self) -> float:
        """Get NATS connection uptime in seconds."""
        if self.nats.connected_since:
            return time.time() - self.nats.connected_since
        return 0.0

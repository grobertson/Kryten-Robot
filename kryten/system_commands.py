"""System PM command handler for kryten-robot.

Intercepts private messages sent to the bot whose text begins with "system:"
and handles them locally — they are NOT forwarded to other services via NATS.

Supported commands (sent as a PM to the bot):
    system:about   version, uptime, and all registered services
    system:help    list all system: commands

Unknown system: commands are silently dropped.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cytube_event_sender import CytubeEventSender
    from .service_registry import ServiceRegistry


class SystemCommandHandler:
    """Handle system: PM commands locally without forwarding to NATS.

    Register ``handle_pm`` as a connector ``on_event("pm", ...)`` callback.
    The ``EventPublisher`` must be configured to drop pm events whose
    message starts with "system:" so they do not reach the NATS bus.
    """

    # Map command name → short description (used by system:help)
    COMMANDS: dict[str, str] = {
        "about": "version, uptime, and all connected services",
        "help": "show this message",
    }

    def __init__(
        self,
        sender: "CytubeEventSender",
        service_registry: "ServiceRegistry | None",
        version: str,
        start_time: float,
        config: Any,
        logger: logging.Logger,
    ) -> None:
        self._sender = sender
        self._service_registry = service_registry
        self._version = version
        self._start_time = start_time
        self._config = config
        self._logger = logger

    # ------------------------------------------------------------------
    # Public synchronous callback (registered via connector.on_event)
    # ------------------------------------------------------------------

    def handle_pm(self, event_name: str, payload: dict) -> None:
        """Synchronous on_event callback.  Spawns an async task for system: PMs."""
        msg = payload.get("msg", "")
        if not msg.startswith("system:"):
            return
        username = payload.get("username", "")
        if username:
            asyncio.create_task(self._dispatch(username, msg))

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, username: str, raw_msg: str) -> None:
        command = raw_msg[len("system:"):].strip().lower()
        handler = {
            "about": self._about,
            "help": self._help,
        }.get(command)
        if handler:
            try:
                await handler(username)
            except Exception as e:
                self._logger.error(
                    f"Error handling system:{command} for {username}: {e}", exc_info=True
                )
        else:
            self._logger.debug(
                f"Unknown system: command '{command}' from {username} — dropped"
            )

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _about(self, username: str) -> None:
        uptime = _format_uptime(time.time() - self._start_time)
        channel = getattr(getattr(self._config, "cytube", None), "channel", "?")
        domain = getattr(getattr(self._config, "cytube", None), "domain", "?")

        parts: list[str] = [
            f"Kryten Robot v{self._version}",
            f"up {uptime}",
            f"channel: {channel}@{domain}",
        ]

        if self._service_registry:
            services = self._service_registry.get_all_services()
            if services:
                svc_strs = [f"{s.name} v{s.version}" for s in services]
                parts.append(f"services: {', '.join(svc_strs)}")
            else:
                parts.append("services: none registered")
        else:
            parts.append("services: registry unavailable")

        await self._sender.send_pm(username, " | ".join(parts))

    async def _help(self, username: str) -> None:
        entries = [f"system:{cmd} — {desc}" for cmd, desc in self.COMMANDS.items()]
        await self._sender.send_pm(username, " | ".join(entries))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_uptime(seconds: float) -> str:
    """Return a compact human-readable uptime string."""
    s = int(seconds)
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    mins = s // 60
    if days:
        return f"{days}d{hours}h{mins}m"
    if hours:
        return f"{hours}h{mins}m"
    return f"{mins}m"

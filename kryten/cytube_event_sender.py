"""CyTube Event Sender - Send events to CyTube channels.

This module provides a high-level interface for sending events to CyTube,
wrapping the Socket.IO connection with convenient methods for common actions.
"""

import logging
from typing import Optional, Dict, Any, List

from .errors import NotConnectedError


class CytubeEventSender:
    """Send events to CyTube channel.
    
    Wraps CytubeConnector to provide action-oriented methods for sending
    events like chat messages, playlist changes, and moderation actions.
    
    Attributes:
        connector: CytubeConnector instance to use for sending.
        logger: Logger for structured output.
    
    Examples:
        >>> sender = CytubeEventSender(connector, logger)
        >>> await sender.send_chat("Hello, world!")
        >>> await sender.add_video("https://youtu.be/dQw4w9WgXcQ")
    """
    
    def __init__(self, connector, logger: logging.Logger, audit_logger=None):
        """Initialize event sender.
        
        Args:
            connector: Connected CytubeConnector instance.
            logger: Logger for structured output.
            audit_logger: Optional AuditLogger for operation tracking.
        """
        self._connector = connector
        self._logger = logger
        self._audit_logger = audit_logger
    
    # ========================================================================
    # Chat Methods
    # ========================================================================
    
    async def send_chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send a public chat message.
        
        Args:
            message: Chat message text.
            metadata: Optional metadata (emotes, styling, etc.).
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.send_chat("Hello!")
            >>> await sender.send_chat("Hello", {"emote": "wave"})
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot send chat: not connected")
            return False
        
        try:
            payload = {"msg": message}
            if metadata:
                payload.update(metadata)
            
            self._logger.debug(f"Sending chat: {message}")
            await self._connector._socket.emit("chatMsg", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to send chat: {e}", exc_info=True)
            return False
    
    async def send_pm(self, to: str, message: str) -> bool:
        """Send a private message to a user.
        
        Args:
            to: Target username.
            message: Private message text.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.send_pm("alice", "Secret message")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot send PM: not connected")
            return False
        
        try:
            payload = {"to": to, "msg": message}
            
            self._logger.debug(f"Sending PM to {to}: {message}")
            await self._connector._socket.emit("pm", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to send PM: {e}", exc_info=True)
            return False
    
    # ========================================================================
    # Playlist Methods
    # ========================================================================
    
    async def add_video(
        self,
        url: str = None,
        media_type: str = None,
        media_id: str = None,
        position: str = "end",
        temp: bool = False,
    ) -> bool:
        """Add video to playlist.
        
        Args:
            url: Video URL (legacy format: "yt:abc123" or full URL).
            media_type: Media type ("yt", "vm", "dm", "cu", etc.).
            media_id: Media ID or URL.
            position: Position to add ("end", "next", or media UID).
            temp: Mark as temporary (removed after playing).
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.add_video(url="https://youtu.be/dQw4w9WgXcQ")
            >>> await sender.add_video(media_type="cu", media_id="https://example.com/video.mp4")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot queue video: not connected")
            return False
        
        try:
            # Build payload based on provided parameters
            if media_type is not None and media_id is not None:
                # New format: type + id
                payload = {
                    "type": media_type,
                    "id": media_id,
                    "pos": position,
                    "temp": temp,
                }
            elif url is not None:
                # Legacy format: url (will be parsed by CyTube)
                payload = {
                    "id": url,
                    "pos": position,
                    "temp": temp,
                }
            else:
                self._logger.error("Must provide either url or (media_type + media_id)")
                return False
            
            self._logger.debug(f"Queueing video: {payload} at {position}")
            await self._connector._socket.emit("queue", payload)
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="queue",
                    media_title=url,  # URL will be replaced with title when available
                    details={"position": position, "temp": temp}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to queue video: {e}", exc_info=True)
            return False
    
    async def delete_video(self, uid: str) -> bool:
        """Remove video from playlist.
        
        Args:
            uid: Unique ID of video to remove.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.delete_video("abc123")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot delete video: not connected")
            return False
        
        try:
            # CyTube expects the UID directly as a number, not wrapped in an object
            # See: src/channel/playlist.js handleDelete expects typeof data !== "number"
            uid_num = int(uid) if isinstance(uid, str) else uid
            
            self._logger.info(f"Deleting video with UID: {uid_num}")
            await self._connector._socket.emit("delete", uid_num)
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="delete",
                    details={"uid": uid}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to delete video: {e}", exc_info=True)
            return False
    
    async def move_video(self, uid: str, after: str) -> bool:
        """Reorder playlist by moving video.
        
        Args:
            uid: UID of video to move.
            after: UID of video to place after (or "prepend"/"append").
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.move_video("abc123", "xyz789")
            >>> await sender.move_video("abc123", "prepend")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot move video: not connected")
            return False
        
        try:
            payload = {"from": uid, "after": after}
            
            self._logger.debug(f"Moving video {uid} after {after}")
            await self._connector._socket.emit("moveMedia", payload)
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="moveMedia",
                    details={"uid": uid, "after": after}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to move video: {e}", exc_info=True)
            return False
    
    async def jump_to(self, uid: str) -> bool:
        """Jump to specific video in playlist.
        
        Args:
            uid: UID of video to jump to.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.jump_to("abc123")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot jump to video: not connected")
            return False
        
        try:
            payload = {"uid": uid}
            
            self._logger.debug(f"Jumping to video: {uid}")
            await self._connector._socket.emit("jumpTo", payload)
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="jumpTo",
                    details={"uid": uid}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to jump to video: {e}", exc_info=True)
            return False
    
    async def clear_playlist(self) -> bool:
        """Clear entire playlist.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.clear_playlist()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot clear playlist: not connected")
            return False
        
        try:
            self._logger.debug("Clearing playlist")
            await self._connector._socket.emit("clearPlaylist", {})
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="clearPlaylist"
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to clear playlist: {e}", exc_info=True)
            return False
    
    async def shuffle_playlist(self) -> bool:
        """Shuffle playlist order.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.shuffle_playlist()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot shuffle playlist: not connected")
            return False
        
        try:
            self._logger.debug("Shuffling playlist")
            await self._connector._socket.emit("shufflePlaylist", {})
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="shufflePlaylist"
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to shuffle playlist: {e}", exc_info=True)
            return False
    
    async def set_temp(self, uid: str, temp: bool = True) -> bool:
        """Mark video as temporary.
        
        Args:
            uid: UID of video.
            temp: True for temporary, False for permanent.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.set_temp("abc123", True)
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set temp status: not connected")
            return False
        
        try:
            payload = {"uid": uid, "temp": temp}
            
            self._logger.debug(f"Setting temp={temp} for video: {uid}")
            await self._connector._socket.emit("setTemp", payload)
            
            # Audit log playlist operation
            if self._audit_logger:
                self._audit_logger.log_playlist_operation(
                    operation="setTemp",
                    details={"uid": uid, "temp": temp}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set temp status: {e}", exc_info=True)
            return False
    
    # ========================================================================
    # Playback Control Methods
    # ========================================================================
    
    async def pause(self) -> bool:
        """Pause current video.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.pause()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot pause: not connected")
            return False
        
        try:
            self._logger.debug("Pausing playback")
            await self._connector._socket.emit("pause", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to pause: {e}", exc_info=True)
            return False
    
    async def play(self) -> bool:
        """Resume playback.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.play()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot play: not connected")
            return False
        
        try:
            self._logger.debug("Resuming playback")
            await self._connector._socket.emit("play", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to play: {e}", exc_info=True)
            return False
    
    async def seek_to(self, time: float) -> bool:
        """Seek to timestamp.
        
        Args:
            time: Target time in seconds.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.seek_to(120.5)  # Seek to 2:00.5
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot seek: not connected")
            return False
        
        try:
            payload = {"time": time}
            
            self._logger.debug(f"Seeking to {time}s")
            await self._connector._socket.emit("seekTo", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to seek: {e}", exc_info=True)
            return False
    
    # ========================================================================
    # Moderation Methods
    # ========================================================================
    
    async def kick_user(self, username: str, reason: Optional[str] = None) -> bool:
        """Kick user from channel.
        
        Args:
            username: Username to kick.
            reason: Optional kick reason.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.kick_user("spammer")
            >>> await sender.kick_user("spammer", "Excessive spam")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot kick user: not connected")
            return False
        
        try:
            payload = {"name": username}
            if reason:
                payload["reason"] = reason
            
            self._logger.debug(f"Kicking user: {username}")
            await self._connector._socket.emit("kick", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to kick user: {e}", exc_info=True)
            return False
    
    async def ban_user(self, username: str, reason: Optional[str] = None) -> bool:
        """Ban user from channel.
        
        Args:
            username: Username to ban.
            reason: Optional ban reason.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.ban_user("troll")
            >>> await sender.ban_user("troll", "Harassment")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot ban user: not connected")
            return False
        
        try:
            payload = {"name": username}
            if reason:
                payload["reason"] = reason
            
            self._logger.debug(f"Banning user: {username}")
            await self._connector._socket.emit("ban", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="ban",
                    target=username,
                    details={"reason": reason} if reason else {}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to ban user: {e}", exc_info=True)
            return False
    
    async def voteskip(self) -> bool:
        """Vote to skip current media.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.voteskip()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot voteskip: not connected")
            return False
        
        try:
            self._logger.debug("Voting to skip")
            await self._connector._socket.emit("voteskip", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to voteskip: {e}", exc_info=True)
            return False
    
    async def assign_leader(self, username: str) -> bool:
        """Assign or remove leader status.
        
        Args:
            username: Username to give leader, or empty string to remove leader.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.assign_leader("alice")  # Give leader
            >>> await sender.assign_leader("")       # Remove leader
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot assign leader: not connected")
            return False
        
        try:
            payload = {"name": username}
            
            action = "Assigning" if username else "Removing"
            self._logger.debug(f"{action} leader: {username or '(none)'}")
            await self._connector._socket.emit("assignLeader", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to assign leader: {e}", exc_info=True)
            return False
    
    async def mute_user(self, username: str) -> bool:
        """Mute user (prevents them from chatting).
        
        This is a direct Socket.IO event, not a chat command.
        The user will see a notification that they've been muted.
        
        Args:
            username: Username to mute.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.mute_user("spammer")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot mute user: not connected")
            return False
        
        try:
            # Mute is handled via chat command on the server side
            # Send as chat message with /mute command
            payload = {"msg": f"/mute {username}", "meta": {}}
            
            self._logger.debug(f"Muting user: {username}")
            await self._connector._socket.emit("chatMsg", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to mute user: {e}", exc_info=True)
            return False
    
    async def shadow_mute_user(self, username: str) -> bool:
        """Shadow mute user (they can chat but only they and mods see it).
        
        Shadow muted users don't know they're muted - their messages
        appear normal to them but are only visible to moderators.
        
        Args:
            username: Username to shadow mute.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.shadow_mute_user("subtle_troll")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot shadow mute user: not connected")
            return False
        
        try:
            # Shadow mute is handled via chat command on the server side
            payload = {"msg": f"/smute {username}", "meta": {}}
            
            self._logger.debug(f"Shadow muting user: {username}")
            await self._connector._socket.emit("chatMsg", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to shadow mute user: {e}", exc_info=True)
            return False
    
    async def unmute_user(self, username: str) -> bool:
        """Unmute user (removes both regular and shadow mute).
        
        Args:
            username: Username to unmute.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.unmute_user("reformed_user")
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot unmute user: not connected")
            return False
        
        try:
            # Unmute is handled via chat command on the server side
            payload = {"msg": f"/unmute {username}", "meta": {}}
            
            self._logger.debug(f"Unmuting user: {username}")
            await self._connector._socket.emit("chatMsg", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to unmute user: {e}", exc_info=True)
            return False
    
    async def play_next(self) -> bool:
        """Skip to next video in playlist.
        
        Unlike voteskip, this immediately skips without voting.
        Requires appropriate permissions.
        
        Returns:
            True if sent successfully, False otherwise.
        
        Examples:
            >>> await sender.play_next()
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot play next: not connected")
            return False
        
        try:
            self._logger.debug("Playing next video")
            await self._connector._socket.emit("playNext", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to play next: {e}", exc_info=True)
            return False
    
    # PHASE 2: Admin Functions (Rank 3+)
    
    async def set_motd(self, motd: str) -> bool:
        """
        Set channel message of the day (MOTD).
        Requires rank 3+ (admin).
        
        Args:
            motd: Message of the day HTML content
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set MOTD: not connected")
            return False
        
        try:
            payload = {"motd": motd}
            self._logger.debug(f"Setting MOTD: {len(motd)} chars")
            await self._connector._socket.emit("setMotd", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setMotd",
                    details={"length": len(motd)}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set MOTD: {e}", exc_info=True)
            return False
    
    async def set_channel_css(self, css: str) -> bool:
        """
        Set channel custom CSS.
        Requires rank 3+ (admin).
        CyTube has a 20KB limit on CSS content.
        
        Args:
            css: CSS content (max ~20KB)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set CSS: not connected")
            return False
        
        try:
            # Check size (20KB = 20480 bytes)
            css_bytes = len(css.encode('utf-8'))
            if css_bytes > 20480:
                self._logger.warning(f"CSS size {css_bytes} bytes exceeds 20KB limit, may be rejected")
            
            payload = {"css": css}
            self._logger.debug(f"Setting channel CSS: {css_bytes} bytes")
            await self._connector._socket.emit("setChannelCSS", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setChannelCSS",
                    details={"size_bytes": css_bytes}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set channel CSS: {e}", exc_info=True)
            return False
    
    async def set_channel_js(self, js: str) -> bool:
        """
        Set channel custom JavaScript.
        Requires rank 3+ (admin).
        CyTube has a 20KB limit on JS content.
        
        Args:
            js: JavaScript content (max ~20KB)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set JS: not connected")
            return False
        
        try:
            # Check size (20KB = 20480 bytes)
            js_bytes = len(js.encode('utf-8'))
            if js_bytes > 20480:
                self._logger.warning(f"JS size {js_bytes} bytes exceeds 20KB limit, may be rejected")
            
            payload = {"js": js}
            self._logger.debug(f"Setting channel JS: {js_bytes} bytes")
            await self._connector._socket.emit("setChannelJS", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setChannelJS",
                    details={"size_bytes": js_bytes}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set channel JS: {e}", exc_info=True)
            return False
    
    async def set_options(self, options: Dict[str, Any]) -> bool:
        """
        Update channel options.
        Requires rank 3+ (admin).
        
        Common options include:
        - allow_voteskip: bool - Enable voteskip
        - voteskip_ratio: float - Ratio needed to skip (0.0-1.0)
        - afk_timeout: int - AFK timeout in seconds
        - pagetitle: str - Channel page title
        - maxlength: int - Max video length in seconds (0 = unlimited)
        - externalcss: str - External CSS URL
        - externaljs: str - External JS URL
        - chat_antiflood: bool - Enable chat antiflood
        - chat_antiflood_params: dict - Antiflood parameters
          - burst: int - Max messages in burst
          - sustained: int - Max sustained rate
          - cooldown: int - Cooldown in seconds
        - show_public: bool - Show in public channel list
        - enable_link_regex: bool - Enable link filtering
        - password: str - Channel password (empty = no password)
        
        Args:
            options: Dictionary of option key-value pairs
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set options: not connected")
            return False
        
        try:
            self._logger.debug(f"Setting channel options: {list(options.keys())}")
            await self._connector._socket.emit("setOptions", options)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setOptions",
                    details={"option_count": len(options)}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set options: {e}", exc_info=True)
            return False
    
    async def set_permissions(self, permissions: Dict[str, int]) -> bool:
        """
        Update channel permissions.
        Requires rank 3+ (admin).
        
        Permissions map actions to minimum rank required.
        Common permission keys:
        - seeplaylist: View playlist
        - playlistadd: Add videos to playlist
        - playlistnext: Add videos to play next
        - playlistmove: Move videos in playlist
        - playlistdelete: Delete videos from playlist
        - playlistjump: Jump to video in playlist
        - playlistshuffle: Shuffle playlist
        - playlistclear: Clear playlist
        - pollctl: Control polls
        - pollvote: Vote in polls
        - viewhiddenpoll: View hidden poll results
        - voteskip: Vote to skip
        - playlistaddlist: Add multiple videos
        - oekaki: Use drawing feature
        - shout: Use shout feature
        - kick: Kick users
        - ban: Ban users
        - mute: Mute users
        - settemp: Set temporary rank
        - filteradd: Add chat filters
        - filteredit: Edit chat filters
        - filterdelete: Delete chat filters
        - emoteupdaute: Update emotes
        - emotedelete: Delete emotes
        - exceedmaxlength: Add videos exceeding max length
        - addnontemp: Add non-temporary media
        
        Args:
            permissions: Dictionary mapping permission names to rank levels
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set permissions: not connected")
            return False
        
        try:
            self._logger.debug(f"Setting permissions: {list(permissions.keys())}")
            await self._connector._socket.emit("setPermissions", permissions)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setPermissions",
                    details={"permission_count": len(permissions)}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set permissions: {e}", exc_info=True)
            return False
    
    async def update_emote(self, name: str, image: str, source: str = "imgur") -> bool:
        """
        Add or update a channel emote.
        Requires rank 3+ (admin).
        
        Args:
            name: Emote name (without colons, e.g. "Kappa")
            image: Image URL or ID (depends on source)
            source: Image source ("imgur", "url", etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot update emote: not connected")
            return False
        
        try:
            payload = {
                "name": name,
                "image": image,
                "source": source
            }
            self._logger.debug(f"Updating emote: {name} from {source}")
            await self._connector._socket.emit("updateEmote", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="updateEmote",
                    target=name,
                    details={"image": image, "source": source}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to update emote: {e}", exc_info=True)
            return False
    
    async def remove_emote(self, name: str) -> bool:
        """
        Remove a channel emote.
        Requires rank 3+ (admin).
        
        Args:
            name: Emote name to remove
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot remove emote: not connected")
            return False
        
        try:
            payload = {"name": name}
            self._logger.debug(f"Removing emote: {name}")
            await self._connector._socket.emit("removeEmote", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="removeEmote",
                    target=name
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to remove emote: {e}", exc_info=True)
            return False
    
    async def add_filter(
        self,
        name: str,
        source: str,
        flags: str,
        replace: str,
        filterlinks: bool = False,
        active: bool = True
    ) -> bool:
        """
        Add a chat filter.
        Requires rank 3+ (admin).
        
        Args:
            name: Filter name
            source: Regex pattern to match
            flags: Regex flags (e.g., "gi" for global case-insensitive)
            replace: Replacement text
            filterlinks: Whether to filter links
            active: Whether filter is active
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot add filter: not connected")
            return False
        
        try:
            payload = {
                "name": name,
                "source": source,
                "flags": flags,
                "replace": replace,
                "filterlinks": filterlinks,
                "active": active
            }
            self._logger.debug(f"Adding chat filter: {name}")
            await self._connector._socket.emit("addFilter", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="addFilter",
                    target=name,
                    details={"source": source, "flags": flags, "replace": replace}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to add filter: {e}", exc_info=True)
            return False
    
    async def update_filter(
        self,
        name: str,
        source: str,
        flags: str,
        replace: str,
        filterlinks: bool = False,
        active: bool = True
    ) -> bool:
        """
        Update an existing chat filter.
        Requires rank 3+ (admin).
        
        Args:
            name: Filter name
            source: Regex pattern to match
            flags: Regex flags (e.g., "gi" for global case-insensitive)
            replace: Replacement text
            filterlinks: Whether to filter links
            active: Whether filter is active
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot update filter: not connected")
            return False
        
        try:
            payload = {
                "name": name,
                "source": source,
                "flags": flags,
                "replace": replace,
                "filterlinks": filterlinks,
                "active": active
            }
            self._logger.debug(f"Updating chat filter: {name}")
            await self._connector._socket.emit("updateFilter", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="updateFilter",
                    target=name,
                    details={"source": source, "flags": flags, "replace": replace}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to update filter: {e}", exc_info=True)
            return False
    
    async def remove_filter(self, name: str) -> bool:
        """
        Remove a chat filter.
        Requires rank 3+ (admin).
        
        Args:
            name: Filter name to remove
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot remove filter: not connected")
            return False
        
        try:
            payload = {"name": name}
            self._logger.debug(f"Removing chat filter: {name}")
            await self._connector._socket.emit("removeFilter", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="removeFilter",
                    target=name
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to remove filter: {e}", exc_info=True)
            return False
    
    # PHASE 3: Advanced Admin Functions (Rank 2-4+)
    
    async def new_poll(
        self,
        title: str,
        options: List[str],
        obscured: bool = False,
        timeout: int = 0
    ) -> bool:
        """
        Create a new poll.
        Requires rank 2+ (moderator).
        
        Args:
            title: Poll question
            options: List of poll options
            obscured: Whether to hide results until poll closes
            timeout: Auto-close timeout in seconds (0 = no timeout)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot create poll: not connected")
            return False
        
        try:
            payload = {
                "title": title,
                "opts": options,
                "obscured": obscured,
                "timeout": timeout
            }
            self._logger.debug(f"Creating poll: {title} with {len(options)} options")
            await self._connector._socket.emit("newPoll", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="newPoll",
                    details={"title": title, "options": len(options)}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to create poll: {e}", exc_info=True)
            return False
    
    async def vote(self, option: int) -> bool:
        """
        Vote in the active poll.
        Requires rank 0+ (guest).
        
        Args:
            option: Option index to vote for (0-based)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot vote: not connected")
            return False
        
        try:
            payload = {"option": option}
            self._logger.debug(f"Voting for option {option}")
            await self._connector._socket.emit("vote", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to vote: {e}", exc_info=True)
            return False
    
    async def close_poll(self) -> bool:
        """
        Close the active poll.
        Requires rank 2+ (moderator).
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot close poll: not connected")
            return False
        
        try:
            self._logger.debug("Closing active poll")
            await self._connector._socket.emit("closePoll", {})
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="closePoll"
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to close poll: {e}", exc_info=True)
            return False
    
    async def set_channel_rank(self, username: str, rank: int) -> bool:
        """
        Set a user's permanent channel rank.
        Requires rank 4+ (owner).
        
        Args:
            username: User to modify
            rank: Rank level (0-4+)
                0: Guest
                1: Registered
                2: Moderator
                3: Admin
                4+: Owner
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot set channel rank: not connected")
            return False
        
        try:
            payload = {"name": username, "rank": rank}
            self._logger.debug(f"Setting {username} to rank {rank}")
            await self._connector._socket.emit("setChannelRank", payload)
            
            # Audit log admin operation
            if self._audit_logger:
                self._audit_logger.log_admin_operation(
                    operation="setChannelRank",
                    target=username,
                    details={"rank": rank}
                )
            
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to set channel rank: {e}", exc_info=True)
            return False
    
    async def request_channel_ranks(self) -> bool:
        """
        Request list of users with elevated channel ranks.
        Requires rank 4+ (owner).
        Server will respond with channelRankFail or channelRanks event.
        
        Returns:
            True if request sent, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot request channel ranks: not connected")
            return False
        
        try:
            self._logger.debug("Requesting channel ranks")
            await self._connector._socket.emit("requestChannelRanks", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to request channel ranks: {e}", exc_info=True)
            return False
    
    async def request_banlist(self) -> bool:
        """
        Request channel ban list.
        Requires rank 3+ (admin).
        Server will respond with banlist event.
        
        Returns:
            True if request sent, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot request banlist: not connected")
            return False
        
        try:
            self._logger.debug("Requesting ban list")
            await self._connector._socket.emit("requestBanlist", {})
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to request banlist: {e}", exc_info=True)
            return False
    
    async def unban(self, ban_id: int) -> bool:
        """
        Remove a ban.
        Requires rank 3+ (admin).
        
        Args:
            ban_id: ID of the ban to remove (from banlist event)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot unban: not connected")
            return False
        
        try:
            payload = {"id": ban_id}
            self._logger.debug(f"Unbanning ID {ban_id}")
            await self._connector._socket.emit("unban", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to unban: {e}", exc_info=True)
            return False
    
    async def read_chan_log(self, count: int = 100) -> bool:
        """
        Request channel event log.
        Requires rank 3+ (admin).
        Server will respond with readChanLog event.
        
        Args:
            count: Number of log entries to retrieve (default 100)
            
        Returns:
            True if request sent, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot read channel log: not connected")
            return False
        
        try:
            payload = {"count": count}
            self._logger.debug(f"Requesting {count} channel log entries")
            await self._connector._socket.emit("readChanLog", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to read channel log: {e}", exc_info=True)
            return False
    
    async def search_library(
        self,
        query: str,
        source: str = "library"
    ) -> bool:
        """
        Search channel library.
        Requires appropriate rank based on channel permissions.
        Server will respond with searchResults event.
        
        Args:
            query: Search query
            source: Search source ("library" or media provider like "yt", "vm")
            
        Returns:
            True if request sent, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot search library: not connected")
            return False
        
        try:
            payload = {"query": query, "source": source}
            self._logger.debug(f"Searching library: {query} in {source}")
            await self._connector._socket.emit("searchMedia", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to search library: {e}", exc_info=True)
            return False
    
    async def delete_from_library(self, media_id: str) -> bool:
        """
        Delete item from channel library.
        Requires rank 2+ (moderator).
        
        Args:
            media_id: ID of media item to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self._connector.is_connected:
            self._logger.error("Cannot delete from library: not connected")
            return False
        
        try:
            payload = {"id": media_id}
            self._logger.debug(f"Deleting library item: {media_id}")
            await self._connector._socket.emit("uncache", payload)
            return True
        
        except Exception as e:
            self._logger.error(f"Failed to delete from library: {e}", exc_info=True)
            return False


__all__ = ["CytubeEventSender"]

"""State Manager - Persist CyTube channel state to NATS KV stores.

This module tracks and persists channel state (emotes, playlist, userlist)
to NATS key-value stores, allowing downstream applications to query state
without directly connecting to the CyTube instance.
"""

import json
import logging
from typing import Any

from nats.errors import NoRespondersError
from nats.js import api
from nats.js.errors import ServiceUnavailableError
from nats.js.kv import KeyValue

from .nats_client import NatsClient


class StateManager:
    """Manage CyTube channel state in NATS key-value stores.

    Maintains three KV buckets for channel state:
    - emotes: Channel emote list
    - playlist: Current playlist items
    - userlist: Connected users

    Attributes:
        nats_client: NATS client for KV operations.
        channel: CyTube channel name.
        logger: Logger instance.
        is_running: Whether state manager is active.

    Examples:
        >>> manager = StateManager(nats_client, "mychannel", logger)
        >>> await manager.start()
        >>> await manager.update_emotes(emote_list)
        >>> await manager.stop()
    """

    def __init__(
        self,
        nats_client: NatsClient,
        channel: str,
        logger: logging.Logger,
        counting_config=None,
    ):
        """Initialize state manager.

        Args:
            nats_client: NATS client instance.
            channel: CyTube channel name.
            logger: Logger for structured output.
            counting_config: Optional StateCountingConfig for filtering counts.
        """
        self._nats = nats_client
        self._channel = channel
        self._logger = logger
        self._counting_config = counting_config
        self._running = False

        # KV bucket handles
        self._kv_emotes: KeyValue | None = None
        self._kv_playlist: KeyValue | None = None
        self._kv_userlist: KeyValue | None = None

        # State tracking
        self._emotes: list[dict[str, Any]] = []
        self._playlist: list[dict[str, Any]] = []
        self._users: dict[str, dict[str, Any]] = {}  # username -> user data

    @property
    def is_running(self) -> bool:
        """Check if state manager is running.

        Returns:
            True if started and managing state, False otherwise.
        """
        return self._running

    def users_count(self) -> int:
        """Get count of users with optional filtering.

        Applies filters from counting_config:
        - users_exclude_afk: Exclude AFK users
        - users_min_rank: Minimum rank to include

        Returns:
            Filtered count of users.

        Examples:
            >>> count = manager.users_count()
            >>> print(f"Active users: {count}")
        """
        if not self._counting_config:
            return len(self._users)

        count = 0
        for user in self._users.values():
            # Check rank filter
            user_rank = user.get("rank", 0)
            if user_rank < self._counting_config.users_min_rank:
                continue

            # Check AFK filter
            if self._counting_config.users_exclude_afk:
                meta = user.get("meta", {})
                if meta.get("afk", False):
                    continue

            count += 1

        return count

    def playlist_count(self) -> int:
        """Get count of playlist items with optional filtering.

        Applies filters from counting_config:
        - playlist_exclude_temp: Exclude temporary items
        - playlist_max_duration: Maximum duration in seconds (0=no limit)

        Returns:
            Filtered count of playlist items.

        Examples:
            >>> count = manager.playlist_count()
            >>> print(f"Playlist items: {count}")
        """
        if not self._counting_config:
            return len(self._playlist)

        count = 0
        for item in self._playlist:
            # Check temp filter
            if self._counting_config.playlist_exclude_temp:
                if item.get("temp", False):
                    continue

            # Check duration filter
            if self._counting_config.playlist_max_duration > 0:
                media = item.get("media", {})
                duration = media.get("seconds", 0)
                if duration > self._counting_config.playlist_max_duration:
                    continue

            count += 1

        return count

    def emotes_count(self) -> int:
        """Get count of emotes with optional filtering.

        Applies filters from counting_config:
        - emotes_only_enabled: Only count enabled emotes

        Returns:
            Filtered count of emotes.

        Examples:
            >>> count = manager.emotes_count()
            >>> print(f"Emotes: {count}")
        """
        if not self._counting_config:
            return len(self._emotes)

        if not self._counting_config.emotes_only_enabled:
            return len(self._emotes)

        # Count only enabled emotes
        count = 0
        for emote in self._emotes:
            if not emote.get("disabled", False):
                count += 1

        return count

    @property
    def stats(self) -> dict[str, int]:
        """Get state statistics using configured counting filters.

        Returns:
            Dictionary with emote_count, playlist_count, user_count.
        """
        return {
            "emote_count": self.emotes_count(),
            "playlist_count": self.playlist_count(),
            "user_count": self.users_count(),
        }

    async def start(self) -> None:
        """Start state manager and create KV buckets.

        Creates or binds to NATS JetStream KV buckets for state storage.
        Buckets are named: cytube_{channel}_emotes, cytube_{channel}_playlist,
        cytube_{channel}_userlist.

        Raises:
            RuntimeError: If NATS is not connected or JetStream unavailable.
        """
        if self._running:
            self._logger.debug("State manager already running")
            return

        if not self._nats.is_connected:
            raise RuntimeError("NATS client not connected")

        try:
            self._logger.info(f"Starting state manager for channel: {self._channel}")

            # Get JetStream context
            js = self._nats._nc.jetstream()

            # Create or bind KV buckets
            bucket_prefix = f"cytube_{self._channel}"

            # Emotes bucket
            try:
                self._kv_emotes = await js.key_value(bucket=f"{bucket_prefix}_emotes")
                self._logger.debug("Bound to existing emotes KV bucket")
            except Exception:
                self._kv_emotes = await js.create_key_value(
                    config=api.KeyValueConfig(
                        bucket=f"{bucket_prefix}_emotes",
                        description=f"CyTube {self._channel} emotes",
                        max_value_size=1024 * 1024,  # 1MB max
                    )
                )
                self._logger.info("Created emotes KV bucket")

            # Playlist bucket
            try:
                self._kv_playlist = await js.key_value(bucket=f"{bucket_prefix}_playlist")
                self._logger.debug("Bound to existing playlist KV bucket")
            except Exception:
                self._kv_playlist = await js.create_key_value(
                    config=api.KeyValueConfig(
                        bucket=f"{bucket_prefix}_playlist",
                        description=f"CyTube {self._channel} playlist",
                        max_value_size=10 * 1024 * 1024,  # 10MB max
                    )
                )
                self._logger.info("Created playlist KV bucket")

            # Userlist bucket
            try:
                self._kv_userlist = await js.key_value(bucket=f"{bucket_prefix}_userlist")
                self._logger.debug("Bound to existing userlist KV bucket")
            except Exception:
                self._kv_userlist = await js.create_key_value(
                    config=api.KeyValueConfig(
                        bucket=f"{bucket_prefix}_userlist",
                        description=f"CyTube {self._channel} users",
                        max_value_size=1024 * 1024,  # 1MB max
                    )
                )
                self._logger.info("Created userlist KV bucket")

            self._running = True
            self._logger.info("State manager started")

        except (ServiceUnavailableError, NoRespondersError) as e:
            self._logger.error(
                "JetStream not available - state persistence disabled. "
                "Ensure NATS server is running with JetStream enabled (use -js flag)."
            )
            raise RuntimeError(
                "JetStream not available. NATS server must be started with JetStream enabled. "
                "Run 'nats-server -js' or configure JetStream in nats-server.conf"
            ) from e

        except Exception as e:
            self._logger.error(f"Failed to start state manager: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop state manager.

        Does not delete KV buckets - state persists for downstream consumers.
        """
        if not self._running:
            return

        self._logger.info("Stopping state manager")

        self._kv_emotes = None
        self._kv_playlist = None
        self._kv_userlist = None
        self._running = False

        self._logger.info("State manager stopped")

    # ========================================================================
    # Emote Management
    # ========================================================================

    async def update_emotes(self, emotes: list[dict[str, Any]]) -> None:
        """Update full emote list.

        Called when 'emoteList' event received from CyTube.

        Args:
            emotes: List of emote objects with 'name', 'image', etc.

        Examples:
            >>> emotes = [{"name": "Kappa", "image": "..."}]
            >>> await manager.update_emotes(emotes)
        """
        if not self._running:
            self._logger.warning("Cannot update emotes: state manager not running")
            return

        try:
            self._emotes = emotes

            # Store as JSON
            emotes_json = json.dumps(emotes).encode()
            await self._kv_emotes.put("list", emotes_json)

            self._logger.info(f"Updated emotes: {len(emotes)} emotes")

        except Exception as e:
            self._logger.error(f"Failed to update emotes: {e}", exc_info=True)

    # ========================================================================
    # Playlist Management
    # ========================================================================

    async def set_playlist(self, playlist: list[dict[str, Any]]) -> None:
        """Set entire playlist.

        Called when 'playlist' event received (initial load).

        Args:
            playlist: List of media items with 'uid', 'title', 'duration', etc.

        Examples:
            >>> items = [{"uid": "abc", "title": "Video 1"}]
            >>> await manager.set_playlist(items)
        """
        if not self._running:
            self._logger.warning("Cannot set playlist: state manager not running")
            return

        try:
            self._playlist = playlist

            # Store as JSON
            playlist_json = json.dumps(playlist).encode()
            await self._kv_playlist.put("items", playlist_json)

            self._logger.info(f"Set playlist: {len(playlist)} items")

        except Exception as e:
            self._logger.error(f"Failed to set playlist: {e}", exc_info=True)

    async def add_playlist_item(self, item: dict[str, Any], after: str | None = None) -> None:
        """Add item to playlist.

        Called when 'queue' event received.

        Args:
            item: Media item to add.
            after: UID of item to insert after, or None for end.

        Examples:
            >>> item = {"uid": "xyz", "title": "New Video"}
            >>> await manager.add_playlist_item(item)
        """
        if not self._running:
            return

        try:
            if after is None:
                # Append to end
                self._playlist.append(item)
            else:
                # Insert after specified UID
                for i, existing in enumerate(self._playlist):
                    if existing.get("uid") == after:
                        self._playlist.insert(i + 1, item)
                        break
                else:
                    # UID not found, append
                    self._playlist.append(item)

            # Update KV store
            playlist_json = json.dumps(self._playlist).encode()
            await self._kv_playlist.put("items", playlist_json)

            self._logger.debug(f"Added playlist item: {item.get('uid')} ({item.get('title', 'Unknown')})")

        except Exception as e:
            self._logger.error(f"Failed to add playlist item: {e}", exc_info=True)

    async def remove_playlist_item(self, uid: str) -> None:
        """Remove item from playlist.

        Called when 'delete' event received.

        Args:
            uid: UID of item to remove.

        Examples:
            >>> await manager.remove_playlist_item("xyz")
        """
        if not self._running:
            return

        try:
            self._playlist = [item for item in self._playlist if item.get("uid") != uid]

            # Update KV store
            playlist_json = json.dumps(self._playlist).encode()
            await self._kv_playlist.put("items", playlist_json)

            self._logger.debug(f"Removed playlist item: {uid}")

        except Exception as e:
            self._logger.error(f"Failed to remove playlist item: {e}", exc_info=True)

    async def move_playlist_item(self, uid: str, after: str) -> None:
        """Move item in playlist.

        Called when 'moveMedia' event received.

        Args:
            uid: UID of item to move.
            after: UID to place after, or "prepend"/"append".

        Examples:
            >>> await manager.move_playlist_item("xyz", "abc")
        """
        if not self._running:
            return

        try:
            # Find and remove item
            item = None
            for i, existing in enumerate(self._playlist):
                if existing.get("uid") == uid:
                    item = self._playlist.pop(i)
                    break

            if item is None:
                self._logger.warning(f"Cannot move item {uid}: not found")
                return

            # Insert at new position
            if after == "prepend":
                self._playlist.insert(0, item)
            elif after == "append":
                self._playlist.append(item)
            else:
                # Insert after specified UID
                for i, existing in enumerate(self._playlist):
                    if existing.get("uid") == after:
                        self._playlist.insert(i + 1, item)
                        break
                else:
                    # UID not found, append
                    self._playlist.append(item)

            # Update KV store
            playlist_json = json.dumps(self._playlist).encode()
            await self._kv_playlist.put("items", playlist_json)

            self._logger.debug(f"Moved playlist item {uid} after {after}")

        except Exception as e:
            self._logger.error(f"Failed to move playlist item: {e}", exc_info=True)

    async def clear_playlist(self) -> None:
        """Clear entire playlist.

        Called when 'playlist' event with empty list received.
        """
        if not self._running:
            return

        try:
            self._playlist = []

            # Update KV store
            playlist_json = json.dumps([]).encode()
            await self._kv_playlist.put("items", playlist_json)

            self._logger.debug("Cleared playlist")

        except Exception as e:
            self._logger.error(f"Failed to clear playlist: {e}", exc_info=True)

    # ========================================================================
    # Userlist Management
    # ========================================================================

    async def set_userlist(self, users: list[dict[str, Any]]) -> None:
        """Set entire userlist.

        Called when 'userlist' event received (initial load).

        Args:
            users: List of user objects with 'name', 'rank', etc.

        Examples:
            >>> users = [{"name": "Alice", "rank": 2}]
            >>> await manager.set_userlist(users)
        """
        if not self._running:
            self._logger.warning("Cannot set userlist: state manager not running")
            return

        try:
            self._users = {user.get("name"): user for user in users if user.get("name")}

            # Store as JSON
            userlist_json = json.dumps(list(self._users.values())).encode()
            await self._kv_userlist.put("users", userlist_json)

            self._logger.info(f"Set userlist: {len(self._users)} users")

        except Exception as e:
            self._logger.error(f"Failed to set userlist: {e}", exc_info=True)

    async def add_user(self, user: dict[str, Any]) -> None:
        """Add user to userlist.

        Called when 'addUser' event received.

        Args:
            user: User object with 'name', 'rank', etc.

        Examples:
            >>> user = {"name": "Bob", "rank": 1}
            >>> await manager.add_user(user)
        """
        if not self._running:
            return

        try:
            username = user.get("name")
            if not username:
                return

            self._users[username] = user

            # Update KV store
            userlist_json = json.dumps(list(self._users.values())).encode()
            await self._kv_userlist.put("users", userlist_json)

            self._logger.debug(f"Added user: {username}")

        except Exception as e:
            self._logger.error(f"Failed to add user: {e}", exc_info=True)

    async def remove_user(self, username: str) -> None:
        """Remove user from userlist.

        Called when 'userLeave' event received.

        Args:
            username: Username to remove.

        Examples:
            >>> await manager.remove_user("Bob")
        """
        if not self._running:
            return

        try:
            if username in self._users:
                del self._users[username]

                # Update KV store
                userlist_json = json.dumps(list(self._users.values())).encode()
                await self._kv_userlist.put("users", userlist_json)

                self._logger.debug(f"Removed user: {username}")

        except Exception as e:
            self._logger.error(f"Failed to remove user: {e}", exc_info=True)

    async def update_user(self, user: dict[str, Any]) -> None:
        """Update user data.

        Called when user properties change (rank, meta, etc).

        Args:
            user: Updated user object.

        Examples:
            >>> user = {"name": "Bob", "rank": 3}
            >>> await manager.update_user(user)
        """
        if not self._running:
            return

        try:
            username = user.get("name")
            if not username:
                return

            self._users[username] = user

            # Update KV store
            userlist_json = json.dumps(list(self._users.values())).encode()
            await self._kv_userlist.put("users", userlist_json)

            self._logger.debug(f"Updated user: {username}")

        except Exception as e:
            self._logger.error(f"Failed to update user: {e}", exc_info=True)

    # ========================================================================
    # State Retrieval
    # ========================================================================

    def get_emotes(self) -> list[dict[str, Any]]:
        """Get current emote list.

        Returns:
            List of emote dictionaries.
        """
        return self._emotes.copy()

    def get_playlist(self) -> list[dict[str, Any]]:
        """Get current playlist.

        Returns:
            List of playlist item dictionaries.
        """
        return self._playlist.copy()

    def get_userlist(self) -> list[dict[str, Any]]:
        """Get current userlist.

        Returns:
            List of user dictionaries.
        """
        return list(self._users.values())

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Get specific user by username.

        Args:
            username: Username to look up.

        Returns:
            User dictionary if found, None otherwise.

        Examples:
            >>> user = manager.get_user("Alice")
            >>> if user:
            ...     print(f"Rank: {user['rank']}")
        """
        return self._users.get(username)

    def get_user_profile(self, username: str) -> dict[str, Any] | None:
        """Get user's profile (avatar and bio).

        Args:
            username: Username to look up.

        Returns:
            Profile dictionary with 'image' and 'text' keys, or None if not found.

        Examples:
            >>> profile = manager.get_user_profile("Alice")
            >>> if profile:
            ...     print(f"Avatar: {profile.get('image')}")
            ...     print(f"Bio: {profile.get('text')}")
        """
        user = self._users.get(username)
        if user:
            return user.get("profile", {})
        return None

    def get_all_profiles(self) -> dict[str, dict[str, Any]]:
        """Get all user profiles.

        Returns:
            Dictionary mapping username to profile dict.

        Examples:
            >>> profiles = manager.get_all_profiles()
            >>> for username, profile in profiles.items():
            ...     print(f"{username}: {profile.get('image')}")
        """
        profiles = {}
        for username, user in self._users.items():
            profile = user.get("profile")
            if profile:
                profiles[username] = profile
        return profiles

    def get_all_state(self) -> dict[str, list[dict[str, Any]]]:
        """Get all channel state.

        Returns:
            Dictionary with emotes, playlist, and userlist.
        """
        return {
            "emotes": self.get_emotes(),
            "playlist": self.get_playlist(),
            "userlist": self.get_userlist()
        }


__all__ = ["StateManager"]



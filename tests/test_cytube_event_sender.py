"""Unit tests for CytubeEventSender."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kryten.cytube_event_sender import CytubeEventSender


@pytest.fixture
def mock_connector():
    """Create a mock CytubeConnector with socket."""
    connector = MagicMock()
    connector.is_connected = True
    connector._socket = AsyncMock()
    return connector


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def sender(mock_connector, mock_logger):
    """Create a CytubeEventSender with mocked dependencies."""
    return CytubeEventSender(mock_connector, mock_logger)


class TestChatMethods:
    """Tests for chat-related methods."""

    @pytest.mark.asyncio
    async def test_send_chat_success(self, sender, mock_connector):
        """Test sending a chat message."""
        result = await sender.send_chat("Hello, world!")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "chatMsg",
            {"msg": "Hello, world!"}
        )

    @pytest.mark.asyncio
    async def test_send_chat_when_disconnected(self, sender, mock_connector):
        """Test sending chat when not connected."""
        mock_connector.is_connected = False
        
        result = await sender.send_chat("Hello")
        
        assert result is False
        mock_connector._socket.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_pm_success(self, sender, mock_connector):
        """Test sending a private message."""
        result = await sender.send_pm("Alice", "Secret message")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "pm",
            {"to": "Alice", "msg": "Secret message"}
        )

    @pytest.mark.asyncio
    async def test_send_pm_when_disconnected(self, sender, mock_connector):
        """Test sending PM when not connected."""
        mock_connector.is_connected = False
        
        result = await sender.send_pm("Bob", "Hello")
        
        assert result is False
        mock_connector._socket.emit.assert_not_called()


class TestPlaylistMethods:
    """Tests for playlist-related methods."""

    @pytest.mark.asyncio
    async def test_add_video_default_position(self, sender, mock_connector):
        """Test adding a video with default position."""
        result = await sender.add_video("https://youtube.com/watch?v=test")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "queue",
            {
                "id": "https://youtube.com/watch?v=test",
                "pos": "end",
                "temp": False
            }
        )

    @pytest.mark.asyncio
    async def test_add_video_with_position(self, sender, mock_connector):
        """Test adding a video at specific position."""
        result = await sender.add_video("yt:abc123", position="next")
        
        assert result is True
        call_args = mock_connector._socket.emit.call_args[0]
        assert call_args[0] == "queue"
        assert call_args[1]["id"] == "yt:abc123"
        assert call_args[1]["pos"] == "next"

    @pytest.mark.asyncio
    async def test_add_video_temp(self, sender, mock_connector):
        """Test adding a temporary video."""
        result = await sender.add_video("yt:xyz789", temp=True)
        
        assert result is True
        call_args = mock_connector._socket.emit.call_args[0]
        assert call_args[1]["temp"] is True

    @pytest.mark.asyncio
    async def test_delete_video(self, sender, mock_connector):
        """Test deleting a video from playlist."""
        result = await sender.delete_video("video-uid-123")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "delete",
            {"uid": "video-uid-123"}
        )

    @pytest.mark.asyncio
    async def test_move_video(self, sender, mock_connector):
        """Test moving a video in playlist."""
        result = await sender.move_video("video-uid-123", after="video-uid-456")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "moveMedia",
            {"from": "video-uid-123", "after": "video-uid-456"}
        )

    @pytest.mark.asyncio
    async def test_jump_to(self, sender, mock_connector):
        """Test jumping to a specific video."""
        result = await sender.jump_to("video-uid-789")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "jumpTo",
            {"uid": "video-uid-789"}
        )

    @pytest.mark.asyncio
    async def test_clear_playlist(self, sender, mock_connector):
        """Test clearing the playlist."""
        result = await sender.clear_playlist()
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with("clearPlaylist", {})

    @pytest.mark.asyncio
    async def test_shuffle_playlist(self, sender, mock_connector):
        """Test shuffling the playlist."""
        result = await sender.shuffle_playlist()
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with("shufflePlaylist", {})

    @pytest.mark.asyncio
    async def test_set_temp_true(self, sender, mock_connector):
        """Test setting video as temporary."""
        result = await sender.set_temp("video-uid-123", True)
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "setTemp",
            {"uid": "video-uid-123", "temp": True}
        )

    @pytest.mark.asyncio
    async def test_set_temp_false(self, sender, mock_connector):
        """Test setting video as permanent."""
        result = await sender.set_temp("video-uid-456", False)
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "setTemp",
            {"uid": "video-uid-456", "temp": False}
        )


class TestPlaybackMethods:
    """Tests for playback control methods."""

    @pytest.mark.asyncio
    async def test_pause(self, sender, mock_connector):
        """Test pausing playback."""
        result = await sender.pause()
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "pause",
            {}
        )

    @pytest.mark.asyncio
    async def test_play(self, sender, mock_connector):
        """Test resuming playback."""
        result = await sender.play()
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "play",
            {}
        )

    @pytest.mark.asyncio
    async def test_seek_to(self, sender, mock_connector):
        """Test seeking to a specific time."""
        result = await sender.seek_to(42.5)
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "seekTo",
            {"time": 42.5}
        )


class TestModerationMethods:
    """Tests for moderation methods."""

    @pytest.mark.asyncio
    async def test_kick_user_with_reason(self, sender, mock_connector):
        """Test kicking a user with reason."""
        result = await sender.kick_user("baduser", "Spamming")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "kick",
            {"name": "baduser", "reason": "Spamming"}
        )

    @pytest.mark.asyncio
    async def test_kick_user_without_reason(self, sender, mock_connector):
        """Test kicking a user without reason."""
        result = await sender.kick_user("baduser")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "kick",
            {"name": "baduser"}
        )

    @pytest.mark.asyncio
    async def test_ban_user_with_reason(self, sender, mock_connector):
        """Test banning a user with reason."""
        result = await sender.ban_user("troll", "Harassment")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "ban",
            {"name": "troll", "reason": "Harassment"}
        )

    @pytest.mark.asyncio
    async def test_ban_user_without_reason(self, sender, mock_connector):
        """Test banning a user without reason."""
        result = await sender.ban_user("troll")
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "ban",
            {"name": "troll"}
        )

    @pytest.mark.asyncio
    async def test_voteskip(self, sender, mock_connector):
        """Test voting to skip current video."""
        result = await sender.voteskip()
        
        assert result is True
        mock_connector._socket.emit.assert_called_once_with(
            "voteskip",
            {}
        )


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_send_when_socket_raises_exception(self, sender, mock_connector, mock_logger):
        """Test handling socket.emit exceptions."""
        mock_connector._socket.emit.side_effect = Exception("Socket error")
        
        result = await sender.send_chat("Test")
        
        assert result is False
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_video_when_disconnected(self, sender, mock_connector):
        """Test adding video when not connected."""
        mock_connector.is_connected = False
        
        result = await sender.add_video("yt:test")
        
        assert result is False
        mock_connector._socket.emit.assert_not_called()

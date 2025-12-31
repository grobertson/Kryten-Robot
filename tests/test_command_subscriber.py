"""Unit tests for CommandSubscriber."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from kryten.command_subscriber import CommandSubscriber


@pytest.fixture
def mock_sender():
    """Create a mock CytubeEventSender."""
    sender = AsyncMock()
    sender.send_chat = AsyncMock(return_value=True)
    sender.send_pm = AsyncMock(return_value=True)
    sender.add_video = AsyncMock(return_value=True)
    sender.delete_video = AsyncMock(return_value=True)
    sender.move_video = AsyncMock(return_value=True)
    sender.jump_to = AsyncMock(return_value=True)
    sender.clear_playlist = AsyncMock(return_value=True)
    sender.shuffle_playlist = AsyncMock(return_value=True)
    sender.set_temp = AsyncMock(return_value=True)
    sender.pause = AsyncMock(return_value=True)
    sender.play = AsyncMock(return_value=True)
    sender.seek_to = AsyncMock(return_value=True)
    sender.kick_user = AsyncMock(return_value=True)
    sender.ban_user = AsyncMock(return_value=True)
    sender.voteskip = AsyncMock(return_value=True)
    return sender


@pytest.fixture
def mock_nats():
    """Create a mock NatsClient."""
    nats = AsyncMock()
    nats.subscribe = AsyncMock()
    nats.unsubscribe = AsyncMock()
    return nats


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def subscriber(mock_sender, mock_nats, mock_logger):
    """Create a CommandSubscriber with mocked dependencies."""
    return CommandSubscriber(mock_sender, mock_nats, mock_logger, "testdomain", "testchannel")


class TestInitialization:
    """Tests for subscriber initialization."""

    def test_init(self, mock_sender, mock_nats, mock_logger):
        """Test basic initialization."""
        sub = CommandSubscriber(mock_sender, mock_nats, mock_logger, "mydomain", "mychannel")

        assert sub._sender == mock_sender
        assert sub._nats == mock_nats
        assert sub._logger == mock_logger
        assert sub._channel == "mychannel"
        assert sub._running is False
        assert sub._subscription is None


class TestStartStop:
    """Tests for starting and stopping the subscriber."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_commands(self, subscriber, mock_nats):
        """Test that start subscribes to correct subject."""
        await subscriber.start()

        assert subscriber._running is True
        mock_nats.subscribe.assert_called_once_with(
            "kryten.commands.cytube.testchannel.>", subscriber._handle_command
        )

    @pytest.mark.asyncio
    async def test_start_twice_does_nothing(self, subscriber, mock_nats):
        """Test that starting twice doesn't double-subscribe."""
        await subscriber.start()
        await subscriber.start()

        # Should only subscribe once
        assert mock_nats.subscribe.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self, subscriber, mock_nats):
        """Test that stop unsubscribes from commands."""
        mock_subscription = MagicMock()
        mock_nats.subscribe.return_value = mock_subscription

        await subscriber.start()
        await subscriber.stop()

        assert subscriber._running is False
        mock_nats.unsubscribe.assert_called_once_with(mock_subscription)
        assert subscriber._subscription is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, subscriber, mock_nats):
        """Test that stopping when not running is safe."""
        await subscriber.stop()

        assert subscriber._running is False
        mock_nats.unsubscribe.assert_not_called()


class TestCommandRouting:
    """Tests for routing commands to sender methods."""

    @pytest.mark.asyncio
    async def test_route_chat_command(self, subscriber, mock_sender):
        """Test routing a chat command."""
        command = {"action": "chat", "data": {"message": "Hello!"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.chat", data)

        mock_sender.send_chat.assert_called_once_with(message="Hello!")

    @pytest.mark.asyncio
    async def test_route_pm_command(self, subscriber, mock_sender):
        """Test routing a PM command."""
        command = {"action": "pm", "data": {"to": "Alice", "message": "Secret"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.pm", data)

        mock_sender.send_pm.assert_called_once_with(to="Alice", message="Secret")

    @pytest.mark.asyncio
    async def test_route_add_video_command(self, subscriber, mock_sender):
        """Test routing an add video command."""
        command = {
            "action": "queue",
            "data": {"url": "yt:test123", "position": "next", "temp": True},
        }
        data = json.dumps(command).encode()

        await subscriber._handle_command("kryten.commands.cytube.testchannel.queue", data)

        mock_sender.add_video.assert_called_once_with(url="yt:test123", position="next", temp=True)

    @pytest.mark.asyncio
    async def test_route_delete_video_command(self, subscriber, mock_sender):
        """Test routing a delete video command."""
        command = {"action": "delete", "data": {"uid": "video-123"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.delete", data)

        mock_sender.delete_video.assert_called_once_with(uid="video-123")

    @pytest.mark.asyncio
    async def test_route_move_video_command(self, subscriber, mock_sender):
        """Test routing a move video command."""
        command = {"action": "move", "data": {"uid": "video-1", "after": "video-2"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.move", data)

        mock_sender.move_video.assert_called_once_with(uid="video-1", after="video-2")

    @pytest.mark.asyncio
    async def test_route_jump_command(self, subscriber, mock_sender):
        """Test routing a jump to command."""
        command = {"action": "jump", "data": {"uid": "video-789"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.jump", data)

        mock_sender.jump_to.assert_called_once_with(uid="video-789")

    @pytest.mark.asyncio
    async def test_route_clear_playlist_command(self, subscriber, mock_sender):
        """Test routing a clear playlist command."""
        command = {"action": "clear", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.clear", data)

        mock_sender.clear_playlist.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_shuffle_command(self, subscriber, mock_sender):
        """Test routing a shuffle playlist command."""
        command = {"action": "shuffle", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.shuffle", data)

        mock_sender.shuffle_playlist.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_set_temp_command(self, subscriber, mock_sender):
        """Test routing a set temp command."""
        command = {"action": "setTemp", "data": {"uid": "video-123", "temp": True}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.setTemp", data)

        mock_sender.set_temp.assert_called_once_with(uid="video-123", temp=True)

    @pytest.mark.asyncio
    async def test_route_pause_command(self, subscriber, mock_sender):
        """Test routing a pause command."""
        command = {"action": "pause", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.pause", data)

        mock_sender.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_play_command(self, subscriber, mock_sender):
        """Test routing a play command."""
        command = {"action": "play", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.play", data)

        mock_sender.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_seek_command(self, subscriber, mock_sender):
        """Test routing a seek command."""
        command = {"action": "seek", "data": {"time": 42.5}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.seek", data)

        mock_sender.seek_to.assert_called_once_with(time=42.5)

    @pytest.mark.asyncio
    async def test_route_kick_command(self, subscriber, mock_sender):
        """Test routing a kick command."""
        command = {"action": "kick", "data": {"username": "baduser", "reason": "Spamming"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.kick", data)

        mock_sender.kick_user.assert_called_once_with(username="baduser", reason="Spamming")

    @pytest.mark.asyncio
    async def test_route_ban_command(self, subscriber, mock_sender):
        """Test routing a ban command."""
        command = {"action": "ban", "data": {"username": "troll", "reason": "Harassment"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.ban", data)

        mock_sender.ban_user.assert_called_once_with(username="troll", reason="Harassment")

    @pytest.mark.asyncio
    async def test_route_voteskip_command(self, subscriber, mock_sender):
        """Test routing a voteskip command."""
        command = {"action": "voteskip", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.voteskip", data)

        mock_sender.voteskip.assert_called_once()


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_json_logs_error(self, subscriber, mock_logger):
        """Test handling invalid JSON."""
        data = b"not valid json"

        await subscriber._handle_command("cytube.commands.testchannel.bad", data)

        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_action_logs_warning(self, subscriber, mock_logger, mock_sender):
        """Test handling command without action field."""
        command = {"data": {"message": "Hello"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.test", data)

        mock_logger.warning.assert_called_once()
        # Should not call any sender methods
        mock_sender.send_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_action_logs_warning(self, subscriber, mock_logger):
        """Test handling unknown action."""
        command = {"action": "unknown_action", "data": {}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.unknown", data)

        # Should log warning for unknown action
        assert mock_logger.warning.call_count >= 1

    @pytest.mark.asyncio
    async def test_sender_exception_logs_error(self, subscriber, mock_sender, mock_logger):
        """Test handling exception from sender."""
        mock_sender.send_chat.side_effect = Exception("Socket error")
        command = {"action": "chat", "data": {"message": "Test"}}
        data = json.dumps(command).encode()

        await subscriber._handle_command("cytube.commands.testchannel.chat", data)

        mock_logger.error.assert_called_once()

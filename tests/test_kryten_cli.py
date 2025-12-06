"""Unit tests for Kryten CLI."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from cli.kryten_cli import KrytenCLI


@pytest.fixture
def mock_config(tmp_path):
    """Create a temporary config file."""
    config = {
        "cytube": {
            "channel": "testchannel"
        },
        "nats": {
            "servers": ["nats://localhost:4222"],
            "user": None,
            "password": None,
            "connect_timeout": 10,
            "reconnect_time_wait": 2,
            "max_reconnect_attempts": 10,
            "allow_reconnect": True
        }
    }
    
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.fixture
async def cli(mock_config):
    """Create a CLI instance with mocked NATS."""
    cli = KrytenCLI(mock_config)
    cli.nats_client = AsyncMock()
    return cli


class TestChatCommands:
    """Tests for chat commands."""
    
    @pytest.mark.asyncio
    async def test_say_command(self, cli):
        """Test sending a chat message."""
        await cli.cmd_say("Hello world")
        
        cli.nats_client.publish.assert_called_once()
        call_args = cli.nats_client.publish.call_args
        
        subject = call_args[0][0]
        message = json.loads(call_args[0][1].decode())
        
        assert subject == "cytube.commands.testchannel.chat"
        assert message["action"] == "chat"
        assert message["data"]["message"] == "Hello world"
    
    @pytest.mark.asyncio
    async def test_pm_command(self, cli):
        """Test sending a private message."""
        await cli.cmd_pm("Alice", "Secret message")
        
        cli.nats_client.publish.assert_called_once()
        call_args = cli.nats_client.publish.call_args
        
        subject = call_args[0][0]
        message = json.loads(call_args[0][1].decode())
        
        assert subject == "cytube.commands.testchannel.pm"
        assert message["action"] == "pm"
        assert message["data"]["to"] == "Alice"
        assert message["data"]["message"] == "Secret message"


class TestPlaylistCommands:
    """Tests for playlist commands."""
    
    @pytest.mark.asyncio
    async def test_playlist_add(self, cli):
        """Test adding video to end."""
        await cli.cmd_playlist_add("yt:test123")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "queue"
        assert message["data"]["url"] == "yt:test123"
        assert message["data"]["position"] == "end"
        assert message["data"]["temp"] is False
    
    @pytest.mark.asyncio
    async def test_playlist_addnext(self, cli):
        """Test adding video to play next."""
        await cli.cmd_playlist_addnext("yt:test456")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["data"]["position"] == "next"
    
    @pytest.mark.asyncio
    async def test_playlist_add_temp(self, cli):
        """Test adding temporary video."""
        await cli.cmd_playlist_add("yt:test789", temp=True)
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["data"]["temp"] is True
    
    @pytest.mark.asyncio
    async def test_playlist_del(self, cli):
        """Test deleting video."""
        await cli.cmd_playlist_del("video-uid-5")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "delete"
        assert message["data"]["uid"] == "video-uid-5"
    
    @pytest.mark.asyncio
    async def test_playlist_move(self, cli):
        """Test moving video."""
        await cli.cmd_playlist_move("uid-1", "uid-2")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "move"
        assert message["data"]["uid"] == "uid-1"
        assert message["data"]["after"] == "uid-2"
    
    @pytest.mark.asyncio
    async def test_playlist_jump(self, cli):
        """Test jumping to video."""
        await cli.cmd_playlist_jump("uid-7")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "jump"
        assert message["data"]["uid"] == "uid-7"
    
    @pytest.mark.asyncio
    async def test_playlist_clear(self, cli):
        """Test clearing playlist."""
        await cli.cmd_playlist_clear()
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "clear"
    
    @pytest.mark.asyncio
    async def test_playlist_shuffle(self, cli):
        """Test shuffling playlist."""
        await cli.cmd_playlist_shuffle()
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "shuffle"
    
    @pytest.mark.asyncio
    async def test_playlist_settemp(self, cli):
        """Test setting temp status."""
        await cli.cmd_playlist_settemp("uid-3", True)
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "setTemp"
        assert message["data"]["uid"] == "uid-3"
        assert message["data"]["temp"] is True


class TestPlaybackCommands:
    """Tests for playback commands."""
    
    @pytest.mark.asyncio
    async def test_pause(self, cli):
        """Test pause command."""
        await cli.cmd_pause()
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "pause"
    
    @pytest.mark.asyncio
    async def test_play(self, cli):
        """Test play command."""
        await cli.cmd_play()
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "play"
    
    @pytest.mark.asyncio
    async def test_seek(self, cli):
        """Test seek command."""
        await cli.cmd_seek(42.5)
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "seek"
        assert message["data"]["time"] == 42.5


class TestModerationCommands:
    """Tests for moderation commands."""
    
    @pytest.mark.asyncio
    async def test_kick_with_reason(self, cli):
        """Test kicking user with reason."""
        await cli.cmd_kick("baduser", "Spamming")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "kick"
        assert message["data"]["username"] == "baduser"
        assert message["data"]["reason"] == "Spamming"
    
    @pytest.mark.asyncio
    async def test_kick_without_reason(self, cli):
        """Test kicking user without reason."""
        await cli.cmd_kick("baduser")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "kick"
        assert message["data"]["username"] == "baduser"
        assert "reason" not in message["data"]
    
    @pytest.mark.asyncio
    async def test_ban_with_reason(self, cli):
        """Test banning user with reason."""
        await cli.cmd_ban("troll", "Harassment")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "ban"
        assert message["data"]["username"] == "troll"
        assert message["data"]["reason"] == "Harassment"
    
    @pytest.mark.asyncio
    async def test_ban_without_reason(self, cli):
        """Test banning user without reason."""
        await cli.cmd_ban("troll")
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "ban"
        assert message["data"]["username"] == "troll"
        assert "reason" not in message["data"]
    
    @pytest.mark.asyncio
    async def test_voteskip(self, cli):
        """Test voteskip command."""
        await cli.cmd_voteskip()
        
        call_args = cli.nats_client.publish.call_args
        message = json.loads(call_args[0][1].decode())
        
        assert message["action"] == "voteskip"

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kryten.robot_command_handler import RobotCommandHandler


@pytest.mark.asyncio
async def test_robot_command_handlers():
    # Setup
    nats = AsyncMock()
    logger = MagicMock()
    connector = AsyncMock()

    handler = RobotCommandHandler(nats_client=nats, logger=logger, connector=connector)

    # Mock message
    msg = MagicMock()
    msg.reply = "reply.subject"

    # 1. Test "say" command
    msg.data = json.dumps({"command": "say", "args": {"message": "Hello World"}}).encode()

    await handler._handle_command(msg)

    connector.send_chat.assert_awaited_with("Hello World")
    nats.publish.assert_called()  # Should send response

    # 2. Test "pm" command
    msg.data = json.dumps({"command": "pm", "args": {"to": "user1", "msg": "secret"}}).encode()

    await handler._handle_command(msg)

    connector.send_pm.assert_awaited_with("user1", "secret")

    # 3. Test "restart" command
    msg.data = json.dumps({"command": "restart"}).encode()

    await handler._handle_command(msg)

    connector.disconnect.assert_awaited()

    # 4. Test "unknown" command - Should be ignored (no response)
    nats.publish.reset_mock()
    msg.data = json.dumps({"command": "unknown_cmd"}).encode()

    await handler._handle_command(msg)

    # Check NO response sent
    nats.publish.assert_not_called()


@pytest.mark.asyncio
async def test_robot_command_handler_subscription():
    nats = AsyncMock()
    logger = MagicMock()
    handler = RobotCommandHandler(nats_client=nats, logger=logger)

    await handler.start()

    # Check subscription subject
    nats.subscribe_request_reply.assert_called_with("kryten.robot.command", handler._handle_command)

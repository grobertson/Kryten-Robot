import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kryten.state_manager import StateManager
from kryten.state_updater import StateUpdater


def _make_manager() -> StateManager:
    manager = StateManager(AsyncMock(), "test", MagicMock())
    manager._running = True
    manager._kv_emotes = AsyncMock()
    manager._emotes = [{"name": "#old", "image": "old.gif", "source": "old-pattern"}]
    return manager


@pytest.mark.parametrize("extension", ["gif", "png", "jpg"])
async def test_incremental_emote_add_edit_and_remove_persist_without_clobbering(extension):
    manager = _make_manager()
    original = dict(manager._emotes[0])
    name = "#leathertowel"
    await manager.update_emote(
        {"name": name, "image": f"external.{extension}", "source": "pattern"}
    )
    await manager.update_emote({"name": name, "image": f"rehosted.{extension}"})

    expected = [original, {"name": name, "image": f"rehosted.{extension}", "source": "pattern"}]
    assert manager.get_emotes() == expected
    assert json.loads(manager._kv_emotes.put.await_args.args[1]) == expected

    await manager.remove_emote({"name": name})
    assert manager.get_emotes() == [original]
    assert json.loads(manager._kv_emotes.put.await_args.args[1]) == [original]


async def test_incremental_removal_accepts_bare_name():
    manager = _make_manager()
    await manager.remove_emote("#old")
    assert manager.get_emotes() == []


async def test_incremental_unknown_removal_does_not_write():
    manager = _make_manager()
    await manager.remove_emote("#missing")
    manager._kv_emotes.put.assert_not_awaited()


async def test_incremental_invalid_name_does_not_mutate_state():
    manager = _make_manager()
    await manager.update_emote({"image": "external.gif"})
    await manager.remove_emote({})
    assert len(manager.get_emotes()) == 1
    manager._kv_emotes.put.assert_not_awaited()


async def test_state_updater_registers_and_handles_incremental_emotes():
    manager = _make_manager()
    nats_client = MagicMock()
    nats_client.is_connected = True
    nats_client._nc.subscribe = AsyncMock()
    updater = StateUpdater(nats_client, manager, "test", "cytu.be", MagicMock())
    await updater.start()
    callbacks = {
        call.kwargs["cb"].__name__: call.kwargs["cb"]
        for call in nats_client._nc.subscribe.await_args_list
    }
    payload = {"name": "#new", "image": "external.png"}
    await callbacks["_handle_update_emote"](
        SimpleNamespace(data=json.dumps({"payload": payload}).encode())
    )
    assert manager.get_emotes()[-1] == payload
    await callbacks["_handle_remove_emote"](
        SimpleNamespace(data=json.dumps({"payload": {"name": "#new"}}).encode())
    )
    assert len(manager.get_emotes()) == 1


@pytest.mark.parametrize("handler", ["_handle_update_emote", "_handle_remove_emote"])
async def test_incremental_event_errors_are_logged_not_raised(handler):
    logger = MagicMock()
    updater = StateUpdater(MagicMock(), _make_manager(), "test", "cytu.be", logger)
    await getattr(updater, handler)(SimpleNamespace(data=b"invalid-json"))
    logger.error.assert_called_once()

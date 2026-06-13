from unittest.mock import AsyncMock, MagicMock

import pytest

from kryten.state_manager import StateManager


def _make_manager() -> StateManager:
    """Build a StateManager wired with mock NATS + userlist KV, marked running."""
    manager = StateManager(
        nats_client=AsyncMock(),
        channel="test",
        logger=MagicMock(),
    )
    manager._running = True
    manager._kv_userlist = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_set_user_afk_merges_into_meta_without_clobbering():
    manager = _make_manager()
    manager._users["Bob"] = {
        "name": "Bob",
        "rank": 3,
        "meta": {"muted": True},
        "profile": {"image": "x.png"},
    }

    await manager.set_user_afk("Bob", True)

    user = manager.get_user("Bob")
    assert user["meta"]["afk"] is True
    # Existing fields preserved.
    assert user["meta"]["muted"] is True
    assert user["rank"] == 3
    assert user["profile"] == {"image": "x.png"}
    manager._kv_userlist.put.assert_awaited()


@pytest.mark.asyncio
async def test_set_user_afk_clear_flag():
    manager = _make_manager()
    manager._users["Bob"] = {"name": "Bob", "rank": 1, "meta": {"afk": True}}

    await manager.set_user_afk("Bob", False)

    assert manager.get_user("Bob")["meta"]["afk"] is False


@pytest.mark.asyncio
async def test_set_user_afk_no_redundant_write_when_unchanged():
    manager = _make_manager()
    manager._users["Bob"] = {"name": "Bob", "meta": {"afk": True}}

    await manager.set_user_afk("Bob", True)

    manager._kv_userlist.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_user_afk_unknown_user_is_noop():
    manager = _make_manager()

    await manager.set_user_afk("Ghost", True)

    assert manager.get_user("Ghost") is None
    manager._kv_userlist.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_user_afk_creates_meta_when_absent():
    manager = _make_manager()
    manager._users["Bob"] = {"name": "Bob", "rank": 1}

    await manager.set_user_afk("Bob", True)

    assert manager.get_user("Bob")["meta"] == {"afk": True}

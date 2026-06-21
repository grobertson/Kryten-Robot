"""Channel CSS/JS persistence in StateManager.

Regression coverage for the bug where the channel CSS KV key was never
populated: the in-process state callback in ``__main__`` did not handle the
``channelCSSJS`` event (and the alternative ``StateUpdater`` path was never
started), so ``kryten_{channel}_state`` stayed empty forever and downstream
consumers (kryten-economy chat-color vanity) always read an empty string.

These tests pin the persistence mechanism the callback relies on.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kryten.state_manager import StateManager


def _make_manager() -> StateManager:
    """StateManager wired with a mock admin-state KV bucket, marked running."""
    manager = StateManager(
        nats_client=AsyncMock(),
        channel="Channel-Z",
        logger=MagicMock(),
    )
    manager._running = True
    manager._kv_state = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_set_channel_css_persists_to_kv():
    manager = _make_manager()
    css = "body { color: #fff; }\n.chat-msg-Alice { color: #112233; }"

    await manager.set_channel_css(css)

    # Cached for in-process reads…
    assert manager.get_channel_css() == css
    # …and persisted to the state KV under the "css" key (bytes).
    manager._kv_state.put.assert_awaited_once_with("css", css.encode())


@pytest.mark.asyncio
async def test_set_channel_js_persists_to_kv():
    manager = _make_manager()
    js = "console.log('hi');"

    await manager.set_channel_js(js)

    assert manager.get_channel_js() == js
    manager._kv_state.put.assert_awaited_once_with("js", js.encode())


@pytest.mark.asyncio
async def test_empty_css_is_persisted_verbatim():
    """An explicitly empty CSS frame is still stored (clears stale CSS)."""
    manager = _make_manager()

    await manager.set_channel_css("")

    assert manager.get_channel_css() == ""
    manager._kv_state.put.assert_awaited_once_with("css", b"")

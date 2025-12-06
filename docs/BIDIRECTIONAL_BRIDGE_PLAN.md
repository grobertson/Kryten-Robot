# Kryten Bidirectional Bridge Plan

**Date**: November 29, 2025  
**Status**: Planning

## Summary

Add the ability to send events to CyTube, not just receive them. This turns Kryten into a proper two-way bridge: receive events from CyTube → publish to NATS (existing), and subscribe to NATS → send to CyTube (new).

## What We're Building

**Current**: CyTube → Kryten → NATS (one-way)  
**Target**: CyTube ↔ Kryten ↔ NATS (two-way)

Use cases:
- Chat bot that can respond
- Automated playlist management
- Remote moderation tools
- Integration with external services

---

## Overview

### Current Architecture

Kryten currently operates as a **unidirectional bridge**:

```
CyTube Server → Kryten → NATS Message Bus
```

- **Receives** events from CyTube via Socket.IO
- **Publishes** events to NATS subjects
- No capability to send events back to CyTube

### Target Architecture

The bidirectional bridge will enable:

```
CyTube Server ←→ Kryten ←→ NATS Message Bus
```

- **Receives** events from CyTube → publishes to NATS (existing)
- **Subscribes** to NATS commands → sends to CyTube (new)
- Full remote control of CyTube channels via NATS messages

### Use Cases

1. **Remote Chat Bot**: Send chat messages from external services
2. **Playlist Management**: Automated DJ adding/removing videos
3. **Moderation**: Automated moderation actions based on rules
4. **Integration**: Trigger CyTube actions from external events
5. **Administration**: Remote channel configuration updates

### Step 1: Add Event Sender Module

Create `kryten/cytube_event_sender.py` to wrap the connector with methods for sending events.

**Event types to support:**

- **Chat**: `send_chat()`, `send_pm()`
- **Playlist**: `add_video()`, `delete_video()`, `move_video()`, `jump_to()`, `clear_playlist()`, `shuffle_playlist()`
- **Playback**: `pause()`, `play()`, `seek_to()`
- **Moderation**: `kick_user()`, `ban_user()`, `voteskip()`
- **Admin**: `update_motd()`, `set_channel_options()`

**Basic structure:**

```python
class CytubeEventSender:
    def __init__(self, connector, logger):
        self._connector = connector
        self._logger = logger
    
    async def send_chat(self, message: str) -> bool:
        """Send a chat message."""
        if not self._connector.is_connected:
            return False
        
        await self._connector._socket.emit("chatMsg", {"msg": message})
        return True
    
    async def add_video(self, url: str, temp: bool = False) -> bool:
        """Add video to playlist."""
        await self._connector._socket.emit("queue", {
            "id": url,
            "pos": "end",
            "temp": temp
        })
        return True
    
    # ... more methods for other events
```

### Step 2: NATS Command Subscriber

Create `kryten/command_subscriber.py` to listen for commands on NATS and route them to the sender.

```python
class CommandSubscriber:
    def __init__(self, sender, nats_client, logger, channel):
        self._sender = sender
        self._nats = nats_client
        self._channel = channel
    
    async def start(self):
        """Subscribe to command subjects."""
        subject = f"cytube.commands.{self._channel}.>"
        await self._nats.subscribe(subject, self._handle_command)
    
    async def _handle_command(self, subject, data):
        """Route commands to sender methods."""
        cmd = json.loads(data)
        action = cmd["action"]
        params = cmd["data"]
        
        if action == "chat":
            await self._sender.send_chat(**params)
        elif action == "queue":
            await self._sender.add_video(**params)
        # ... etc
```

**Command format** (sent to NATS):
```json
{
  "action": "chat",
  "data": {"message": "Hello!"}
}
```

### Step 3: Wire It Up

Update `__main__.py` to create the subscriber and start it:

```python
# After creating connector and publisher
sender = CytubeEventSender(connector, logger)
cmd_subscriber = CommandSubscriber(sender, nats_client, logger, config.cytube.channel)
await cmd_subscriber.start()
```

### Step 4: Configuration

Add to `config.json`:

```json
{
  "commands": {
    "enabled": true,
    "subject": "cytube.commands.mychannel.>"
  }
}
```

## Testing

Start simple:
1. Write unit tests for sender methods (mock the socket)
2. Write integration test: send NATS message → verify it calls sender
3. Manual test: send message via NATS CLI, check it appears in CyTube

## Implementation Order

1. **Day 1-2**: Build `CytubeEventSender` with chat and playlist methods
2. **Day 2-3**: Build `CommandSubscriber` and wire it up
3. **Day 3-4**: Add tests and fix bugs
4. **Day 4-5**: Add more event types as needed
5. **Optional**: Add rate limiting if bot gets too spammy

## Notes

- Start with just chat and playlist events - those are the most useful
- Add moderation/admin events later if you need them
- Don't overthink it - the socket connection already exists, just need to use it for sending
- Rate limiting can be added later if it becomes a problem

## Example Bot Usage

Once implemented, you could build a bot like:

```python
# Listen for !play commands in chat
async for event_name, payload in connector.recv_events():
    if event_name == "chatMsg":
        msg = payload["msg"]
        if msg.startswith("!play "):
            url = msg.split(" ", 1)[1]
            await sender.add_video(url)
```

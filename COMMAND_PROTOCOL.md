# Kryten Command Protocol

This document defines the **strictly enforced** protocol for service-to-service communication within the Kryten ecosystem.

## Core Principle: Separation of Concerns

*   **Events (1-to-Many)**: Broadcasts *from* a service to anyone listening.
    *   Subject: `kryten.cytube.{channel}.{event}` (e.g., `kryten.cytube.lounge.chatMsg`)
    *   Usage: State updates, chat messages, system notifications.
    *   Pattern: Publish-Subscribe (PubSub).

*   **Commands (1-to-1)**: Directives *to* a specific service to perform an action.
    *   Subject: `kryten.command.{service}` (e.g., `kryten.command.robot`)
    *   Usage: Control actions (restart, mute), data requests (query state), operations (add video).
    *   Pattern: Request-Reply.

> **CRITICAL**: Do NOT publish commands to event channels. Do NOT listen for commands on event channels.

## Command Structure

All commands MUST be sent to `kryten.command.{service_name}`.

### Request Format

```json
{
  "command": "action_name",
  "args": {
    "param1": "value1",
    "param2": "value2"
  },
  "meta": {
    "source": "sending-service-name",
    "timestamp": "ISO-8601-timestamp",
    "request_id": "uuid-v4"
  }
}
```

### Response Format

Services MUST reply to the NATS `reply_to` subject (if provided) with:

```json
{
  "service": "responding-service-name",
  "command": "action_name",
  "success": true,  // or false
  "data": { ... },  // Result data on success
  "error": "Error message" // Only present if success is false
}
```

## Standard Commands

### Target: `robot` (`kryten.robot.command`)

Controls the core bot instance connected to CyTube.

| Command | Args | Description |
| :--- | :--- | :--- |
| `restart` | None | Reconnects to CyTube |
| `halt` | None | Disconnects from CyTube |
| `say` | `message` | Sends public chat message |
| `pm` | `to`, `message` | Sends private message |
| `system.ping` | None | Health check (returns uptime/version) |
| `system.stats` | None | Returns internal metrics |

### Target: `playlist` (`kryten.playlist.command`)

Manages the video queue and playlist state.

| Command | Args | Description |
| :--- | :--- | :--- |
| `add` | `url`, `pos` | Adds video to queue |
| `delete` | `uid` | Removes video from queue |
| `move` | `uid`, `pos` | Moves video in queue |
| `shuffle` | None | Shuffles the active playlist |

## Implementation Guide (Python)

Using `kryten-py`:

```python
from kryten.client import KrytenClient

async with KrytenClient(config) as client:
    # INCORRECT: Publishing to event channel
    # await client.publish("kryten.cytube.lounge.command", ...) 
    
    # CORRECT: Using the command API
    await client.send_command(
        service="robot",
        type="say",
        body="Hello humans"
    )
```

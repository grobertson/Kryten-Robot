# State Query Endpoint - Implementation Summary

## Overview
Added a new NATS request/reply endpoint to Kryten-Robot that exposes channel state (emotes, playlist, userlist) for consumption by other microservices like kryten-userstats.

## Files Created

### `kryten/state_query_handler.py`
- **Purpose**: NATS request/reply handler for state queries
- **Subscribes to**: `cytube.state.{domain}.{channel}`
- **Returns**: JSON with emotes, playlist, userlist arrays
- **Features**:
  - Optional key filtering (request specific state elements)
  - Error handling with error responses
  - Query statistics tracking
  - Graceful start/stop lifecycle

**Response Format**:
```json
{
  "success": true,
  "data": {
    "emotes": [...],
    "playlist": [...],
    "userlist": [...]
  },
  "stats": {
    "emotes_count": 150,
    "playlist_items": 45,
    "users_count": 12
  }
}
```

### `test_state_query.py`
- **Purpose**: Test script to verify state query endpoint
- **Usage**: `python test_state_query.py`
- **Displays**: Sample data and statistics from state query

## Files Modified

### `kryten/__init__.py`
- Added `StateQueryHandler` import
- Added to `__all__` exports

### `kryten/__main__.py`
**Imports** (line 24-36):
- Added `StateQueryHandler` import

**Initialization** (after line 277):
```python
# Start state query handler for NATS queries
try:
    logger.info("Starting state query handler")
    state_query_handler = StateQueryHandler(
        state_manager=state_manager,
        nats_client=nats_client,
        logger=logger,
        domain=config.cytube.domain,
        channel=config.cytube.channel
    )
    await state_query_handler.start()
    logger.info(f"State query handler listening on: cytube.state.{domain}.{channel}")
except Exception as e:
    logger.error(f"Failed to start state query handler: {e}", exc_info=True)
    logger.warning("Continuing without state query endpoint")
    state_query_handler = None
```

**Shutdown Sequence** (line 338-346):
```python
# 2. Stop state query handler
if state_query_handler:
    logger.info("Stopping state query handler")
    await state_query_handler.stop()
    logger.info("State query handler stopped")
```

## Integration with StateManager

The `StateQueryHandler` uses the newly added getter methods from `StateManager`:
- `get_emotes()` → Returns List[Dict] of emote definitions
- `get_playlist()` → Returns List[Dict] of playlist items
- `get_userlist()` → Returns List[Dict] of users
- `get_all_state()` → Returns Dict with all three

StateManager maintains these in memory and updates them on CyTube events:
- `emoteList` → Updates emotes
- `playlist`, `queue`, `delete`, `moveMedia` → Updates playlist
- `userlist`, `addUser`, `userLeave`, `setUserRank` → Updates users

## NATS Subject Pattern

**Request Subject**: `cytube.state.{domain}.{channel}`
- Example: `cytube.state.cytu.be.roboMrRoboto`

**Request Payload** (optional):
```json
{
  "keys": ["emotes", "playlist"]  // Optional: request specific elements
}
```

## Next Steps

### For kryten-userstats Integration:
1. Add method in `main.py` to query state on startup:
   ```python
   async def _load_initial_state(self):
       """Query Kryten-Robot for initial channel state."""
       try:
           subject = f"cytube.state.{self._domain}.{self._channel}"
           response = await self._nats.request(subject, b'{}', timeout=5.0)
           data = json.loads(response.data)
           
           if data.get('success'):
               state = data['data']
               # Load emotes into EmoteDetector
               # Store userlist for reference
               # Log playlist info
       except Exception as e:
           self._logger.warning(f"Could not load initial state: {e}")
   ```

2. Call during startup (after NATS connection):
   ```python
   await self._load_initial_state()
   ```

3. Update EmoteDetector to accept emote list on initialization

## Testing

1. **Start Kryten-Robot**:
   ```powershell
   cd d:\Devel\Kryten-Robot
   python -m kryten config.json
   ```

2. **Run test script** (in another terminal):
   ```powershell
   cd d:\Devel\Kryten-Robot
   python test_state_query.py
   ```

3. **Expected output**:
   ```
   Connected to NATS
   Querying: cytube.state.cytu.be.roboMrRoboto
   
   ============================================================
   STATE QUERY RESPONSE
   ============================================================
   
   ✅ Success!
   
   Emotes: 150 loaded
   Playlist: 45 items
   Userlist: 12 users
   
   StateManager Stats:
     emotes_count: 150
     playlist_items: 45
     users_count: 12
   ```

## Architecture

```
┌─────────────────┐
│ kryten-userstats│
└────────┬────────┘
         │ NATS Request
         │ cytube.state.{domain}.{channel}
         ▼
┌─────────────────────────┐
│ StateQueryHandler       │
│ (Kryten-Robot)          │
├─────────────────────────┤
│ • Receives request      │
│ • Calls StateManager    │
│ • Returns JSON response │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ StateManager            │
├─────────────────────────┤
│ • In-memory state       │
│ • Updates on events     │
│ • Persists to NATS KV   │
└─────────────────────────┘
```

## Benefits

1. **Single Source of Truth**: StateManager maintains authoritative state
2. **Fast Access**: In-memory reads, no KV store queries needed
3. **Decoupled**: Microservices query via NATS, no direct dependencies
4. **Persistent**: StateManager still writes to KV stores for durability
5. **Efficient**: Request/reply pattern with JSON compression

## Version Updates

- **Kryten-Robot**: Ready for v0.6.0 (new state query endpoint)
- **kryten-userstats**: Pending v0.2.5 (will add state loading on startup)

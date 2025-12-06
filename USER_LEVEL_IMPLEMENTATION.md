# User Level / Rank Implementation

## Overview

This document describes the implementation of user level/rank tracking and its use for gating playlist access in Kryten-Robot and related services.

## Problem Statement

CyTube restricts full playlist access to users with moderator or higher permissions (rank >= 2). When Kryten-Robot connects with a guest or regular user account, the `requestPlaylist` Socket.IO event returns no data, causing:

- Empty playlist KV stores
- Failed playlist loading in downstream services
- Unnecessary NATS traffic for requests that cannot succeed

## Solution Architecture

### 1. User Rank Tracking in Kryten-Robot

**File**: `kryten/cytube_connector.py`

**Changes**:
- Added `_user_rank: int` attribute to `CytubeConnector`
  - Initialized to 0 (guest rank)
  - Updated from login response in both `_authenticate_registered()` and `_authenticate_guest()`
  
- Added `user_rank` property to expose the rank:
  ```python
  @property
  def user_rank(self) -> int:
      """Get the rank of the logged-in user.
      
      Returns:
          User rank: 0=guest, 1=registered, 2=moderator, 3+=admin.
      """
      return self._user_rank
  ```

- Modified `_request_initial_state()` to gate playlist request:
  ```python
  if self._user_rank >= 2:
      await self._socket.emit("requestPlaylist", {})
      self.logger.debug(f"Playlist request sent (rank: {self._user_rank})")
  else:
      self.logger.debug(f"Skipping playlist request - insufficient permissions (rank: {self._user_rank}, need >= 2)")
  ```

### 2. NATS User Level Query Endpoint

**File**: `kryten/__main__.py`

**Changes**:
- Added NATS subscription handler for user level queries
- Subject pattern: `cytube.user_level.{domain}.{channel}`
- Response format:
  ```json
  {
    "success": true,
    "rank": 2,
    "username": "KrytenBot"
  }
  ```

**Implementation**:
```python
async def handle_user_level_query(msg):
    """Handle NATS queries for logged-in user's level/rank."""
    response = {
        "success": True,
        "rank": connector.user_rank,
        "username": config.cytube.user or "guest"
    }
    
    if msg.reply:
        response_bytes = json.dumps(response).encode('utf-8')
        await nats_client.publish(msg.reply, response_bytes)
```

**Lifecycle**:
- Started after state query handler initialization
- Stopped during graceful shutdown (unsubscribe from NATS)

### 3. kryten-py Client Method

**File**: `kryten-py/src/kryten/client.py`

**Changes**:
- Added `async def get_user_level()` method to `KrytenClient`

**Usage**:
```python
result = await client.get_user_level("lounge", domain="cytu.be")

if result["success"]:
    rank = result["rank"]  # 0=guest, 1=registered, 2=moderator, 3+=admin
    username = result["username"]
    print(f"Bot is logged in as {username} with rank {rank}")
else:
    print(f"Error: {result['error']}")
```

**Error Handling**:
- Returns error dict on timeout (Kryten-Robot not responding)
- Returns error dict on exception
- 2-second default timeout

### 4. kryten-userstats Playlist Loading

**File**: `kryten-userstats/userstats/main.py`

**Changes**:
- Modified `_load_initial_state_from_kv()` to check user level before loading playlist
- Queries Kryten-Robot via `client.get_user_level()`
- Only loads playlist if `rank >= 2`
- Fixed KV key from "emotes" to "list" for emote loading

**Implementation**:
```python
# Query Kryten-Robot for user level
user_level_result = await self.client.get_user_level(channel, domain=domain, timeout=2.0)

if user_level_result.get("success"):
    user_rank = user_level_result.get("rank", 0)
    
    if user_rank >= 2:
        # Load playlist from KV store
        playlist_json = await self.client.kv_get(f"{bucket_prefix}_playlist", "items", default=[], parse_json=True)
        # ... process playlist
    else:
        self.logger.info(f"Skipping playlist load - insufficient permissions (rank: {user_rank}, need >= 2)")
else:
    self.logger.warning(f"Could not query user level: {error_msg}")
```

## CyTube Rank Levels

| Rank | Role | Permissions |
|------|------|-------------|
| 0 | Guest | View only, chat |
| 1 | Registered User | View, chat, possibly vote |
| 2 | Moderator | View, chat, manage playlist, moderate users |
| 3+ | Admin/Owner | Full control |

## Benefits

1. **Eliminates Unnecessary Requests**: Kryten-Robot no longer sends playlist requests when logged in with insufficient permissions

2. **Clear Logging**: Both Kryten-Robot and kryten-userstats log when playlist access is skipped due to insufficient rank

3. **Graceful Degradation**: Services continue functioning with userlist and emotes even when playlist is unavailable

4. **Reusable Pattern**: Other services can query user level via kryten-py for any permission-based logic

## Testing

### Verify User Rank Tracking
1. Check Kryten-Robot logs on startup:
   ```
   Authenticated as: KrytenBot (rank: 2)
   ```

2. Check initial state request:
   ```
   Playlist request sent (rank: 2)
   ```
   OR
   ```
   Skipping playlist request - insufficient permissions (rank: 1, need >= 2)
   ```

### Verify NATS Query Endpoint
```bash
nats request cytube.user_level.cytu.be.lounge '{}'
```

Expected response:
```json
{
  "success": true,
  "rank": 2,
  "username": "KrytenBot"
}
```

### Verify kryten-userstats Loading
Check logs on startup:
```
Bot user level: KrytenBot (rank: 2)
Loaded 50 playlist items from KV store
```
OR
```
Bot user level: KrytenBot (rank: 1)
Skipping playlist load - insufficient permissions (rank: 1, need >= 2)
```

## Related Files

- `kryten/cytube_connector.py` - User rank tracking and gated playlist request
- `kryten/__main__.py` - NATS user level query endpoint
- `kryten-py/src/kryten/client.py` - `get_user_level()` method
- `kryten-userstats/userstats/main.py` - Conditional playlist loading
- `INITIAL_STATE_IMPLEMENTATION.md` - Related initial state request documentation

## Future Enhancements

1. **Permission-based Command Filtering**: Use rank to filter available commands
2. **Role-based Feature Flags**: Enable/disable features based on user rank
3. **Automatic Escalation Requests**: Log warnings when admin features are needed but unavailable
4. **Multi-user Support**: Track ranks for multiple bot accounts in the same channel

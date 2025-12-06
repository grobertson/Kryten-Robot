# Audit Logging System

This document describes the comprehensive audit logging system implemented in Kryten-Robot for tracking CyTube operations, chat messages, and commands.

## Overview

The audit logging system provides separate log files for different operation types, enabling detailed auditing, debugging, and compliance tracking. All logs use UTF-8 encoding to support Unicode characters (emotes, international text, etc.).

## Log Files

Four specialized log files are maintained:

| Log File | Purpose | Contains |
|----------|---------|----------|
| `admin-operations.log` | Admin operations | MOTD, CSS/JS, permissions, emotes, filters, ranks, bans, polls |
| `playlist-operations.log` | Playlist changes | Queue, delete, move, jump, clear, shuffle, setTemp, playNext |
| `chat-messages.log` | Chat messages | IRC-style timestamped chat log |
| `command-audit.log` | Command audit trail | All NATS commands with username and arguments |

## Configuration

### Config Structure

Add the `logging` section to your `config.json`:

```json
{
  "logging": {
    "base_path": "d:\\Devel\\logs\\",
    "admin_operations": "admin-operations.log",
    "playlist_operations": "playlist-operations.log",
    "chat_messages": "chat-messages.log",
    "command_audit": "command-audit.log"
  }
}
```

### Configuration Options

- **`base_path`**: Base directory for all log files (created if doesn't exist)
- **`admin_operations`**: Filename for admin operation log
- **`playlist_operations`**: Filename for playlist operation log
- **`chat_messages`**: Filename for chat message log
- **`command_audit`**: Filename for command audit log

All filenames are configurable independently.

### Example Configurations

**Development (relative path):**
```json
"logging": {
  "base_path": "./logs",
  "admin_operations": "admin-operations.log",
  "playlist_operations": "playlist-operations.log",
  "chat_messages": "chat-messages.log",
  "command_audit": "command-audit.log"
}
```

**Production (absolute path with custom names):**
```json
"logging": {
  "base_path": "/var/log/kryten/",
  "admin_operations": "admin.log",
  "playlist_operations": "playlist.log",
  "chat_messages": "chat.log",
  "command_audit": "commands.log"
}
```

## Log Formats

### Admin Operations Log

**Format:** `YYYY-MM-DD HH:MM:SS [operation] key=value ...`

**Examples:**
```
2024-01-15 14:30:22 [setMotd] by=SaveTheRobots length=156
2024-01-15 14:31:05 [setChannelCSS] by=SaveTheRobots size_bytes=8432
2024-01-15 14:32:18 [ban] by=SaveTheRobots target=SpamUser duration=3600 reason="Spamming"
2024-01-15 14:33:45 [updateEmote] by=SaveTheRobots target=wave image=wave.gif source=imgur
2024-01-15 14:34:12 [addFilter] by=SaveTheRobots target=profanity source=\\b(bad|word)\\b flags=gi replace=[redacted]
2024-01-15 14:35:30 [setChannelRank] by=SaveTheRobots target=Alice rank=3
2024-01-15 14:36:55 [newPoll] by=SaveTheRobots title="What to watch?" options=4
```

### Playlist Operations Log

**Format:** `YYYY-MM-DD HH:MM:SS [operation] key=value ...`

**Examples:**
```
2024-01-15 14:40:10 [queue] user=Alice title="Awesome Video" position=end temp=false
2024-01-15 14:41:22 [delete] user=Bob uid=abc123
2024-01-15 14:42:35 [moveMedia] user=Charlie uid=xyz789 after=def456
2024-01-15 14:43:18 [jumpTo] user=Dave uid=ghi012
2024-01-15 14:44:05 [clearPlaylist] user=Admin
2024-01-15 14:45:30 [shufflePlaylist] user=Admin
2024-01-15 14:46:12 [setTemp] user=Eve uid=jkl345 temp=true
```

### Chat Messages Log

**Format:** `HH:MM:SS <username>: message`

**Examples:**
```
14:50:15 <Alice>: Hello everyone!
14:50:22 <Bob>: Hey Alice! How's it going?
14:50:35 <Charlie>: Anyone want to queue some videos?
14:50:48 <Dave>: Sure, I have some good ones
14:51:02 <Eve>: 👍 sounds good
```

**Features:**
- IRC-style format for easy parsing and familiarity
- UTF-8 encoding supports emojis and international characters
- Simple HH:MM:SS timestamp for readability
- Complete chat history for moderation and debugging

### Command Audit Log

**Format:** `YYYY-MM-DD HH:MM:SS [source] command=action user=username args=(key=value ...)`

**Examples:**
```
2024-01-15 15:00:10 [NATS] command=sendChat user=bot args=(message="Hello from bot")
2024-01-15 15:01:22 [NATS] command=queue user=bot args=(url="https://youtu.be/..." position="next" temp="false")
2024-01-15 15:02:35 [NATS] command=setMotd user=bot args=(motd="<h1>Welcome!</h1>")
2024-01-15 15:03:18 [NATS] command=ban user=bot args=(username="SpamUser" reason="Excessive spam")
```

**Security:**
- Sensitive fields (containing "password") are automatically redacted to `***`
- All command parameters are logged for complete audit trail
- Source identification (NATS, internal, etc.)

## Logged Operations

### Admin Operations (Rank 3+)

All admin-level operations are logged to `admin-operations.log`:

| Operation | Details Logged |
|-----------|----------------|
| `setMotd` | MOTD content length |
| `setChannelCSS` | CSS size in bytes |
| `setChannelJS` | JS size in bytes |
| `setOptions` | Number of options changed |
| `setPermissions` | Number of permissions changed |
| `updateEmote` | Emote name, image URL, source |
| `removeEmote` | Emote name |
| `addFilter` | Filter name, regex source, flags, replacement |
| `updateFilter` | Filter name, regex source, flags, replacement |
| `removeFilter` | Filter name |
| `setChannelRank` | Target username, new rank |
| `ban` | Target username, reason (if provided) |
| `newPoll` | Poll title, number of options |
| `closePoll` | (operation only) |

### Playlist Operations

All playlist modifications are logged to `playlist-operations.log`:

| Operation | Details Logged |
|-----------|----------------|
| `queue` | Media title/URL, position, temp flag |
| `delete` | Media UID |
| `moveMedia` | Media UID, target position |
| `jumpTo` | Media UID |
| `clearPlaylist` | (operation only) |
| `shufflePlaylist` | (operation only) |
| `setTemp` | Media UID, temp flag value |

### Chat Messages

All channel chat messages are logged to `chat-messages.log` in IRC format:
- Timestamp (HH:MM:SS)
- Username
- Message content

### Command Audit

All commands received via NATS are logged to `command-audit.log`:
- Full timestamp
- Command source (NATS)
- Command name
- Username (if available)
- All command arguments (sensitive fields redacted)

## Architecture

### Components

1. **`AuditLogger` class** (`audit_logger.py`)
   - Manages four specialized loggers
   - Creates log directory automatically
   - UTF-8 encoding for all files
   - Simple, readable format

2. **`CytubeEventSender` integration**
   - Accepts optional `audit_logger` parameter
   - Logs admin and playlist operations after successful emit
   - Includes operation-specific details

3. **`CommandSubscriber` integration**
   - Accepts optional `audit_logger` parameter
   - Logs all received commands before routing
   - Extracts username from command parameters

4. **Chat message handler** (`__main__.py`)
   - Registered as event callback for `chatMsg` events
   - Logs in IRC format with HH:MM:SS timestamp

### Flow Diagram

```
CyTube Server
    |
    v
CytubeConnector (Socket.IO)
    |
    +---> EventPublisher --> NATS
    |
    +---> [chatMsg] --> AuditLogger.log_chat_message() --> chat-messages.log
    |
    v
CytubeEventSender
    |
    +---> Admin operations --> AuditLogger.log_admin_operation() --> admin-operations.log
    |
    +---> Playlist operations --> AuditLogger.log_playlist_operation() --> playlist-operations.log

NATS
    |
    v
CommandSubscriber
    |
    +---> AuditLogger.log_command() --> command-audit.log
    |
    v
CytubeEventSender --> CyTube Server
```

## Usage Examples

### Parsing Chat Logs

```python
import re
from datetime import datetime

# Parse chat log line
pattern = r'(\d{2}:\d{2}:\d{2}) <([^>]+)>: (.+)'
match = re.match(pattern, "14:50:15 <Alice>: Hello everyone!")
if match:
    time_str, username, message = match.groups()
    print(f"At {time_str}, {username} said: {message}")
```

### Monitoring Admin Operations

```bash
# Watch admin operations in real-time
tail -f d:\Devel\logs\admin-operations.log

# Find all bans
grep "\[ban\]" d:\Devel\logs\admin-operations.log

# Find all MOTD changes
grep "\[setMotd\]" d:\Devel\logs\admin-operations.log
```

### Analyzing Playlist Activity

```bash
# Count queue operations by user
grep "\[queue\]" d:\Devel\logs\playlist-operations.log | grep -oP 'user=\K\w+' | sort | uniq -c

# Find all clears/shuffles
grep -E "\[(clearPlaylist|shufflePlaylist)\]" d:\Devel\logs\playlist-operations.log
```

### Auditing Commands

```bash
# View all commands received
cat d:\Devel\logs\command-audit.log

# Find commands from specific user
grep "user=bot" d:\Devel\logs\command-audit.log

# Find specific command types
grep "command=ban" d:\Devel\logs\command-audit.log
```

## Performance Considerations

- **Asynchronous I/O**: All logging is asynchronous (file handlers)
- **No blocking**: Logging never blocks command processing
- **Append-only**: Logs use append mode for efficiency
- **UTF-8 encoding**: Minimal overhead for Unicode support
- **Conditional checks**: Logging only occurs if `audit_logger` is provided

## Log Rotation (Optional)

The audit logging system doesn't include built-in log rotation. For production deployments, consider using external tools:

### Linux/Unix (logrotate)

Create `/etc/logrotate.d/kryten`:

```
/var/log/kryten/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 kryten kryten
    sharedscripts
    postrotate
        systemctl reload kryten
    endscript
}
```

### Windows (PowerShell script)

```powershell
# Archive logs older than 30 days
$LogPath = "d:\Devel\logs"
$ArchivePath = "d:\Devel\logs\archive"
$DaysToKeep = 30

Get-ChildItem "$LogPath\*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-$DaysToKeep)
} | ForEach-Object {
    Compress-Archive -Path $_.FullName -DestinationPath "$ArchivePath\$($_.BaseName)-$(Get-Date -Format 'yyyyMMdd').zip"
    Remove-Item $_.FullName
}
```

## Troubleshooting

### Logs not being created

1. **Check directory permissions**: Ensure the bot has write access to `base_path`
2. **Check configuration**: Verify `logging` section in `config.json`
3. **Check bot logs**: Look for errors during audit logger initialization

### Missing log entries

1. **Check audit_logger is passed**: Verify both `CytubeEventSender` and `CommandSubscriber` receive `audit_logger`
2. **Check conditional**: Ensure `if self._audit_logger:` conditions are present
3. **Check operation success**: Logs are only written after successful operations

### Unicode characters not displaying

1. **Verify UTF-8 encoding**: All log files should use UTF-8
2. **Check viewer**: Ensure your log viewer/editor supports UTF-8
3. **Windows users**: Use editors like VSCode, Notepad++, or modern terminal emulators

## Best Practices

1. **Regular monitoring**: Set up alerts for suspicious patterns (repeated bans, excessive admin changes)
2. **Backup logs**: Include audit logs in backup procedures
3. **Retention policy**: Define how long to keep logs based on compliance requirements
4. **Access control**: Restrict read access to audit logs (may contain sensitive usernames)
5. **Correlation**: Use timestamps to correlate events across different log files
6. **Archival**: Compress and archive old logs to save disk space

## Security Considerations

- **Sensitive data**: Passwords in command parameters are automatically redacted
- **Channel passwords**: Not logged in any audit file
- **User privacy**: Chat messages contain full conversation history
- **Access control**: Protect audit logs with appropriate file permissions
- **Compliance**: Ensure log retention meets your jurisdiction's requirements

## Future Enhancements

Potential improvements for future versions:

- [ ] Structured JSON log format option
- [ ] Built-in log rotation
- [ ] Elasticsearch/Loki integration
- [ ] Real-time log streaming via WebSocket
- [ ] Log aggregation across multiple bot instances
- [ ] Automated anomaly detection
- [ ] Web UI for log viewing and searching

## Support

For issues, questions, or contributions related to audit logging:

1. Check this documentation first
2. Review the source code in `audit_logger.py`
3. Check main application logs for initialization errors
4. Verify configuration in `config.json`
5. Test with minimal configuration first

---

**Implementation Date:** January 2024  
**Module:** `kryten.audit_logger`  
**Configuration:** `config.logging` section

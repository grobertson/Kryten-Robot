# Quick Start: Audit Logging

## Setup (5 minutes)

### 1. Add to config.json

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

### 2. Start the bot

```bash
python -m kryten config.json
```

The `d:\Devel\logs\` directory and all log files will be created automatically.

## What Gets Logged

| Log File | Contains |
|----------|----------|
| `admin-operations.log` | MOTD, CSS/JS, permissions, emotes, filters, ranks, bans, polls |
| `playlist-operations.log` | Queue, delete, move, jump, clear, shuffle, setTemp |
| `chat-messages.log` | All channel chat in IRC format |
| `command-audit.log` | All NATS commands with username and arguments |

## Quick Commands

```bash
# Watch logs in real-time
tail -f d:\Devel\logs\admin-operations.log
tail -f d:\Devel\logs\chat-messages.log

# Find specific operations
grep "\[ban\]" d:\Devel\logs\admin-operations.log
grep "\[queue\]" d:\Devel\logs\playlist-operations.log
grep "command=setMotd" d:\Devel\logs\command-audit.log

# View recent chat
tail -n 100 d:\Devel\logs\chat-messages.log
```

## Log Format Examples

**Admin:**
```
2024-01-15 14:30:22 [setMotd] by=SaveTheRobots length=156
2024-01-15 14:32:18 [ban] by=SaveTheRobots target=SpamUser reason="Spam"
```

**Playlist:**
```
2024-01-15 14:40:10 [queue] user=Alice title="Video" position=end temp=false
2024-01-15 14:41:22 [delete] user=Bob uid=abc123
```

**Chat:**
```
14:50:15 <Alice>: Hello everyone!
14:50:22 <Bob>: Hey Alice! 👋
```

**Commands:**
```
2024-01-15 15:00:10 [NATS] command=sendChat user=bot args=(message="Hello")
```

## Features

✅ UTF-8 encoding (emojis, Unicode, international text)  
✅ Automatic directory creation  
✅ Configurable filenames and paths  
✅ Non-blocking async I/O  
✅ Automatic password redaction  
✅ IRC-style chat format  

## Documentation

- **Full Guide:** `AUDIT_LOGGING.md` - Complete documentation with examples
- **Implementation:** `AUDIT_LOGGING_SUMMARY.md` - Technical details
- **Code:** `kryten/audit_logger.py` - Source code with docstrings

## Common Use Cases

**Moderation:**
```bash
# Find all bans today
grep "$(date +%Y-%m-%d)" d:\Devel\logs\admin-operations.log | grep "\[ban\]"

# View chat history for user
grep "<Alice>:" d:\Devel\logs\chat-messages.log
```

**Debugging:**
```bash
# See what commands were sent
cat d:\Devel\logs\command-audit.log

# Check playlist activity
grep -E "\[(queue|delete|clearPlaylist)\]" d:\Devel\logs\playlist-operations.log
```

**Analytics:**
```bash
# Count operations by type
grep -oP '\[\K\w+' d:\Devel\logs\admin-operations.log | sort | uniq -c
grep -oP '\[\K\w+' d:\Devel\logs\playlist-operations.log | sort | uniq -c
```

## Troubleshooting

**Logs not created?**
- Check write permissions on `base_path`
- Verify `logging` section in config.json
- Check main bot logs for errors

**Unicode not displaying?**
- Ensure your editor/viewer supports UTF-8
- Windows: Use VSCode, Notepad++, or modern terminal

**Missing entries?**
- Verify bot is connected to CyTube
- Check that operations are successful
- Logs only written after successful emit()

## That's It!

The audit logging system is now active and tracking all operations. No restart needed when changing filenames (takes effect on next start).

For detailed information, see **AUDIT_LOGGING.md**.

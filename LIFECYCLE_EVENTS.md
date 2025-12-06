# Lifecycle Events - Implementation Guide

## Overview

Kryten services now publish lifecycle events for monitoring, coordination, and debugging. This enables:
- Centralized monitoring of service health
- Coordinated restarts across service groups
- Automated alerting on connection issues
- Audit trail of service lifecycle

## Event Types

### 1. Service Startup
**Subject**: `kryten.lifecycle.{service}.startup`

Published when a service completes initialization and is ready to process events.

**Payload**:
```json
{
  "service": "robot",
  "version": "0.6.0",
  "hostname": "server1",
  "timestamp": "2025-12-06T10:30:00Z",
  "uptime_seconds": null,
  "domain": "cytu.be",
  "channel": "roboMrRoboto",
  "commands_enabled": true,
  "health_enabled": true
}
```

### 2. Service Shutdown
**Subject**: `kryten.lifecycle.{service}.shutdown`

Published before service terminates.

**Payload**:
```json
{
  "service": "robot",
  "version": "0.6.0",
  "hostname": "server1",
  "timestamp": "2025-12-06T12:45:00Z",
  "uptime_seconds": 8100,
  "reason": "Normal shutdown"
}
```

### 3. Connection Established
**Subject**: `kryten.lifecycle.{service}.connected`

Published when a service establishes a connection to an external system.

**Payload**:
```json
{
  "service": "robot",
  "version": "0.6.0",
  "hostname": "server1",
  "timestamp": "2025-12-06T10:29:55Z",
  "uptime_seconds": 5,
  "target": "CyTube",
  "domain": "cytu.be",
  "channel": "roboMrRoboto"
}
```

or for NATS:
```json
{
  "service": "robot",
  "target": "NATS",
  "servers": ["nats://localhost:4222"]
}
```

### 4. Connection Lost
**Subject**: `kryten.lifecycle.{service}.disconnected`

Published when a service loses connection to an external system.

**Payload**:
```json
{
  "service": "robot",
  "version": "0.6.0",
  "hostname": "server1",
  "timestamp": "2025-12-06T12:44:59Z",
  "uptime_seconds": 8099,
  "target": "CyTube",
  "reason": "Graceful shutdown"
}
```

### 5. Groupwide Restart Notice
**Subject**: `kryten.lifecycle.group.restart`

Broadcast message requesting all Kryten services to restart.

**Payload**:
```json
{
  "initiator": "admin",
  "reason": "Configuration update",
  "delay_seconds": 5,
  "timestamp": "2025-12-06T13:00:00Z"
}
```

**Behavior**: 
- All services subscribe to this subject
- Upon receiving, services wait `delay_seconds` then initiate graceful shutdown
- Services should be managed by systemd or similar to auto-restart

## Service Names

| Service | Name |
|---------|------|
| Kryten-Robot | `robot` |
| kryten-userstats | `userstats` |
| Future services | TBD |

## Implementation in Kryten-Robot

### Files Added

**`kryten/lifecycle_events.py`**: 
- `LifecycleEventPublisher` class
- Methods: `publish_startup()`, `publish_shutdown()`, `publish_connected()`, `publish_disconnected()`, `publish_group_restart()`
- Subscribes to groupwide restart notices

### Integration Points

**`kryten/__main__.py`**:

1. **After NATS connection** (line ~175):
   ```python
   lifecycle = LifecycleEventPublisher("robot", nats_client, logger, __version__)
   await lifecycle.start()
   lifecycle.on_restart_notice(handle_restart_notice)
   await lifecycle.publish_connected("NATS", servers=config.nats.servers)
   ```

2. **After CyTube connection** (line ~195):
   ```python
   await lifecycle.publish_connected("CyTube", domain=..., channel=...)
   ```

3. **After full startup** (line ~360):
   ```python
   await lifecycle.publish_startup(domain=..., channel=..., ...)
   ```

4. **During shutdown** (line ~415):
   ```python
   await lifecycle.publish_disconnected("CyTube", reason="Graceful shutdown")
   await lifecycle.publish_shutdown(reason="Normal shutdown")
   await lifecycle.stop()
   ```

## Usage Examples

### Monitor All Lifecycle Events

```bash
# Terminal 1: Run the monitor
python test_lifecycle_events.py

# Terminal 2: Start/stop Kryten services to see events
python -m kryten config.json
```

### Send Groupwide Restart

```bash
# Using the helper script
python send_restart_notice.py "Configuration update" 10

# Or using NATS CLI
nats pub kryten.lifecycle.group.restart '{"initiator":"admin","reason":"Config reload","delay_seconds":5}'
```

### Subscribe with Python

```python
from nats.aio.client import Client as NATS
import json

async def handle_event(msg):
    data = json.loads(msg.data.decode('utf-8'))
    print(f"Event: {msg.subject}")
    print(f"Data: {data}")

nc = NATS()
await nc.connect("nats://localhost:4222")

# Monitor all lifecycle events
await nc.subscribe("kryten.lifecycle.>", cb=handle_event)
```

### Subscribe with NATS CLI

```bash
# Monitor all lifecycle events
nats sub "kryten.lifecycle.>"

# Monitor only startup events
nats sub "kryten.lifecycle.*.startup"

# Monitor only robot service
nats sub "kryten.lifecycle.robot.>"
```

## Integration with Other Services

### kryten-userstats

Add similar lifecycle event publishing:

```python
from kryten import LifecycleEventPublisher

# During startup
lifecycle = LifecycleEventPublisher(
    service_name="userstats",
    nats_client=nats_client,
    logger=logger,
    version="0.2.5"
)
await lifecycle.start()

# Register restart handler
async def handle_restart(data):
    delay = data.get('delay_seconds', 5)
    await asyncio.sleep(delay)
    shutdown_event.set()

lifecycle.on_restart_notice(handle_restart)

# Publish events at appropriate times
await lifecycle.publish_connected("NATS", ...)
await lifecycle.publish_startup(domain=..., channel=...)

# During shutdown
await lifecycle.publish_shutdown(reason="Normal shutdown")
await lifecycle.stop()
```

## Monitoring & Alerting

### Prometheus Metrics (Future)

Lifecycle events can be converted to Prometheus metrics:
- `kryten_service_up{service="robot"}` - Service up/down
- `kryten_service_restarts_total{service="robot"}` - Restart counter
- `kryten_connection_up{service="robot",target="CyTube"}` - Connection status

### Log Aggregation

Events include structured data perfect for log aggregation:
- Timestamp (ISO8601)
- Service name
- Hostname
- Version
- Uptime

### Health Checks

Services can monitor lifecycle events to determine group health:
- Last startup time
- Current uptime
- Connection status
- Recent restart frequency

## Restart Coordination

### Use Case: Config Reload

1. Admin updates configuration in git repo
2. CI/CD pipeline sends restart notice:
   ```bash
   python send_restart_notice.py "Config updated from git" 10
   ```
3. All services receive notice and log warning
4. After 10 seconds, services shutdown gracefully
5. Systemd restarts services with new config

### Use Case: Maintenance Window

1. Send restart notice with longer delay:
   ```bash
   python send_restart_notice.py "Maintenance window" 300
   ```
2. Services continue processing for 5 minutes
3. Services shutdown cleanly
4. Manual restart after maintenance complete

## Subject Pattern

All lifecycle events follow this pattern:
```
kryten.lifecycle.{service|group}.{event_type}
```

Examples:
- `kryten.lifecycle.robot.startup`
- `kryten.lifecycle.userstats.connected`
- `kryten.lifecycle.group.restart`

Wildcard subscriptions:
- `kryten.lifecycle.>` - All lifecycle events
- `kryten.lifecycle.*.startup` - All startup events
- `kryten.lifecycle.robot.>` - All robot events
- `kryten.lifecycle.group.>` - All group events

## Testing

### 1. Test Lifecycle Event Publishing

```bash
# Terminal 1: Monitor events
nats sub "kryten.lifecycle.>"

# Terminal 2: Start Kryten
python -m kryten config.json

# You should see:
# - robot.connected (NATS)
# - robot.connected (CyTube)
# - robot.startup

# Stop Kryten (Ctrl+C)
# You should see:
# - robot.disconnected (CyTube)
# - robot.shutdown
```

### 2. Test Restart Notice

```bash
# Terminal 1: Start Kryten
python -m kryten config.json

# Terminal 2: Send restart notice
python send_restart_notice.py "Test restart" 5

# Terminal 1: Should see warning and shutdown after 5s
```

### 3. Test Event Monitor

```bash
# Start the event monitor
python test_lifecycle_events.py

# Start/stop other Kryten services to see events
```

## Error Handling

- If NATS connection fails, lifecycle events are logged but not published
- If restart notice subscription fails, service continues without restart coordination
- Restart notice with invalid JSON is logged and ignored
- All event publishing errors are logged but don't crash the service

## Future Enhancements

1. **Service Discovery**: Use startup events to build service registry
2. **Health Aggregation**: Collect lifecycle events to generate overall system health
3. **Automatic Failover**: Detect disconnection events and trigger backup services
4. **Metrics Export**: Convert lifecycle events to Prometheus metrics
5. **Alerting**: Send notifications on unexpected shutdowns or frequent restarts
6. **Replay Buffer**: Store recent lifecycle events for debugging

## Version History

- **v0.6.0**: Initial lifecycle events implementation
  - Startup/shutdown events
  - Connection/disconnection events
  - Groupwide restart coordination

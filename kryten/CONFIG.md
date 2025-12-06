# Kryten Configuration Guide

This guide explains all configuration options for the Kryten CyTube connector.

## Quick Start

1. Copy `config.example.json` to `config.json`
2. Edit required fields (marked with ⚠️ below)
3. Customize optional fields as needed
4. Run Kryten: `python -m bot.kryten config.json`

## Configuration File Format

Kryten uses JSON configuration files. JSON does not support comments, so this guide explains each field.

## Configuration Sections

### CyTube Connection (`cytube`)

Configures connection to CyTube chat server.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `domain` | string | ⚠️ Yes | - | CyTube server domain (e.g., "cytu.be") |
| `channel` | string | ⚠️ Yes | - | Channel name to join (case-sensitive) |
| `channel_password` | string\|null | No | `null` | Password for password-protected channels |
| `user` | string\|null | No | `null` | Bot username for authentication |
| `password` | string\|null | No | `null` | Bot password (use env var for security) |

**Examples:**

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "MyAwesomeChannel",
    "channel_password": null,
    "user": "MyBot",
    "password": null
  }
}
```

**Security Notes:**
- Never commit passwords to version control
- Use environment variables: `KRYTEN_CYTUBE_USER`, `KRYTEN_CYTUBE_PASSWORD`
- Set `password: null` if using guest access

### NATS Message Bus (`nats`)

Configures connection to NATS message broker.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `servers` | array[string] | ⚠️ Yes | - | NATS server URLs (e.g., ["nats://localhost:4222"]) |
| `user` | string\|null | No | `null` | NATS username for authentication |
| `password` | string\|null | No | `null` | NATS password (use env var for security) |
| `connect_timeout` | integer | No | `10` | Connection timeout in seconds |
| `reconnect_time_wait` | integer | No | `2` | Wait time between reconnects in seconds |
| `max_reconnect_attempts` | integer | No | `10` | Maximum reconnection attempts |
| `allow_reconnect` | boolean | No | `true` | Enable automatic reconnection |

**Examples:**

Development (local NATS):
```json
{
  "nats": {
    "servers": ["nats://localhost:4222"],
    "user": null,
    "password": null,
    "connect_timeout": 10,
    "reconnect_time_wait": 2,
    "max_reconnect_attempts": 10,
    "allow_reconnect": true
  }
}
```

Production (authenticated, clustered):
```json
{
  "nats": {
    "servers": [
      "nats://nats1.example.com:4222",
      "nats://nats2.example.com:4222",
      "nats://nats3.example.com:4222"
    ],
    "user": "kryten_user",
    "password": null,
    "connect_timeout": 15,
    "reconnect_time_wait": 5,
    "max_reconnect_attempts": -1,
    "allow_reconnect": true
  }
}
```

**Security Notes:**
- Use environment variable: `KRYTEN_NATS_URL`
- Set `max_reconnect_attempts: -1` for infinite retries in production
- Use TLS URLs for production: `tls://nats.example.com:4222`

### Logging (`logging`)

Configures structured logging output.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `level` | string | No | `"INFO"` | Global log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `format` | string | No | `"text"` | Output format: "text" (human-readable) or "json" (structured) |
| `output` | string | No | `"console"` | Output destination: "console" (stdout) or "file" |
| `file_path` | string\|null | No | `null` | Log file path (required if output="file") |
| `max_bytes` | integer | No | `10485760` | Max log file size before rotation (10MB default) |
| `backup_count` | integer | No | `5` | Number of backup files to keep |
| `component_levels` | object | No | `{}` | Per-component log levels (see below) |

**Valid Log Levels:**
- `DEBUG` - Detailed diagnostic information
- `INFO` - General informational messages (default)
- `WARNING` - Warning messages for unexpected events
- `ERROR` - Error messages for failures
- `CRITICAL` - Critical failures requiring immediate attention

**Examples:**

Development (console, text, verbose):
```json
{
  "logging": {
    "level": "DEBUG",
    "format": "text",
    "output": "console",
    "file_path": null,
    "component_levels": {
      "bot.kryten.nats_client": "DEBUG",
      "bot.kryten.cytube_connector": "DEBUG"
    }
  }
}
```

Production (file, JSON, structured):
```json
{
  "logging": {
    "level": "INFO",
    "format": "json",
    "output": "file",
    "file_path": "/var/log/kryten/kryten.log",
    "max_bytes": 104857600,
    "backup_count": 10,
    "component_levels": {
      "bot.kryten.nats_client": "WARNING",
      "bot.kryten.health_monitor": "WARNING"
    }
  }
}
```

**Component-Specific Logging:**

You can set different log levels for specific components using `component_levels`:

```json
{
  "logging": {
    "level": "INFO",
    "component_levels": {
      "bot.kryten.nats_client": "DEBUG",
      "bot.kryten.cytube_connector": "WARNING",
      "bot.kryten.event_publisher": "DEBUG"
    }
  }
}
```

Available components:
- `bot.kryten.nats_client` - NATS connection and publishing
- `bot.kryten.cytube_connector` - CyTube Socket.IO connection
- `bot.kryten.event_publisher` - Event bridging logic
- `bot.kryten.health_monitor` - Health check HTTP server
- `bot.kryten.shutdown_handler` - Graceful shutdown coordination

**Sensitive Data Redaction:**

Kryten automatically redacts sensitive data in logs:
- Passwords → `***REDACTED***`
- Tokens → `***REDACTED***`
- API keys → `***REDACTED***`

### Health Monitoring (`health`)

Configures HTTP health check endpoint for operational visibility.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | boolean | No | `true` | Enable health monitoring HTTP server |
| `host` | string | No | `"0.0.0.0"` | HTTP server bind address |
| `port` | integer | No | `8080` | HTTP server port |

**Examples:**

Development (localhost only):
```json
{
  "health": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080
  }
}
```

Production (all interfaces, non-standard port):
```json
{
  "health": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 9090
  }
}
```

Disabled:
```json
{
  "health": {
    "enabled": false
  }
}
```

**Health Endpoints:**

When enabled, health monitoring exposes:

- **`GET /health`** - JSON health status
  - Returns 200 OK when healthy
  - Returns 503 Service Unavailable when unhealthy
  - Response includes component states and metrics

- **`GET /metrics`** - Prometheus-compatible metrics
  - Text format for Prometheus scraping
  - Includes uptime, event counts, error rates

**Example Response:**

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.45,
  "components": {
    "cytube_connector": "connected",
    "nats_client": "connected",
    "event_publisher": "running"
  },
  "metrics": {
    "events_received": 15420,
    "events_published": 15420,
    "publish_errors": 2,
    "nats_bytes_sent": 2048576
  }
}
```

**Kubernetes Integration:**

Use health endpoint for liveness and readiness probes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Legacy Top-Level Field

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `log_level` | string | No | `"INFO"` | **DEPRECATED**: Use `logging.level` instead |

This field is maintained for backward compatibility but will be removed in a future version.

## Environment Variable Overrides

Kryten supports environment variables to override sensitive configuration:

| Variable | Overrides | Example |
|----------|-----------|---------|
| `KRYTEN_CYTUBE_USER` | `cytube.user` | `export KRYTEN_CYTUBE_USER=MyBot` |
| `KRYTEN_CYTUBE_PASSWORD` | `cytube.password` | `export KRYTEN_CYTUBE_PASSWORD=secret` |
| `KRYTEN_NATS_URL` | `nats.servers[0]` | `export KRYTEN_NATS_URL=nats://prod:4222` |

**Docker Example:**

```bash
docker run -d \
  -e KRYTEN_CYTUBE_USER=MyBot \
  -e KRYTEN_CYTUBE_PASSWORD=secret123 \
  -e KRYTEN_NATS_URL=nats://nats:4222 \
  -v $(pwd)/config.json:/config/config.json \
  kryten:latest /config/config.json
```

**Kubernetes Secret:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kryten-secrets
type: Opaque
stringData:
  KRYTEN_CYTUBE_USER: "MyBot"
  KRYTEN_CYTUBE_PASSWORD: "secret123"
  KRYTEN_NATS_URL: "nats://nats:4222"
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: kryten
        envFrom:
        - secretRef:
            name: kryten-secrets
```

## Complete Examples

### Development Configuration

**File: `config-dev.json`**

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "test-channel",
    "channel_password": null,
    "user": "DevBot",
    "password": null
  },
  "nats": {
    "servers": ["nats://localhost:4222"],
    "user": null,
    "password": null,
    "connect_timeout": 10,
    "reconnect_time_wait": 2,
    "max_reconnect_attempts": 10,
    "allow_reconnect": true
  },
  "logging": {
    "level": "DEBUG",
    "format": "text",
    "output": "console",
    "file_path": null,
    "max_bytes": 10485760,
    "backup_count": 5,
    "component_levels": {
      "bot.kryten.nats_client": "DEBUG",
      "bot.kryten.cytube_connector": "DEBUG",
      "bot.kryten.event_publisher": "DEBUG"
    }
  },
  "health": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080
  },
  "log_level": "DEBUG"
}
```

### Production Configuration

**File: `config-prod.json`**

```json
{
  "cytube": {
    "domain": "cytu.be",
    "channel": "production-channel",
    "channel_password": null,
    "user": null,
    "password": null
  },
  "nats": {
    "servers": [
      "nats://nats1.prod.example.com:4222",
      "nats://nats2.prod.example.com:4222",
      "nats://nats3.prod.example.com:4222"
    ],
    "user": "kryten_prod",
    "password": null,
    "connect_timeout": 15,
    "reconnect_time_wait": 5,
    "max_reconnect_attempts": -1,
    "allow_reconnect": true
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "output": "file",
    "file_path": "/var/log/kryten/kryten.log",
    "max_bytes": 104857600,
    "backup_count": 10,
    "component_levels": {
      "bot.kryten.health_monitor": "WARNING"
    }
  },
  "health": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080
  },
  "log_level": "INFO"
}
```

## Validation

Test your configuration file:

```bash
# Validate JSON syntax
python -m json.tool config.json

# Test Kryten can load it
python -c "from bot.kryten import load_config; cfg = load_config('config.json'); print('Valid!')"
```

## Troubleshooting

### Common Errors

**FileNotFoundError: Configuration file not found**
- Check file path is correct
- Use absolute path if relative path fails

**ValueError: Invalid JSON**
- Validate JSON syntax (no trailing commas, proper quotes)
- Use `python -m json.tool config.json` to check

**ValueError: Missing required field: cytube.domain**
- Ensure all required fields present
- Check field names match exactly (case-sensitive)

**ValueError: Invalid log_level: 'debug'**
- Log levels must be uppercase: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Check both `log_level` and `logging.level`

### Getting Help

- Documentation: `docs/guides/LLM_CONFIGURATION.md`
- Architecture: `docs/ARCHITECTURE.md`
- Issues: File a GitHub issue with your config (redact passwords!)

## Migration from Old Format

If migrating from old Kryten config format:

**Old format:**
```json
{
  "cytube": {...},
  "nats": {
    "url": "nats://localhost:4222"
  },
  "log_level": "INFO"
}
```

**New format:**
```json
{
  "cytube": {...},
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "logging": {
    "level": "INFO"
  },
  "log_level": "INFO"
}
```

Key changes:
- `nats.url` → `nats.servers` (now array)
- Add `logging` section for advanced options
- Keep `log_level` for backward compatibility

---
title: LLM Chat Bot Observability Specification
version: 1.0
date_created: 2025-12-03
owner: Development Team
tags: [observability, logging, metrics, monitoring, health]
---

# Introduction

This specification defines the logging, metrics, health check, and monitoring capabilities of the LLM Chat Bot. These systems provide visibility into bot behavior, performance, and operational status.

## 1. Purpose & Scope

**Purpose**: Define structured logging format, Prometheus metrics, health check endpoints, and monitoring integration for operational visibility.

**Scope**: This specification covers:
- Structured JSON logging format
- Log levels and event types
- Correlation ID propagation
- Prometheus metrics (counters, histograms, gauges)
- Health check endpoint (/health)
- Metrics endpoint (/metrics)
- Integration with monitoring systems (Prometheus, Grafana)

**Audience**: Software engineers implementing logging and metrics. DevOps engineers configuring monitoring and alerting.

**Assumptions**:
- Python logging module for structured logs
- Prometheus client library for metrics
- HTTP server (aiohttp) for health/metrics endpoints
- Monitoring system can scrape /metrics endpoint

## 2. Definitions

- **Structured Logging**: JSON-formatted log entries with consistent fields
- **Correlation ID**: UUID tracking a request through the system
- **Metric**: Quantitative measurement of system behavior
- **Counter**: Metric that only increases (e.g., total requests)
- **Histogram**: Metric tracking distribution (e.g., latency buckets)
- **Gauge**: Metric that can increase or decrease (e.g., queue size)
- **Cardinality**: Number of unique label combinations for a metric
- **Scrape**: Prometheus polling /metrics endpoint

## 3. Requirements, Constraints & Guidelines

### Logging Requirements

- **REQ-001**: All logs SHALL use structured JSON format
- **REQ-002**: All logs SHALL include correlation ID for tracing
- **REQ-003**: All logs SHALL include timestamp (ISO 8601 UTC)
- **REQ-004**: All logs SHALL include log level, logger name, message
- **REQ-005**: Sensitive data (message content) SHALL be redacted or truncated

### Metrics Requirements

- **REQ-006**: Metrics SHALL use Prometheus format (text exposition)
- **REQ-007**: Metrics SHALL include HELP and TYPE comments
- **REQ-008**: Metrics SHALL have low cardinality (avoid unbounded labels)
- **REQ-009**: Health endpoint SHALL always return 200 OK (even if degraded)
- **REQ-010**: Metrics endpoint SHALL return current values (not historical)

### Observability Constraints

- **CON-001**: Log entries MUST NOT include full message content (privacy)
- **CON-002**: Metrics MUST NOT include usernames as labels (cardinality explosion)
- **CON-003**: Health check MUST complete within 100ms
- **CON-004**: Metrics endpoint MUST complete within 500ms
- **CON-005**: Log volume MUST NOT exceed 1000 entries/minute (prevent disk fill)

### Logging Guidelines

- **GUD-001**: Use DEBUG for verbose diagnostic information
- **GUD-002**: Use INFO for normal operational events (trigger fired, message sent)
- **GUD-003**: Use WARNING for recoverable errors (LLM timeout, rate limit exceeded)
- **GUD-004**: Use ERROR for unrecoverable errors (config invalid, NATS disconnect)
- **GUD-005**: Use CRITICAL for fatal errors (startup failure)

### Metrics Patterns

- **PAT-001**: Use counters for totals (events_received_total)
- **PAT-002**: Use histograms for latency (llm_request_duration_seconds)
- **PAT-003**: Use gauges for current state (context_window_size)
- **PAT-004**: Use labels for dimensions (event_type, channel, trigger_type)
- **PAT-005**: Use _total suffix for counters (Prometheus convention)

## 4. Interfaces & Data Contracts

### 4.1 Structured Log Format

```json
{
  "timestamp": "2025-12-03T12:34:56.789Z",
  "level": "INFO",
  "logger": "llm_bot.triggers.mention",
  "message": "Trigger fired",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "channel": "gaming",
  "trigger_type": "mention",
  "username": "Alice",
  "duration_ms": 125
}
```

**Required Fields**:
- `timestamp`: ISO 8601 UTC (e.g., "2025-12-03T12:34:56.789Z")
- `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `logger`: Module name (e.g., "llm_bot.triggers.mention")
- `message`: Human-readable description

**Optional Fields** (context-dependent):
- `correlation_id`: UUID for request tracing
- `channel`: CyTube channel name
- `username`: User who triggered event (no full message content)
- `trigger_type`: mention, keyword, contextual, pm
- `event_type`: chatMsg, pm, changeMedia
- `duration_ms`: Operation duration (for latency tracking)
- `error`: Error message (for ERROR/CRITICAL logs)
- `error_type`: Exception class name

### 4.2 Log Event Types

#### 4.2.1 Event Received

```json
{
  "timestamp": "2025-12-03T12:34:56.789Z",
  "level": "DEBUG",
  "logger": "llm_bot.event_handler",
  "message": "Event received",
  "correlation_id": "uuid",
  "channel": "gaming",
  "event_type": "chatMsg",
  "username": "Alice"
}
```

#### 4.2.2 Trigger Evaluation

```json
{
  "timestamp": "2025-12-03T12:34:56.800Z",
  "level": "DEBUG",
  "logger": "llm_bot.triggers.mention",
  "message": "Trigger evaluated",
  "correlation_id": "uuid",
  "trigger_type": "mention",
  "decision": "fire",
  "reason": null
}
```

#### 4.2.3 Trigger Suppressed

```json
{
  "timestamp": "2025-12-03T12:34:56.800Z",
  "level": "INFO",
  "logger": "llm_bot.triggers.keyword",
  "message": "Trigger suppressed",
  "correlation_id": "uuid",
  "trigger_type": "keyword",
  "decision": "suppress_rate_limit",
  "reason": "User rate limit exceeded (3/minute)"
}
```

#### 4.2.4 LLM API Request

```json
{
  "timestamp": "2025-12-03T12:34:57.000Z",
  "level": "DEBUG",
  "logger": "llm_bot.llm_client",
  "message": "LLM API request sent",
  "correlation_id": "uuid",
  "model": "gpt-4o-mini",
  "prompt_tokens": 150,
  "max_tokens": 100
}
```

#### 4.2.5 LLM API Response

```json
{
  "timestamp": "2025-12-03T12:34:58.500Z",
  "level": "INFO",
  "logger": "llm_bot.llm_client",
  "message": "LLM API response received",
  "correlation_id": "uuid",
  "duration_ms": 1500,
  "completion_tokens": 45,
  "finish_reason": "stop"
}
```

#### 4.2.6 Response Filtered

```json
{
  "timestamp": "2025-12-03T12:34:58.600Z",
  "level": "WARNING",
  "logger": "llm_bot.response_processor",
  "message": "Response filtered",
  "correlation_id": "uuid",
  "reason": "Contains blocked pattern (URL)",
  "filter_type": "content_filter"
}
```

#### 4.2.7 Message Sent

```json
{
  "timestamp": "2025-12-03T12:34:58.700Z",
  "level": "INFO",
  "logger": "llm_bot.nats_client",
  "message": "Command sent",
  "correlation_id": "uuid",
  "channel": "gaming",
  "command": "chat",
  "response_length": 87
}
```

#### 4.2.8 Error Occurred

```json
{
  "timestamp": "2025-12-03T12:34:59.000Z",
  "level": "ERROR",
  "logger": "llm_bot.llm_client",
  "message": "LLM API request failed",
  "correlation_id": "uuid",
  "error": "Connection timeout after 30s",
  "error_type": "TimeoutError",
  "retry_attempt": 2
}
```

### 4.3 Prometheus Metrics

#### 4.3.1 Counters

```python
from prometheus_client import Counter

# Events received from NATS
events_received_total = Counter(
    'events_received_total',
    'Total number of events received from NATS',
    ['event_type', 'channel']
)

# Triggers evaluated
triggers_evaluated_total = Counter(
    'triggers_evaluated_total',
    'Total number of trigger evaluations',
    ['trigger_type', 'channel']
)

# Triggers fired
triggers_fired_total = Counter(
    'triggers_fired_total',
    'Total number of triggers that fired',
    ['trigger_type', 'channel']
)

# Triggers suppressed
triggers_suppressed_total = Counter(
    'triggers_suppressed_total',
    'Total number of triggers suppressed',
    ['trigger_type', 'reason', 'channel']
)

# LLM API requests
llm_requests_total = Counter(
    'llm_requests_total',
    'Total number of LLM API requests',
    ['model', 'status']  # status: success, timeout, error
)

# Responses sent
responses_sent_total = Counter(
    'responses_sent_total',
    'Total number of responses sent to NATS',
    ['target_type', 'channel']  # target_type: chat, pm
)

# Responses filtered
responses_filtered_total = Counter(
    'responses_filtered_total',
    'Total number of responses filtered out',
    ['reason', 'channel']  # reason: length, content_filter, quality_check
)
```

#### 4.3.2 Histograms

```python
from prometheus_client import Histogram

# LLM API request duration
llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM API request duration in seconds',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Response length
response_length_characters = Histogram(
    'response_length_characters',
    'Response length in characters',
    ['channel'],
    buckets=[10, 50, 100, 150, 200, 250, 300]
)

# Event processing duration (receive to response)
event_processing_duration_seconds = Histogram(
    'event_processing_duration_seconds',
    'Time from event receipt to response sent',
    ['channel'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
```

#### 4.3.3 Gauges

```python
from prometheus_client import Gauge

# Context window size
context_window_size = Gauge(
    'context_window_size',
    'Current number of messages in context window',
    ['channel']
)

# Rate limit remaining
rate_limit_remaining = Gauge(
    'rate_limit_remaining',
    'Remaining capacity in rate limit window',
    ['limit_type', 'entity']  # limit_type: user_per_minute, channel_per_hour
)

# NATS connection state
nats_connected = Gauge(
    'nats_connected',
    'NATS connection state (1=connected, 0=disconnected)'
)

# LLM API availability
llm_api_available = Gauge(
    'llm_api_available',
    'LLM API availability (1=available, 0=unavailable)'
)

# Active channels
active_channels = Gauge(
    'active_channels',
    'Number of channels currently monitored'
)
```

### 4.4 Health Endpoint

**URL**: `GET /health`

**Response** (200 OK):
```json
{
  "status": "healthy",
  "uptime_seconds": 12345,
  "nats_connected": true,
  "llm_api_available": true,
  "channels": {
    "gaming": "active",
    "movies": "active"
  },
  "last_event_timestamp": "2025-12-03T12:34:56.789Z",
  "metrics": {
    "events_received": 1500,
    "triggers_fired": 45,
    "responses_sent": 42
  }
}
```

**Status Values**:
- `"healthy"`: All systems operational
- `"degraded"`: NATS or LLM API unavailable, but bot still running
- `"unhealthy"`: Critical failure (should not reach this state; bot would exit)

**Implementation**:
```python
from aiohttp import web
import time

start_time = time.time()

async def health_check(request):
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy" if nats_connected and llm_api_available else "degraded",
        "uptime_seconds": int(time.time() - start_time),
        "nats_connected": nats_client.is_connected(),
        "llm_api_available": llm_client.is_available(),
        "channels": {
            ch.name: "active" if ch.enabled else "disabled"
            for ch in config.channels
        },
        "last_event_timestamp": last_event_time.isoformat() if last_event_time else None,
        "metrics": {
            "events_received": int(events_received_total._value.sum()),
            "triggers_fired": int(triggers_fired_total._value.sum()),
            "responses_sent": int(responses_sent_total._value.sum())
        }
    })
```

### 4.5 Metrics Endpoint

**URL**: `GET /metrics`

**Response** (200 OK, text/plain):
```
# HELP events_received_total Total number of events received from NATS
# TYPE events_received_total counter
events_received_total{event_type="chatMsg",channel="gaming"} 1450
events_received_total{event_type="pm",channel="gaming"} 50

# HELP triggers_fired_total Total number of triggers that fired
# TYPE triggers_fired_total counter
triggers_fired_total{trigger_type="mention",channel="gaming"} 40
triggers_fired_total{trigger_type="keyword",channel="gaming"} 5

# HELP llm_request_duration_seconds LLM API request duration in seconds
# TYPE llm_request_duration_seconds histogram
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="0.5"} 5
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="1.0"} 15
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="2.0"} 30
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="5.0"} 40
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="10.0"} 42
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="30.0"} 42
llm_request_duration_seconds_bucket{model="gpt-4o-mini",le="+Inf"} 42
llm_request_duration_seconds_sum{model="gpt-4o-mini"} 85.5
llm_request_duration_seconds_count{model="gpt-4o-mini"} 42

# HELP context_window_size Current number of messages in context window
# TYPE context_window_size gauge
context_window_size{channel="gaming"} 45
context_window_size{channel="movies"} 32
```

**Implementation**:
```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

async def metrics_endpoint(request):
    """Prometheus metrics endpoint."""
    return web.Response(
        body=generate_latest(),
        content_type=CONTENT_TYPE_LATEST
    )
```

## 5. Acceptance Criteria

- **AC-001**: Given any log event, When logged, Then includes timestamp, level, logger, message
- **AC-002**: Given correlated request, When logged, Then same correlation_id in all logs
- **AC-003**: Given LLM API call, When logged, Then includes duration_ms
- **AC-004**: Given health check request, When /health called, Then returns 200 OK within 100ms
- **AC-005**: Given metrics request, When /metrics called, Then returns valid Prometheus format
- **AC-006**: Given trigger fires, When metrics checked, Then triggers_fired_total incremented
- **AC-007**: Given message content, When logged, Then content NOT included (privacy)
- **AC-008**: Given histogram metric, When queried, Then includes buckets, sum, count

## 6. Test Automation Strategy

- **Test Levels**: Unit tests for logging, metrics, health endpoint
- **Frameworks**: pytest, pytest-aiohttp
- **Test Data**: Mock events, log capture fixtures
- **Logging Tests**: Verify JSON structure, required fields
- **Metrics Tests**: Verify counter increments, histogram buckets
- **Health Tests**: Verify response format, status calculation
- **Integration Tests**: End-to-end request with full logging/metrics

## 7. Rationale & Context

### Why Structured JSON Logging?

**Advantages**:
- Machine-parseable (easy to index in Elasticsearch, Loki)
- Consistent schema (programmatic log analysis)
- Query-friendly (filter by correlation_id, channel, etc.)

**Disadvantages**:
- Less human-readable (use `jq` for pretty printing)
- Larger log files (JSON overhead)

**Decision**: Structured logging enables better observability tooling integration.

### Why Correlation IDs?

**Use Case**: Trace a single request through the entire system.

**Example**:
1. Event received (correlation_id=abc123)
2. Trigger evaluated (correlation_id=abc123)
3. LLM API request (correlation_id=abc123)
4. Response sent (correlation_id=abc123)

**Query**: `grep "abc123" logs.json` → See complete request flow

### Why Prometheus Metrics?

**Advantages**:
- Industry standard for monitoring
- Pull-based (bot doesn't push to server)
- Time-series database (historical data)
- Integrates with Grafana (dashboards)
- Alert manager (threshold alerts)

**Alternative**: StatsD (push-based)
- Requires external daemon
- More complex setup

**Decision**: Prometheus is simpler (just expose /metrics endpoint).

### Why Always Return 200 OK for /health?

**Philosophy**: Health check shows current state, not pass/fail.

**Rationale**:
- Load balancers often interpret 503 as "remove from pool"
- Bot can be degraded (LLM unavailable) but still functioning
- Return 200 with `"status": "degraded"` instead

**Exception**: If bot is completely non-functional, it would have exited (not serving /health).

### Why Low Cardinality for Metrics?

**Problem**: High cardinality = many unique label combinations = memory explosion.

**Bad Example**:
```python
# DON'T DO THIS: Unbounded cardinality (one label per user)
responses_sent_total = Counter(
    'responses_sent_total',
    'Responses sent',
    ['username']  # If 10,000 users → 10,000 time series
)
```

**Good Example**:
```python
# DO THIS: Bounded cardinality (fixed set of channels)
responses_sent_total = Counter(
    'responses_sent_total',
    'Responses sent',
    ['channel']  # If 10 channels → 10 time series
)
```

**Rule of Thumb**: Keep total label combinations < 1000.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Prometheus - Scrapes /metrics endpoint
- **EXT-002**: Grafana - Visualizes metrics dashboards
- **EXT-003**: Elasticsearch/Loki - Indexes structured logs (optional)

### Technology Platform Dependencies

- **PLT-001**: prometheus_client - Python library for metrics
- **PLT-002**: Python logging - Standard library
- **PLT-003**: aiohttp - HTTP server for endpoints

## 9. Examples & Edge Cases

### Example: Correlation ID Flow

```python
import uuid
import logging

logger = logging.getLogger(__name__)

async def handle_event(nats_msg):
    # Generate correlation ID
    correlation_id = nats_msg.headers.get('Correlation-Id') or str(uuid.uuid4())
    
    # Log with correlation ID
    logger.info("Event received",
                extra={
                    "correlation_id": correlation_id,
                    "channel": channel,
                    "event_type": "chatMsg"
                })
    
    # Pass to trigger evaluation
    result = await evaluate_triggers(event, correlation_id)
    
    if result:
        # Log response with same correlation ID
        logger.info("Response sent",
                    extra={
                        "correlation_id": correlation_id,
                        "response_length": len(result)
                    })
```

### Example: Histogram Usage

```python
import time
from prometheus_client import Histogram

llm_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0]
)

async def call_llm(prompt):
    start = time.time()
    try:
        response = await llm_client.complete(prompt)
        return response
    finally:
        duration = time.time() - start
        llm_duration.observe(duration)
```

### Edge Case: Log Volume Spike

```python
# Scenario: Spam attack (1000 messages/second)
# Without rate limiting: 1000 log entries/second × 60 = 60,000/minute
# Solution: Sample logs when rate limit exceeded

if rate_limit_exceeded:
    # Only log first occurrence
    if not rate_limit_logged:
        logger.warning("Rate limit exceeded", username=username)
        rate_limit_logged = True
else:
    rate_limit_logged = False
```

### Edge Case: High Cardinality Leak

```python
# BAD: Username in label (unbounded)
responses_sent_total.labels(username=username).inc()  # DON'T DO THIS

# GOOD: Username in log (not metric)
logger.info("Response sent", extra={"username": username})
responses_sent_total.labels(channel=channel).inc()  # DO THIS
```

## 10. Validation Criteria

- **VAL-001**: All logs include timestamp, level, logger, message
- **VAL-002**: All logs with correlation_id use same ID throughout request
- **VAL-003**: Log volume stays < 1000 entries/minute under normal load
- **VAL-004**: Health endpoint responds < 100ms (99th percentile)
- **VAL-005**: Metrics endpoint responds < 500ms (99th percentile)
- **VAL-006**: Histogram buckets cover expected latency range
- **VAL-007**: Metric cardinality < 1000 unique label combinations
- **VAL-008**: No sensitive data (message content) in logs

## 11. Related Specifications / Further Reading

- [Architecture Specification](./spec-architecture-design.md) - Component interactions
- [Data Contracts Specification](./spec-data-contracts.md) - Event schemas
- [Triggers Specification](./spec-triggers-ratelimiting.md) - Trigger decisions

**External References**:
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Structured Logging](https://www.honeycomb.io/blog/structured-logging-and-your-team)

---

## Grafana Dashboard Example

### Key Metrics to Display

**Panel 1: Event Rate**
- Query: `rate(events_received_total[5m])`
- Type: Graph (events/second)

**Panel 2: Trigger Success Rate**
- Query: `rate(triggers_fired_total[5m]) / rate(triggers_evaluated_total[5m])`
- Type: Gauge (percentage)

**Panel 3: LLM Latency**
- Query: `histogram_quantile(0.95, llm_request_duration_seconds_bucket)`
- Type: Graph (95th percentile)

**Panel 4: Response Filter Rate**
- Query: `rate(responses_filtered_total[5m])`
- Type: Graph (filters/second)

**Panel 5: Context Window Size**
- Query: `context_window_size`
- Type: Graph per channel

**Panel 6: Rate Limit Usage**
- Query: `rate_limit_remaining`
- Type: Bar chart

### Alert Rules

**High Error Rate**:
```yaml
alert: HighLLMErrorRate
expr: rate(llm_requests_total{status="error"}[5m]) > 0.1
for: 5m
annotations:
  summary: "LLM API error rate > 10%"
```

**NATS Disconnected**:
```yaml
alert: NATSDisconnected
expr: nats_connected == 0
for: 1m
annotations:
  summary: "NATS connection lost"
```

**High Response Filter Rate**:
```yaml
alert: HighFilterRate
expr: rate(responses_filtered_total[5m]) / rate(triggers_fired_total[5m]) > 0.5
for: 10m
annotations:
  summary: "More than 50% of responses filtered"
```

---

## Version History

- **v1.0** - 2025-12-03 - Initial observability specification

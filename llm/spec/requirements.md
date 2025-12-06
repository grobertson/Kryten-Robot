# LLM Chat Bot Requirements

## Overview

A standalone daemon that integrates OpenAI-compatible LLM APIs with CyTube chat through NATS messaging. The bot monitors chat activity and responds intelligently while maintaining tight control over response frequency, length, and relevance.

**Key Design Principle**: NATS is the only integration point. This bot never directly connects to CyTube - all communication flows through the Kryten connector via NATS.

---

## Architecture

### System Components

```
CyTube <-> Kryten Connector <-> NATS <-> LLM Bot <-> LLM API
```

**LLM Bot** is a standalone Python daemon that:
- Subscribes to NATS subjects for CyTube events
- Maintains chat context window
- Evaluates trigger conditions
- Queries LLM API when appropriate
- Publishes commands back to NATS for Kryten to execute

**No Direct CyTube Connection**: All CyTube interaction is via NATS commands processed by Kryten.

---

## Functional Requirements

### FR-001: Event Ingestion

**Requirement**: Bot SHALL subscribe to NATS subjects for CyTube events.

**Events to Monitor**:
- `cytube.events.{channel}.chatMsg` - Public chat messages
- `cytube.events.{channel}.pm` - Private messages to the bot
- `cytube.events.{channel}.changeMedia` - Video changes (optional context)

**Event Processing**:
- Parse event payload (username, message, timestamp, etc.)
- Add to rolling context window
- Evaluate against trigger conditions
- Track user interaction history

---

### FR-002: Context Window Management

**Requirement**: Bot SHALL maintain a configurable rolling window of recent chat messages.

**Configuration**:
- `context_window_size`: Number of messages to retain (default: 50)
- `context_max_age_seconds`: Maximum age of messages (default: 3600)
- `include_usernames`: Include usernames in context (default: true)
- `include_timestamps`: Include relative timestamps (default: false)

**Context Format**:
```
User1: Hey everyone!
User2: What's up?
User1: Just watching videos
```

**Context Cleanup**: Remove messages older than `context_max_age_seconds`.

---

### FR-003: Trigger Mechanisms

**Requirement**: Bot SHALL support multiple configurable trigger types.

#### FR-003.1: Direct Mention Trigger

**Activation**: Message contains `@botname`, bot username, or any configured alias.

**Configuration**:
```yaml
type: mention
enabled: true
fire_probability: 1.0
rate_limit:
  max_per_user_per_minute: 2
  max_per_channel_per_minute: 5
cooldown_seconds: 10
```

**Behavior**: Always consider triggering when mentioned (subject to rate limits).

**Detection**: Case-insensitive matching of bot username and all configured aliases.

#### FR-003.2: Keyword Trigger

**Activation**: Message contains specific words or phrases.

**Configuration**:
```yaml
type: keyword
enabled: true
keywords:
  - bot help
  - what do you think
  - any suggestions
case_sensitive: false
fire_probability: 0.3
rate_limit:
  max_per_hour: 10
cooldown_seconds: 60
```

**Behavior**: Probabilistically trigger when keyword detected.

#### FR-003.3: Contextual Participation Trigger

**Activation**: LLM evaluates chat context to decide if participation is appropriate.

**Configuration**:
```yaml
type: contextual
enabled: true
evaluation_interval_seconds: 120
fire_probability: 0.1
min_messages_since_last_bot_message: 5
# Prompt used to determine if bot should participate
participation_prompt: "Based on this chat, would it be natural for you to add a comment? Reply ONLY 'yes' or 'no'."
rate_limit:
  max_per_hour: 5
```

**Behavior**: Periodically evaluate context to participate naturally in conversation.

#### FR-003.4: Private Message Trigger

**Activation**: User sends PM to bot.

**Configuration**:
```yaml
type: pm
enabled: true
fire_probability: 1.0
rate_limit:
  max_per_user_per_minute: 3
cooldown_seconds: 5
```

**Behavior**: Always respond to PMs (subject to rate limits).

---

### FR-004: Rate Limiting and Cooldowns

**Requirement**: Bot SHALL enforce configurable rate limits to prevent spam.

#### FR-004.1: Per-User Rate Limits

**Purpose**: Prevent individual users from spamming bot.

**Tracking**: Count triggers per user over sliding time window.

**Configuration**:
- `max_per_user_per_minute`: Maximum triggers per user per minute
- `max_per_user_per_hour`: Maximum triggers per user per hour

**Behavior**: Silently ignore triggers exceeding limit.

#### FR-004.2: Per-Channel Rate Limits

**Purpose**: Prevent bot from dominating channel conversation.

**Tracking**: Count bot messages sent to channel over sliding time window.

**Configuration**:
- `max_per_channel_per_minute`: Maximum bot messages per minute
- `max_per_channel_per_hour`: Maximum bot messages per hour

**Behavior**: Queue or drop messages exceeding limit.

#### FR-004.3: Cooldown Periods

**Purpose**: Prevent rapid-fire responses.

**Tracking**: Time since last bot message (global and per-trigger-type).

**Configuration**:
- `global_cooldown_seconds`: Minimum seconds between any bot messages
- `per_trigger_cooldown_seconds`: Minimum seconds between same trigger type

**Behavior**: Suppress triggers during cooldown.

#### FR-004.4: Media Change Cooldown

**Purpose**: Avoid responding immediately when video changes.

**Configuration**:
- `media_change_cooldown_seconds`: Silence period after video changes (default: 30)

**Behavior**: Suppress all triggers for N seconds after `changeMedia` event.

---

### FR-005: LLM API Integration

**Requirement**: Bot SHALL integrate with OpenAI-compatible API endpoints.

#### FR-005.1: API Configuration

**Configuration**:
```yaml
api:
  base_url: https://api.openai.com/v1
  # API key from environment variable
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini
  timeout_seconds: 30
  retry_attempts: 2
  retry_delay_seconds: 1
```

**Supported Endpoints**:
- `/v1/chat/completions` (primary)
- Any OpenAI-compatible API (Ollama, LM Studio, etc.)

#### FR-005.2: Prompt Construction

**System Prompt** (configurable):
```
You are a helpful chat participant in a video watching community.
Keep responses under 200 characters.
Be concise, friendly, and relevant.
Avoid repeating yourself.
```

**User Prompt Template**:
```
Recent chat:
{context_window}

Respond to: {trigger_message}
```

**Configuration**:
- `system_prompt`: Bot personality and constraints
- `user_prompt_template`: Template for constructing user prompt
- `include_context_in_prompt`: Whether to include chat history
- `max_context_messages`: Maximum context messages in prompt (default: 20)

#### FR-005.3: API Request Parameters

**Configuration**:
```yaml
parameters:
  temperature: 0.7
  max_tokens: 100
  top_p: 0.9
  frequency_penalty: 0.5  # Reduce repetition
  presence_penalty: 0.3    # Encourage diverse topics
  stop:
    - "\n\n"
    - "User:"
    - "Assistant:"
```

**Constraints**: Optimize for short, focused responses.

---

### FR-006: Response Processing and Filtering

**Requirement**: Bot SHALL process and filter LLM responses before sending.

#### FR-006.1: Length Limits

**Purpose**: Enforce maximum response length.

**Configuration**:
- `max_response_length`: Maximum characters (default: 200)
- `truncation_strategy`: "hard" (cut at limit) or "sentence" (cut at sentence)

**Behavior**: 
- Truncate responses exceeding limit
- Add "..." if truncated mid-sentence

#### FR-006.2: Content Filtering

**Purpose**: Block inappropriate or unwanted responses.

**Configuration**:
```yaml
content_filter:
  enabled: true
  # Block URLs in responses
  block_patterns:
    - "http://"
    - "https://"
  block_keywords:
    - inappropriate
    - offensive
  require_keywords: []  # Optional: require certain words
  min_word_count: 2
  max_word_count: 50
```

**Behavior**: Drop responses matching block criteria.

#### FR-006.3: Quality Checks

**Purpose**: Ensure responses are relevant and appropriate.

**Checks**:
- Not empty or whitespace-only
- Not identical to recent bot messages (avoid repetition)
- Not just echoing user input
- Contains actual content (not just "okay" or "yes")

**Configuration**:
- `quality_checks_enabled`: Enable quality filtering
- `deduplicate_window`: Check last N bot messages for duplicates (default: 10)

#### FR-006.4: Formatting

**Purpose**: Clean up response for chat display.

**Processing**:
- Strip leading/trailing whitespace
- Remove markdown formatting (optional)
- Replace newlines with spaces
- Collapse multiple spaces

**Configuration**:
- `strip_markdown`: Remove markdown syntax (default: true)
- `collapse_newlines`: Replace newlines with spaces (default: true)

---

### FR-007: Response Delivery

**Requirement**: Bot SHALL send responses via NATS commands to Kryten.

#### FR-007.1: Channel Messages

**NATS Subject**: `cytube.commands.{channel}.chat`

**Message Format**:
```json
{
  "action": "chat",
  "data": {
    "message": "This is the bot response"
  }
}
```

**Note**: Message format remains JSON for NATS compatibility.

**Behavior**: Send to channel when trigger was public message.

#### FR-007.2: Private Messages

**NATS Subject**: `cytube.commands.{channel}.pm`

**Message Format**:
```json
{
  "action": "pm",
  "data": {
    "to": "username",
    "message": "This is the PM response"
  }
}
```

**Behavior**: Send PM when trigger was PM or user explicitly requested.

#### FR-007.3: Response Metadata

**Tracking**: Record sent messages for rate limiting and deduplication.

**Data Stored**:
- Message content
- Timestamp
- Target (channel/user)
- Trigger type
- Response time (API latency)

---

### FR-008: Configuration Management

**Requirement**: Bot SHALL support flexible, runtime-reloadable configuration.

**Configuration File**: `config.yaml`

**Top-Level Structure**:
```yaml
# NATS connection settings
nats:
  servers:
    - nats://localhost:4222
  user: null
  password: null

# CyTube channels to monitor (can specify multiple)
channels:
  - name: mychannel
    enabled: true
  - name: otherchannel
    enabled: false

# Bot identity
bot:
  username: MyBot
  # Alternate names the bot responds to
  aliases:
    - bot
    - assistant

# LLM API configuration (see FR-005.1)
llm_api:
  # ...

# Trigger configurations (see FR-003)
triggers:
  # ...

# Rate limiting (see FR-004)
rate_limits:
  # ...

# Response processing (see FR-006)
response_processing:
  # ...

# Context window settings (see FR-002)
context_window:
  # ...

log_level: INFO
```

**Environment Variables**: Support `${ENV_VAR}` substitution for secrets.

**Reload Signal**: `SIGHUP` triggers config reload without restart.

---

### FR-009: Logging and Observability

**Requirement**: Bot SHALL provide comprehensive logging and metrics.

#### FR-009.1: Structured Logging

**Log Events**:
- Event received (with rate limit decisions)
- Trigger evaluation (fired, suppressed, reason)
- LLM API request/response (with latency)
- Response filtering (passed, blocked, reason)
- Message sent
- Errors and exceptions

**Log Format**: JSON structured logs with correlation IDs.

#### FR-009.2: Metrics

**Counters**:
- `events_received_total{event_type}`
- `triggers_evaluated_total{trigger_type}`
- `triggers_fired_total{trigger_type}`
- `triggers_suppressed_total{reason}`
- `llm_requests_total{status}`
- `responses_sent_total{target_type}`
- `responses_filtered_total{reason}`

**Histograms**:
- `llm_request_duration_seconds`
- `response_length_characters`

**Gauges**:
- `context_window_size`
- `rate_limit_remaining{limit_type}`

#### FR-009.3: Health Endpoint

**HTTP Endpoint**: `GET /health`

**Response** (JSON format):
```json
{
  "status": "healthy",
  "uptime_seconds": 12345,
  "nats_connected": true,
  "llm_api_available": true,
  "channels": {
    "mychannel": "active",
    "otherchannel": "active"
  },
  "last_event_timestamp": "2025-12-03T12:34:56Z",
  "metrics": {
    "events_received": 1500,
    "triggers_fired": 45,
    "responses_sent": 42
  }
}
```

#### FR-009.4: Metrics Endpoint

**HTTP Endpoint**: `GET /metrics`

**Format**: Prometheus text format

**Response Example**:
```
# HELP events_received_total Total number of events received from NATS
# TYPE events_received_total counter
events_received_total{event_type="chatMsg"} 1450
events_received_total{event_type="pm"} 50

# HELP triggers_fired_total Total number of triggers that fired
# TYPE triggers_fired_total counter
triggers_fired_total{trigger_type="mention"} 40
triggers_fired_total{trigger_type="keyword"} 5

# HELP llm_request_duration_seconds LLM API request duration
# TYPE llm_request_duration_seconds histogram
llm_request_duration_seconds_bucket{le="0.5"} 20
llm_request_duration_seconds_bucket{le="1.0"} 35
llm_request_duration_seconds_sum 42.5
llm_request_duration_seconds_count 42

# HELP context_window_size Current context window size per channel
# TYPE context_window_size gauge
context_window_size{channel="mychannel"} 45
```

**Behavior**: Returns current metric values in Prometheus format for monitoring integration.

---

### FR-010: Multi-Channel Support

**Requirement**: Bot SHALL support monitoring and responding to multiple CyTube channels simultaneously.

#### FR-010.1: Channel Configuration

**Configuration**:
```yaml
channels:
  - name: mainchannel
    enabled: true
    # Per-channel trigger overrides (optional)
    triggers:
      - type: mention
        fire_probability: 1.0
  
  - name: testchannel
    enabled: true
    # Inherit global trigger config
  
  - name: archivedchannel
    enabled: false  # Don't monitor this channel
```

**Behavior**:
- Subscribe to NATS subjects for all enabled channels
- Maintain separate context windows per channel
- Apply per-channel rate limits independently
- Support channel-specific trigger overrides

#### FR-010.2: Channel Isolation

**Context Windows**: Each channel maintains its own rolling context window.

**Rate Limits**: Rate limits are tracked per-channel (but per-user limits span all channels).

**Trigger Evaluation**: Triggers evaluated independently per channel.

#### FR-010.3: Channel-Specific Configuration

**Per-Channel Overrides**:
- Custom trigger configurations
- Different LLM models per channel
- Channel-specific system prompts
- Custom rate limits

**Example**:
```yaml
channels:
  - name: serious_discussion
    enabled: true
    system_prompt: "You are a thoughtful, serious discussion participant."
    llm_model: gpt-4  # Use more capable model for serious discussions
    triggers:
      - type: mention
        fire_probability: 1.0
        cooldown_seconds: 30
  
  - name: casual_chat
    enabled: true
    system_prompt: "You are a fun, casual chat participant."
    llm_model: gpt-4o-mini  # Use faster/cheaper model for casual chat
    triggers:
      - type: mention
        fire_probability: 1.0
        cooldown_seconds: 5
      - type: contextual
        fire_probability: 0.3
```

#### FR-010.4: Dynamic Channel Management

**Runtime Changes**:
- Add/remove channels via config reload (SIGHUP)
- Enable/disable channels without restart
- Update per-channel settings on the fly

**Subscription Management**:
- Automatically subscribe to newly enabled channels
- Unsubscribe from disabled channels
- Clean up context windows for disabled channels

---

### FR-011: Error Handling

**Requirement**: Bot SHALL handle errors gracefully without crashing.

#### FR-011.1: NATS Connection Errors

**Behavior**:
- Automatic reconnection with exponential backoff
- Log connection state changes
- Queue outbound messages during disconnection (limited buffer)

#### FR-011.2: LLM API Errors

**Behavior**:
- Retry on timeout or 5xx errors
- Log and skip on 4xx errors (bad request)
- Fallback message on persistent failures (optional)

**Configuration**:
- `fallback_responses_enabled`: Use canned responses on API failure
- `fallback_responses`: List of generic responses

#### FR-011.3: Rate Limit Exceeded (API)

**Behavior**:
- Back off exponentially
- Log rate limit hit
- Skip response (don't spam retries)

#### FR-011.4: Invalid Events

**Behavior**:
- Log warning
- Skip event
- Don't crash

---

### FR-012: Startup and Shutdown

**Requirement**: Bot SHALL start up cleanly and shut down gracefully.

#### FR-012.1: Startup Sequence

**Order**:
1. Load configuration from YAML file
2. Validate configuration (check required fields, valid channel names, etc.)
3. Initialize logging subsystem
4. Connect to NATS with retry logic
5. Initialize LLM API client (optional health check)
6. Subscribe to NATS subjects for all enabled channels
7. Start HTTP server for health/metrics endpoints
8. Log "Bot ready" message with channel list

**Validation**:
- Fail fast if config is invalid (missing required fields, malformed YAML)
- Retry NATS connection with exponential backoff (max 5 attempts)
- Continue without LLM API if health check fails (degrade gracefully)

#### FR-012.2: Graceful Shutdown

**Trigger Signals**:
- `SIGTERM` - Graceful shutdown (systemd, Docker)
- `SIGINT` - Graceful shutdown (Ctrl+C)

**Shutdown Sequence**:
1. Log "Shutdown initiated" message
2. Stop accepting new events (unsubscribe from NATS)
3. Wait for in-flight LLM API requests to complete (max 30s timeout)
4. Flush any pending messages to NATS
5. Close NATS connection
6. Stop HTTP server
7. Close log handlers
8. Exit with code 0

**Behavior**:
- Don't drop in-flight responses
- Log all shutdown steps for debugging
- Use asyncio task cancellation for clean async shutdown

#### FR-012.3: Process Management

**PID File**: Optional creation of PID file for process management.

**Exit Codes**:
- `0` - Clean shutdown
- `1` - Configuration error
- `2` - NATS connection failure (exhausted retries)
- `3` - Critical runtime error

**Systemd Integration**:
- Type=notify support (optional)
- Ready signal after startup complete
- Watchdog support (optional keepalive)

---

## Non-Functional Requirements

### NFR-001: Performance

- Process events within 100ms (excluding LLM API time)
- Maintain context window with O(1) operations
- Support 1000+ messages/hour throughput

### NFR-002: Reliability

- Graceful degradation when LLM API unavailable
- No message loss on restart (durable NATS subscriptions)
- Automatic recovery from transient failures

### NFR-003: Resource Usage

- Memory: < 100MB base, < 500MB with large context
- CPU: < 5% idle, < 50% during LLM requests
- Disk: Minimal (logs only, no state persistence)

### NFR-004: Security

- API keys stored in environment variables
- No logging of sensitive message content (optional redaction)
- Rate limiting prevents abuse

### NFR-005: Maintainability

- Clear configuration file with comments
- Structured logs for debugging
- Modular architecture (easy to add trigger types)

---

## Out of Scope (Future Enhancements)

- Persistent conversation memory across restarts
- Learning from user feedback
- Voice/audio integration
- Image generation or analysis
- Custom LLM fine-tuning
- Web UI for configuration
- Distributed deployment across multiple bots

---

## Success Criteria

1. **Natural Participation**: Bot contributes meaningfully without dominating chat
2. **Low Latency**: Responses feel near-instant (< 5s typical)
3. **Controlled Output**: Responses consistently under 200 characters
4. **No Spam**: Rate limits prevent bot from overwhelming users
5. **High Reliability**: Operates for days without intervention
6. **Easy Configuration**: Non-developers can tune trigger behavior

---

## Implementation Notes

### Technology Stack

- **Language**: Python 3.11+
- **NATS Client**: `nats-py`
- **HTTP Client**: `httpx` (async)
- **LLM API**: OpenAI Python SDK (compatible mode)
- **Logging**: Python `logging` module (structured JSON)
- **Config**: YAML with inline comments and environment variable expansion
- **YAML Parser**: `PyYAML` or `ruamel.yaml` (for preserving comments)
- **Metrics**: Prometheus client library for `/metrics` endpoint
- **HTTP Server**: `aiohttp` (async HTTP server for health/metrics endpoints)

### Project Structure

```
llm/
├── spec/
│   └── requirements.md          # This document
├── llm_bot/
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   ├── config.py                # Configuration loading
│   ├── nats_client.py           # NATS connection
│   ├── event_handler.py         # Event processing
│   ├── context_window.py        # Chat context management
│   ├── triggers/
│   │   ├── __init__.py
│   │   ├── base.py              # Base trigger class
│   │   ├── mention.py           # Mention trigger
│   │   ├── keyword.py           # Keyword trigger
│   │   ├── contextual.py        # Contextual trigger
│   │   └── pm.py                # PM trigger
│   ├── llm_client.py            # LLM API client
│   ├── response_processor.py   # Response filtering
│   ├── rate_limiter.py          # Rate limit enforcement
│   ├── health.py                # Health and metrics HTTP server
│   └── shutdown_handler.py      # Graceful shutdown coordination
├── tests/
│   └── ...                      # Unit and integration tests
├── config.example.yaml          # Example configuration
├── README.md                    # Setup and usage
├── requirements.txt             # Python dependencies
└── pyproject.toml               # Package metadata
```

### Development Phases

**Phase 1 - Core Functionality** (MVP):
- NATS event subscription (single channel for simplicity)
- Basic context window
- Mention trigger only
- Simple LLM API integration
- Basic response filtering (length only)
- Channel message responses
- Health endpoint
- Graceful startup/shutdown

**Phase 2 - Enhanced Triggers**:
- Multi-channel support
- Keyword triggers with probability
- PM triggers
- Global rate limiting
- Per-user cooldowns

**Phase 3 - Advanced Features**:
- Contextual participation trigger
- Advanced response filtering
- Quality checks and deduplication
- Metrics and health endpoint

**Phase 4 - Production Readiness**:
- Comprehensive error handling
- Logging and observability
- Configuration reload
- Documentation and examples

---

## Dependencies on Kryten

This bot depends on Kryten connector being operational:

1. **NATS Events**: Kryten publishes CyTube events to NATS
2. **Command Execution**: Kryten processes commands from NATS and sends to CyTube
3. **Event Format**: Bot must parse Kryten's event JSON format
4. **Subject Naming**: Bot uses Kryten's subject naming convention

**No changes required to Kryten** - bot operates as a pure consumer/publisher of NATS messages.

---

## Testing Strategy

### Unit Tests

- Context window operations
- Trigger evaluation logic
- Rate limiter tracking
- Response processing and filtering
- Configuration parsing

### Integration Tests

- NATS message flow (mock)
- LLM API interaction (mock)
- End-to-end trigger to response

### Manual Testing

- Deploy alongside Kryten on test channel
- Trigger bot with various message patterns
- Verify rate limits and cooldowns
- Test error recovery (kill LLM API, NATS)

---

## Example Configurations

### Conservative Bot (Low Activity)

```yaml
# Only respond to direct mentions and PMs
triggers:
  - type: mention
    fire_probability: 1.0
    cooldown_seconds: 30
  
  - type: pm
    fire_probability: 1.0
    cooldown_seconds: 10

rate_limits:
  max_per_channel_per_hour: 10
  max_per_user_per_hour: 3
```

### Active Participant (Higher Engagement)

```yaml
# More active participation with keywords and context
triggers:
  - type: mention
    fire_probability: 1.0
    cooldown_seconds: 10
  
  - type: keyword
    keywords:
      - bot
      - think
      - opinion
    fire_probability: 0.5
    cooldown_seconds: 60
  
  - type: contextual
    evaluation_interval_seconds: 180
    fire_probability: 0.2

rate_limits:
  max_per_channel_per_hour: 30
```

### Multi-Channel Configuration

```yaml
# Bot active on multiple channels with different personalities
channels:
  - name: gaming
    enabled: true
    system_prompt: "You are an enthusiastic gaming community member."
    triggers:
      - type: mention
        fire_probability: 1.0
      - type: keyword
        keywords: ["gg", "nice play", "thoughts"]
        fire_probability: 0.4
  
  - name: movies
    enabled: true
    system_prompt: "You are a film enthusiast with thoughtful opinions."
    triggers:
      - type: mention
        fire_probability: 1.0
      - type: contextual
        fire_probability: 0.15
  
  - name: music
    enabled: true
    # Inherits global configuration
```

---

## Version History

- **v1.1** - 2025-12-03 - Added FR-012 (startup/shutdown), metrics endpoint, per-channel LLM models, alias detection
- **v1.0** - 2025-12-03 - Initial requirements document

---
title: LLM Chat Bot Architecture and Design Specification
version: 1.0
date_created: 2025-12-03
owner: Development Team
tags: [architecture, design, llm, nats, async]
---

# Introduction

This specification defines the architecture and design of the LLM Chat Bot, a standalone daemon that integrates OpenAI-compatible LLM APIs with CyTube chat through NATS messaging. The bot monitors chat activity across multiple channels and responds intelligently while maintaining tight control over response frequency, length, and relevance.

## 1. Purpose & Scope

**Purpose**: Define the architectural patterns, component interactions, and design decisions for the LLM Chat Bot system.

**Scope**: This specification covers:
- System architecture and component boundaries
- NATS integration patterns
- Asyncio-based concurrency model
- Multi-channel isolation
- Component lifecycle management
- Error handling strategies

**Audience**: Software engineers implementing or extending the LLM Chat Bot.

**Assumptions**:
- Python 3.11+ runtime environment
- NATS server available (localhost or remote)
- Kryten connector operational and publishing events
- OpenAI-compatible LLM API accessible

## 2. Definitions

- **LLM**: Large Language Model (e.g., GPT-4, Claude)
- **NATS**: Neural Autonomic Transport System (messaging system)
- **Kryten**: CyTube connector that publishes events to NATS
- **Trigger**: Condition that causes bot to evaluate whether to respond
- **Context Window**: Rolling buffer of recent chat messages
- **Channel**: CyTube channel (e.g., "gaming", "movies")
- **Subject**: NATS topic name (e.g., "cytube.events.gaming.chatMsg")
- **Correlation ID**: Unique identifier tracking a request through the system

## 3. Requirements, Constraints & Guidelines

### Architecture Requirements

- **REQ-001**: System SHALL use asyncio for all I/O operations (NATS, HTTP, LLM API)
- **REQ-002**: System SHALL maintain complete isolation between channels (separate context windows, rate limiters)
- **REQ-003**: System SHALL use NATS as the ONLY integration point with CyTube
- **REQ-004**: System SHALL support runtime configuration reload without restart (SIGHUP)
- **REQ-005**: System SHALL implement graceful shutdown (SIGTERM/SIGINT)

### Design Constraints

- **CON-001**: All NATS operations MUST be non-blocking (async)
- **CON-002**: LLM API calls MUST have timeout protection (default 30s)
- **CON-003**: Context windows MUST have bounded memory usage (max 50 messages per channel)
- **CON-004**: HTTP server MUST be lightweight (health/metrics only, no admin UI)
- **CON-005**: No persistent state storage (in-memory only, stateless across restarts)

### Design Guidelines

- **GUD-001**: Use dependency injection for testability
- **GUD-002**: Prefer composition over inheritance
- **GUD-003**: Use type hints for all public APIs
- **GUD-004**: Log all state transitions with correlation IDs
- **GUD-005**: Fail fast on startup, degrade gracefully at runtime

### Design Patterns

- **PAT-001**: Use Strategy pattern for trigger implementations
- **PAT-002**: Use Observer pattern for event distribution
- **PAT-003**: Use Factory pattern for channel context creation
- **PAT-004**: Use Singleton pattern for metrics collector
- **PAT-005**: Use Command pattern for NATS message handlers

## 4. Interfaces & Data Contracts

### 4.1 NATS Event Subscription

**Pattern**: Subscribe to wildcard subjects for all enabled channels.

**Subject Pattern**: `cytube.events.{channel}.*`

**Event Types**:
- `cytube.events.{channel}.chatMsg` - Public chat message
- `cytube.events.{channel}.pm` - Private message to bot
- `cytube.events.{channel}.changeMedia` - Video change event

**Message Format**: JSON with correlation ID in NATS headers.

### 4.2 NATS Command Publication

**Pattern**: Publish commands to channel-specific subjects.

**Subject Pattern**: `cytube.commands.{channel}.{action}`

**Actions**:
- `chat` - Send public message
- `pm` - Send private message

**Message Format**: JSON with action and data fields.

### 4.3 HTTP Endpoints

**Health Endpoint**: `GET /health`
- Returns JSON with system status
- Always returns 200 OK (even if degraded)

**Metrics Endpoint**: `GET /metrics`
- Returns Prometheus text format
- Includes counters, histograms, gauges

### 4.4 LLM API Client

**Protocol**: HTTP POST to `/v1/chat/completions`

**Request Format**: OpenAI-compatible JSON
- `model`: Model identifier
- `messages`: Array of message objects
- `temperature`, `max_tokens`, etc.

**Response Format**: JSON with `choices` array
- Extract `choices[0].message.content`

## 5. Acceptance Criteria

- **AC-001**: Given NATS is available, When bot starts, Then it connects within 5 seconds
- **AC-002**: Given a chatMsg event, When mention trigger fires, Then response sent within 5 seconds (excluding LLM latency)
- **AC-003**: Given multi-channel config, When event received on channel A, Then it does not affect channel B context
- **AC-004**: Given NATS disconnect, When reconnection succeeds, Then bot resumes event processing
- **AC-005**: Given SIGTERM received, When in-flight requests exist, Then bot waits max 30s before exit
- **AC-006**: Given invalid YAML config, When bot starts, Then it exits with code 1 and logs error
- **AC-007**: Given config reload (SIGHUP), When new channels added, Then bot subscribes without restart

## 6. Test Automation Strategy

- **Test Levels**: Unit, Integration, End-to-End
- **Frameworks**: pytest, pytest-asyncio, pytest-mock
- **Test Data**: Fixtures for NATS events, LLM responses, config files
- **CI/CD Integration**: GitHub Actions with NATS test container
- **Coverage Requirements**: Minimum 80% line coverage
- **Mocking Strategy**: Mock NATS client and LLM API client at integration layer

## 7. Rationale & Context

### Why Asyncio?

Python's asyncio provides:
- Efficient I/O multiplexing for NATS subscriptions
- Native async HTTP client support (httpx, aiohttp)
- Structured concurrency with task groups
- Built-in cancellation support for graceful shutdown

### Why NATS-Only Integration?

- **Separation of Concerns**: Bot doesn't need to know CyTube protocol
- **Resilience**: Kryten failure doesn't crash bot (NATS buffers)
- **Scalability**: Multiple bots can subscribe to same events
- **Testability**: Easy to mock NATS messages for testing

### Why No Persistent State?

- **Simplicity**: No database or file system dependencies
- **Stateless**: Easy to restart or scale horizontally
- **Performance**: All operations in-memory (no I/O latency)
- **Reliability**: No state corruption on crash

### Why Multi-Channel Isolation?

- **Fairness**: One busy channel doesn't starve others
- **Customization**: Different triggers/prompts per channel
- **Rate Limiting**: Independent rate limits per channel
- **Context Relevance**: Chat history specific to each channel

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Kryten Connector - Publishes CyTube events to NATS (required)
- **EXT-002**: NATS Server - Message broker (required)
- **EXT-003**: LLM API - OpenAI-compatible endpoint (required)

### Third-Party Services

- **SVC-001**: OpenAI API or compatible - LLM inference (configurable endpoint)

### Infrastructure Dependencies

- **INF-001**: Python 3.11+ runtime - asyncio, type hints
- **INF-002**: Network connectivity - NATS and LLM API access
- **INF-003**: HTTP port for health/metrics - Default 8080

### Technology Platform Dependencies

- **PLT-001**: NATS messaging protocol - At least v2.0 for headers support
- **PLT-002**: OpenAI API v1 - /v1/chat/completions endpoint

## 9. Examples & Edge Cases

### Example: Event Flow

```python
# 1. Receive NATS event
event = {
    "user": {"name": "Alice"},
    "msg": "@bot what do you think?",
    "time": 1701622800000
}

# 2. Evaluate trigger
trigger = MentionTrigger(config)
should_fire = trigger.evaluate(event, context)  # True

# 3. Check rate limits
if rate_limiter.allow(user="Alice", channel="gaming"):
    # 4. Query LLM
    response = await llm_client.complete(prompt, context_window)
    
    # 5. Process response
    filtered = response_processor.filter(response)
    
    # 6. Send via NATS
    await nats_client.publish(
        subject="cytube.commands.gaming.chat",
        data={"action": "chat", "data": {"message": filtered}}
    )
```

### Edge Case: NATS Reconnection

```python
# Scenario: NATS connection drops mid-operation
async def handle_nats_disconnect():
    # 1. Log disconnect event
    logger.warning("NATS disconnected", correlation_id=cid)
    
    # 2. Buffer outbound messages (up to 100)
    pending_queue.append(message)
    
    # 3. Attempt reconnection with exponential backoff
    for attempt in range(5):
        await asyncio.sleep(2 ** attempt)
        if await nats_client.reconnect():
            # 4. Flush pending queue
            for msg in pending_queue:
                await nats_client.publish(msg)
            return
    
    # 5. Degrade gracefully (discard queue, continue read-only)
    logger.error("NATS reconnection failed, entering degraded mode")
```

### Edge Case: LLM API Timeout

```python
# Scenario: LLM API hangs beyond timeout
async def query_llm_with_timeout(prompt: str) -> str:
    try:
        # Timeout after 30 seconds
        response = await asyncio.wait_for(
            llm_client.complete(prompt),
            timeout=30.0
        )
        return response
    except asyncio.TimeoutError:
        logger.warning("LLM API timeout", prompt_preview=prompt[:50])
        # Return None, trigger will be suppressed
        return None
```

### Edge Case: Config Reload During Request

```python
# Scenario: SIGHUP received while processing trigger
async def handle_sighup():
    # 1. Load new config
    new_config = Config.load("config.yaml")
    
    # 2. Wait for in-flight requests (max 5s)
    await asyncio.wait_for(
        wait_for_inflight_requests(),
        timeout=5.0
    )
    
    # 3. Swap config atomically
    app.config = new_config
    
    # 4. Update channel subscriptions
    await update_channel_subscriptions(new_config.channels)
    
    logger.info("Configuration reloaded", channels=len(new_config.channels))
```

## 10. Validation Criteria

- **VAL-001**: All async functions use `async def` and `await` correctly
- **VAL-002**: No blocking I/O in asyncio event loop (no `time.sleep`, `requests.get`)
- **VAL-003**: All NATS publish operations check connection state
- **VAL-004**: All LLM API calls wrapped in timeout protection
- **VAL-005**: Graceful shutdown completes within 35 seconds (30s timeout + 5s cleanup)
- **VAL-006**: Memory usage stays below 500MB under load (1000 msg/hr)
- **VAL-007**: Health endpoint responds within 100ms
- **VAL-008**: Config validation fails fast (exit code 1) on startup

## 11. Related Specifications / Further Reading

- [Data Contracts Specification](./spec-data-contracts.md) - NATS message schemas
- [Configuration Specification](./spec-configuration.md) - YAML config schema
- [Triggers Specification](./spec-triggers.md) - Trigger evaluation logic
- [Observability Specification](./spec-observability.md) - Logging and metrics

**External References**:
- [NATS Documentation](https://docs.nats.io/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)

---

## Component Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                      LLM Chat Bot Process                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────┐      ┌──────────────────┐                │
│  │ Main Loop     │─────▶│ Event Handler    │                │
│  │ (asyncio)     │      │ (per channel)    │                │
│  └───────────────┘      └──────────────────┘                │
│         │                        │                            │
│         │                        ▼                            │
│         │               ┌──────────────────┐                 │
│         │               │ Trigger Manager  │                 │
│         │               │ - Mention        │                 │
│         │               │ - Keyword        │                 │
│         │               │ - Contextual     │                 │
│         │               │ - PM             │                 │
│         │               └──────────────────┘                 │
│         │                        │                            │
│         │                        ▼                            │
│         │               ┌──────────────────┐                 │
│         │               │ Rate Limiter     │                 │
│         │               │ (sliding window) │                 │
│         │               └──────────────────┘                 │
│         │                        │                            │
│         │                        ▼                            │
│         │               ┌──────────────────┐                 │
│         │               │ LLM Client       │───────┐         │
│         │               │ (httpx async)    │       │         │
│         │               └──────────────────┘       │         │
│         │                        │                 │         │
│         │                        ▼                 │         │
│         │               ┌──────────────────┐      │         │
│         │               │ Response Proc    │      │         │
│         │               │ - Filter         │      │         │
│         │               │ - Format         │      │         │
│         │               │ - Validate       │      │         │
│         │               └──────────────────┘      │         │
│         │                        │                │         │
│         ▼                        ▼                │         │
│  ┌──────────────┐      ┌──────────────────┐     │         │
│  │ NATS Client  │◀─────│ Context Window   │     │         │
│  │ (nats-py)    │      │ (per channel)    │     │         │
│  └──────────────┘      └──────────────────┘     │         │
│         │                                        │         │
│         │                                        │         │
│  ┌──────────────┐                               │         │
│  │ HTTP Server  │                               │         │
│  │ (aiohttp)    │                               │         │
│  │ - /health    │                               │         │
│  │ - /metrics   │                               │         │
│  └──────────────┘                               │         │
│                                                  │         │
└──────────────────────────────────────────────────┼─────────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │ LLM API        │
                                          │ (external)     │
                                          └────────────────┘
         ▲                                      
         │                                      
         │ NATS Messages                        
         │                                      
┌────────┴────────┐                             
│ NATS Server     │                             
│ (external)      │                             
└─────────────────┘                             
         ▲                                      
         │                                      
┌────────┴────────┐                             
│ Kryten          │                             
│ Connector       │                             
└─────────────────┘                             
```

### Component Responsibilities

#### Main Loop (\_\_main\_\_.py)
- Load configuration
- Initialize all components
- Start asyncio event loop
- Handle signals (SIGTERM, SIGINT, SIGHUP)
- Coordinate graceful shutdown

#### NATS Client (nats_client.py)
- Connect to NATS servers
- Subscribe to event subjects
- Publish command messages
- Handle reconnection with exponential backoff
- Track connection state metrics

#### Event Handler (event_handler.py)
- Receive NATS events
- Parse event payload
- Update context window
- Dispatch to trigger manager
- Generate correlation IDs

#### Context Window (context_window.py)
- Store last N messages per channel
- Expire old messages by age
- Format context for LLM prompt
- Provide O(1) add/remove operations
- Track window size metrics

#### Trigger Manager (triggers/base.py)
- Evaluate all enabled triggers
- Apply fire probability (random selection)
- Check cooldown periods
- Coordinate with rate limiter
- Log trigger decisions

#### Trigger Implementations (triggers/*.py)
- **MentionTrigger**: Detect @mentions and aliases (case-insensitive)
- **KeywordTrigger**: Match configured keywords/phrases
- **ContextualTrigger**: Use LLM to evaluate participation
- **PMTrigger**: Always fire on private messages

#### Rate Limiter (rate_limiter.py)
- Track per-user trigger counts (sliding window)
- Track per-channel message counts (sliding window)
- Enforce global cooldown periods
- Enforce per-trigger cooldowns
- Handle media change cooldown

#### LLM Client (llm_client.py)
- Construct chat completion requests
- Send HTTP POST to LLM API
- Handle timeout and retry logic
- Parse LLM response
- Track API latency metrics

#### Response Processor (response_processor.py)
- Enforce length limits (truncation)
- Filter content (block patterns, keywords)
- Validate quality (not empty, not duplicate)
- Strip markdown and format
- Log filter decisions

#### Health Monitor (health.py)
- Run HTTP server on configurable port
- Serve /health endpoint (JSON)
- Serve /metrics endpoint (Prometheus)
- Aggregate metrics from all components
- Check NATS/LLM API availability

#### Shutdown Handler (shutdown_handler.py)
- Register signal handlers
- Coordinate component shutdown
- Cancel asyncio tasks
- Wait for in-flight requests
- Flush pending NATS messages

### Concurrency Model

**Single Event Loop**: All components run in single asyncio event loop.

**Task Structure**:
```python
asyncio.create_task(nats_client.connect())
asyncio.create_task(http_server.start())

# One task per channel for event processing
for channel in config.channels:
    asyncio.create_task(process_channel_events(channel))

# Periodic tasks
asyncio.create_task(contextual_trigger_evaluator())
asyncio.create_task(metrics_aggregator())
```

**Cancellation**: Use `asyncio.TaskGroup` for structured cancellation on shutdown.

**Backpressure**: Limit concurrent LLM requests to 10 per channel (semaphore).

### Data Flow

1. **Inbound Event Path**:
   - NATS callback → Event Handler → Context Window → Trigger Manager → Rate Limiter → LLM Client → Response Processor → NATS Client (publish)

2. **Contextual Trigger Path**:
   - Periodic timer → Context Window (read) → LLM Client (participation check) → Trigger Manager → (continue as above)

3. **Health Check Path**:
   - HTTP request → Health Monitor → Query all components → Aggregate status → HTTP response

4. **Config Reload Path**:
   - SIGHUP signal → Shutdown Handler → Wait for in-flight → Load new config → Update subscriptions → Resume

### Error Propagation

**Strategy**: Fail fast on startup, degrade gracefully at runtime.

**Startup Errors** (exit process):
- Invalid YAML config
- NATS connection failure (after retries)
- HTTP port bind failure

**Runtime Errors** (log and continue):
- Invalid NATS event (skip event)
- LLM API timeout (suppress trigger)
- NATS publish failure (log, drop message)
- Rate limiter exception (deny trigger)

**Degraded Mode**:
- NATS disconnected: Queue outbound messages (bounded)
- LLM API unavailable: Use fallback responses (if configured) or suppress triggers

### State Management

**No Persistent State**: All state is in-memory and ephemeral.

**Stateful Components**:
- Context Window: Last N messages per channel
- Rate Limiter: Sliding window counters per user/channel
- Trigger Manager: Last fire timestamp per trigger type
- NATS Client: Connection state, pending queue

**State Isolation**: Each channel has independent state (context, rate limits).

### Security Considerations

- **SEC-001**: API keys loaded from environment variables (never in config file)
- **SEC-002**: No message content in logs (only metadata)
- **SEC-003**: NATS credentials support (username/password or token)
- **SEC-004**: HTTP server binds to localhost only by default
- **SEC-005**: Rate limiting prevents abuse (DoS protection)

---

## Deployment Architecture

### Single Instance Deployment

```
┌─────────────────────────────────────────┐
│         Server (Linux VM / Container)    │
│                                          │
│  ┌────────────┐                          │
│  │ NATS       │◀──────┐                  │
│  │ Server     │       │                  │
│  └────────────┘       │                  │
│        ▲              │                  │
│        │              │                  │
│  ┌─────┴──────┐  ┌───┴──────┐           │
│  │ Kryten     │  │ LLM Bot  │           │
│  │ Connector  │  │          │           │
│  └────────────┘  └──────────┘           │
│                       │                  │
│                       │ HTTP             │
│                       ▼                  │
│                  ┌──────────┐            │
│                  │ Prometheus│           │
│                  │ (optional)│           │
│                  └──────────┘            │
└─────────────────────────────────────────┘
         │
         │ HTTPS
         ▼
   ┌────────────┐
   │ OpenAI API │
   │ (external) │
   └────────────┘
```

### Multi-Instance Deployment (Advanced)

```
┌─────────────────────────────────────────────────────────┐
│                    NATS Cluster                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ NATS-1   │◀──▶│ NATS-2   │◀──▶│ NATS-3   │          │
│  └──────────┘    └──────────┘    └──────────┘          │
└─────────────────────────────────────────────────────────┘
         ▲                   ▲                   ▲
         │                   │                   │
    ┌────┴────┐         ┌────┴────┐        ┌────┴────┐
    │ Kryten  │         │ LLM Bot │        │ LLM Bot │
    │         │         │ (chan A)│        │ (chan B)│
    └─────────┘         └─────────┘        └─────────┘
                             │                   │
                             ▼                   ▼
                        ┌─────────────────────────┐
                        │   OpenAI API            │
                        └─────────────────────────┘
```

**Note**: Multi-instance requires careful rate limit coordination (future enhancement).

---

## Performance Characteristics

### Latency Targets

- **Event Receipt to Trigger Evaluation**: < 10ms
- **Trigger Evaluation**: < 50ms
- **LLM API Call**: 500ms - 5s (variable, external dependency)
- **Response Processing**: < 50ms
- **NATS Publish**: < 10ms
- **Total (excluding LLM)**: < 100ms

### Throughput Targets

- **Events Processed**: 1000+ per hour per channel
- **Concurrent Channels**: 10+ channels simultaneously
- **LLM Requests**: Up to 10 concurrent per channel (semaphore-limited)
- **HTTP Requests**: 100+ /health checks per second

### Resource Usage

- **Base Memory**: ~50MB (Python runtime + libraries)
- **Per Channel**: ~10MB (context window + state)
- **Peak Memory**: <500MB (10 channels with full context)
- **CPU (Idle)**: <5% (mostly sleeping, waiting for events)
- **CPU (Active)**: <50% (LLM request processing, JSON parsing)

---

## Version History

- **v1.0** - 2025-12-03 - Initial architecture specification

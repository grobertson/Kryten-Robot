---
title: LLM Chat Bot Data Contracts Specification
version: 1.0
date_created: 2025-12-03
owner: Development Team
tags: [data, schema, nats, api, validation]
---

# Introduction

This specification defines all data contracts for the LLM Chat Bot, including NATS message schemas, LLM API request/response formats, and internal data structures. These contracts ensure consistent communication between components and external systems.

## 1. Purpose & Scope

**Purpose**: Define precise data structures, validation rules, and serialization formats for all data flowing through the LLM Chat Bot.

**Scope**: This specification covers:
- NATS event message schemas (inbound from Kryten)
- NATS command message schemas (outbound to Kryten)
- LLM API request/response formats
- Internal data structures (events, triggers, context)
- Validation rules and error handling

**Audience**: Software engineers implementing message handlers, API clients, and data validation.

**Assumptions**:
- All NATS messages use JSON serialization
- All timestamps are Unix epoch milliseconds
- All text fields are UTF-8 encoded
- NATS headers support correlation IDs

## 2. Definitions

- **Schema**: JSON structure with required and optional fields
- **Validation**: Process of checking data against schema rules
- **Serialization**: Converting data structure to JSON bytes
- **Deserialization**: Parsing JSON bytes to data structure
- **Correlation ID**: UUID v4 string tracking request through system
- **Event**: Inbound NATS message from Kryten
- **Command**: Outbound NATS message to Kryten

## 3. Requirements, Constraints & Guidelines

### Data Requirements

- **REQ-001**: All NATS messages SHALL include correlation ID in headers
- **REQ-002**: All timestamps SHALL be Unix epoch milliseconds (int64)
- **REQ-003**: All user names SHALL be validated (non-empty, max 50 chars)
- **REQ-004**: All message content SHALL be validated (max 500 chars)
- **REQ-005**: All channel names SHALL match pattern `[a-z0-9_-]+`

### Validation Constraints

- **CON-001**: Invalid messages MUST be logged and dropped (never crash)
- **CON-002**: Required fields MUST fail validation if missing
- **CON-003**: Unknown fields MUST be ignored (forward compatibility)
- **CON-004**: Numeric fields MUST be validated for range (prevent overflow)
- **CON-005**: String fields MUST be validated for length (prevent DoS)

### Serialization Guidelines

- **GUD-001**: Use compact JSON (no pretty printing) for NATS messages
- **GUD-002**: Use dataclasses or Pydantic models for internal structures
- **GUD-003**: Validate on deserialization, not serialization (fail fast)
- **GUD-004**: Include schema version in outbound messages (future proofing)
- **GUD-005**: Log malformed messages with truncated content (privacy)

### Validation Patterns

- **PAT-001**: Use schema validation library (e.g., Pydantic)
- **PAT-002**: Define separate schemas for inbound and outbound
- **PAT-003**: Use enums for constrained string values
- **PAT-004**: Use Optional[] for nullable fields
- **PAT-005**: Use strict validation in tests, lenient in production

## 4. Interfaces & Data Contracts

### 4.1 NATS Event Schemas (Inbound)

#### 4.1.1 Chat Message Event

**Subject**: `cytube.events.{channel}.chatMsg`

**Payload**:
```json
{
  "user": {
    "name": "Alice",
    "rank": 2,
    "profile": {
      "image": "https://example.com/avatar.png",
      "text": "Moderator"
    }
  },
  "msg": "Hey @bot, what do you think about this video?",
  "meta": {},
  "time": 1701622800000
}
```

**Schema**:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserProfile:
    image: str
    text: str

@dataclass
class User:
    name: str                    # Required, max 50 chars
    rank: int                    # Required, 0-10
    profile: Optional[UserProfile] = None

@dataclass
class ChatMessageEvent:
    user: User                   # Required
    msg: str                     # Required, max 500 chars
    meta: dict                   # Required (can be empty)
    time: int                    # Required, Unix epoch ms
```

**Validation Rules**:
- `user.name`: Non-empty, max 50 characters, no control characters
- `user.rank`: Integer 0-10 (higher = more privileges)
- `msg`: Non-empty, max 500 characters (CyTube limit)
- `time`: Positive integer, within last 24 hours (sanity check)

#### 4.1.2 Private Message Event

**Subject**: `cytube.events.{channel}.pm`

**Payload**:
```json
{
  "from": {
    "name": "Alice",
    "rank": 2
  },
  "to": {
    "name": "MyBot",
    "rank": 0
  },
  "msg": "Hey bot, can you help me?",
  "time": 1701622800000
}
```

**Schema**:
```python
@dataclass
class PrivateMessageEvent:
    from_user: User              # Renamed from 'from' (Python keyword)
    to_user: User                # Renamed from 'to'
    msg: str                     # Required, max 500 chars
    time: int                    # Required, Unix epoch ms
```

**Validation Rules**:
- `from_user.name`: Non-empty, max 50 characters
- `to_user.name`: Must match bot username or alias
- `msg`: Non-empty, max 500 characters
- `time`: Positive integer

#### 4.1.3 Media Change Event

**Subject**: `cytube.events.{channel}.changeMedia`

**Payload**:
```json
{
  "title": "Cool Video Title",
  "type": "youtube",
  "id": "dQw4w9WgXcQ",
  "duration": 212,
  "currentTime": 0
}
```

**Schema**:
```python
from enum import Enum

class MediaType(Enum):
    YOUTUBE = "youtube"
    VIMEO = "vimeo"
    DIRECT = "direct"
    TWITCH = "twitch"

@dataclass
class MediaChangeEvent:
    title: str                   # Required, max 200 chars
    type: MediaType              # Required
    id: str                      # Required, max 100 chars
    duration: int                # Required, seconds
    current_time: int            # Required, seconds (usually 0)
```

**Validation Rules**:
- `title`: Max 200 characters
- `type`: Must be valid MediaType enum
- `id`: Non-empty, max 100 characters
- `duration`: Non-negative integer
- `current_time`: Non-negative integer, <= duration

### 4.2 NATS Command Schemas (Outbound)

#### 4.2.1 Chat Command

**Subject**: `cytube.commands.{channel}.chat`

**Payload**:
```json
{
  "action": "chat",
  "data": {
    "message": "That's a great question! I think..."
  }
}
```

**Schema**:
```python
@dataclass
class ChatCommandData:
    message: str                 # Required, max 240 chars (CyTube limit)

@dataclass
class ChatCommand:
    action: str = "chat"         # Literal "chat"
    data: ChatCommandData        # Required
```

**Validation Rules**:
- `action`: Must be exactly "chat"
- `data.message`: Non-empty, max 240 characters
- `data.message`: No newlines (collapsed to spaces)

#### 4.2.2 Private Message Command

**Subject**: `cytube.commands.{channel}.pm`

**Payload**:
```json
{
  "action": "pm",
  "data": {
    "to": "Alice",
    "message": "Sure, I can help with that!"
  }
}
```

**Schema**:
```python
@dataclass
class PMCommandData:
    to: str                      # Required, max 50 chars
    message: str                 # Required, max 240 chars

@dataclass
class PMCommand:
    action: str = "pm"           # Literal "pm"
    data: PMCommandData          # Required
```

**Validation Rules**:
- `action`: Must be exactly "pm"
- `data.to`: Non-empty, max 50 characters, valid username
- `data.message`: Non-empty, max 240 characters

### 4.3 LLM API Schemas

#### 4.3.1 Chat Completion Request

**Endpoint**: `POST /v1/chat/completions`

**Request Body**:
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful chat participant..."
    },
    {
      "role": "user",
      "content": "Recent chat:\nAlice: Hey everyone!\n\nRespond to: what do you think?"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 100,
  "top_p": 0.9,
  "frequency_penalty": 0.5,
  "presence_penalty": 0.3,
  "stop": ["\n\n", "User:", "Assistant:"]
}
```

**Schema**:
```python
from enum import Enum
from typing import List

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class ChatMessage:
    role: MessageRole
    content: str

@dataclass
class ChatCompletionRequest:
    model: str                   # Required
    messages: List[ChatMessage]  # Required, min 1 message
    temperature: float = 0.7     # Optional, 0.0-2.0
    max_tokens: int = 100        # Optional, positive int
    top_p: float = 0.9           # Optional, 0.0-1.0
    frequency_penalty: float = 0.5  # Optional, -2.0 to 2.0
    presence_penalty: float = 0.3   # Optional, -2.0 to 2.0
    stop: Optional[List[str]] = None  # Optional
```

**Validation Rules**:
- `model`: Non-empty string
- `messages`: At least one message (system prompt)
- `temperature`: 0.0 to 2.0
- `max_tokens`: 1 to 4096 (model dependent)
- `top_p`: 0.0 to 1.0
- `frequency_penalty`: -2.0 to 2.0
- `presence_penalty`: -2.0 to 2.0

#### 4.3.2 Chat Completion Response

**Response Body**:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1701622800,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I think it's really interesting how..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 20,
    "total_tokens": 70
  }
}
```

**Schema**:
```python
from enum import Enum

class FinishReason(Enum):
    STOP = "stop"              # Natural completion
    LENGTH = "length"          # Max tokens reached
    CONTENT_FILTER = "content_filter"  # Filtered by API

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class Choice:
    index: int
    message: ChatMessage
    finish_reason: FinishReason

@dataclass
class ChatCompletionResponse:
    id: str
    object: str
    created: int                 # Unix epoch seconds
    model: str
    choices: List[Choice]        # At least one choice
    usage: Usage
```

**Extraction Logic**:
```python
def extract_response_text(response: ChatCompletionResponse) -> str:
    """Extract the first choice content."""
    if not response.choices:
        raise ValueError("No choices in response")
    return response.choices[0].message.content
```

**Error Response**:
```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

### 4.4 Internal Data Structures

#### 4.4.1 Context Window Entry

```python
@dataclass
class ContextEntry:
    username: str                # User who sent message
    message: str                 # Message content
    timestamp: int               # Unix epoch ms
    is_bot: bool = False         # True if bot's own message
```

**Usage**: Stored in `collections.deque` with max length per channel.

#### 4.4.2 Trigger Evaluation Result

```python
from enum import Enum

class TriggerDecision(Enum):
    FIRE = "fire"                # Trigger should fire
    SUPPRESS_RATE_LIMIT = "suppress_rate_limit"
    SUPPRESS_COOLDOWN = "suppress_cooldown"
    SUPPRESS_PROBABILITY = "suppress_probability"
    SUPPRESS_NO_MATCH = "suppress_no_match"

@dataclass
class TriggerResult:
    decision: TriggerDecision
    trigger_type: str            # "mention", "keyword", etc.
    reason: Optional[str] = None  # Human-readable explanation
    matched_text: Optional[str] = None  # What triggered (for logging)
```

#### 4.4.3 Rate Limit State

```python
from collections import deque
from dataclasses import dataclass, field

@dataclass
class RateLimitWindow:
    """Sliding window rate limiter."""
    window_seconds: int          # Window size (e.g., 60 for per-minute)
    max_count: int               # Max events in window
    events: deque = field(default_factory=deque)  # Timestamps

    def allow(self, now: int) -> bool:
        """Check if event is allowed at given timestamp."""
        # Remove events outside window
        cutoff = now - (self.window_seconds * 1000)
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
        
        # Check limit
        if len(self.events) >= self.max_count:
            return False
        
        # Record event
        self.events.append(now)
        return True
```

#### 4.4.4 Response Metadata

```python
@dataclass
class ResponseMetadata:
    """Metadata tracked for each bot response."""
    correlation_id: str          # UUID for tracking
    channel: str                 # Target channel
    trigger_type: str            # What caused response
    username: Optional[str]      # Target user (for PMs)
    timestamp: int               # When sent (Unix epoch ms)
    response_text: str           # What was sent
    llm_latency_ms: int          # API call duration
    filtered: bool               # Was response modified by filters?
```

## 5. Acceptance Criteria

- **AC-001**: Given a valid chatMsg event, When deserialized, Then all fields parse correctly
- **AC-002**: Given an event with missing required field, When validated, Then raises ValueError with field name
- **AC-003**: Given a message > 500 chars, When validated, Then raises ValueError
- **AC-004**: Given a chat command, When serialized, Then JSON is compact (no newlines/spaces)
- **AC-005**: Given an LLM response, When parsed, Then extracts first choice content
- **AC-006**: Given an invalid channel name (spaces), When validated, Then raises ValueError
- **AC-007**: Given unknown event fields, When deserialized, Then ignores extra fields

## 6. Test Automation Strategy

- **Test Levels**: Unit tests for each schema
- **Frameworks**: pytest, hypothesis (property-based testing)
- **Test Data**: JSON fixtures for valid/invalid messages
- **Validation Tests**: Test all validation rules (boundary cases)
- **Serialization Tests**: Round-trip testing (serialize → deserialize)
- **Error Handling**: Test all error paths (missing fields, wrong types)

## 7. Rationale & Context

### Why JSON for NATS?

- **Ubiquitous**: Every language has JSON support
- **Human-Readable**: Easy to debug with NATS CLI
- **Flexible**: Forward-compatible with unknown fields
- **Lightweight**: Compact representation for small messages

### Why Dataclasses vs Pydantic?

**Dataclasses** (Standard Library):
- Lightweight, no dependencies
- Good for internal structures
- Manual validation required

**Pydantic** (Recommended):
- Automatic validation
- Better error messages
- JSON schema generation
- Type coercion (strings → ints)

**Decision**: Use Pydantic for NATS message schemas (inbound/outbound), dataclasses for internal structures.

### Why Unix Epoch Milliseconds?

- **Precision**: Millisecond resolution for event ordering
- **Compatibility**: JavaScript uses ms, Python uses seconds (easy conversion)
- **Compactness**: Integer vs ISO 8601 string

### Why Max Length Validation?

- **DoS Prevention**: Prevent memory exhaustion from huge messages
- **CyTube Limits**: CyTube enforces 240 char limit for chat
- **Context Window Size**: Prevent context from growing unbounded

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Kryten Connector - Must publish events matching these schemas
- **EXT-002**: CyTube - Enforces 240 char message limit

### Third-Party Services

- **SVC-001**: OpenAI API - Must accept requests and return responses matching these schemas

### Technology Platform Dependencies

- **PLT-001**: Pydantic v2+ - For schema validation and serialization
- **PLT-002**: Python 3.11+ - For native dataclass improvements

## 9. Examples & Edge Cases

### Example: Valid Event Processing

```python
import json
from pydantic import BaseModel, ValidationError

class ChatMessageEvent(BaseModel):
    user: dict  # Simplified for example
    msg: str
    time: int

# Valid event
raw_json = '{"user": {"name": "Alice", "rank": 2}, "msg": "Hello!", "time": 1701622800000}'
event = ChatMessageEvent.model_validate_json(raw_json)
print(event.msg)  # "Hello!"

# Invalid event (missing field)
bad_json = '{"user": {"name": "Alice", "rank": 2}, "time": 1701622800000}'
try:
    event = ChatMessageEvent.model_validate_json(bad_json)
except ValidationError as e:
    print(e)  # "Field required: msg"
```

### Edge Case: Empty Message

```python
# Event with empty message (should fail validation)
event_data = {
    "user": {"name": "Alice", "rank": 2},
    "msg": "",  # Empty!
    "time": 1701622800000
}

class ChatMessageEvent(BaseModel):
    user: dict
    msg: str = Field(..., min_length=1, max_length=500)
    time: int

try:
    event = ChatMessageEvent(**event_data)
except ValidationError as e:
    # Validation fails: msg too short
    pass
```

### Edge Case: Very Long Message

```python
# Message exceeding CyTube limit
event_data = {
    "user": {"name": "Spammer", "rank": 0},
    "msg": "A" * 501,  # 501 chars, over limit
    "time": 1701622800000
}

try:
    event = ChatMessageEvent(**event_data)
except ValidationError as e:
    # Validation fails: msg too long
    pass
```

### Edge Case: Future Timestamp

```python
import time

# Sanity check: reject messages from far future
current_time_ms = int(time.time() * 1000)
future_time_ms = current_time_ms + (24 * 60 * 60 * 1000) + 1  # 24 hours + 1ms

event_data = {
    "user": {"name": "TimeTraveler", "rank": 0},
    "msg": "Hello from the future!",
    "time": future_time_ms
}

class ChatMessageEvent(BaseModel):
    user: dict
    msg: str
    time: int
    
    @validator('time')
    def check_time(cls, v):
        now = int(time.time() * 1000)
        if v > now + (24 * 60 * 60 * 1000):
            raise ValueError('Timestamp too far in future')
        return v

try:
    event = ChatMessageEvent(**event_data)
except ValidationError as e:
    # Validation fails: timestamp check
    pass
```

### Edge Case: Unknown Fields (Forward Compatibility)

```python
# Event with extra field (future version)
raw_json = '''
{
  "user": {"name": "Alice", "rank": 2},
  "msg": "Hello!",
  "time": 1701622800000,
  "emoji_count": 3,
  "mentions": ["@bot"]
}
'''

class ChatMessageEvent(BaseModel):
    user: dict
    msg: str
    time: int
    
    class Config:
        extra = 'ignore'  # Ignore unknown fields

event = ChatMessageEvent.model_validate_json(raw_json)
# Success! emoji_count and mentions ignored
```

### Edge Case: Malformed JSON

```python
# Invalid JSON syntax
bad_json = '{"user": {"name": "Alice", "rank": 2}, "msg": "Hello!'  # Missing closing brace

try:
    event = ChatMessageEvent.model_validate_json(bad_json)
except json.JSONDecodeError as e:
    # Log error, skip event
    logger.warning("Malformed JSON", error=str(e), json_preview=bad_json[:100])
```

## 10. Validation Criteria

- **VAL-001**: All required fields validated on deserialization
- **VAL-002**: String length limits enforced (max 50 for usernames, 500 for messages)
- **VAL-003**: Numeric ranges validated (rank 0-10, timestamps positive)
- **VAL-004**: Enum values validated (MediaType, FinishReason)
- **VAL-005**: Unknown fields ignored (forward compatibility)
- **VAL-006**: Validation errors include field name and constraint
- **VAL-007**: Malformed JSON caught and logged, not crashed

## 11. Related Specifications / Further Reading

- [Architecture Specification](./spec-architecture-design.md) - Component interactions
- [Configuration Specification](./spec-configuration.md) - Config file schemas
- [Observability Specification](./spec-observability.md) - Logging structured data

**External References**:
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat)
- [JSON Schema](https://json-schema.org/)

---

## NATS Message Headers

### Standard Headers

All NATS messages SHOULD include these headers:

```python
headers = {
    'Correlation-Id': 'uuid-v4-string',      # Track request through system
    'Timestamp': '1701622800000',            # When message was sent (ms)
    'Source': 'llm-bot',                     # Which component sent it
    'Schema-Version': '1.0'                  # Message schema version
}
```

### Correlation ID Flow

1. **Inbound Event**: Extract correlation ID from Kryten (if present), or generate new UUID
2. **Internal Processing**: Pass correlation ID through all components
3. **Outbound Command**: Include same correlation ID in headers
4. **Logging**: Include correlation ID in all log statements

Example:
```python
import uuid

def handle_event(nats_msg):
    # Extract or generate correlation ID
    correlation_id = nats_msg.headers.get('Correlation-Id') or str(uuid.uuid4())
    
    # Log with correlation ID
    logger.info("Event received", 
                correlation_id=correlation_id,
                channel=channel,
                event_type=event_type)
    
    # Process event...
    
    # Send command with same correlation ID
    await nats_client.publish(
        subject=f"cytube.commands.{channel}.chat",
        data=command_json,
        headers={'Correlation-Id': correlation_id}
    )
```

---

## Version History

- **v1.0** - 2025-12-03 - Initial data contracts specification

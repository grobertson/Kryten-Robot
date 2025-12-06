# Sprint 2 Tasks: Event Processing & Context Management

**Duration**: 2 weeks  
**Focus**: Event handling, context window management, and media change tracking

## Overview

Sprint 2 builds the event processing pipeline. Events from NATS are parsed, validated, routed to appropriate channels, and added to context windows. By the end of this sprint, the bot maintains chat history per channel.

## Tasks in This Sprint

### TASK-016: Implement EventHandler Class

**Estimated Duration**: 4-5 hours  
**Prerequisites**: TASK-011, TASK-008  
**Related Specs**: [Architecture Specification](./spec-architecture-design.md) - Section 5.2

**Objective**: Create event handler that parses NATS messages into Pydantic models and routes to appropriate handlers.

**Implementation Pattern**:

```python
# llm_bot/event_handler.py

import json
import logging
from typing import Dict, Callable, Optional
from nats.aio.msg import Msg
from llm_bot.config import Config
from llm_bot.raw_event import ChatMessageEvent, PrivateMessageEvent, MediaChangeEvent

logger = logging.getLogger(__name__)

class EventHandler:
    """Handles incoming NATS events and routes to appropriate processors."""
    
    def __init__(self, config: Config):
        self.config = config
        self.handlers: Dict[str, Callable] = {}
        
    def register_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """Register a handler for specific event type."""
        self.handlers[event_type] = handler
        logger.debug(f"Registered handler for: {event_type}")
    
    async def handle_message(self, msg: Msg) -> None:
        """
        Handle incoming NATS message.
        
        Args:
            msg: NATS message
        """
        try:
            # Extract correlation ID from headers or generate
            correlation_id = self._get_correlation_id(msg)
            
            # Parse message
            subject_parts = msg.subject.split('.')
            if len(subject_parts) < 4:
                logger.warning(f"Invalid subject format: {msg.subject}")
                return
            
            # Extract channel and event type
            # Subject format: cytube.events.{channel}.{event_type}
            channel = subject_parts[2]
            event_type = subject_parts[3]
            
            # Parse JSON payload
            data = json.loads(msg.data.decode('utf-8'))
            
            # Log event receipt
            logger.info(
                "Event received",
                extra={
                    "correlation_id": correlation_id,
                    "channel": channel,
                    "event_type": event_type,
                }
            )
            
            # Route to appropriate handler
            await self._route_event(
                channel,
                event_type,
                data,
                correlation_id
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def _route_event(
        self,
        channel: str,
        event_type: str,
        data: dict,
        correlation_id: str
    ) -> None:
        """Route event to registered handler."""
        handler_key = f"{channel}.{event_type}"
        
        if handler_key in self.handlers:
            await self.handlers[handler_key](data, correlation_id)
        elif event_type in self.handlers:
            # Fallback to event type handler
            await self.handlers[event_type](channel, data, correlation_id)
        else:
            logger.debug(f"No handler for: {handler_key}")
    
    def _get_correlation_id(self, msg: Msg) -> str:
        """Extract or generate correlation ID."""
        if msg.headers and 'Correlation-Id' in msg.headers:
            return msg.headers['Correlation-Id']
        
        import uuid
        return str(uuid.uuid4())
```

**Testing**:

```python
# tests/unit/test_event_handler.py

@pytest.mark.asyncio
async def test_event_handler_routes_message():
    config = Config.load("config.example.yaml")
    handler = EventHandler(config)
    
    handled = []
    async def test_handler(channel, data, correlation_id):
        handled.append((channel, data, correlation_id))
    
    handler.register_handler("chatMsg", test_handler)
    
    # Create mock NATS message
    msg = Mock()
    msg.subject = "cytube.events.test.chatMsg"
    msg.data = b'{"user": {"name": "Alice"}, "msg": "Hello"}'
    msg.headers = {"Correlation-Id": "test-123"}
    
    await handler.handle_message(msg)
    
    assert len(handled) == 1
    assert handled[0][0] == "test"
```

**Acceptance Criteria**:
- [ ] Parses NATS message subject and payload
- [ ] Extracts/generates correlation ID
- [ ] Routes to registered handlers
- [ ] Logs event receipt with correlation ID
- [ ] Handles JSON parse errors gracefully
- [ ] Tests pass

---

### TASK-017: Implement Event Validation and Error Handling

**Estimated Duration**: 3-4 hours  
**Prerequisites**: TASK-016, TASK-011  
**Related Specs**: [Data Contracts Specification](./spec-data-contracts.md) - Section 4.1

**Objective**: Validate events against Pydantic schemas and handle malformed data gracefully.

**Implementation Pattern**:

```python
# Add to llm_bot/event_handler.py

from pydantic import ValidationError

class EventHandler:
    # ... existing code ...
    
    async def _route_event(
        self,
        channel: str,
        event_type: str,
        data: dict,
        correlation_id: str
    ) -> None:
        """Route event to handler with validation."""
        try:
            # Validate based on event type
            validated_event = self._validate_event(event_type, data)
            
            # Route to handler
            handler_key = f"{channel}.{event_type}"
            if handler_key in self.handlers:
                await self.handlers[handler_key](
                    validated_event,
                    correlation_id
                )
            
        except ValidationError as e:
            logger.warning(
                f"Invalid event data: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "event_type": event_type,
                    "channel": channel,
                }
            )
            # Drop invalid events
        except Exception as e:
            logger.error(
                f"Error processing event: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True
            )
    
    def _validate_event(self, event_type: str, data: dict):
        """Validate event data against Pydantic models."""
        if event_type == "chatMsg":
            return ChatMessageEvent(**data)
        elif event_type == "pm":
            return PrivateMessageEvent(**data)
        elif event_type == "changeMedia":
            return MediaChangeEvent(**data)
        else:
            # Unknown event type - return dict for forward compatibility
            logger.debug(f"Unknown event type: {event_type}")
            return data
```

**Testing**:

```python
def test_invalid_event_validation():
    handler = EventHandler(config)
    
    # Missing required field
    invalid_data = {"user": {}}  # Missing 'name'
    
    with pytest.raises(ValidationError):
        handler._validate_event("chatMsg", invalid_data)
```

**Acceptance Criteria**:
- [ ] Validates events with Pydantic models
- [ ] Logs validation errors with correlation ID
- [ ] Drops invalid events (doesn't crash)
- [ ] Handles unknown event types gracefully
- [ ] Tests pass

---

### TASK-018: Implement Per-Channel Event Routing

**Estimated Duration**: 2-3 hours  
**Prerequisites**: TASK-016  
**Related Specs**: [Architecture Specification](./spec-architecture-design.md) - Section 5.3

**Objective**: Route events to channel-specific handlers with isolation.

**Implementation Pattern**:

```python
# llm_bot/event_handler.py

class EventHandler:
    """Enhanced with per-channel routing."""
    
    def __init__(self, config: Config):
        self.config = config
        # Map: channel_name -> event_type -> handler
        self.channel_handlers: Dict[str, Dict[str, Callable]] = {}
        
        # Initialize channel handlers
        for channel_config in config.channels:
            if channel_config.enabled:
                self.channel_handlers[channel_config.name] = {}
    
    def register_channel_handler(
        self,
        channel: str,
        event_type: str,
        handler: Callable
    ) -> None:
        """Register handler for specific channel and event type."""
        if channel not in self.channel_handlers:
            self.channel_handlers[channel] = {}
        
        self.channel_handlers[channel][event_type] = handler
        logger.debug(f"Registered {event_type} handler for channel: {channel}")
    
    async def _route_event(
        self,
        channel: str,
        event_type: str,
        data: dict,
        correlation_id: str
    ) -> None:
        """Route to channel-specific handler."""
        # Check if channel is enabled
        if channel not in self.channel_handlers:
            logger.debug(f"Ignoring event for disabled channel: {channel}")
            return
        
        # Validate event
        try:
            validated_event = self._validate_event(event_type, data)
        except ValidationError:
            return  # Already logged in _validate_event
        
        # Get channel-specific handler
        if event_type in self.channel_handlers[channel]:
            handler = self.channel_handlers[channel][event_type]
            await handler(validated_event, correlation_id)
        else:
            logger.debug(
                f"No handler for {event_type} in channel {channel}"
            )
```

**Acceptance Criteria**:
- [ ] Maintains separate handlers per channel
- [ ] Ignores events for disabled channels
- [ ] Routes to correct channel handler
- [ ] Tests pass

---

### TASK-019: Implement ContextWindow Class

**Estimated Duration**: 4-5 hours  
**Prerequisites**: TASK-013  
**Related Specs**: [Architecture Specification](./spec-architecture-design.md) - Section 5.4

**Objective**: Implement rolling context window with age-based cleanup and formatting.

**Implementation Pattern**:

```python
# llm_bot/context_window.py

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ContextEntry:
    """Single entry in context window."""
    timestamp: datetime
    username: str
    message: str

class ContextWindow:
    """Rolling window of recent chat messages."""
    
    def __init__(
        self,
        max_size: int = 50,
        max_age_seconds: int = 3600,
        include_usernames: bool = True,
        include_timestamps: bool = False
    ):
        self.max_size = max_size
        self.max_age = timedelta(seconds=max_age_seconds)
        self.include_usernames = include_usernames
        self.include_timestamps = include_timestamps
        
        # Use deque with maxlen for O(1) operations
        self.messages: deque[ContextEntry] = deque(maxlen=max_size)
    
    def add_message(
        self,
        username: str,
        message: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Add message to context window.
        
        Args:
            username: User who sent message
            message: Message content
            timestamp: Message timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        entry = ContextEntry(
            timestamp=timestamp,
            username=username,
            message=message
        )
        
        self.messages.append(entry)
        self._cleanup_old_messages()
        
        logger.debug(
            f"Added message to context: {len(self.messages)}/{self.max_size}"
        )
    
    def _cleanup_old_messages(self) -> None:
        """Remove messages older than max_age."""
        cutoff = datetime.utcnow() - self.max_age
        
        # Remove from left while old
        while self.messages and self.messages[0].timestamp < cutoff:
            self.messages.popleft()
    
    def get_recent_messages(self, count: Optional[int] = None) -> List[ContextEntry]:
        """
        Get recent messages from context.
        
        Args:
            count: Number of messages (None = all)
            
        Returns:
            List of recent context entries
        """
        self._cleanup_old_messages()
        
        if count is None:
            return list(self.messages)
        
        # Return last N messages
        return list(self.messages)[-count:]
    
    def get_formatted_context(self, max_messages: int = 20) -> str:
        """
        Format context for LLM prompt.
        
        Args:
            max_messages: Maximum messages to include
            
        Returns:
            Formatted context string
        """
        messages = self.get_recent_messages(max_messages)
        
        formatted = []
        for entry in messages:
            if self.include_usernames:
                line = f"{entry.username}: {entry.message}"
            else:
                line = entry.message
            
            if self.include_timestamps:
                elapsed = datetime.utcnow() - entry.timestamp
                minutes_ago = int(elapsed.total_seconds() / 60)
                line = f"[{minutes_ago}m ago] {line}"
            
            formatted.append(line)
        
        return "\\n".join(formatted)
    
    def size(self) -> int:
        """Return current number of messages in context."""
        return len(self.messages)
    
    def clear(self) -> None:
        """Clear all messages from context."""
        self.messages.clear()
        logger.debug("Context window cleared")
```

**Testing**:

```python
# tests/unit/test_context_window.py

def test_context_window_add_message():
    ctx = ContextWindow(max_size=5)
    ctx.add_message("Alice", "Hello")
    ctx.add_message("Bob", "Hi there")
    
    assert ctx.size() == 2
    messages = ctx.get_recent_messages()
    assert messages[0].username == "Alice"

def test_context_window_max_size():
    ctx = ContextWindow(max_size=3)
    for i in range(5):
        ctx.add_message(f"User{i}", f"Message {i}")
    
    assert ctx.size() == 3
    messages = ctx.get_recent_messages()
    assert messages[0].username == "User2"  # Oldest kept

def test_context_window_age_cleanup():
    ctx = ContextWindow(max_age_seconds=1)
    old_time = datetime.utcnow() - timedelta(seconds=2)
    ctx.add_message("Alice", "Old message", timestamp=old_time)
    ctx.add_message("Bob", "New message")
    
    messages = ctx.get_recent_messages()
    assert len(messages) == 1
    assert messages[0].username == "Bob"

def test_formatted_context():
    ctx = ContextWindow()
    ctx.add_message("Alice", "Hello")
    ctx.add_message("Bob", "Hi")
    
    formatted = ctx.get_formatted_context()
    assert "Alice: Hello" in formatted
    assert "Bob: Hi" in formatted
```

**Acceptance Criteria**:
- [ ] Uses deque with maxlen for O(1) operations
- [ ] add_message() adds to window
- [ ] _cleanup_old_messages() removes old entries
- [ ] get_recent_messages() returns last N
- [ ] get_formatted_context() formats for LLM
- [ ] Tests pass

---

### TASK-020 through TASK-022

Continue with remaining Sprint 2 tasks following the same pattern:

- **TASK-020**: Implement context window per-channel isolation
- **TASK-021**: Implement context window configuration options
- **TASK-022**: Implement media change cooldown tracking

## Sprint 2 Completion Criteria

By the end of Sprint 2, you should be able to:

- [ ] Receive events from NATS
- [ ] Parse and validate events
- [ ] Route events to channel-specific handlers
- [ ] Maintain context window per channel
- [ ] Format context for LLM prompts
- [ ] Track media changes with cooldown

## Integration Test for Sprint 2

```python
# tests/integration/test_sprint2_events.py

@pytest.mark.asyncio
async def test_event_to_context_flow():
    """Test event processing into context window."""
    
    config = Config.load("config.example.yaml")
    handler = EventHandler(config)
    
    # Create context window for test channel
    context = ContextWindow(max_size=10)
    
    # Register handler that adds to context
    async def chat_handler(event, correlation_id):
        context.add_message(
            event.user.name,
            event.msg,
            timestamp=datetime.fromtimestamp(event.time / 1000)
        )
    
    handler.register_channel_handler("test", "chatMsg", chat_handler)
    
    # Simulate NATS message
    msg = Mock()
    msg.subject = "cytube.events.test.chatMsg"
    msg.data = json.dumps({
        "user": {"name": "Alice", "rank": 2},
        "msg": "Hello world",
        "time": int(datetime.utcnow().timestamp() * 1000)
    }).encode()
    msg.headers = {}
    
    await handler.handle_message(msg)
    
    # Verify context updated
    assert context.size() == 1
    messages = context.get_recent_messages()
    assert messages[0].username == "Alice"
    assert messages[0].message == "Hello world"
```

## Next Sprint

**Sprint 3**: Trigger System & Rate Limiting (Tasks 023-032)

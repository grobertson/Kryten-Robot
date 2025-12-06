---
title: LLM Chat Bot Triggers and Rate Limiting Specification
version: 1.0
date_created: 2025-12-03
owner: Development Team
tags: [triggers, rate-limiting, algorithms, cooldowns]
---

# Introduction

This specification defines the trigger evaluation logic, rate limiting algorithms, cooldown tracking mechanisms, and trigger priority handling for the LLM Chat Bot. These systems control when and how frequently the bot responds to chat events.

## 1. Purpose & Scope

**Purpose**: Define precise algorithms for trigger evaluation, rate limiting, and cooldown management to ensure controlled bot participation.

**Scope**: This specification covers:
- Four trigger types (mention, keyword, contextual, PM)
- Trigger evaluation order and short-circuiting
- Fire probability (random selection)
- Rate limiting algorithms (sliding window)
- Cooldown period tracking
- Per-user, per-channel, and global limits
- Media change silence period

**Audience**: Software engineers implementing trigger evaluation, rate limiting, and cooldown tracking.

**Assumptions**:
- All timestamps are Unix epoch milliseconds
- System clock is monotonically increasing
- Random number generator is properly seeded
- Multiple channels processed independently

## 2. Definitions

- **Trigger**: Condition that may cause bot to respond
- **Fire**: When a trigger decides to generate a response
- **Suppress**: When a trigger decides not to respond
- **Fire Probability**: Chance (0.0-1.0) that trigger fires when condition met
- **Rate Limit**: Maximum events allowed in time window
- **Cooldown**: Minimum time between events
- **Sliding Window**: Time-based window that moves forward with each event
- **Correlation ID**: UUID tracking trigger evaluation through system

## 3. Requirements, Constraints & Guidelines

### Trigger Requirements

- **REQ-001**: System SHALL evaluate triggers in priority order (mention, PM, keyword, contextual)
- **REQ-002**: System SHALL short-circuit evaluation (stop on first fire)
- **REQ-003**: System SHALL apply fire probability after condition check
- **REQ-004**: System SHALL check cooldowns before fire probability
- **REQ-005**: System SHALL check rate limits after fire probability

### Rate Limiting Constraints

- **CON-001**: Rate limiters MUST use sliding window algorithm (not fixed buckets)
- **CON-002**: Per-user limits MUST span all channels (global per user)
- **CON-003**: Per-channel limits MUST be independent (isolated)
- **CON-004**: Rate limit state MUST be in-memory only (no persistence)
- **CON-005**: Media change cooldown MUST suppress ALL triggers (global silence)

### Implementation Guidelines

- **GUD-001**: Log all trigger decisions with correlation ID
- **GUD-002**: Use random.random() for fire probability (0.0-1.0)
- **GUD-003**: Use collections.deque for efficient sliding window
- **GUD-004**: Track cooldowns with simple last_fire_time dictionary
- **GUD-005**: Fail open on rate limiter errors (allow trigger, log error)

### Algorithm Patterns

- **PAT-001**: Strategy pattern for trigger implementations
- **PAT-002**: Sliding window with O(n) cleanup, O(1) check
- **PAT-003**: Cooldown tracking with O(1) lookup
- **PAT-004**: Priority-based evaluation with early exit
- **PAT-005**: Stateful rate limiters per channel/user

## 4. Interfaces & Data Contracts

### 4.1 Trigger Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class TriggerContext:
    """Context passed to trigger evaluation."""
    event: dict                  # Raw event data
    channel: str                 # Channel name
    username: str                # User who sent message
    message: str                 # Message content
    timestamp: int               # Unix epoch ms
    context_window: list         # Recent messages
    correlation_id: str          # UUID for tracking

class TriggerDecision(Enum):
    FIRE = "fire"
    SUPPRESS_NO_MATCH = "suppress_no_match"
    SUPPRESS_PROBABILITY = "suppress_probability"
    SUPPRESS_COOLDOWN = "suppress_cooldown"
    SUPPRESS_RATE_LIMIT = "suppress_rate_limit"

@dataclass
class TriggerResult:
    decision: TriggerDecision
    trigger_type: str
    reason: Optional[str] = None
    matched_text: Optional[str] = None

class BaseTrigger(ABC):
    """Base class for all triggers."""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.fire_probability = config.get('fire_probability', 1.0)
        self.cooldown_seconds = config.get('cooldown_seconds', 0)
        self.last_fire_time = {}  # {channel: timestamp}
    
    @abstractmethod
    def check_condition(self, ctx: TriggerContext) -> bool:
        """Check if trigger condition is met."""
        pass
    
    def evaluate(self, ctx: TriggerContext) -> TriggerResult:
        """Evaluate trigger (full logic)."""
        # 1. Check if enabled
        if not self.enabled:
            return TriggerResult(
                decision=TriggerDecision.SUPPRESS_NO_MATCH,
                trigger_type=self.__class__.__name__,
                reason="Trigger disabled"
            )
        
        # 2. Check condition
        if not self.check_condition(ctx):
            return TriggerResult(
                decision=TriggerDecision.SUPPRESS_NO_MATCH,
                trigger_type=self.__class__.__name__
            )
        
        # 3. Check cooldown
        if not self._check_cooldown(ctx):
            return TriggerResult(
                decision=TriggerDecision.SUPPRESS_COOLDOWN,
                trigger_type=self.__class__.__name__,
                reason=f"Cooldown active ({self.cooldown_seconds}s)"
            )
        
        # 4. Check fire probability
        if not self._check_probability():
            return TriggerResult(
                decision=TriggerDecision.SUPPRESS_PROBABILITY,
                trigger_type=self.__class__.__name__,
                reason=f"Probability check failed ({self.fire_probability})"
            )
        
        # 5. Fire!
        self.last_fire_time[ctx.channel] = ctx.timestamp
        return TriggerResult(
            decision=TriggerDecision.FIRE,
            trigger_type=self.__class__.__name__
        )
    
    def _check_cooldown(self, ctx: TriggerContext) -> bool:
        """Check if cooldown period has elapsed."""
        if self.cooldown_seconds == 0:
            return True
        
        last_fire = self.last_fire_time.get(ctx.channel)
        if last_fire is None:
            return True
        
        elapsed_ms = ctx.timestamp - last_fire
        elapsed_seconds = elapsed_ms / 1000
        return elapsed_seconds >= self.cooldown_seconds
    
    def _check_probability(self) -> bool:
        """Check fire probability (random selection)."""
        import random
        return random.random() < self.fire_probability
```

### 4.2 Mention Trigger

```python
class MentionTrigger(BaseTrigger):
    """Trigger on @mentions or bot name/aliases."""
    
    def __init__(self, config: dict, bot_username: str, bot_aliases: list):
        super().__init__(config)
        self.bot_username = bot_username.lower()
        self.bot_aliases = [alias.lower() for alias in bot_aliases]
    
    def check_condition(self, ctx: TriggerContext) -> bool:
        """Check if message mentions bot."""
        message_lower = ctx.message.lower()
        
        # Check @username
        if f"@{self.bot_username}" in message_lower:
            return True
        
        # Check aliases (whole word match)
        import re
        for alias in self.bot_aliases:
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, message_lower):
                return True
        
        return False
```

### 4.3 Keyword Trigger

```python
class KeywordTrigger(BaseTrigger):
    """Trigger on specific keywords/phrases."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.keywords = config.get('keywords', [])
        self.case_sensitive = config.get('case_sensitive', False)
        
        if not self.case_sensitive:
            self.keywords = [kw.lower() for kw in self.keywords]
    
    def check_condition(self, ctx: TriggerContext) -> bool:
        """Check if message contains keyword."""
        message = ctx.message
        if not self.case_sensitive:
            message = message.lower()
        
        for keyword in self.keywords:
            if keyword in message:
                return True
        
        return False
```

### 4.4 Contextual Trigger

```python
class ContextualTrigger(BaseTrigger):
    """Trigger based on LLM evaluation of chat context."""
    
    def __init__(self, config: dict, llm_client):
        super().__init__(config)
        self.llm_client = llm_client
        self.evaluation_interval_seconds = config.get('evaluation_interval_seconds', 120)
        self.min_messages_since_last_bot = config.get('min_messages_since_last_bot_message', 5)
        self.participation_prompt = config.get('participation_prompt', '')
        self.last_evaluation_time = {}  # {channel: timestamp}
    
    def check_condition(self, ctx: TriggerContext) -> bool:
        """Check if bot should participate (LLM decides)."""
        # 1. Check evaluation interval
        last_eval = self.last_evaluation_time.get(ctx.channel)
        if last_eval is not None:
            elapsed_seconds = (ctx.timestamp - last_eval) / 1000
            if elapsed_seconds < self.evaluation_interval_seconds:
                return False
        
        # 2. Check min messages since last bot message
        messages_since_bot = self._count_messages_since_bot(ctx.context_window)
        if messages_since_bot < self.min_messages_since_last_bot:
            return False
        
        # 3. Ask LLM if participation is natural
        self.last_evaluation_time[ctx.channel] = ctx.timestamp
        return self._llm_evaluate(ctx)
    
    def _count_messages_since_bot(self, context_window: list) -> int:
        """Count messages since last bot message."""
        count = 0
        for entry in reversed(context_window):
            if entry.is_bot:
                break
            count += 1
        return count
    
    def _llm_evaluate(self, ctx: TriggerContext) -> bool:
        """Use LLM to decide if participation is appropriate."""
        # Format context
        context_str = '\n'.join(
            f"{entry.username}: {entry.message}"
            for entry in ctx.context_window[-20:]
        )
        
        # Query LLM
        response = self.llm_client.complete(
            prompt=f"{self.participation_prompt}\n\nChat:\n{context_str}",
            max_tokens=5
        )
        
        # Parse yes/no
        return response.strip().lower() == 'yes'
```

### 4.5 PM Trigger

```python
class PMTrigger(BaseTrigger):
    """Trigger on private messages."""
    
    def check_condition(self, ctx: TriggerContext) -> bool:
        """Always true for PM events (already filtered by event type)."""
        return True
```

### 4.6 Rate Limiter

```python
from collections import deque
from typing import Dict

class RateLimiter:
    """Sliding window rate limiter."""
    
    def __init__(self, window_seconds: int, max_count: int):
        self.window_seconds = window_seconds
        self.max_count = max_count
        self.events: deque = deque()  # Timestamps
    
    def allow(self, timestamp: int) -> bool:
        """Check if event is allowed at given timestamp."""
        # 1. Remove events outside window
        cutoff = timestamp - (self.window_seconds * 1000)
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
        
        # 2. Check limit
        if len(self.events) >= self.max_count:
            return False
        
        # 3. Record event
        self.events.append(timestamp)
        return True
    
    def remaining(self, timestamp: int) -> int:
        """Get remaining capacity in current window."""
        cutoff = timestamp - (self.window_seconds * 1000)
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
        return max(0, self.max_count - len(self.events))

class RateLimitManager:
    """Manage multiple rate limiters per user/channel."""
    
    def __init__(self, config: dict):
        self.config = config
        # Per-user limiters (spans all channels)
        self.user_limiters: Dict[str, Dict[str, RateLimiter]] = {}
        # Per-channel limiters
        self.channel_limiters: Dict[str, Dict[str, RateLimiter]] = {}
        # Global cooldown
        self.last_bot_message_time = {}  # {channel: timestamp}
    
    def allow_user(self, username: str, timestamp: int) -> bool:
        """Check per-user rate limits."""
        if username not in self.user_limiters:
            self.user_limiters[username] = self._create_user_limiters()
        
        limiters = self.user_limiters[username]
        
        # Check all user limits
        for limiter in limiters.values():
            if not limiter.allow(timestamp):
                return False
        
        return True
    
    def allow_channel(self, channel: str, timestamp: int) -> bool:
        """Check per-channel rate limits."""
        if channel not in self.channel_limiters:
            self.channel_limiters[channel] = self._create_channel_limiters()
        
        limiters = self.channel_limiters[channel]
        
        # Check all channel limits
        for limiter in limiters.values():
            if not limiter.allow(timestamp):
                return False
        
        return True
    
    def check_global_cooldown(self, channel: str, timestamp: int) -> bool:
        """Check global cooldown between bot messages."""
        cooldown_seconds = self.config.get('global_cooldown_seconds', 5)
        if cooldown_seconds == 0:
            return True
        
        last_time = self.last_bot_message_time.get(channel)
        if last_time is None:
            return True
        
        elapsed_ms = timestamp - last_time
        elapsed_seconds = elapsed_ms / 1000
        return elapsed_seconds >= cooldown_seconds
    
    def record_bot_message(self, channel: str, timestamp: int):
        """Record that bot sent a message (for cooldown)."""
        self.last_bot_message_time[channel] = timestamp
    
    def _create_user_limiters(self) -> Dict[str, RateLimiter]:
        """Create rate limiters for a user."""
        return {
            'per_minute': RateLimiter(
                window_seconds=60,
                max_count=self.config.get('max_per_user_per_minute', 3)
            ),
            'per_hour': RateLimiter(
                window_seconds=3600,
                max_count=self.config.get('max_per_user_per_hour', 10)
            )
        }
    
    def _create_channel_limiters(self) -> Dict[str, RateLimiter]:
        """Create rate limiters for a channel."""
        return {
            'per_minute': RateLimiter(
                window_seconds=60,
                max_count=self.config.get('max_per_channel_per_minute', 5)
            ),
            'per_hour': RateLimiter(
                window_seconds=3600,
                max_count=self.config.get('max_per_channel_per_hour', 30)
            )
        }
```

## 5. Acceptance Criteria

- **AC-001**: Given mention trigger, When "@bot" in message, Then condition is true
- **AC-002**: Given keyword trigger, When keyword not in message, Then condition is false
- **AC-003**: Given fire_probability=0.5, When evaluated 1000 times, Then fires ~500 times (±10%)
- **AC-004**: Given cooldown=10s, When fired at T=0, Then suppressed until T=10s
- **AC-005**: Given rate_limit max=3/min, When 3 events in window, Then 4th is denied
- **AC-006**: Given global cooldown=5s, When bot sent message at T=0, Then all triggers suppressed until T=5s
- **AC-007**: Given media change at T=0, When cooldown=30s, Then all triggers suppressed until T=30s
- **AC-008**: Given mention and keyword both match, When evaluated, Then mention fires (priority)

## 6. Test Automation Strategy

- **Test Levels**: Unit tests for each trigger, rate limiter
- **Frameworks**: pytest, hypothesis (property-based testing)
- **Test Data**: Mock events, context windows
- **Trigger Tests**: Test condition check, probability, cooldown
- **Rate Limiter Tests**: Test sliding window, boundary cases
- **Integration Tests**: Test full evaluation pipeline
- **Property Tests**: Verify rate limiter invariants (never exceeds max)

## 7. Rationale & Context

### Why Priority-Based Evaluation?

**Problem**: Multiple triggers may match same event.

**Solution**: Evaluate in priority order, fire first match.

**Priority Order**:
1. Mention (highest) - Direct address to bot
2. PM - Private message (always respond)
3. Keyword - Specific topics
4. Contextual (lowest) - General participation

**Rationale**: More specific triggers should take precedence.

### Why Sliding Window vs Fixed Buckets?

**Fixed Buckets** (e.g., hourly):
- Simple implementation
- Can burst at bucket boundary
- Example: 60 requests at 10:59, 60 at 11:00 = 120 in 1 minute

**Sliding Window**:
- Fair distribution over time
- No burst at boundaries
- Slightly more complex (deque cleanup)

**Decision**: Sliding window prevents burst abuse, worth the complexity.

### Why Fire Probability?

**Use Case**: Reduce bot activity without disabling trigger.

**Example**: Keyword trigger fires on "bot" (common word)
- `fire_probability: 0.3` → Bot responds to 30% of mentions
- Feels more natural (not every single time)

**Implementation**: `random.random() < fire_probability`

### Why Global Cooldown?

**Problem**: Bot could rapid-fire if multiple triggers fire in sequence.

**Solution**: Global cooldown across all triggers per channel.

**Example**:
- Mention trigger fires at T=0
- Keyword trigger would fire at T=1
- Global cooldown suppresses keyword until T=5

**Rationale**: Prevents bot from dominating conversation.

### Why Media Change Cooldown?

**Problem**: Users often comment when video changes ("oh I love this song").

**Solution**: Silent period after media change to let organic discussion flow.

**Duration**: 30 seconds (configurable)

**Rationale**: Bot shouldn't immediately chime in when video changes.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Context Window - Provides recent chat history
- **EXT-002**: LLM Client - For contextual trigger evaluation

### Technology Platform Dependencies

- **PLT-001**: Python random module - For fire probability
- **PLT-002**: Python collections.deque - For sliding window

## 9. Examples & Edge Cases

### Example: Trigger Evaluation Pipeline

```python
async def evaluate_triggers(event: dict, channel: str) -> Optional[str]:
    """Evaluate triggers, return response or None."""
    # Build context
    ctx = TriggerContext(
        event=event,
        channel=channel,
        username=event['user']['name'],
        message=event['msg'],
        timestamp=event['time'],
        context_window=context_windows[channel],
        correlation_id=str(uuid.uuid4())
    )
    
    # Check media change cooldown
    if media_change_cooldown.is_active(channel, ctx.timestamp):
        logger.info("All triggers suppressed (media change cooldown)",
                    correlation_id=ctx.correlation_id)
        return None
    
    # Evaluate triggers in priority order
    triggers = [
        mention_trigger,
        pm_trigger,
        keyword_trigger,
        contextual_trigger
    ]
    
    for trigger in triggers:
        result = trigger.evaluate(ctx)
        
        logger.debug("Trigger evaluated",
                     correlation_id=ctx.correlation_id,
                     trigger=result.trigger_type,
                     decision=result.decision.value,
                     reason=result.reason)
        
        if result.decision == TriggerDecision.FIRE:
            # Check rate limits
            if not rate_limiter.allow_user(ctx.username, ctx.timestamp):
                logger.info("Trigger suppressed (user rate limit)",
                            correlation_id=ctx.correlation_id,
                            username=ctx.username)
                return None
            
            if not rate_limiter.allow_channel(channel, ctx.timestamp):
                logger.info("Trigger suppressed (channel rate limit)",
                            correlation_id=ctx.correlation_id,
                            channel=channel)
                return None
            
            if not rate_limiter.check_global_cooldown(channel, ctx.timestamp):
                logger.info("Trigger suppressed (global cooldown)",
                            correlation_id=ctx.correlation_id,
                            channel=channel)
                return None
            
            # Fire! Generate response
            logger.info("Trigger fired",
                        correlation_id=ctx.correlation_id,
                        trigger=result.trigger_type)
            
            response = await generate_response(ctx)
            rate_limiter.record_bot_message(channel, ctx.timestamp)
            return response
    
    # No trigger fired
    return None
```

### Edge Case: Rapid-Fire Keywords

```python
# Scenario: User types "bot bot bot bot" (4 mentions)
message = "bot bot bot bot"

# Without cooldown: 4 responses
# With cooldown=10s: 1 response, then 10s silence
```

### Edge Case: Sliding Window Boundary

```python
# Scenario: Rate limit 3/minute
# T=0s: Event 1 (allowed)
# T=10s: Event 2 (allowed)
# T=20s: Event 3 (allowed)
# T=30s: Event 4 (denied - 3 in last 60s)
# T=61s: Event 5 (allowed - Event 1 dropped from window)
```

### Edge Case: Probability Never Fires

```python
# Scenario: fire_probability=0.1, user gets unlucky
# User: "@bot help"  (probability check fails)
# User: "@bot help"  (probability check fails)
# User: "@bot help"  (probability check fails)
# ...10 attempts later...
# User: "@bot help"  (finally fires!)

# Solution: Consider minimum guaranteed response after N attempts
```

### Edge Case: Contextual Trigger LLM Timeout

```python
# Scenario: LLM API hangs during participation check
try:
    should_participate = await asyncio.wait_for(
        llm_client.evaluate_participation(context),
        timeout=5.0
    )
except asyncio.TimeoutError:
    logger.warning("Contextual trigger LLM timeout",
                   correlation_id=ctx.correlation_id)
    # Suppress trigger (fail safe)
    should_participate = False
```

## 10. Validation Criteria

- **VAL-001**: Rate limiter never allows more than max_count events in window
- **VAL-002**: Cooldown always enforces minimum time between fires
- **VAL-003**: Fire probability distributes uniformly over many samples
- **VAL-004**: Mention trigger detects @bot, bot name, and all aliases
- **VAL-005**: Keyword trigger matches case-insensitively (when configured)
- **VAL-006**: Global cooldown suppresses all triggers across types
- **VAL-007**: Media change cooldown suppresses all triggers globally
- **VAL-008**: Trigger evaluation logs all decisions with correlation ID

## 11. Related Specifications / Further Reading

- [Architecture Specification](./spec-architecture-design.md) - Trigger component design
- [Configuration Specification](./spec-configuration.md) - Trigger configuration
- [Observability Specification](./spec-observability.md) - Trigger decision logging

**External References**:
- [Rate Limiting Algorithms](https://en.wikipedia.org/wiki/Rate_limiting)
- [Sliding Window](https://en.wikipedia.org/wiki/Sliding_window_protocol)

---

## Performance Characteristics

### Trigger Evaluation

- **Mention Check**: O(n) where n = message length (string search)
- **Keyword Check**: O(k×n) where k = keywords, n = message length
- **Contextual Check**: O(API_LATENCY) - LLM call dominates
- **PM Check**: O(1) - always true

### Rate Limiter

- **Allow Check**: O(w) where w = events in window (deque cleanup)
- **Typical w**: 3-30 (per-minute and per-hour limits)
- **Worst Case**: O(max_count) cleanup per check
- **Amortized**: O(1) with periodic cleanup

### Memory Usage

- **Per User**: ~1KB (2 deques with 3-10 timestamps each)
- **Per Channel**: ~1KB (2 deques with 5-30 timestamps each)
- **10 Users, 5 Channels**: ~15KB (negligible)

---

## Version History

- **v1.0** - 2025-12-03 - Initial triggers and rate limiting specification

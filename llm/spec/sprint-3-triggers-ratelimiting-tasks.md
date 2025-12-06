# Sprint 3 Tasks: Trigger System & Rate Limiting

**Duration**: 2 weeks  
**Focus**: Implementing trigger evaluation logic and sliding window rate limiting

## Overview

Sprint 3 implements the core intelligence of when the bot should respond. Triggers evaluate conditions, rate limiters prevent spam, and the system decides whether to fire based on probability and cooldowns.

## Task Templates

### TASK-023: Implement BaseTrigger Abstract Class

**Estimated Duration**: 3-4 hours  
**Prerequisites**: TASK-013, TASK-019  
**Related Specs**: [Triggers Specification](./spec-triggers-ratelimiting.md) - Section 4.1

**Objective**: Create abstract base class defining trigger interface and common logic.

**Implementation Pattern**:

```python
# llm_bot/triggers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Optional, Dict
import random
import logging

logger = logging.getLogger(__name__)

class TriggerDecision(Enum):
    """Trigger evaluation result."""
    FIRE = "fire"
    SUPPRESS_COOLDOWN = "suppress_cooldown"
    SUPPRESS_PROBABILITY = "suppress_probability"
    SUPPRESS_CONDITION = "suppress_condition"

@dataclass
class TriggerResult:
    """Result of trigger evaluation."""
    decision: TriggerDecision
    reason: Optional[str] = None
    trigger_type: Optional[str] = None

class BaseTrigger(ABC):
    """Base class for all trigger implementations."""
    
    def __init__(
        self,
        enabled: bool = True,
        fire_probability: float = 1.0,
        cooldown_seconds: int = 10
    ):
        self.enabled = enabled
        self.fire_probability = fire_probability
        self.cooldown_seconds = cooldown_seconds
        
        # Track last fire time per channel
        self._last_fire_time: Dict[str, datetime] = {}
    
    async def evaluate(
        self,
        event,
        context,
        channel: str
    ) -> TriggerResult:
        """
        Evaluate whether trigger should fire.
        
        Pipeline:
        1. Check if enabled
        2. Check condition (implemented by subclass)
        3. Check cooldown
        4. Check probability
        5. Return FIRE or suppress reason
        
        Args:
            event: Event that triggered evaluation
            context: Chat context window
            channel: Channel name
            
        Returns:
            TriggerResult with decision and reason
        """
        if not self.enabled:
            return TriggerResult(
                TriggerDecision.SUPPRESS_CONDITION,
                "Trigger disabled"
            )
        
        # Step 1: Check condition
        if not await self._check_condition(event, context):
            return TriggerResult(
                TriggerDecision.SUPPRESS_CONDITION,
                "Condition not met"
            )
        
        # Step 2: Check cooldown
        if not self._check_cooldown(channel):
            time_remaining = self._get_cooldown_remaining(channel)
            return TriggerResult(
                TriggerDecision.SUPPRESS_COOLDOWN,
                f"Cooldown active ({time_remaining}s remaining)"
            )
        
        # Step 3: Check probability
        if not self._check_probability():
            return TriggerResult(
                TriggerDecision.SUPPRESS_PROBABILITY,
                f"Probability check failed (p={self.fire_probability})"
            )
        
        # Record fire time
        self._record_fire(channel)
        
        return TriggerResult(
            TriggerDecision.FIRE,
            trigger_type=self.__class__.__name__
        )
    
    @abstractmethod
    async def _check_condition(self, event, context) -> bool:
        """
        Check if trigger condition is met.
        
        Must be implemented by subclass.
        
        Returns:
            True if condition met, False otherwise
        """
        pass
    
    def _check_cooldown(self, channel: str) -> bool:
        """Check if cooldown period has elapsed."""
        if channel not in self._last_fire_time:
            return True
        
        elapsed = (datetime.utcnow() - self._last_fire_time[channel]).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def _get_cooldown_remaining(self, channel: str) -> int:
        """Get remaining cooldown time in seconds."""
        if channel not in self._last_fire_time:
            return 0
        
        elapsed = (datetime.utcnow() - self._last_fire_time[channel]).total_seconds()
        remaining = max(0, self.cooldown_seconds - elapsed)
        return int(remaining)
    
    def _check_probability(self) -> bool:
        """Check if random probability allows firing."""
        return random.random() < self.fire_probability
    
    def _record_fire(self, channel: str) -> None:
        """Record that trigger fired."""
        self._last_fire_time[channel] = datetime.utcnow()
        logger.debug(f"{self.__class__.__name__} fired for channel: {channel}")
```

**Testing**:

```python
# tests/unit/test_triggers.py

class TestTrigger(BaseTrigger):
    """Test trigger implementation."""
    
    def __init__(self, condition_result=True, **kwargs):
        super().__init__(**kwargs)
        self.condition_result = condition_result
    
    async def _check_condition(self, event, context):
        return self.condition_result

@pytest.mark.asyncio
async def test_trigger_fires_when_all_checks_pass():
    trigger = TestTrigger(enabled=True, fire_probability=1.0, cooldown_seconds=0)
    result = await trigger.evaluate(None, None, "test")
    assert result.decision == TriggerDecision.FIRE

@pytest.mark.asyncio
async def test_trigger_suppressed_by_cooldown():
    trigger = TestTrigger(cooldown_seconds=10)
    
    # First fire succeeds
    result1 = await trigger.evaluate(None, None, "test")
    assert result1.decision == TriggerDecision.FIRE
    
    # Immediate second fire suppressed
    result2 = await trigger.evaluate(None, None, "test")
    assert result2.decision == TriggerDecision.SUPPRESS_COOLDOWN

@pytest.mark.asyncio
async def test_trigger_respects_probability():
    # Probability 0 = never fires
    trigger = TestTrigger(fire_probability=0.0, cooldown_seconds=0)
    result = await trigger.evaluate(None, None, "test")
    assert result.decision == TriggerDecision.SUPPRESS_PROBABILITY
```

**Acceptance Criteria**:
- [ ] Abstract base class with evaluate() method
- [ ] Evaluation pipeline: enabled → condition → cooldown → probability
- [ ] _check_condition() abstract method
- [ ] _check_cooldown() tracks per-channel
- [ ] _check_probability() uses random.random()
- [ ] Tests pass

---

### TASK-024: Implement MentionTrigger

**Estimated Duration**: 2-3 hours  
**Prerequisites**: TASK-023  
**Related Specs**: [Triggers Specification](./spec-triggers-ratelimiting.md) - Section 4.2

**Implementation Pattern**:

```python
# llm_bot/triggers/mention.py

import re
from typing import List
from llm_bot.triggers.base import BaseTrigger

class MentionTrigger(BaseTrigger):
    """Trigger when bot is mentioned."""
    
    def __init__(
        self,
        bot_username: str,
        aliases: List[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.bot_username = bot_username.lower()
        self.aliases = [a.lower() for a in (aliases or [])]
        
        # Build regex pattern for whole-word matching
        names = [re.escape(self.bot_username)] + [re.escape(a) for a in self.aliases]
        pattern = r'\b(' + '|'.join(names) + r')\b'
        self.pattern = re.compile(pattern, re.IGNORECASE)
    
    async def _check_condition(self, event, context) -> bool:
        """Check if message contains bot mention."""
        message = event.msg.lower()
        
        # Check for @username
        if f"@{self.bot_username}" in message:
            return True
        
        # Check for regex match (bot name or aliases)
        if self.pattern.search(message):
            return True
        
        return False
```

**Testing**:

```python
def test_mention_trigger_detects_username():
    trigger = MentionTrigger("TestBot", aliases=["bot"])
    
    event = Mock()
    event.msg = "Hey @TestBot, what do you think?"
    
    result = await trigger._check_condition(event, None)
    assert result is True

def test_mention_trigger_detects_alias():
    trigger = MentionTrigger("TestBot", aliases=["bot"])
    
    event = Mock()
    event.msg = "Hey bot, are you there?"
    
    result = await trigger._check_condition(event, None)
    assert result is True

def test_mention_trigger_whole_word_only():
    trigger = MentionTrigger("bot")
    
    event = Mock()
    event.msg = "This is a robot"  # Contains "bot" but not whole word
    
    result = await trigger._check_condition(event, None)
    assert result is False
```

---

### TASK-025 through TASK-027

Implement remaining trigger types following the same pattern:

- **TASK-025**: KeywordTrigger (substring search, optional case-sensitive)
- **TASK-026**: PMTrigger (always returns true for PM events)
- **TASK-027**: ContextualTrigger (LLM evaluation with interval check)

---

### TASK-030: Implement RateLimiter Class

**Estimated Duration**: 4-5 hours  
**Prerequisites**: TASK-023  
**Related Specs**: [Triggers Specification](./spec-triggers-ratelimiting.md) - Section 4.4

**Implementation Pattern**:

```python
# llm_bot/rate_limiter.py

from collections import deque
from datetime import datetime, timedelta
from typing import Deque
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Sliding window rate limiter."""
    
    def __init__(self, max_count: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_count: Maximum events in window
            window_seconds: Window size in seconds
        """
        self.max_count = max_count
        self.window = timedelta(seconds=window_seconds)
        
        # Store event timestamps
        self.events: Deque[datetime] = deque()
    
    def allow(self) -> bool:
        """
        Check if new event is allowed within rate limit.
        
        Returns:
            True if allowed, False if rate limit exceeded
        """
        self._cleanup_old_events()
        
        if len(self.events) < self.max_count:
            self.events.append(datetime.utcnow())
            return True
        
        return False
    
    def remaining(self) -> int:
        """
        Get remaining capacity in current window.
        
        Returns:
            Number of events that can still be allowed
        """
        self._cleanup_old_events()
        return max(0, self.max_count - len(self.events))
    
    def _cleanup_old_events(self) -> None:
        """Remove events outside the sliding window."""
        cutoff = datetime.utcnow() - self.window
        
        # Remove from left while old (O(w) where w = events outside window)
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
    
    def reset(self) -> None:
        """Clear all tracked events."""
        self.events.clear()
```

**Testing**:

```python
# tests/unit/test_rate_limiter.py

def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_count=3, window_seconds=60)
    
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.remaining() == 0

def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(max_count=2, window_seconds=60)
    
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False  # Third blocked

def test_rate_limiter_cleanup_old_events():
    limiter = RateLimiter(max_count=2, window_seconds=1)
    
    # Add two events
    limiter.allow()
    limiter.allow()
    
    # Wait for window to expire
    import time
    time.sleep(1.1)
    
    # Should allow again
    assert limiter.allow() is True
```

**Acceptance Criteria**:
- [ ] Uses deque for O(1) append/popleft
- [ ] allow() checks and updates limit
- [ ] remaining() returns capacity
- [ ] _cleanup_old_events() removes expired
- [ ] Tests pass

---

### TASK-031: Implement RateLimitManager

**Estimated Duration**: 4-5 hours  
**Prerequisites**: TASK-030  
**Related Specs**: [Triggers Specification](./spec-triggers-ratelimiting.md) - Section 4.5

**Implementation Pattern**:

```python
# llm_bot/rate_limiter.py (add to existing file)

from typing import Dict

class RateLimitManager:
    """Manages rate limiters for users and channels."""
    
    def __init__(self, config: RateLimitsConfig):
        self.config = config
        
        # Per-user rate limiters (spans all channels)
        self.user_limiters: Dict[str, Dict[str, RateLimiter]] = {}
        
        # Per-channel rate limiters (isolated per channel)
        self.channel_limiters: Dict[str, Dict[str, RateLimiter]] = {}
        
        # Global cooldown tracking
        self.last_bot_message: Dict[str, datetime] = {}
    
    def check_user_limit(self, username: str) -> bool:
        """Check if user is within rate limits."""
        if username not in self.user_limiters:
            self._init_user_limiters(username)
        
        # Check per-minute limit
        if not self.user_limiters[username]["per_minute"].allow():
            logger.info(f"User rate limit exceeded: {username} (per minute)")
            return False
        
        # Check per-hour limit
        if not self.user_limiters[username]["per_hour"].allow():
            logger.info(f"User rate limit exceeded: {username} (per hour)")
            return False
        
        return True
    
    def check_channel_limit(self, channel: str) -> bool:
        """Check if channel is within rate limits."""
        if channel not in self.channel_limiters:
            self._init_channel_limiters(channel)
        
        # Check per-minute limit
        if not self.channel_limiters[channel]["per_minute"].allow():
            logger.info(f"Channel rate limit exceeded: {channel} (per minute)")
            return False
        
        # Check per-hour limit
        if not self.channel_limiters[channel]["per_hour"].allow():
            logger.info(f"Channel rate limit exceeded: {channel} (per hour)")
            return False
        
        return True
    
    def check_global_cooldown(self, channel: str) -> bool:
        """Check if global cooldown has elapsed."""
        if channel not in self.last_bot_message:
            return True
        
        elapsed = (datetime.utcnow() - self.last_bot_message[channel]).total_seconds()
        if elapsed < self.config.global_cooldown_seconds:
            logger.debug(
                f"Global cooldown active: {channel} "
                f"({self.config.global_cooldown_seconds - elapsed:.1f}s remaining)"
            )
            return False
        
        return True
    
    def record_bot_message(self, channel: str) -> None:
        """Record that bot sent a message."""
        self.last_bot_message[channel] = datetime.utcnow()
    
    def _init_user_limiters(self, username: str) -> None:
        """Initialize rate limiters for user."""
        self.user_limiters[username] = {
            "per_minute": RateLimiter(
                self.config.max_per_user_per_minute,
                60
            ),
            "per_hour": RateLimiter(
                self.config.max_per_user_per_hour,
                3600
            ),
        }
    
    def _init_channel_limiters(self, channel: str) -> None:
        """Initialize rate limiters for channel."""
        self.channel_limiters[channel] = {
            "per_minute": RateLimiter(
                self.config.max_per_channel_per_minute,
                60
            ),
            "per_hour": RateLimiter(
                self.config.max_per_channel_per_hour,
                3600
            ),
        }
```

**Acceptance Criteria**:
- [ ] Per-user limiters span channels
- [ ] Per-channel limiters isolated
- [ ] Global cooldown tracked per channel
- [ ] record_bot_message() updates state
- [ ] Tests pass

---

## Sprint 3 Completion Criteria

By the end of Sprint 3, you should be able to:

- [ ] Evaluate mention triggers (bot name/aliases)
- [ ] Evaluate keyword triggers (with probability)
- [ ] Evaluate PM triggers (always fire)
- [ ] Evaluate contextual triggers (LLM-based)
- [ ] Apply per-user rate limits
- [ ] Apply per-channel rate limits
- [ ] Apply global cooldowns
- [ ] Suppress triggers with clear reasons

## Integration Test for Sprint 3

```python
# tests/integration/test_sprint3_triggers.py

@pytest.mark.asyncio
async def test_trigger_evaluation_with_rate_limiting():
    """Test complete trigger evaluation with rate limiting."""
    
    config = Config.load("config.example.yaml")
    
    # Create trigger
    trigger = MentionTrigger("TestBot", fire_probability=1.0, cooldown_seconds=5)
    
    # Create rate limit manager
    rate_manager = RateLimitManager(config.rate_limits)
    
    # Create mock event
    event = Mock()
    event.msg = "Hey @TestBot"
    
    # First evaluation - should fire
    result = await trigger.evaluate(event, None, "test")
    assert result.decision == TriggerDecision.FIRE
    
    # Check rate limits
    assert rate_manager.check_user_limit("Alice") is True
    assert rate_manager.check_channel_limit("test") is True
    
    # Record bot message
    rate_manager.record_bot_message("test")
    
    # Check global cooldown
    assert rate_manager.check_global_cooldown("test") is False
    
    # Immediate second evaluation - suppressed by cooldown
    result = await trigger.evaluate(event, None, "test")
    assert result.decision == TriggerDecision.SUPPRESS_COOLDOWN
```

## Next Sprint

**Sprint 4**: LLM Integration & Response Processing (Tasks 033-043)

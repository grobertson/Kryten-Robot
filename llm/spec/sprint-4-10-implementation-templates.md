# Sprint 4-10 Tasks: Implementation Templates

This document provides task templates and patterns for Sprints 4-10. Each sprint follows the established pattern from Sprints 1-3.

## Sprint 4: LLM Integration & Response Processing (Tasks 033-043)

**Duration**: 2 weeks  
**Focus**: LLM API client, prompt construction, response filtering

### Key Tasks Pattern

**TASK-033: Implement LLMClient Class**
- HTTP client with httpx.AsyncClient
- POST to /v1/chat/completions
- Timeout and retry logic
- Reference: spec-data-contracts.md Section 4.2

**TASK-034-035: Request/Response Handling**
- Build ChatCompletionRequest with messages array
- Parse ChatCompletionResponse for content and metadata
- Reference: spec-data-contracts.md Section 4.2

**TASK-039-043: ResponseProcessor**
- Length truncation (hard/sentence)
- Content filtering (regex patterns, keywords)
- Quality checks (deduplication, echo detection)
- Formatting (markdown stripping, newline collapse)
- Reference: spec-configuration.md Section 4.1 (response_processing)

### Implementation Pattern

```python
# llm_bot/llm_client.py

import httpx
import asyncio
from typing import Optional

class LLMClient:
    """Async client for OpenAI-compatible LLM APIs."""
    
    def __init__(self, config: LLMAPIConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {config.api_key}"}
        )
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        correlation_id: str
    ) -> Optional[str]:
        """
        Request completion from LLM API.
        
        Returns:
            Completion text or None on error
        """
        request_data = {
            "model": self.config.model,
            "messages": messages,
            **self.config.parameters.model_dump()
        }
        
        for attempt in range(self.config.retry_attempts + 1):
            try:
                response = await self.client.post(
                    "/chat/completions",
                    json=request_data
                )
                response.raise_for_status()
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
            except httpx.TimeoutException:
                if attempt < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_delay_seconds)
                else:
                    logger.error("LLM API timeout", extra={"correlation_id": correlation_id})
                    return None
```

---

## Sprint 5: Response Delivery & Multi-Channel (Tasks 044-048)

**Duration**: 1 week  
**Focus**: NATS command publishing, channel isolation

### Key Tasks Pattern

**TASK-044: Response Delivery via NATS**
- Publish ChatCommand to cytube.commands.{channel}.chat
- Publish PMCommand to cytube.commands.{channel}.pm
- Include correlation ID in headers
- Reference: spec-data-contracts.md Section 4.2

**TASK-046-048: Multi-Channel Support**
- Separate ContextWindow per channel
- Separate TriggerManager per channel  
- Dynamic channel add/remove on config reload
- Reference: spec-architecture-design.md Section 5.3

### Implementation Pattern

```python
# In event handling pipeline

async def handle_trigger_fire(
    event,
    trigger_result,
    context,
    channel,
    correlation_id
):
    """Handle trigger fire event."""
    
    # Build LLM prompt
    messages = prompt_builder.build_messages(
        context.get_formatted_context(),
        event.msg
    )
    
    # Call LLM
    response_text = await llm_client.complete(messages, correlation_id)
    
    # Process response
    filtered_response = response_processor.process(response_text)
    
    if filtered_response:
        # Publish to NATS
        await nats_client.publish_chat_command(
            channel,
            filtered_response,
            correlation_id
        )
        
        # Update rate limiters
        rate_manager.record_bot_message(channel)
```

---

## Sprint 6: Health, Metrics & Startup/Shutdown (Tasks 049-057)

**Duration**: 1 week  
**Focus**: HTTP endpoints, application lifecycle

### Key Tasks Pattern

**TASK-049-051: HTTP Server**
- aiohttp server on configured host:port
- GET /health returns JSON status
- GET /metrics returns Prometheus text format
- Reference: spec-observability.md Sections 4.4, 4.5

**TASK-052-057: Application Lifecycle**
- Main entry point with argument parsing
- Startup sequence (config → NATS → subscriptions → HTTP)
- SIGTERM/SIGINT signal handlers
- Graceful shutdown (drain NATS, finish in-flight, close connections)
- Reference: requirements.md FR-012

### Implementation Pattern

```python
# llm_bot/__main__.py

import asyncio
import signal
from llm_bot.config import Config
from llm_bot.nats_client import NATSClient
from llm_bot.health import HealthServer

async def main():
    """Main application entry point."""
    
    # Load config
    config = Config.load("config.yaml")
    
    # Setup shutdown handler
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    # Connect to NATS
    nats_client = NATSClient(config.nats)
    await nats_client.connect()
    
    # Start HTTP server
    health_server = HealthServer(config.health)
    await health_server.start()
    
    # Subscribe to events
    # ... setup event handlers ...
    
    logger.info("Bot ready")
    
    # Wait for shutdown signal
    await shutdown_event.wait()
    
    # Graceful shutdown
    logger.info("Shutting down...")
    await nats_client.disconnect()
    await health_server.stop()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

---

## Sprint 7: Testing & Documentation (Tasks 058-071)

**Duration**: 2 weeks  
**Focus**: Comprehensive test coverage and documentation

### Testing Pattern

**Unit Tests (Tasks 058-063)**
- Test each module in isolation with mocks
- pytest fixtures for common test data
- 80%+ code coverage target

```python
# tests/unit/test_*.py pattern

@pytest.fixture
def mock_config():
    return Mock(spec=Config)

@pytest.fixture
def mock_nats_client():
    return Mock(spec=NATSClient)

def test_component_with_mocks(mock_config, mock_nats_client):
    component = Component(mock_config, mock_nats_client)
    result = component.do_something()
    assert result == expected
```

**Integration Tests (Tasks 064-067)**
- Test component interactions
- Mock external services (NATS, LLM API)
- End-to-end event flow

**Documentation (Tasks 068-071)**
- README.md: Installation, configuration, running
- DEPLOYMENT.md: Production deployment (Docker, systemd)
- DEVELOPMENT.md: Contributing, testing, code style
- API.md: Internal API documentation

---

## Sprint 8: Error Handling & Edge Cases (Tasks 072-079)

**Duration**: 1 week  
**Focus**: Robustness and error recovery

### Error Handling Pattern

**TASK-072: NATS Connection Errors**
- Automatic reconnection with exponential backoff
- Queue outbound messages during disconnection (bounded buffer)
- Log connection state changes

**TASK-073: LLM API Errors**
- Retry on 5xx and timeouts
- Skip on 4xx errors
- Optional fallback responses

**TASK-074-079: Edge Cases**
- Invalid/malformed events
- Config reload failures
- Rapid-fire triggers
- High message volume
- LLM timeout handling

---

## Sprint 9: Performance & Optimization (Tasks 080-086)

**Duration**: 1 week  
**Focus**: Benchmarking and optimization

### Performance Testing Pattern

**Benchmarking (Tasks 080-083)**
```python
# tests/performance/bench_*.py

import time

def bench_event_processing(n=1000):
    """Benchmark event processing latency."""
    start = time.time()
    
    for i in range(n):
        # Process event
        pass
    
    elapsed = time.time() - start
    avg_latency = (elapsed / n) * 1000  # ms
    
    assert avg_latency < 100  # Target: <100ms
```

**Optimization (Tasks 084-086)**
- Cache formatted prompts
- Optimize string operations
- Profile memory usage
- Reduce metric cardinality

---

## Sprint 10: Production Readiness (Tasks 087-096)

**Duration**: 1 week  
**Focus**: Deployment and final polish

### Deployment Artifacts Pattern

**TASK-087: Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY llm_bot/ ./llm_bot/
COPY config.example.yaml .

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

EXPOSE 8080

CMD ["python", "-m", "llm_bot"]
```

**TASK-088: Systemd Service**
```ini
[Unit]
Description=LLM Chat Bot
After=network.target nats.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/llm-bot
Environment="OPENAI_API_KEY=secret"
ExecStart=/opt/llm-bot/venv/bin/python -m llm_bot
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**TASK-089-090: Monitoring**
- Prometheus alerting rules
- Grafana dashboards (reference spec-observability.md examples)

**TASK-091-093: Security**
- Environment variables for secrets
- Input validation hardening
- Rate limiting DoS protection

**TASK-094-096: Final Testing**
- Manual end-to-end testing
- Chaos testing (kill NATS, kill LLM API)
- Code review and cleanup

---

## General Implementation Guidelines

### Code Style
- Use type hints on all functions
- Document with docstrings (Google style)
- Log at appropriate levels (DEBUG/INFO/WARNING/ERROR)
- Include correlation IDs in all logs

### Testing Strategy
- Write tests alongside implementation
- Use pytest fixtures for common setup
- Mock external dependencies
- Aim for 80%+ coverage

### Error Handling
- Fail fast on startup (invalid config, missing connections)
- Degrade gracefully at runtime (log and continue)
- Never crash on invalid events
- Always log errors with context

### Performance Considerations
- Use async/await for all I/O
- Avoid blocking operations
- Use bounded buffers/deques
- Profile memory usage under load

### Documentation
- Keep specifications up to date
- Document all configuration options
- Provide examples for common use cases
- Include troubleshooting guides

---

## Task Completion Checklist

For each task, ensure:

- [ ] Implementation matches specification
- [ ] Type hints on all functions
- [ ] Docstrings on classes and methods
- [ ] Unit tests written and passing
- [ ] Integration test written (if applicable)
- [ ] Logging statements added
- [ ] Error handling implemented
- [ ] Acceptance criteria met
- [ ] Code reviewed
- [ ] Documentation updated

---

## Next Steps

1. Review all sprint template documents
2. Start with Sprint 1, Task 001
3. Follow the established patterns for each task
4. Refer to specifications for detailed requirements
5. Write tests alongside implementation
6. Complete sprint integration tests before moving to next sprint

For detailed implementation of any specific task, refer to:
- The specification documents in this directory
- The detailed task documents (001-003) as examples
- The sprint template documents for patterns

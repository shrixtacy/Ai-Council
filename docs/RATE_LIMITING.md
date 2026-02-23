# Rate Limiting Documentation

## Overview

AI Council implements comprehensive rate limiting to prevent API abuse, ensure fair resource usage, and protect against external service rate limits.

## Components

### 1. RateLimitManager Class (`ai_council/core/timeout_handler.py`)

Manages internal rate limiting and backoff strategies.

**Key Methods:**
- `set_rate_limit(resource, requests_per_minute, burst_limit)` - Configure limits
- `check_rate_limit(resource)` - Check if request allowed
- `record_rate_limit_hit()` - Log external rate limit hits
- `get_rate_limit_status()` - Get current status

**Usage:**
```python
from ai_council.core.timeout_handler import rate_limit_manager

# Set rate limit
rate_limit_manager.set_rate_limit("openai_api", 60, burst_limit=10)

# Check before making request
allowed, wait_time = rate_limit_manager.check_rate_limit("openai_api")
if not allowed:
    time.sleep(wait_time)
```

### 2. FastAPI Rate Limiting (`web_app/backend/main.py`)

Implements HTTP endpoint rate limiting using `slowapi`.

**Features:**
- 100 requests per 15 minutes per IP
- Custom rate limit headers
- Graceful error handling
- WebSocket connections excluded

**Middleware:**
- `SlowAPIMiddleware` - Core rate limiting
- `RateLimitHeaderMiddleware` - Adds rate limit headers

**Decorators:**
```python
@limiter.limit("100/15minutes")
async def endpoint(request: Request):
    # Your endpoint logic
```

## Configuration

### Internal Rate Limits

Configure for external APIs:
```python
rate_limit_manager.set_rate_limit("openai_gpt4", 60)  # 60 req/min
rate_limit_manager.set_rate_limit("anthropic_claude", 50)  # 50 req/min
```

### HTTP API Limits

Modify in `main.py`:
```python
@limiter.limit("200/15minutes")  # Change from 100 to 200
```

## Headers

Responses include rate limit headers:
- `X-RateLimit-Limit` - Total requests allowed
- `X-RateLimit-Remaining` - Requests remaining
- `X-RateLimit-Reset` - Window reset time
- `Retry-After` - Seconds to wait when limited

## Error Handling

Rate limit exceeded returns:
```json
{
    "success": false,
    "message": "Too many requests",
    "retryAfter": 900
}
```

## Best Practices

1. **Check limits before external API calls**
2. **Implement exponential backoff**
3. **Monitor rate limit hit metrics**
4. **Use adaptive timeouts with rate limiting**
5. **Configure different limits per API provider**

## Monitoring

Track rate limit events through:
- Failure handling system
- Timeout statistics
- Request history logs

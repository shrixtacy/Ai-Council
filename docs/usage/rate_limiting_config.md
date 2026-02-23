# Rate Limiting Configuration Guide

## Quick Start

### 1. Basic Configuration

```python
from ai_council.core.timeout_handler import rate_limit_manager

# Set rate limits
rate_limit_manager.set_rate_limit("openai_api", 60, burst_limit=10)
rate_limit_manager.set_rate_limit("anthropic_api", 50, burst_limit=8)
```

### 2. Check Limits Before API Calls

```python
allowed, wait_time = rate_limit_manager.check_rate_limit("openai_api")
if not allowed:
    time.sleep(wait_time)
# Make API call
```

## Configuration Options

### Rate Limit Parameters

- **resource**: String identifier for the API/service
- **requests_per_minute**: Maximum requests per minute
- **burst_limit**: Optional burst capacity (defaults to requests_per_minute)

### Recommended Limits by Provider

| Provider | Model | Requests/Minute | Burst Limit |
|----------|-------|-----------------|-------------|
| OpenAI | GPT-4 | 60 | 10 |
| OpenAI | GPT-3.5 | 200 | 40 |
| Anthropic | Claude | 50 | 8 |
| Google | Gemini | 100 | 20 |

## Environment Configuration

### Development Environment

```python
# config/development.yaml
rate_limiting:
  openai_gpt4:
    requests_per_minute: 120
    burst_limit: 20
  anthropic_claude:
    requests_per_minute: 80
    burst_limit: 15
```

### Production Environment

```python
# config/production.yaml
rate_limiting:
  openai_gpt4:
    requests_per_minute: 40
    burst_limit: 8
  anthropic_claude:
    requests_per_minute: 30
    burst_limit: 6
```

## HTTP API Rate Limiting

### FastAPI Configuration

```python
# web_app/backend/main.py
@limiter.limit("100/15minutes")
async def process_request(request: Request, req: RequestModel):
    # Your endpoint logic
```

### Custom Rate Limits per Endpoint

```python
# Different limits for different endpoints
@limiter.limit("200/15minutes")  # Higher limit for status
async def get_status(request: Request):
    pass

@limiter.limit("50/15minutes")   # Lower limit for expensive operations
async def expensive_operation(request: Request):
    pass
```

## Advanced Configuration

### Dynamic Rate Limiting

```python
def configure_rate_limits_by_tier(tier: str):
    limits = {
        "free": {"rpm": 20, "burst": 5},
        "pro": {"rpm": 100, "burst": 20},
        "enterprise": {"rpm": 500, "burst": 100}
    }
    
    config = limits.get(tier, limits["free"])
    rate_limit_manager.set_rate_limit(
        resource=f"user_{tier}",
        requests_per_minute=config["rpm"],
        burst_limit=config["burst"]
    )
```

### Time-Based Rate Limiting

```python
def configure_time_based_limits():
    current_hour = time.localtime().tm_hour
    
    if 9 <= current_hour <= 17:  # Business hours
        rate_limit_manager.set_rate_limit("api", 100)
    else:  # Off-peak hours
        rate_limit_manager.set_rate_limit("api", 200)
```

## Monitoring and Alerts

### Rate Limit Monitoring

```python
def monitor_rate_limits():
    resources = ["openai_api", "anthropic_api", "google_api"]
    
    for resource in resources:
        status = rate_limit_manager.get_rate_limit_status(resource)
        
        # Alert if approaching limit
        usage_percentage = (status["current_count"] / status["requests_per_minute"]) * 100
        if usage_percentage > 80:
            send_alert(f"High usage for {resource}: {usage_percentage:.1f}%")
```

### Integration with Monitoring Systems

```python
def export_metrics():
    """Export rate limit metrics for monitoring systems."""
    metrics = {}
    
    for resource in rate_limit_manager.rate_limits:
        status = rate_limit_manager.get_rate_limit_status(resource)
        metrics[f"rate_limit_{resource}"] = {
            "limit": status["requests_per_minute"],
            "used": status["current_count"],
            "remaining": status["requests_per_minute"] - status["current_count"],
            "reset_in": status["time_until_reset"]
        }
    
    return metrics
```

## Best Practices

### 1. Conservative Limits
- Start with lower limits and increase as needed
- Monitor usage patterns before adjusting
- Consider peak traffic times

### 2. Burst Capacity
- Set burst limits 15-20% of regular limits
- Allows for temporary traffic spikes
- Prevents false rate limit triggers

### 3. Error Handling
- Always handle rate limit exceptions
- Implement exponential backoff
- Record rate limit hits for monitoring

### 4. Testing
- Test rate limiting in staging environment
- Verify headers are correctly set
- Test error responses

## Troubleshooting

### Common Issues

1. **Rate Limits Too Restrictive**
   - Monitor actual usage patterns
   - Adjust limits based on metrics
   - Consider different limits per user tier

2. **Rate Limits Not Working**
   - Verify rate limit manager initialization
   - Check resource names match exactly
   - Ensure thread-safe access

3. **Headers Not Showing**
   - Verify middleware order
   - Check slowapi configuration
   - Test with different clients

### Debug Commands

```python
# Check current limits
print(rate_limit_manager.rate_limits)

# Check specific resource status
status = rate_limit_manager.get_rate_limit_status("openai_api")
print(status)

# Test rate limiting
for i in range(10):
    allowed, wait_time = rate_limit_manager.check_rate_limit("test_api")
    print(f"Request {i+1}: allowed={allowed}, wait={wait_time}")
```

## Migration Guide

### From No Rate Limiting

1. Add rate limit manager to existing code
2. Set conservative initial limits
3. Add rate limit checks before API calls
4. Monitor and adjust limits

### From Simple Rate Limiting

1. Replace existing rate limiting with RateLimitManager
2. Add burst capacity
3. Implement monitoring and alerts
4. Add dynamic configuration options
